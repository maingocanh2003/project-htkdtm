"""D9 — Bat Trang ceramic product collector using public WooCommerce Store API.

Integrates with the existing ETL foundation:
- ``source_registry.py`` (uses ``bat_trang`` source ID)
- ``http_client.py`` (uses shared ``HttpClient`` for HTTP GET)
- ``raw_storage.py`` (stores D9 JSON payload + manifest + SHA-256)
- ``domestic_parser.py`` (parses into ``ParsedDomesticPayload``)
- ``normalizer.py``, ``quality_validator.py``, ``deduplicator.py``, ``quarantine.py``

Design rules:
- Never invents missing fields (price=0 / unpriced -> None, missing MOQ/material -> None).
- Continues safely when an individual page fails, marking status as PARTIAL.
- Deduplicates collected products by ``source_product_id`` across pages.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

from .deduplicator import DeduplicationIndex, DuplicateStatus
from .domestic_parser import DomesticSupplierCatalogParser
from .http_client import HttpClient
from .normalizer import normalize_domestic_product
from .parsed_record import ParsedDomesticPayload
from .quality_validator import DataQualityValidator
from .quarantine import QuarantineStore
from .raw_storage import CollectionStatus, RawStorage
from .source_registry import (
    CollectionMetadata,
    SourceGroup,
    SourceRegistry,
)


_BAT_TRANG_SOURCE_ID = "bat_trang"
_DEFAULT_BASE_URL = "https://gombattrang.vn"
_STORE_API_PATH = "/wp-json/wc/store/products"
_COLLECTOR_VERSION = "d9/v1-wc-store"
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class BatTrangCollectionResult:
    """Summary of one Bat Trang catalog collection and ETL pipeline run."""

    collection_id: str
    source_id: str
    source_url: str
    status: CollectionStatus
    pages_requested: int
    pages_succeeded: int
    failed_pages: Tuple[Tuple[int, str], ...]
    raw_product_count: int
    parsed_count: int
    unique_count: int
    duplicate_count: int
    valid_count: int
    quarantined_count: int
    parsed_payload: ParsedDomesticPayload


def _strip_html(html_text: Optional[str]) -> Optional[str]:
    if not html_text or not isinstance(html_text, str):
        return None
    cleaned = _WHITESPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", unescape(html_text))).strip()
    return cleaned or None


def _extract_attribute_value(attributes: Any, keywords: Tuple[str, ...]) -> Optional[str]:
    if not isinstance(attributes, list):
        return None
    for attr in attributes:
        if not isinstance(attr, dict):
            continue
        name = str(attr.get("name") or "").lower()
        if any(kw in name for kw in keywords):
            terms = attr.get("terms")
            if isinstance(terms, list) and terms:
                vals = [str(t.get("name")).strip() for t in terms if isinstance(t, dict) and t.get("name")]
                if vals:
                    return ", ".join(vals)
    return None


def _map_wc_product_to_d9(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one WooCommerce Store API product object into D9 product JSON dict."""
    if not isinstance(item, dict):
        return None

    wc_id = item.get("id")
    if wc_id is None:
        return None

    raw_sku = item.get("sku")
    sku = raw_sku.strip() if isinstance(raw_sku, str) and raw_sku.strip() else None
    source_product_id = sku if sku is not None else f"GBT-{wc_id}"

    # Price: WooCommerce Store API uses "0" when price is not listed ("Liên hệ")
    prices = item.get("prices") if isinstance(item.get("prices"), dict) else {}
    price_html = item.get("price_html")
    raw_price = prices.get("price")
    minor_unit = int(prices.get("currency_minor_unit") or 0)
    price_vnd: Optional[float] = None
    currency: Optional[str] = None

    if raw_price is not None and str(raw_price).strip() != "":
        try:
            int_price = int(raw_price)
            # Only treat as a real price when > 0 (or price_html is non-empty and > 0)
            if int_price > 0:
                dec_price = Decimal(int_price) / (Decimal(10) ** minor_unit)
                price_vnd = float(dec_price)
                curr_code = prices.get("currency_code")
                currency = str(curr_code).strip().upper() if curr_code else "VND"
        except (TypeError, ValueError):
            price_vnd = None

    cats = item.get("categories")
    category: Optional[str] = None
    if isinstance(cats, list) and cats:
        first_cat = cats[0]
        if isinstance(first_cat, dict) and first_cat.get("name"):
            category = str(first_cat["name"]).strip()

    images = item.get("images")
    image_url: Optional[str] = None
    if isinstance(images, list) and images:
        first_img = images[0]
        if isinstance(first_img, dict) and first_img.get("src"):
            image_url = str(first_img["src"]).strip()

    attrs = item.get("attributes")
    material = _extract_attribute_value(attrs, ("chất liệu", "material", "men"))
    dimensions = _extract_attribute_value(attrs, ("kích thước", "size", "dimension"))
    color = _extract_attribute_value(attrs, ("màu", "color"))
    pattern = _extract_attribute_value(attrs, ("họa tiết", "pattern"))

    desc = _strip_html(item.get("description")) or _strip_html(item.get("short_description"))

    return {
        "source_product_id": source_product_id,
        "wc_id": wc_id,
        "sku": sku,
        "name": str(item.get("name")).strip() if item.get("name") else None,
        "description": desc,
        "product_url": str(item.get("permalink")).strip() if item.get("permalink") else None,
        "image_url": image_url,
        "category": category,
        "material": material,
        "dimensions": dimensions,
        "color": color,
        "pattern": pattern,
        "origin_region": None,
        "price_vnd": price_vnd,
        "currency": currency,
        "moq": None,
        "lead_time_days": None,
        "wholesale_available": None,
        "price_html": price_html if isinstance(price_html, str) else None,
    }


