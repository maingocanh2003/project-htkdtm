"""D10 parser for D7 raw Etsy review payloads.

Design rules:
- Each raw review dict is attached unchanged to its ParsedReviewRecord.
- review_text=None means the source explicitly sent null — not the same as absent.
- reviewed_at_iso is an ISO-8601 string; we do not reparse Unix timestamps into
  datetime objects — the collector already did that; we store the ISO string from
  that conversion here, or convert from the raw Unix int without altering the int.
- ParseError.kind distinguishes MISSING / NULL / WRONG_TYPE / WRONG_FORMAT.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .parsed_record import (
    ParseError,
    ParseErrorKind,
    ParsedReviewPayload,
    ParsedReviewRecord,
    RecordProvenance,
)


class EtsyReviewParser:
    """Parse one raw Etsy listing-review page payload into ParsedReviewPayload."""

    def parse(
        self,
        payload: bytes,
        raw_collection_id: str,
        expected_listing_id: Optional[int] = None,
        source_id: str = "etsy",
        collected_at_iso: str = "",
        source_url: Optional[str] = None,
    ) -> ParsedReviewPayload:
        provenance = RecordProvenance(
            source_id=source_id,
            raw_collection_id=raw_collection_id,
            collected_at_iso=collected_at_iso,
            source_url=source_url,
        )
        body = _decode_json(payload, source_id, raw_collection_id)

        # count — required nonnegative int
        if "count" not in body:
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.MISSING_FIELD, "'count' is required",
            )
        count = body["count"]
        if count is None:
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.NULL_FIELD, "'count' must not be null",
            )
        if type(count) is not int:
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.WRONG_TYPE,
                f"'count' expected int, got {type(count).__name__}",
            )
        if count < 0:
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.WRONG_FORMAT, "'count' must be nonnegative",
            )

        # results — required list
        if "results" not in body:
            raise ParseError(
                source_id, raw_collection_id, "results",
                ParseErrorKind.MISSING_FIELD, "'results' is required",
            )
        results = body["results"]
        if results is None:
            raise ParseError(
                source_id, raw_collection_id, "results",
                ParseErrorKind.NULL_FIELD, "'results' must not be null",
            )
        if not isinstance(results, list):
            raise ParseError(
                source_id, raw_collection_id, "results",
                ParseErrorKind.WRONG_TYPE,
                f"'results' expected list, got {type(results).__name__}",
            )
        if count < len(results):
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.WRONG_FORMAT,
                f"count ({count}) < results length ({len(results)})",
            )

        records = tuple(
            self._parse_review(raw, i, provenance, expected_listing_id)
            for i, raw in enumerate(results)
        )
        return ParsedReviewPayload(
            provenance=provenance,
            records=records,
            record_count=len(records),
            reported_count=count,
        )

    def _parse_review(
        self,
        raw: Any,
        index: int,
        provenance: RecordProvenance,
        expected_listing_id: Optional[int],
    ) -> ParsedReviewRecord:
        sid = provenance.source_id
        cid = provenance.raw_collection_id
        prefix = f"results[{index}]"

        if not isinstance(raw, dict):
            raise ParseError(
                sid, cid, prefix, ParseErrorKind.WRONG_TYPE,
                f"review must be a JSON object, got {type(raw).__name__}",
            )

        # listing_id — required; validate cross-reference if expected provided
        if "listing_id" not in raw:
            raise ParseError(
                sid, cid, f"{prefix}.listing_id", ParseErrorKind.MISSING_FIELD,
                "listing_id is required",
            )
        listing_id = raw["listing_id"]
        if listing_id is None:
            raise ParseError(
                sid, cid, f"{prefix}.listing_id", ParseErrorKind.NULL_FIELD,
                "listing_id must not be null",
            )
        if type(listing_id) is not int:
            raise ParseError(
                sid, cid, f"{prefix}.listing_id", ParseErrorKind.WRONG_TYPE,
                f"listing_id expected int, got {type(listing_id).__name__}",
            )
        if expected_listing_id is not None and listing_id != expected_listing_id:
            raise ParseError(
                sid, cid, f"{prefix}.listing_id", ParseErrorKind.WRONG_FORMAT,
                f"listing_id {listing_id} does not match expected {expected_listing_id}",
            )

        # rating — required int 1–5
        if "rating" not in raw:
            raise ParseError(
                sid, cid, f"{prefix}.rating", ParseErrorKind.MISSING_FIELD,
                "rating is required",
            )
        rating = raw["rating"]
        if rating is None:
            raise ParseError(
                sid, cid, f"{prefix}.rating", ParseErrorKind.NULL_FIELD,
                "rating must not be null",
            )
        if type(rating) is not int:
            raise ParseError(
                sid, cid, f"{prefix}.rating", ParseErrorKind.WRONG_TYPE,
                f"rating expected int, got {type(rating).__name__}",
            )
        if not 1 <= rating <= 5:
            raise ParseError(
                sid, cid, f"{prefix}.rating", ParseErrorKind.WRONG_FORMAT,
                f"rating must be 1–5, got {rating}",
            )

        # review text — optional; null is preserved as None
        review_text: Optional[str] = None
        if "review" in raw:
            rv = raw["review"]
            if rv is not None:
                if not isinstance(rv, str):
                    raise ParseError(
                        sid, cid, f"{prefix}.review", ParseErrorKind.WRONG_TYPE,
                        f"review text expected str, got {type(rv).__name__}",
                    )
                review_text = rv  # keep raw including leading/trailing whitespace

        # language — optional string
        language: Optional[str] = None
        if "language" in raw:
            lang = raw["language"]
            if lang is not None:
                if not isinstance(lang, str):
                    raise ParseError(
                        sid, cid, f"{prefix}.language", ParseErrorKind.WRONG_TYPE,
                        f"language expected str, got {type(lang).__name__}",
                    )
                language = lang

        # timestamp — prefer created_timestamp, fall back to create_timestamp
        reviewed_at_iso = _parse_review_timestamp(raw, sid, cid, prefix)

        return ParsedReviewRecord(
            provenance=provenance,
            raw_record=dict(raw),
            product_reference=str(listing_id),
            rating=rating,
            review_text=review_text,
            reviewed_at_iso=reviewed_at_iso,
            language=language,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_review_timestamp(
    raw: Dict[str, Any],
    source_id: str,
    cid: str,
    prefix: str,
) -> Optional[str]:
    """Convert Unix timestamp to ISO-8601 UTC string; None when absent."""
    ts: Optional[Any] = None
    ts_key: Optional[str] = None
    for key in ("created_timestamp", "create_timestamp"):
        if key in raw:
            ts = raw[key]
            ts_key = key
            break

    if ts_key is None or ts is None:
        return None

    if type(ts) is not int:
        raise ParseError(
            source_id, cid, f"{prefix}.{ts_key}", ParseErrorKind.WRONG_TYPE,
            f"timestamp expected int, got {type(ts).__name__}",
        )
    if ts < 0:
        raise ParseError(
            source_id, cid, f"{prefix}.{ts_key}", ParseErrorKind.WRONG_FORMAT,
            "timestamp must be nonnegative",
        )
    try:
        dt = datetime.fromtimestamp(ts, timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ParseError(
            source_id, cid, f"{prefix}.{ts_key}", ParseErrorKind.WRONG_FORMAT,
            f"timestamp out of range: {exc}",
        ) from exc
    return dt.isoformat()


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
