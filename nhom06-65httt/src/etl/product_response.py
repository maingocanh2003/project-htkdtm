"""Fixture-compatible product response adapters for official marketplace APIs."""

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from .source_registry import CollectionMetadata


_ETSY_ENDPOINT = "/v3/application/listings/active"
_AMAZON_ENDPOINT = "/catalog/v1/searchItems"


@dataclass(frozen=True)
class ProductPrice:
    """A price explicitly returned by a marketplace response."""

    amount: Decimal
    currency_code: str
    basis: str


@dataclass(frozen=True)
class ProductRecord:
    """Source product fields without generated IDs, URLs, or inferred prices."""

    source_id: str
    source_product_id: str
    product_url: Optional[str]
    name: Optional[str]
    category: Optional[str]
    category_id: Optional[str]
    prices: Tuple[ProductPrice, ...]


@dataclass(frozen=True)
class ProductResponse:
    """Parsed records plus the original response bytes and provenance metadata."""

    metadata: CollectionMetadata
    records: Tuple[ProductRecord, ...]
    raw_payload: bytes


class ProductResponseError(ValueError):
    """Raised when a marketplace response does not match its documented shape."""


class EtsyListingResponseAdapter:
    """Parse documented Etsy active-listing response fields without network I/O."""

    def parse(self, payload: bytes, collected_at: datetime) -> ProductResponse:
        body = _decode_json(payload, "Etsy")
        results = body.get("results")
        count = body.get("count")
        if (
            type(count) is not int
            or count < 0
            or not isinstance(results, list)
            or count < len(results)
        ):
            raise ProductResponseError(
                "Etsy response must contain a valid count and results list"
            )

        records = tuple(
            self._parse_listing(listing) for listing in results
        )
        return ProductResponse(
            metadata=CollectionMetadata(
                collected_at=collected_at,
                source_id="etsy",
                data_format="json",
                version="3.0.0",
                endpoint=_ETSY_ENDPOINT,
            ),
            records=records,
            raw_payload=payload,
        )

    @staticmethod
    def _parse_listing(listing: Any) -> ProductRecord:
        if not isinstance(listing, dict):
            raise ProductResponseError("Etsy results must contain listing objects")
        listing_id = listing.get("listing_id")
        if type(listing_id) is not int or listing_id < 1:
            raise ProductResponseError("Etsy listing is missing a valid listing_id")

        price = listing.get("price")
        prices = () if price is None else (_parse_etsy_price(price),)
        taxonomy_id = listing.get("taxonomy_id")
        if taxonomy_id is not None and (
            type(taxonomy_id) is not int or taxonomy_id < 1
        ):
            raise ProductResponseError("Etsy taxonomy_id must be a positive integer")

        return ProductRecord(
            source_id="etsy",
            source_product_id=str(listing_id),
            product_url=_optional_string(listing.get("url"), "Etsy url"),
            name=_optional_string(listing.get("title"), "Etsy title"),
            category=None,
            category_id=None if taxonomy_id is None else str(taxonomy_id),
            prices=prices,
        )


class AmazonCreatorsResponseAdapter:
    """Parse documented Amazon Creators API SearchItems response fields."""

    def parse(self, payload: bytes, collected_at: datetime) -> ProductResponse:
        body = _decode_json(payload, "Amazon Creators API")
        items_result = body.get("itemsResult")
        items = items_result.get("items") if isinstance(items_result, dict) else None
        if not isinstance(items, list):
            raise ProductResponseError(
                "Amazon response must contain itemsResult.items"
            )

        records = tuple(self._parse_item(item) for item in items)
        return ProductResponse(
            metadata=CollectionMetadata(
                collected_at=collected_at,
                source_id="amazon",
                data_format="json",
                version="v1",
                endpoint=_AMAZON_ENDPOINT,
            ),
            records=records,
            raw_payload=payload,
        )

    @staticmethod
    def _parse_item(item: Any) -> ProductRecord:
        if not isinstance(item, dict):
            raise ProductResponseError("Amazon items must contain item objects")
        asin = item.get("asin")
        if not isinstance(asin, str) or not asin.strip():
            raise ProductResponseError("Amazon item is missing a valid asin")

        item_info = item.get("itemInfo")
        if not isinstance(item_info, dict):
            item_info = {}
        title = item_info.get("title")
        name = title.get("displayValue") if isinstance(title, dict) else None
        if name is not None and not isinstance(name, str):
            raise ProductResponseError("Amazon item title must be a string")

        category, category_id = _amazon_category(item)
        return ProductRecord(
            source_id="amazon",
            source_product_id=asin,
            product_url=_optional_string(
                item.get("detailPageURL"), "Amazon detailPageURL"
            ),
            name=name,
            category=category,
            category_id=category_id,
            prices=_parse_amazon_prices(item.get("offersV2")),
        )


