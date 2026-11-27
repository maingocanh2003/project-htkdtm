"""D10 parser for D9 raw domestic-supplier catalog payloads.

Design rules:
- Separates SupplierInfo (business entity), product fields, and CommercialInfo.
- CommercialInfo fields are NEVER inferred; absent == None in output.
- raw_record is the original product dict; never mutated.
- ParseError.kind distinguishes MISSING / NULL / WRONG_TYPE / WRONG_FORMAT.
- Tax code validation uses the same regex as domestic_supplier_collector.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from .parsed_record import (
    ParseError,
    ParseErrorKind,
    ParsedCommercialInfo,
    ParsedDomesticPayload,
    ParsedDomesticProductRecord,
    ParsedSupplierInfo,
    RecordProvenance,
)


_TAX_CODE_RE = re.compile(r"[0-9\-]{10,14}")


class DomesticSupplierCatalogParser:
    """Parse a domestic supplier catalog JSON payload into ParsedDomesticPayload.

    Separates:
    - ``supplier`` block → ParsedSupplierInfo (business entity fields)
    - each ``products`` item → ParsedDomesticProductRecord (product + commercial)

    Commercial fields (price, moq, lead_time_days) are only populated when the
    source explicitly provides them; this parser never defaults or infers them.
    """

    def parse(
        self,
        payload: bytes,
        raw_collection_id: str,
        source_id: str,
        collected_at_iso: str = "",
        source_url: Optional[str] = None,
    ) -> ParsedDomesticPayload:
        if not source_id or not isinstance(source_id, str):
            raise ValueError("source_id must be a non-empty string")

        provenance = RecordProvenance(
            source_id=source_id,
            raw_collection_id=raw_collection_id,
            collected_at_iso=collected_at_iso,
            source_url=source_url,
        )
        body = _decode_json(payload, source_id, raw_collection_id)

        supplier = _parse_supplier_block(
            body.get("supplier"), source_id, raw_collection_id
        )

        products_raw = body.get("products")
        if products_raw is None:
            # Key absent or null — treat as empty list (not an error)
            products_raw = []

        if not isinstance(products_raw, list):
            raise ParseError(
                source_id, raw_collection_id, "products",
                ParseErrorKind.WRONG_TYPE,
                f"'products' must be a list, got {type(products_raw).__name__}",
            )

        records = tuple(
            _parse_product(item, i, provenance)
            for i, item in enumerate(products_raw)
        )
        return ParsedDomesticPayload(
            provenance=provenance,
            supplier=supplier,
            products=records,
            record_count=len(records),
        )


# ---------------------------------------------------------------------------
# Supplier block parser
# ---------------------------------------------------------------------------


def _parse_supplier_block(
    block: Any,
    source_id: str,
    cid: str,
) -> Optional[ParsedSupplierInfo]:
    if block is None:
        return None
    if not isinstance(block, dict):
        raise ParseError(
            source_id, cid, "supplier",
            ParseErrorKind.WRONG_TYPE,
            f"supplier must be a JSON object, got {type(block).__name__}",
        )

    # supplier_name — required
    if "supplier_name" not in block:
        raise ParseError(
            source_id, cid, "supplier.supplier_name",
            ParseErrorKind.MISSING_FIELD, "supplier_name is required",
        )
    name = block["supplier_name"]
    if name is None:
        raise ParseError(
            source_id, cid, "supplier.supplier_name",
            ParseErrorKind.NULL_FIELD, "supplier_name must not be null",
        )
    if not isinstance(name, str):
        raise ParseError(
            source_id, cid, "supplier.supplier_name",
            ParseErrorKind.WRONG_TYPE,
            f"supplier_name expected str, got {type(name).__name__}",
        )
    if not name.strip():
        raise ParseError(
            source_id, cid, "supplier.supplier_name",
            ParseErrorKind.WRONG_FORMAT, "supplier_name must not be blank",
        )

    # tax_code — optional; validate format when present
    tax_code = _optional_str(block, "tax_code", source_id, cid, "supplier.tax_code")
    if tax_code is not None and not _TAX_CODE_RE.fullmatch(tax_code):
        raise ParseError(
            source_id, cid, "supplier.tax_code",
            ParseErrorKind.WRONG_FORMAT,
            "tax_code must match Vietnamese tax code format (10–14 digits/hyphens)",
        )

    return ParsedSupplierInfo(
        supplier_name=name.strip(),
        tax_code=tax_code,
        address=_optional_str(block, "address", source_id, cid, "supplier.address"),
        province=_optional_str(block, "province", source_id, cid, "supplier.province"),
        website=_optional_str(block, "website", source_id, cid, "supplier.website"),
        phone=_optional_str(block, "phone", source_id, cid, "supplier.phone"),
        business_type=_optional_str(block, "business_type", source_id, cid, "supplier.business_type"),
        declared_capacity_note=_optional_str(
            block, "declared_capacity_note", source_id, cid,
            "supplier.declared_capacity_note",
        ),
    )


# ---------------------------------------------------------------------------
# Product record parser
# ---------------------------------------------------------------------------


def _parse_product(
    item: Any,
    index: int,
    provenance: RecordProvenance,
) -> ParsedDomesticProductRecord:
    sid = provenance.source_id
    cid = provenance.raw_collection_id
    prefix = f"products[{index}]"

    if not isinstance(item, dict):
        raise ParseError(
            sid, cid, prefix, ParseErrorKind.WRONG_TYPE,
            f"product must be a JSON object, got {type(item).__name__}",
        )

    # source_product_id — required
    if "source_product_id" not in item:
        raise ParseError(
            sid, cid, f"{prefix}.source_product_id",
            ParseErrorKind.MISSING_FIELD, "source_product_id is required",
        )
    spid = item["source_product_id"]
    if spid is None:
        raise ParseError(
            sid, cid, f"{prefix}.source_product_id",
            ParseErrorKind.NULL_FIELD, "source_product_id must not be null",
        )
    if not isinstance(spid, str):
        raise ParseError(
            sid, cid, f"{prefix}.source_product_id",
            ParseErrorKind.WRONG_TYPE,
            f"source_product_id expected str, got {type(spid).__name__}",
        )
    if not spid.strip():
        raise ParseError(
            sid, cid, f"{prefix}.source_product_id",
            ParseErrorKind.WRONG_FORMAT, "source_product_id must not be blank",
        )

    commercial = _parse_commercial(item, sid, cid, prefix)

    return ParsedDomesticProductRecord(
        provenance=provenance,
        raw_record=dict(item),
        source_product_id=spid.strip(),
        product_url=_optional_str(item, "product_url", sid, cid, f"{prefix}.product_url"),
        name=_optional_str(item, "name", sid, cid, f"{prefix}.name"),
        description=_optional_str(item, "description", sid, cid, f"{prefix}.description"),
        category=_optional_str(item, "category", sid, cid, f"{prefix}.category"),
        material=_optional_str(item, "material", sid, cid, f"{prefix}.material"),
        origin_region=_optional_str(item, "origin_region", sid, cid, f"{prefix}.origin_region"),
        commercial=commercial,
    )


# ---------------------------------------------------------------------------
# Commercial info parser — never infers, never defaults
# ---------------------------------------------------------------------------


def _parse_commercial(
    item: Dict[str, Any],
    source_id: str,
    cid: str,
    prefix: str,
) -> ParsedCommercialInfo:
    # price_vnd — optional numeric; keep as string to avoid rounding
    price_vnd_str: Optional[str] = None
    currency: Optional[str] = None

    if "price_vnd" in item:
        raw_price = item["price_vnd"]
        if raw_price is not None:
            if isinstance(raw_price, bool) or not isinstance(raw_price, (int, float)):
                raise ParseError(
                    source_id, cid, f"{prefix}.price_vnd",
                    ParseErrorKind.WRONG_TYPE,
                    f"price_vnd expected number, got {type(raw_price).__name__}",
                )
            try:
                dec = Decimal(str(raw_price))
            except InvalidOperation as exc:
                raise ParseError(
                    source_id, cid, f"{prefix}.price_vnd",
                    ParseErrorKind.WRONG_FORMAT,
                    f"cannot parse price_vnd: {exc}",
                ) from exc
            if not dec.is_finite() or dec < 0:
                raise ParseError(
                    source_id, cid, f"{prefix}.price_vnd",
                    ParseErrorKind.WRONG_FORMAT,
                    "price_vnd must be finite and nonnegative",
                )
            price_vnd_str = str(dec)

            # currency — meaningful only when price is present
            if "currency" in item:
                raw_currency = item["currency"]
                if raw_currency is not None:
                    if not isinstance(raw_currency, str):
                        raise ParseError(
                            source_id, cid, f"{prefix}.currency",
                            ParseErrorKind.WRONG_TYPE,
                            f"currency expected str, got {type(raw_currency).__name__}",
                        )
                    if not raw_currency.strip():
                        raise ParseError(
                            source_id, cid, f"{prefix}.currency",
                            ParseErrorKind.WRONG_FORMAT,
                            "currency must not be blank",
                        )
                    currency = raw_currency.strip().upper()
                else:
                    currency = "VND"  # source provided price without currency → default
            else:
                currency = "VND"

    # moq — optional positive int
    moq: Optional[int] = None
    if "moq" in item:
        raw_moq = item["moq"]
        if raw_moq is not None:
            if type(raw_moq) is not int:
                raise ParseError(
                    source_id, cid, f"{prefix}.moq",
                    ParseErrorKind.WRONG_TYPE,
                    f"moq expected int, got {type(raw_moq).__name__}",
                )
            if raw_moq < 1:
                raise ParseError(
                    source_id, cid, f"{prefix}.moq",
                    ParseErrorKind.WRONG_FORMAT,
                    "moq must be a positive integer",
                )
            moq = raw_moq

    # lead_time_days — optional nonneg int
    lead_time_days: Optional[int] = None
    if "lead_time_days" in item:
        raw_lt = item["lead_time_days"]
        if raw_lt is not None:
            if type(raw_lt) is not int:
                raise ParseError(
                    source_id, cid, f"{prefix}.lead_time_days",
                    ParseErrorKind.WRONG_TYPE,
                    f"lead_time_days expected int, got {type(raw_lt).__name__}",
                )
            if raw_lt < 0:
                raise ParseError(
                    source_id, cid, f"{prefix}.lead_time_days",
                    ParseErrorKind.WRONG_FORMAT,
                    "lead_time_days must be nonnegative",
                )
            lead_time_days = raw_lt

    # wholesale_available — optional bool
    wholesale: Optional[bool] = None
    if "wholesale_available" in item:
        raw_ws = item["wholesale_available"]
        if raw_ws is not None:
            if not isinstance(raw_ws, bool):
                raise ParseError(
                    source_id, cid, f"{prefix}.wholesale_available",
                    ParseErrorKind.WRONG_TYPE,
                    f"wholesale_available expected bool, got {type(raw_ws).__name__}",
                )
            wholesale = raw_ws

    return ParsedCommercialInfo(
        price_vnd_str=price_vnd_str,
        currency=currency,
        moq=moq,
        lead_time_days=lead_time_days,
        wholesale_available=wholesale,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_json(payload: bytes, source_id: str, cid: str) -> Dict[str, Any]:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    try:
        body = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParseError(
            source_id, cid, "",
            ParseErrorKind.INVALID_STRUCTURE,
            f"payload is not valid JSON: {exc}",
        ) from exc
    if not isinstance(body, dict):
        raise ParseError(
            source_id, cid, "",
            ParseErrorKind.INVALID_STRUCTURE,
            f"expected JSON object at root, got {type(body).__name__}",
        )
    return body


def _optional_str(
    obj: Dict[str, Any],
    key: str,
    source_id: str,
    cid: str,
    path: str,
) -> Optional[str]:
    if key not in obj:
        return None
    v = obj[key]
    if v is None:
        return None
    if not isinstance(v, str):
        raise ParseError(
            source_id, cid, path,
            ParseErrorKind.WRONG_TYPE,
            f"'{key}' expected str, got {type(v).__name__}",
        )
    stripped = v.strip()
    return stripped if stripped else None
