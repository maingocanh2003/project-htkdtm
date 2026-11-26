"""Source registry and collection provenance metadata for the ETL package."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Tuple
from urllib.parse import urlsplit


class SourceGroup(str, Enum):
    """Project-level source groups identified during the D0 survey."""

    UN_COMTRADE = "un_comtrade"
    ITC_TRADE_MAP = "itc_trade_map"
    GOOGLE_TRENDS = "google_trends"
    MARKETPLACE_PRODUCTS = "marketplace_products"
    DOMESTIC_SUPPLIER_CATALOGS = "domestic_supplier_catalogs"


class SourceType(str, Enum):
    """How data from a source is provided to the ETL process."""

    API = "api"
    FILE_DATASET = "file_dataset"
    MANUAL = "manual"


class SourceStatus(str, Enum):
    """Registration/collection readiness state for a source."""

    PLANNED = "planned"
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(frozen=True)
class Source:
    """Describes a data source; deliberately contains no credential fields."""

    source_id: str
    source_name: str
    source_type: SourceType
    base_url: Optional[str]
    status: SourceStatus
    description: str
    source_group: SourceGroup

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", self.source_id):
            raise ValueError("source_id must be a non-empty lowercase snake_case id")
        if not self.source_name.strip():
            raise ValueError("source_name must not be empty")
        if not self.description.strip():
            raise ValueError("description must not be empty")
        if not isinstance(self.source_type, SourceType):
            raise ValueError("source_type must be a SourceType")
        if not isinstance(self.status, SourceStatus):
            raise ValueError("status must be a SourceStatus")
        if not isinstance(self.source_group, SourceGroup):
            raise ValueError("source_group must be a SourceGroup")
        if self.base_url is not None:
            _validate_http_url(self.base_url, "base_url")


@dataclass(frozen=True)
class CollectionMetadata:
    """Provenance for one collection event, without collected payload data."""

    collected_at: datetime
    source_id: str
    data_format: str
    version: Optional[str] = None
    endpoint: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.collected_at, datetime):
            raise ValueError("collected_at must be a datetime")
        if self.collected_at.tzinfo is None or self.collected_at.utcoffset() is None:
            raise ValueError("collected_at must include a timezone")
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")
        if not self.data_format.strip():
            raise ValueError("data_format must not be empty")
        if self.version is not None and not self.version.strip():
            raise ValueError("version must not be empty when provided")
        if self.endpoint is not None:
            if not self.endpoint.strip():
                raise ValueError("endpoint must not be empty when provided")
            if self.endpoint.startswith("/"):
                parsed = urlsplit(self.endpoint)
                if parsed.query or parsed.fragment:
                    raise ValueError("endpoint must not contain a query or fragment")
            else:
                _validate_http_url(self.endpoint, "endpoint")


class SourceRegistry:
    """In-memory registry for source definitions and metadata validation."""

    def __init__(self) -> None:
        self._sources: Dict[str, Source] = {}

    def register(self, source: Source) -> None:
        """Register a source, rejecting duplicate identifiers."""
        if not isinstance(source, Source):
            raise TypeError("source must be a Source")
        if source.source_id in self._sources:
            raise ValueError(f"source_id already registered: {source.source_id}")
        self._sources[source.source_id] = source

    def get(self, source_id: str) -> Source:
        """Return a registered source or raise KeyError if it is unknown."""
        return self._sources[source_id]

    def list_sources(self) -> Tuple[Source, ...]:
        """Return registered sources as an immutable snapshot."""
        return tuple(self._sources.values())

    def validate_metadata(self, metadata: CollectionMetadata) -> None:
        """Ensure metadata refers to a known source and valid source type."""
        if not isinstance(metadata, CollectionMetadata):
            raise TypeError("metadata must be CollectionMetadata")
        source = self.get(metadata.source_id)
        if metadata.endpoint is not None and source.source_type is not SourceType.API:
            raise ValueError("endpoint metadata is only valid for API sources")


def create_project_source_registry() -> SourceRegistry:
    """Build the project's source catalog without enabling any collection."""
    registry = SourceRegistry()
    sources = (
        Source(
            source_id="un_comtrade",
            source_name="UN Comtrade",
            source_type=SourceType.API,
            base_url="https://comtradeapi.un.org",
            status=SourceStatus.PLANNED,
            description="International trade statistics API source.",
            source_group=SourceGroup.UN_COMTRADE,
        ),
        Source(
            source_id="itc_trade_map",
            source_name="ITC Trade Map",
            source_type=SourceType.FILE_DATASET,
            base_url="https://www.trademap.org",
            status=SourceStatus.PLANNED,
            description="Trade statistics dataset obtained as a file export.",
            source_group=SourceGroup.ITC_TRADE_MAP,
        ),
        Source(
            source_id="google_trends",
            source_name="Google Trends",
            source_type=SourceType.MANUAL,
            base_url="https://trends.google.com",
            status=SourceStatus.PLANNED,
            description="Search trend data; collection method remains to be agreed.",
            source_group=SourceGroup.GOOGLE_TRENDS,
        ),
        Source(
            source_id="etsy",
            source_name="Etsy",
            source_type=SourceType.API,
            base_url="https://openapi.etsy.com",
            status=SourceStatus.PLANNED,
            description=(
                "Official marketplace API; access and retention requirements "
                "must be confirmed before collection."
            ),
            source_group=SourceGroup.MARKETPLACE_PRODUCTS,
        ),
        Source(
            source_id="amazon",
            source_name="Amazon",
            source_type=SourceType.API,
            base_url="https://creatorsapi.amazon",
            status=SourceStatus.PLANNED,
            description=(
                "Official Creators API; program eligibility and retention "
                "requirements must be confirmed before collection."
            ),
            source_group=SourceGroup.MARKETPLACE_PRODUCTS,
        ),
        Source(
            source_id="minh_long_1",
            source_name="Minh Long 1",
            source_type=SourceType.MANUAL,
            base_url=None,
            status=SourceStatus.PLANNED,
            description="Domestic supplier product catalog; website URL not specified.",
            source_group=SourceGroup.DOMESTIC_SUPPLIER_CATALOGS,
        ),
        Source(
            source_id="bat_trang",
            source_name="Bat Trang suppliers",
            source_type=SourceType.MANUAL,
            base_url=None,
            status=SourceStatus.PLANNED,
            description="Domestic supplier product catalogs; website URL not specified.",
            source_group=SourceGroup.DOMESTIC_SUPPLIER_CATALOGS,
        ),
    )
    for source in sources:
        registry.register(source)
    return registry


def _validate_http_url(value: str, field_name: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{field_name} must be an HTTP(S) URL without credentials, "
            "query, or fragment"
        )
