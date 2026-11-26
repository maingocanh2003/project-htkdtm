"""Google Trends UI export ingestion with explicit collection provenance."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional, Tuple

from .raw_storage import CollectionStatus, RawStorage
from .source_registry import (
    CollectionMetadata,
    SourceGroup,
    SourceRegistry,
    SourceType,
)


class TrendsDataType(str, Enum):
    """Project-level chart types recorded for a Google Trends export."""

    INTEREST_OVER_TIME = "interest_over_time"
    INTEREST_BY_REGION = "interest_by_region"
    RELATED_QUERIES = "related_queries"
    RELATED_TOPICS = "related_topics"


@dataclass(frozen=True)
class GoogleTrendsRequest:
    """User-selected query context for a manually exported Trends chart."""

    keywords: Tuple[str, ...]
    period_start: date
    period_end: date
    geo: str
    data_type: TrendsDataType
    search_type: str
    interval: Optional[str] = None
    category: Optional[str] = None
    original_filename: Optional[str] = None
    export_date: Optional[date] = None
    export_timestamp: Optional[datetime] = None
    related_section: Optional[str] = None
    exported_keywords: Optional[Tuple[str, ...]] = None
    keyword_header_matches_request: Optional[bool] = None

    def __post_init__(self) -> None:
        if not all(isinstance(keyword, str) for keyword in self.keywords):
            raise ValueError("keywords must be strings")
        if not self.keywords or any(not keyword.strip() for keyword in self.keywords):
            raise ValueError("keywords must contain at least one non-empty term")
        if self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        if not self.geo.strip():
            raise ValueError("geo must not be empty")
        if not isinstance(self.data_type, TrendsDataType):
            raise ValueError("data_type must be a TrendsDataType")
        if not self.search_type.strip():
            raise ValueError("search_type must not be empty")
        if self.interval is not None and not self.interval.strip():
            raise ValueError("interval must not be empty when provided")
        if self.category is not None and not self.category.strip():
            raise ValueError("category must not be empty when provided")
        if self.original_filename is not None and not self.original_filename.strip():
            raise ValueError("original_filename must not be empty when provided")
        if self.related_section is not None and (
            self.related_section not in {"top", "rising"}
        ):
            raise ValueError("related_section must be 'top' or 'rising'")
        if self.related_section is not None and self.data_type not in {
            TrendsDataType.RELATED_QUERIES,
            TrendsDataType.RELATED_TOPICS,
        }:
            raise ValueError(
                "related_section is only valid for related queries or topics"
            )
        if self.exported_keywords is not None and not all(
            isinstance(keyword, str) and keyword.strip()
            for keyword in self.exported_keywords
        ):
            raise ValueError("exported_keywords must contain non-empty strings")
        if self.keyword_header_matches_request is not None and not isinstance(
            self.keyword_header_matches_request, bool
        ):
            raise ValueError("keyword_header_matches_request must be a bool or None")
        if (
            self.keyword_header_matches_request is not None
            and self.exported_keywords is None
        ):
            raise ValueError(
                "keyword_header_matches_request requires exported_keywords"
            )
        if self.export_date is not None and (
            not isinstance(self.export_date, date)
            or isinstance(self.export_date, datetime)
        ):
            raise ValueError("export_date must be a date")
        if self.export_timestamp is not None and not isinstance(
            self.export_timestamp, datetime
        ):
            raise ValueError("export_timestamp must be a datetime")
        if self.export_timestamp is not None and (
            self.export_timestamp.tzinfo is None
            or self.export_timestamp.utcoffset() is None
        ):
            raise ValueError("export_timestamp must include a timezone")


class GoogleTrendsExportError(ValueError):
    """Raised when an export contains no payload; its raw manifest is retained."""

    def __init__(self, collection_id: str) -> None:
        super().__init__(
            f"Google Trends export is empty; raw collection_id={collection_id}"
        )
        self.collection_id = collection_id


class GoogleTrendsExportAdapter:
    """Store official Google Trends UI CSV exports without parsing or scaling."""

    def __init__(
        self, raw_storage: RawStorage, source_registry: SourceRegistry
    ) -> None:
        source = source_registry.get("google_trends")
        if source.source_group is not SourceGroup.GOOGLE_TRENDS:
            raise ValueError("google_trends source has an unexpected source group")
        if source.source_type is not SourceType.MANUAL:
            raise ValueError("google_trends must be registered as a manual source")
        self._raw_storage = raw_storage

    def ingest(self, payload: bytes, request: GoogleTrendsRequest) -> str:
        """Persist CSV bytes and request provenance exactly as supplied."""
        if not isinstance(request, GoogleTrendsRequest):
            raise TypeError("request must be a GoogleTrendsRequest")
        request_parameters = {
            "collection_method": "google_trends_ui_csv_export",
            "keywords": list(
                request.exported_keywords
                if request.exported_keywords is not None
                else request.keywords
            ),
            "requested_keywords": list(request.keywords),
            "keyword_header_matches_request": (
                request.keyword_header_matches_request
            ),
            "period_start": request.period_start.isoformat(),
            "period_end": request.period_end.isoformat(),
            "geo": request.geo,
            "data_type": request.data_type.value,
            "search_type": request.search_type,
            "interval": request.interval,
            "category": request.category,
            "original_filename": request.original_filename,
            "related_section": request.related_section,
            "export_date": (
                request.export_date.isoformat()
                if request.export_date is not None
                else None
            ),
            "export_timestamp": (
                request.export_timestamp.isoformat()
                if request.export_timestamp is not None
                else None
            ),
            "value_semantics": _value_semantics(request.data_type),
            "attribution_required": True,
            "attribution_text": "Data source: Google Trends (https://trends.google.com).",
        }
        metadata = CollectionMetadata(
            collected_at=datetime.now(timezone.utc),
            source_id="google_trends",
            data_format="csv",
        )

        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        status = CollectionStatus.SUCCESS if payload else CollectionStatus.FAILED
        collection_id = self._raw_storage.save(
            payload,
            metadata,
            request_parameters,
            status=status,
        )
        if not payload:
            raise GoogleTrendsExportError(collection_id)
        return collection_id


def _value_semantics(data_type: TrendsDataType) -> dict[str, str]:
    scope = "Google Trends UI CSV export only; not the Google Trends API alpha"
    if data_type in {
        TrendsDataType.INTEREST_OVER_TIME,
        TrendsDataType.INTEREST_BY_REGION,
    }:
        return {
            "measure": "relative_search_interest",
            "unit": "dimensionless_index",
            "scale": "0-100 per selected query, geography, and time range",
            "meaning": (
                "100 is peak relative interest in the selected scope; 0 may "
                "mean insufficient search volume, not zero absolute searches"
            ),
            "scope": scope,
        }
    return {
        "measure": "source_specific_related_query_or_topic_value",
        "unit": "not_interpreted",
        "scale": "not_assumed",
        "meaning": (
            "Preserve the source value; verify whether it is a ranking, "
            "relative index, or growth measure before interpreting it"
        ),
        "scope": scope,
    }
