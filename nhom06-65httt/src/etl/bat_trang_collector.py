"""D9 — Bat Trang ceramic product collector using public WooCommerce Store API.

Integrates with the existing ETL foundation:
- ``source_registry.py`` (uses ``bat_trang`` source ID)
- ``http_client.py`` (uses shared ``HttpClient`` for HTTP GET)
- ``raw_storage.py`` (stores lossless API responses + manifest + SHA-256)
- ``domestic_parser.py`` (parses into ``ParsedDomesticPayload``)
- ``normalizer.py``, ``quality_validator.py``, ``deduplicator.py``, ``quarantine.py``

Design rules:
- Does not infer prices from ``price_html``; zero remains a valid numeric price.
- Maps ``price_vnd`` only when amount, VND currency, and minor-unit precision are present.
- Missing MOQ/material remain ``None``.
- Continues safely when an individual page fails, marking status as PARTIAL.
- Deduplicates collected products by ``source_product_id`` across pages.
"""

from __future__ import annotations

import base64
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, Overflow
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
_RAW_RESPONSE_FORMAT = "woocommerce_store_api_raw_v1"
_COLLECTOR_VERSION = "d9/v3-wc-store-raw"
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

    prices = item.get("prices") if isinstance(item.get("prices"), dict) else {}
    price_html = item.get("price_html")
    raw_price = prices.get("price")
    price_vnd: Optional[float] = None
    currency: Optional[str] = None

    raw_currency = prices.get("currency_code")
    if isinstance(raw_currency, str) and raw_currency.strip():
        currency = raw_currency.strip().upper()

    raw_minor_unit = prices.get("currency_minor_unit")
    minor_unit: Optional[int] = None
    if type(raw_minor_unit) is int and raw_minor_unit >= 0:
        minor_unit = raw_minor_unit
    elif (
        isinstance(raw_minor_unit, str)
        and re.fullmatch(r"[0-9]+", raw_minor_unit.strip())
    ):
        try:
            minor_unit = int(raw_minor_unit.strip())
        except ValueError:
            minor_unit = None

    raw_price_text = (
        str(raw_price).strip()
        if isinstance(raw_price, (str, int)) and not isinstance(raw_price, bool)
        else ""
    )
    if (
        re.fullmatch(r"[0-9]+", raw_price_text)
        and currency == "VND"
        and minor_unit is not None
    ):
        try:
            dec_price = Decimal(raw_price_text).scaleb(-minor_unit)
            if dec_price.is_finite():
                converted_price = float(dec_price)
                if math.isfinite(converted_price):
                    price_vnd = converted_price
        except (InvalidOperation, Overflow, OverflowError, ValueError):
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
        "store_api_prices": dict(prices),
        "moq": None,
        "lead_time_days": None,
        "wholesale_available": None,
        "price_html": price_html if isinstance(price_html, str) else None,
    }


def wc_store_raw_payload_to_d9(payload: bytes) -> bytes:
    """Convert a lossless raw Store API envelope to the existing D9 parser shape.

    Legacy D9 collections are returned unchanged so existing immutable raw data
    remains replayable.
    """
    body = json.loads(payload.decode("utf-8"))

    if not isinstance(body, dict) or body.get("format") != _RAW_RESPONSE_FORMAT:
        return payload

    base_url = body.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        base_url = _DEFAULT_BASE_URL

    responses = body.get("responses")
    if not isinstance(responses, list):
        raise ValueError("WooCommerce raw envelope must contain a responses array")

    products: List[Dict[str, Any]] = []
    for index, response in enumerate(responses):
        if not isinstance(response, dict):
            raise ValueError(f"WooCommerce raw response {index} must be an object")
        if response.get("status_code") != 200 or response.get("items_valid") is not True:
            continue

        encoded_body = response.get("body_base64")
        if not isinstance(encoded_body, str):
            raise ValueError(f"WooCommerce raw response {index} has no encoded body")
        response_body = base64.b64decode(encoded_body, validate=True)
        items = json.loads(response_body.decode("utf-8"))
        if not isinstance(items, list):
            raise ValueError(f"WooCommerce raw response {index} is not a JSON array")

        for item in items:
            mapped = _map_wc_product_to_d9(item)
            if mapped is not None:
                products.append(mapped)

    d9_envelope = {
        "supplier": {
            "supplier_name": "Gốm Bát Tràng (gombattrang.vn)",
            "tax_code": None,
            "address": None,
            "province": None,
            "website": base_url,
            "phone": None,
            "business_type": None,
            "declared_capacity_note": None,
        },
        "products": products,
    }
    return json.dumps(
        d9_envelope,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
    ).encode("utf-8")


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
        raw_responses: List[Dict[str, Any]] = []
        pages_requested = 0
        pages_succeeded = 0
        failed_pages: List[Tuple[int, str]] = []
        duplicate_count = 0
        raw_product_count = 0

        for page in range(1, max_pages + 1):
            pages_requested += 1
            try:
                response = self._http_client.get(
                    endpoint_url,
                    params={"per_page": per_page, "page": page},
                )
            except Exception as exc:
                failed_pages.append((page, str(exc)))
                continue

            raw_response: Dict[str, Any] = {
                "page": page,
                "request_parameters": {"per_page": per_page, "page": page},
                "status_code": response.status_code,
                "url": response.url,
                "body_base64": base64.b64encode(response.body).decode("ascii"),
                "items_valid": False,
            }
            raw_responses.append(raw_response)

            if response.status_code != 200:
                failed_pages.append((page, f"HTTP {response.status_code}"))
                continue
            try:
                items = json.loads(response.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                failed_pages.append((page, str(exc)))
                continue
            if not isinstance(items, list):
                failed_pages.append(
                    (page, "Expected JSON array from WooCommerce Store API")
                )
                continue

            raw_response["items_valid"] = True
            pages_succeeded += 1
            raw_product_count += len(items)
            if not items:
                break
            if len(items) < per_page:
                break

        status = CollectionStatus.SUCCESS
        if failed_pages and pages_succeeded > 0:
            status = CollectionStatus.PARTIAL
        elif failed_pages and pages_succeeded == 0:
            status = CollectionStatus.FAILED

        payload_bytes = json.dumps(
            {
                "format": _RAW_RESPONSE_FORMAT,
                "base_url": self._base_url,
                "responses": raw_responses,
            },
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        ).encode("utf-8")
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

        mapped_payload = json.loads(wc_store_raw_payload_to_d9(payload_bytes))
        collected_products: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        for mapped in mapped_payload["products"]:
            product_id = mapped["source_product_id"]
            if product_id in seen_ids:
                duplicate_count += 1
                continue
            seen_ids.add(product_id)
            collected_products.append(mapped)

        d9_payload = json.dumps(
            {
                "supplier": mapped_payload["supplier"],
                "products": collected_products,
            },
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        parsed_payload = DomesticSupplierCatalogParser().parse(
            d9_payload,
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
            raw_product_count=raw_product_count,
            parsed_count=parsed_payload.record_count,
            unique_count=unique_count,
            duplicate_count=duplicate_count,
            valid_count=valid_count,
            quarantined_count=quarantined_count,
            parsed_payload=parsed_payload,
        )
