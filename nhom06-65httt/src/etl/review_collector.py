"""Etsy review collection through its official listing-reviews API."""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Tuple

from .http_client import HttpClient
from .raw_storage import CollectionStatus, RawStorage
from .source_registry import (
    CollectionMetadata,
    SourceGroup,
    SourceRegistry,
    SourceStatus,
    SourceType,
)


_ETSY_SOURCE_ID = "etsy"
_ETSY_API_VERSION = "3.0.0"
_ETSY_PAGE_SIZE = 100
_ETSY_MAX_OFFSET = 12000


@dataclass(frozen=True)
class ReviewRecord:
    """Unclassified review content and source-provided product metadata."""

    source_id: str
    source_review_id: Optional[str]
    product_reference: str
    review_text: Optional[str]
    reviewed_at: Optional[datetime]
    rating: int
    review_url: Optional[str]


@dataclass(frozen=True)
class ReviewCollectionResult:
    """Parsed reviews and the raw collection ID for each API page."""

    product_reference: str
    reported_count: int
    records: Tuple[ReviewRecord, ...]
    raw_collection_ids: Tuple[str, ...]
    status: CollectionStatus


class ReviewCollectionError(ValueError):
    """Raised when an Etsy review response cannot be collected or parsed."""

    def __init__(
        self, message: str, collection_id: Optional[str] = None
    ) -> None:
        if collection_id is not None:
            message = f"{message}; raw collection_id={collection_id}"
        super().__init__(message)
        self.collection_id = collection_id