class BatTrangWooCommerceCollector:
    """Collect real Bat Trang product catalog from a public WooCommerce Store API."""

    def __init__(
        self,
        http_client: HttpClient,
        raw_storage: RawStorage,
        source_registry: SourceRegistry,
        base_url: str = _DEFAULT_BASE_URL,
        source_id: str = _BAT_TRANG_SOURCE_ID,
    ) -> None:
        source = source_registry.get(source_id)
        if source.source_group is not SourceGroup.DOMESTIC_SUPPLIER_CATALOGS:
            raise ValueError(f"{source_id} is not in DOMESTIC_SUPPLIER_CATALOGS group")
        self._http_client = http_client
        self._raw_storage = raw_storage
        self._source_id = source_id
        self._base_url = base_url.rstrip("/")

    def collect(
        self,
        per_page: int = 100,
        max_pages: int = 20,
        dedup_index: Optional[DeduplicationIndex] = None,
        quarantine_store: Optional[QuarantineStore] = None,
    ) -> BatTrangCollectionResult:
        """Fetch paginated products, persist raw JSON + SHA-256, parse, validate, and dedup."""
        if per_page < 1 or per_page > 100:
            raise ValueError("per_page must be between 1 and 100")
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")

        endpoint_url = f"{self._base_url}{_STORE_API_PATH}"
        collected_products: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        pages_requested = 0
        pages_succeeded = 0
        failed_pages: List[Tuple[int, str]] = []
        duplicate_count = 0

        for page in range(1, max_pages + 1):
            pages_requested += 1
            try:
                response = self._http_client.get(
                    endpoint_url,
                    params={"per_page": per_page, "page": page},
                )
                if response.status_code != 200:
                    failed_pages.append((page, f"HTTP {response.status_code}"))
                    continue
                items = json.loads(response.body.decode("utf-8"))
                if not isinstance(items, list):
                    failed_pages.append((page, "Expected JSON array from WooCommerce Store API"))
                    continue
            except Exception as exc:
                failed_pages.append((page, str(exc)))
                continue

            pages_succeeded += 1
            if not items:
                break

            for raw_item in items:
                mapped = _map_wc_product_to_d9(raw_item)
                if mapped is None:
                    continue
                pid = mapped["source_product_id"]
                if pid in seen_ids:
                    duplicate_count += 1
                    continue
                seen_ids.add(pid)
                collected_products.append(mapped)

            if len(items) < per_page:
                break

        status = CollectionStatus.SUCCESS
        if failed_pages and pages_succeeded > 0:
            status = CollectionStatus.PARTIAL
        elif failed_pages and pages_succeeded == 0:
            status = CollectionStatus.FAILED

        d9_envelope = {
            "supplier": {
                "supplier_name": "Gốm Bát Tràng (gombattrang.vn)",
                "tax_code": None,
                "address": None,
                "province": None,
                "website": self._base_url,
                "phone": None,
                "business_type": None,
                "declared_capacity_note": None,
            },
            "products": collected_products,
        }
        payload_bytes = json.dumps(d9_envelope, ensure_ascii=False).encode("utf-8")
        collected_at = datetime.now(timezone.utc)

        metadata = CollectionMetadata(
            collected_at=collected_at,
            source_id=self._source_id,
            data_format="json",
            version=_COLLECTOR_VERSION,
        )
        collection_id = self._raw_storage.save(
            payload_bytes,
            metadata,
            {
                "ingestion_method": "public_wc_store_api",
                "source_url": endpoint_url,
                "per_page": per_page,
                "pages_requested": pages_requested,
                "pages_succeeded": pages_succeeded,
                "failed_pages": [{"page": p, "error": e} for p, e in failed_pages],
            },
            status=status,
        )

        parsed_payload = DomesticSupplierCatalogParser().parse(
            payload_bytes,
            raw_collection_id=collection_id,
            source_id=self._source_id,
            collected_at_iso=collected_at.isoformat(),
            source_url=endpoint_url,
        )

        dedup = dedup_index or DeduplicationIndex()
        unique_count = 0
        valid_count = 0
        quarantined_count = 0

        for prod in parsed_payload.products:
            norm = normalize_domestic_product(prod)
            dedup_res = dedup.check_and_register(norm)
            if dedup_res.status == DuplicateStatus.EXACT_DUPLICATE:
                duplicate_count += 1
                if quarantine_store is not None:
                    quarantine_store.quarantine_duplicate(dedup_res, norm, norm.provenance)
                    quarantined_count += 1
                continue

            unique_count += 1
            val_res = DataQualityValidator.validate_domestic_product(norm)
            if val_res.is_valid:
                valid_count += 1
            else:
                if quarantine_store is not None:
                    quarantine_store.quarantine_from_validation(val_res, norm, norm.provenance)
                    quarantined_count += 1

        return BatTrangCollectionResult(
            collection_id=collection_id,
            source_id=self._source_id,
            source_url=endpoint_url,
            status=status,
            pages_requested=pages_requested,
            pages_succeeded=pages_succeeded,
            failed_pages=tuple(failed_pages),
            raw_product_count=len(collected_products),
            parsed_count=parsed_payload.record_count,
            unique_count=unique_count,
            duplicate_count=duplicate_count,
            valid_count=valid_count,
            quarantined_count=quarantined_count,
            parsed_payload=parsed_payload,
        )