def _decode_json(payload: bytes, source_name: str) -> Dict[str, Any]:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    try:
        body = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProductResponseError(
            f"{source_name} response is not valid JSON"
        ) from error
    if not isinstance(body, dict):
        raise ProductResponseError(f"{source_name} response must be a JSON object")
    return body


def _parse_etsy_price(value: Any) -> ProductPrice:
    if not isinstance(value, dict):
        raise ProductResponseError("Etsy price must be a Money object")
    amount = value.get("amount")
    divisor = value.get("divisor")
    currency_code = value.get("currency_code")
    if (
        type(amount) is not int
        or type(divisor) is not int
        or divisor <= 0
        or not isinstance(currency_code, str)
        or not currency_code.strip()
    ):
        raise ProductResponseError("Etsy Money must include amount, divisor, currency")
    return ProductPrice(
        amount=Decimal(amount) / Decimal(divisor),
        currency_code=currency_code,
        basis="minimum_listing_price",
    )


def _parse_amazon_prices(offers: Any) -> Tuple[ProductPrice, ...]:
    if offers is None:
        return ()
    if not isinstance(offers, dict):
        raise ProductResponseError("Amazon offersV2 must be an object")
    listings = offers.get("listings")
    if listings is None:
        return ()
    if not isinstance(listings, list):
        raise ProductResponseError("Amazon offer listings must be a list")

    prices: List[ProductPrice] = []
    for listing in listings:
        if not isinstance(listing, dict):
            raise ProductResponseError("Amazon offers must contain listing objects")
        price = listing.get("price")
        if price is None:
            continue
        if not isinstance(price, dict):
            raise ProductResponseError("Amazon offer price must be an object")
        money = price.get("money")
        if not isinstance(money, dict):
            raise ProductResponseError("Amazon offer price must contain money")
        amount = money.get("amount")
        currency_code = money.get("currency")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float, Decimal))
            or not isinstance(currency_code, str)
            or not currency_code.strip()
        ):
            raise ProductResponseError(
                "Amazon Money must include amount and currency"
            )
        try:
            decimal_amount = Decimal(str(amount))
        except InvalidOperation as error:
            raise ProductResponseError("Amazon price amount is invalid") from error
        if not decimal_amount.is_finite() or decimal_amount < 0:
            raise ProductResponseError("Amazon price amount must be finite and nonnegative")
        prices.append(
            ProductPrice(
                amount=decimal_amount,
                currency_code=currency_code,
                basis="marketplace_offer",
            )
        )
    return tuple(prices)


def _amazon_category(item: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    browse_node_info = item.get("browseNodeInfo")
    if isinstance(browse_node_info, dict):
        browse_nodes = browse_node_info.get("browseNodes")
        if isinstance(browse_nodes, list) and browse_nodes:
            node = browse_nodes[0]
            if isinstance(node, dict):
                name = node.get("displayName")
                node_id = node.get("id")
                if name is not None and not isinstance(name, str):
                    raise ProductResponseError(
                        "Amazon browse node displayName must be a string"
                    )
                if node_id is not None and not isinstance(node_id, (int, str)):
                    raise ProductResponseError("Amazon browse node id is invalid")
                return name, None if node_id is None else str(node_id)

    item_info = item.get("itemInfo")
    classifications = (
        item_info.get("classifications")
        if isinstance(item_info, dict)
        else None
    )
    product_group = (
        classifications.get("productGroup")
        if isinstance(classifications, dict)
        else None
    )
    if isinstance(product_group, dict):
        name = product_group.get("displayValue")
        if name is not None and not isinstance(name, str):
            raise ProductResponseError("Amazon productGroup displayValue must be a string")
        return name, None
    return None, None


def _optional_string(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProductResponseError(f"{field_name} must be a string")
    return value
