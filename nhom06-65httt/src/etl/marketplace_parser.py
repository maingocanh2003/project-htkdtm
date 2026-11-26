"""D10 parser for D6 raw marketplace product payloads (Etsy, Amazon).

Design rules:
- raw_record is the original JSON dict; never mutated.
- Prices use amount_str (string) to avoid float rounding — semantics are from source.
- ParseError.kind precisely classifies MISSING / NULL / WRONG_TYPE / WRONG_FORMAT.
- No DB IDs, no transformation of source values.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from .parsed_record import (
    ParseError,
    ParseErrorKind,
    ParsedPriceInfo,
    ParsedProductPayload,
    ParsedProductRecord,
    RecordProvenance,
)


# ---------------------------------------------------------------------------
# Etsy active-listings parser
# ---------------------------------------------------------------------------


class EtsyListingParser:
    """Parse a raw Etsy active-listing JSON payload (``/v3/application/listings/active``)."""

    def parse(
        self,
        payload: bytes,
        raw_collection_id: str,
        source_id: str = "etsy",
        collected_at_iso: str = "",
        source_url: Optional[str] = None,
    ) -> ParsedProductPayload:
        provenance = RecordProvenance(
            source_id=source_id,
            raw_collection_id=raw_collection_id,
            collected_at_iso=collected_at_iso,
            source_url=source_url,
        )
        body = _decode_json(payload, source_id, raw_collection_id)

        count = _require_int(body, "count", source_id, raw_collection_id, "count", nullable=False)
        results = _require_list(body, "results", source_id, raw_collection_id, "results")

        if count < len(results):
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.WRONG_FORMAT,
                f"count ({count}) is less than results length ({len(results)})",
            )

        records = tuple(
            self._parse_listing(item, i, provenance)
            for i, item in enumerate(results)
        )
        return ParsedProductPayload(
            provenance=provenance,
            records=records,
            record_count=len(records),
            reported_count=count,
        )

    def _parse_listing(
        self, raw: Any, index: int, provenance: RecordProvenance
    ) -> ParsedProductRecord:
        sid = provenance.source_id
        cid = provenance.raw_collection_id
        prefix = f"results[{index}]"

        if not isinstance(raw, dict):
            raise ParseError(
                sid, cid, prefix, ParseErrorKind.WRONG_TYPE,
                f"listing must be JSON object, got {type(raw).__name__}",
            )

        # listing_id — required, positive int
        listing_id = _require_int(raw, "listing_id", sid, cid, f"{prefix}.listing_id", nullable=False)
        if listing_id < 1:
            raise ParseError(
                sid, cid, f"{prefix}.listing_id", ParseErrorKind.WRONG_FORMAT,
                "listing_id must be a positive integer",
            )

        title = _optional_str(raw, "title", sid, cid, f"{prefix}.title")
        url = _optional_str(raw, "url", sid, cid, f"{prefix}.url")

        # taxonomy_id — optional positive int
        taxonomy_id: Optional[str] = None
        if "taxonomy_id" in raw:
            tid = raw["taxonomy_id"]
            if tid is None:
                taxonomy_id = None
            elif type(tid) is not int or tid < 1:
                raise ParseError(
                    sid, cid, f"{prefix}.taxonomy_id", ParseErrorKind.WRONG_FORMAT,
                    "taxonomy_id must be a positive integer when present",
                )
            else:
                taxonomy_id = str(tid)

        prices = _parse_etsy_price(raw.get("price"), sid, cid, f"{prefix}.price")

        return ParsedProductRecord(
            provenance=provenance,
            raw_record=dict(raw),
            source_product_id=str(listing_id),
            product_url=url,
            name=title,
            category=None,
            category_id=taxonomy_id,
            prices=prices,
        )


# ---------------------------------------------------------------------------
# Amazon Creators API parser
# ---------------------------------------------------------------------------


class AmazonCreatorsParser:
    """Parse a raw Amazon Creators API SearchItems JSON payload."""

    def parse(
        self,
        payload: bytes,
        raw_collection_id: str,
        source_id: str = "amazon",
        collected_at_iso: str = "",
        source_url: Optional[str] = None,
    ) -> ParsedProductPayload:
        provenance = RecordProvenance(
            source_id=source_id,
            raw_collection_id=raw_collection_id,
            collected_at_iso=collected_at_iso,
            source_url=source_url,
        )
        body = _decode_json(payload, source_id, raw_collection_id)

        if "itemsResult" not in body:
            raise ParseError(
                source_id, raw_collection_id, "itemsResult",
                ParseErrorKind.MISSING_FIELD, "top-level 'itemsResult' is absent",
            )
        items_result = body["itemsResult"]
        if items_result is None:
            raise ParseError(
                source_id, raw_collection_id, "itemsResult",
                ParseErrorKind.NULL_FIELD, "'itemsResult' must not be null",
            )
        if not isinstance(items_result, dict):
            raise ParseError(
                source_id, raw_collection_id, "itemsResult",
                ParseErrorKind.WRONG_TYPE,
                f"expected object, got {type(items_result).__name__}",
            )

        items = _require_list(items_result, "items", source_id, raw_collection_id, "itemsResult.items")

        records = tuple(
            self._parse_item(item, i, provenance)
            for i, item in enumerate(items)
        )
        return ParsedProductPayload(
            provenance=provenance,
            records=records,
            record_count=len(records),
            reported_count=None,  # Creators API has no envelope count
        )

    def _parse_item(
        self, raw: Any, index: int, provenance: RecordProvenance
    ) -> ParsedProductRecord:
        sid = provenance.source_id
        cid = provenance.raw_collection_id
        prefix = f"itemsResult.items[{index}]"

        if not isinstance(raw, dict):
            raise ParseError(
                sid, cid, prefix, ParseErrorKind.WRONG_TYPE,
                f"item must be JSON object, got {type(raw).__name__}",
            )

        # asin — required non-empty string
        if "asin" not in raw:
            raise ParseError(
                sid, cid, f"{prefix}.asin", ParseErrorKind.MISSING_FIELD,
                "asin is required",
            )
        asin = raw["asin"]
        if asin is None:
            raise ParseError(
                sid, cid, f"{prefix}.asin", ParseErrorKind.NULL_FIELD,
                "asin must not be null",
            )
        if not isinstance(asin, str):
            raise ParseError(
                sid, cid, f"{prefix}.asin", ParseErrorKind.WRONG_TYPE,
                f"asin expected str, got {type(asin).__name__}",
            )
        if not asin.strip():
            raise ParseError(
                sid, cid, f"{prefix}.asin", ParseErrorKind.WRONG_FORMAT,
                "asin must not be blank",
            )

        url = _optional_str(raw, "detailPageURL", sid, cid, f"{prefix}.detailPageURL")

        # name via itemInfo.title.displayValue
        name: Optional[str] = None
        item_info = raw.get("itemInfo")
        if isinstance(item_info, dict):
            title_obj = item_info.get("title")
            if isinstance(title_obj, dict):
                dv = title_obj.get("displayValue")
                if dv is not None:
                    if not isinstance(dv, str):
                        raise ParseError(
                            sid, cid, f"{prefix}.itemInfo.title.displayValue",
                            ParseErrorKind.WRONG_TYPE,
                            f"expected str, got {type(dv).__name__}",
                        )
                    name = dv

        category, category_id = _amazon_category(raw, sid, cid, prefix)

        prices = _parse_amazon_offers(raw.get("offersV2"), sid, cid, f"{prefix}.offersV2")

        return ParsedProductRecord(
            provenance=provenance,
            raw_record=dict(raw),
            source_product_id=asin,
            product_url=url,
            name=name,
            category=category,
            category_id=category_id,
            prices=prices,
        )


# ---------------------------------------------------------------------------
# Shared price helpers
# ---------------------------------------------------------------------------


def _parse_etsy_price(
    price: Any, source_id: str, cid: str, path: str
) -> Tuple[ParsedPriceInfo, ...]:
    if price is None:
        return ()
    if not isinstance(price, dict):
        raise ParseError(
            source_id, cid, path, ParseErrorKind.WRONG_TYPE,
            f"price must be a Money object, got {type(price).__name__}",
        )
    for key in ("amount", "divisor", "currency_code"):
        if key not in price:
            raise ParseError(
                source_id, cid, f"{path}.{key}", ParseErrorKind.MISSING_FIELD,
                f"Etsy Money.{key} is required",
            )
        if price[key] is None:
            raise ParseError(
                source_id, cid, f"{path}.{key}", ParseErrorKind.NULL_FIELD,
                f"Etsy Money.{key} must not be null",
            )

    amount = price["amount"]
    divisor = price["divisor"]
    currency_code = price["currency_code"]

    if type(amount) is not int:
        raise ParseError(
            source_id, cid, f"{path}.amount", ParseErrorKind.WRONG_TYPE,
            f"expected int, got {type(amount).__name__}",
        )
    if type(divisor) is not int or divisor <= 0:
        raise ParseError(
            source_id, cid, f"{path}.divisor", ParseErrorKind.WRONG_FORMAT,
            "divisor must be a positive integer",
        )
    if not isinstance(currency_code, str) or not currency_code.strip():
        raise ParseError(
            source_id, cid, f"{path}.currency_code", ParseErrorKind.WRONG_FORMAT,
            "currency_code must be a non-empty string",
        )

    try:
        amount_decimal = Decimal(amount) / Decimal(divisor)
    except InvalidOperation as exc:
        raise ParseError(
            source_id, cid, path, ParseErrorKind.WRONG_FORMAT,
            f"cannot compute price: {exc}",
        ) from exc

    return (ParsedPriceInfo(
        amount_str=str(amount_decimal),
        currency_code=currency_code,
        basis="minimum_listing_price",
    ),)


def _parse_amazon_offers(
    offers: Any, source_id: str, cid: str, path: str
) -> Tuple[ParsedPriceInfo, ...]:
    if offers is None:
        return ()
    if not isinstance(offers, dict):
        raise ParseError(
            source_id, cid, path, ParseErrorKind.WRONG_TYPE,
            f"offersV2 must be an object, got {type(offers).__name__}",
        )
    listings = offers.get("listings")
    if listings is None:
        return ()
    if not isinstance(listings, list):
        raise ParseError(
            source_id, cid, f"{path}.listings", ParseErrorKind.WRONG_TYPE,
            f"listings must be a list, got {type(listings).__name__}",
        )

    result: List[ParsedPriceInfo] = []
    for i, listing in enumerate(listings):
        lpath = f"{path}.listings[{i}]"
        if not isinstance(listing, dict):
            raise ParseError(
                source_id, cid, lpath, ParseErrorKind.WRONG_TYPE,
                f"listing must be an object, got {type(listing).__name__}",
            )
        price = listing.get("price")
        if price is None:
            continue
        if not isinstance(price, dict):
            raise ParseError(
                source_id, cid, f"{lpath}.price", ParseErrorKind.WRONG_TYPE,
                f"price must be an object, got {type(price).__name__}",
            )
        money = price.get("money")
        if money is None:
            continue
        if not isinstance(money, dict):
            raise ParseError(
                source_id, cid, f"{lpath}.price.money", ParseErrorKind.WRONG_TYPE,
                f"money must be an object, got {type(money).__name__}",
            )
        for key in ("amount", "currency"):
            if key not in money:
                raise ParseError(
                    source_id, cid, f"{lpath}.price.money.{key}",
                    ParseErrorKind.MISSING_FIELD, f"money.{key} is required",
                )
            if money[key] is None:
                raise ParseError(
                    source_id, cid, f"{lpath}.price.money.{key}",
                    ParseErrorKind.NULL_FIELD, f"money.{key} must not be null",
                )

        amount = money["amount"]
        currency = money["currency"]

        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ParseError(
                source_id, cid, f"{lpath}.price.money.amount",
                ParseErrorKind.WRONG_TYPE,
                f"amount must be a number, got {type(amount).__name__}",
            )
        if not isinstance(currency, str) or not currency.strip():
            raise ParseError(
                source_id, cid, f"{lpath}.price.money.currency",
                ParseErrorKind.WRONG_FORMAT, "currency must be a non-empty string",
            )

        try:
            dec = Decimal(str(amount))
        except InvalidOperation as exc:
            raise ParseError(
                source_id, cid, f"{lpath}.price.money.amount",
                ParseErrorKind.WRONG_FORMAT, f"cannot parse amount: {exc}",
            ) from exc

        if not dec.is_finite() or dec < 0:
            raise ParseError(
                source_id, cid, f"{lpath}.price.money.amount",
                ParseErrorKind.WRONG_FORMAT, "amount must be finite and nonnegative",
            )

        result.append(ParsedPriceInfo(
            amount_str=str(dec),
            currency_code=currency,
            basis="marketplace_offer",
        ))

    return tuple(result)


def _amazon_category(
    item: Dict[str, Any], source_id: str, cid: str, prefix: str
) -> Tuple[Optional[str], Optional[str]]:
    browse_node_info = item.get("browseNodeInfo")
    if isinstance(browse_node_info, dict):
        nodes = browse_node_info.get("browseNodes")
        if isinstance(nodes, list) and nodes:
            node = nodes[0]
            if isinstance(node, dict):
                name = node.get("displayName")
                nid = node.get("id")
                if name is not None and not isinstance(name, str):
                    raise ParseError(
                        source_id, cid,
                        f"{prefix}.browseNodeInfo.browseNodes[0].displayName",
                        ParseErrorKind.WRONG_TYPE,
                        f"displayName must be str, got {type(name).__name__}",
                    )
                return name, (None if nid is None else str(nid))

    item_info = item.get("itemInfo")
    if isinstance(item_info, dict):
        classifications = item_info.get("classifications")
        if isinstance(classifications, dict):
            pg = classifications.get("productGroup")
            if isinstance(pg, dict):
                name = pg.get("displayValue")
                if name is not None and not isinstance(name, str):
                    raise ParseError(
                        source_id, cid,
                        f"{prefix}.itemInfo.classifications.productGroup.displayValue",
                        ParseErrorKind.WRONG_TYPE,
                        f"displayValue must be str, got {type(name).__name__}",
                    )
                return name, None
    return None, None


# ---------------------------------------------------------------------------
# Common helpers
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


def _require_int(
    obj: Dict[str, Any],
    key: str,
    source_id: str,
    cid: str,
    path: str,
    nullable: bool = True,
) -> int:
    if key not in obj:
        raise ParseError(
            source_id, cid, path, ParseErrorKind.MISSING_FIELD,
            f"'{key}' is required",
        )
    v = obj[key]
    if v is None:
        if nullable:
            return 0
        raise ParseError(
            source_id, cid, path, ParseErrorKind.NULL_FIELD,
            f"'{key}' must not be null",
        )
    if type(v) is not int:
        raise ParseError(
            source_id, cid, path, ParseErrorKind.WRONG_TYPE,
            f"'{key}' expected int, got {type(v).__name__}",
        )
    return v


def _require_list(
    obj: Dict[str, Any],
    key: str,
    source_id: str,
    cid: str,
    path: str,
) -> list:
    if key not in obj:
        raise ParseError(
            source_id, cid, path, ParseErrorKind.MISSING_FIELD,
            f"'{key}' is required",
        )
    v = obj[key]
    if v is None:
        raise ParseError(
            source_id, cid, path, ParseErrorKind.NULL_FIELD,
            f"'{key}' must not be null",
        )
    if not isinstance(v, list):
        raise ParseError(
            source_id, cid, path, ParseErrorKind.WRONG_TYPE,
            f"'{key}' expected list, got {type(v).__name__}",
        )
    return v


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
            source_id, cid, path, ParseErrorKind.WRONG_TYPE,
            f"'{key}' expected str, got {type(v).__name__}",
        )
    return v