class EtsyReviewCollector:
    """Collect raw Etsy listing reviews using the shared GET client.

    The registry source must be activated only after API access and data-retention
    requirements have been confirmed. This collector does not infer a review ID
    because Etsy's listing-review response does not provide one.
    """

    def __init__(
        self,
        http_client: HttpClient,
        raw_storage: RawStorage,
        source_registry: SourceRegistry,
        api_key: str,
        page_size: int = _ETSY_PAGE_SIZE,
    ) -> None:
        source = source_registry.get(_ETSY_SOURCE_ID)
        if source.source_group is not SourceGroup.MARKETPLACE_PRODUCTS:
            raise ValueError("etsy source has an unexpected source group")
        if source.source_type is not SourceType.API or source.base_url is None:
            raise ValueError("etsy must be registered as an API source")
        if source.status is not SourceStatus.ACTIVE:
            raise ValueError(
                "etsy source must be active after access and retention approval"
            )
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must not be empty")
        if type(page_size) is not int or not 1 <= page_size <= _ETSY_PAGE_SIZE:
            raise ValueError(
                f"page_size must be an integer between 1 and {_ETSY_PAGE_SIZE}"
            )

        self._http_client = http_client
        self._raw_storage = raw_storage
        self._base_url = source.base_url.rstrip("/")
        self._api_key = api_key
        self._page_size = page_size
        self._max_pages = (_ETSY_MAX_OFFSET // page_size) + 1

    @classmethod
    def from_env(
        cls,
        http_client: HttpClient,
        raw_storage: RawStorage,
        source_registry: SourceRegistry,
        environ: Optional[Mapping[str, str]] = None,
    ) -> "EtsyReviewCollector":
        """Create a collector from ETSY_API_KEY without logging its value."""
        values = os.environ if environ is None else environ
        api_key = values.get("ETSY_API_KEY", "").strip()
        if not api_key:
            raise ValueError("ETSY_API_KEY must be configured")
        return cls(http_client, raw_storage, source_registry, api_key)

    def collect_listing(self, listing_id: int) -> ReviewCollectionResult:
        """Fetch all reachable pages for one listing and preserve each raw page."""
        if type(listing_id) is not int or listing_id < 1:
            raise ValueError("listing_id must be a positive integer")

        endpoint = f"/v3/application/listings/{listing_id}/reviews"
        request_url = f"{self._base_url}{endpoint}"
        offset = 0
        reported_count = 0
        records = []
        collection_ids = []
        status = CollectionStatus.SUCCESS
        page_number = 0

        while page_number < self._max_pages and offset <= _ETSY_MAX_OFFSET:
            request_parameters = {
                "listing_id": listing_id,
                "limit": self._page_size,
                "offset": offset,
            }
            response = self._http_client.get(
                request_url,
                params={
                    "limit": self._page_size,
                    "offset": offset,
                },
                headers={"x-api-key": self._api_key},
            )
            if response.status_code != 200:
                raise ReviewCollectionError(
                    f"Etsy returned unexpected HTTP status {response.status_code}"
                )

            metadata = CollectionMetadata(
                collected_at=datetime.now(timezone.utc),
                source_id=_ETSY_SOURCE_ID,
                data_format="json",
                version=_ETSY_API_VERSION,
                endpoint=endpoint,
            )
            try:
                page_count, page_records = _decode_review_page(
                    response.body,
                    expected_listing_id=listing_id,
                )
            except ReviewCollectionError as error:
                collection_id = self._raw_storage.save(
                    response.body,
                    metadata,
                    request_parameters,
                    status=CollectionStatus.FAILED,
                )
                raise ReviewCollectionError(
                    error.args[0],
                    collection_id,
                ) from error

            collection_id = self._raw_storage.save(
                response.body,
                metadata,
                request_parameters,
                status=CollectionStatus.SUCCESS,
            )
            collection_ids.append(collection_id)
            records.extend(page_records)
            reported_count = page_count
            page_number += 1

            next_offset = offset + len(page_records)
            if next_offset >= reported_count:
                break
            if not page_records:
                status = CollectionStatus.PARTIAL
                break
            if (
                next_offset > _ETSY_MAX_OFFSET
                or page_number == self._max_pages
            ):
                status = CollectionStatus.PARTIAL
                break
            offset = next_offset
        else:
            status = CollectionStatus.PARTIAL

        return ReviewCollectionResult(
            product_reference=str(listing_id),
            reported_count=reported_count,
            records=tuple(records),
            raw_collection_ids=tuple(collection_ids),
            status=status,
        )


def _decode_review_page(
    payload: bytes,
    expected_listing_id: int,
) -> Tuple[int, Tuple[ReviewRecord, ...]]:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    try:
        body = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReviewCollectionError("Etsy response is not valid JSON") from error
    if not isinstance(body, dict):
        raise ReviewCollectionError("Etsy response must be a JSON object")

    count = body.get("count")
    results = body.get("results")
    if (
        type(count) is not int
        or count < 0
        or not isinstance(results, list)
        or count < len(results)
    ):
        raise ReviewCollectionError(
            "Etsy response must contain a valid count and results list"
        )

    records = tuple(
        _parse_review(review, expected_listing_id) for review in results
    )
    return count, records


def _parse_review(review: Any, expected_listing_id: int) -> ReviewRecord:
    if not isinstance(review, dict):
        raise ReviewCollectionError("Etsy results must contain review objects")
    listing_id = review.get("listing_id")
    if type(listing_id) is not int or listing_id != expected_listing_id:
        raise ReviewCollectionError(
            "Etsy review listing_id does not match the requested product"
        )

    rating = review.get("rating")
    if type(rating) is not int or not 1 <= rating <= 5:
        raise ReviewCollectionError("Etsy review rating must be an integer from 1 to 5")

    review_text = review.get("review")
    if review_text is not None and not isinstance(review_text, str):
        raise ReviewCollectionError("Etsy review text must be a string or null")

    timestamp = review.get("created_timestamp")
    if timestamp is None:
        timestamp = review.get("create_timestamp")
    reviewed_at = _parse_timestamp(timestamp)

    return ReviewRecord(
        source_id=_ETSY_SOURCE_ID,
        source_review_id=None,
        product_reference=str(listing_id),
        review_text=review_text,
        reviewed_at=reviewed_at,
        rating=rating,
        review_url=None,
    )


def _parse_timestamp(timestamp: Any) -> Optional[datetime]:
    if timestamp is None:
        return None
    if type(timestamp) is not int or timestamp < 0:
        raise ReviewCollectionError("Etsy review timestamp must be a nonnegative integer")
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ReviewCollectionError("Etsy review timestamp is out of range") from error
