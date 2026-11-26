"""Shared intermediate data structures and error taxonomy for D10 parsers.

Every parsed record:
- Carries a ``raw_collection_id`` and ``source_id`` (provenance link to raw storage).
- Carries the original ``raw_record`` dict/row unchanged (no mutations).
- Uses a typed ``ParseErrorKind`` to distinguish missing, null, wrong-type and
  wrong-format errors — callers can branch on the kind without string matching.

No database IDs are generated here; no data is transformed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------


class ParseErrorKind(str, Enum):
    """Distinguishes the four error categories required by the spec."""

    MISSING_FIELD = "missing_field"       # key absent from the payload
    NULL_FIELD = "null_field"             # key present but value is JSON null / None
    WRONG_TYPE = "wrong_type"             # value present but Python type is unexpected
    WRONG_FORMAT = "wrong_format"         # type correct but value violates a constraint
    INVALID_STRUCTURE = "invalid_structure"  # top-level envelope malformed


@dataclass(frozen=True)
class ParseError(Exception):
    """Structured parse failure with provenance and error taxonomy.

    Attributes:
        source_id:          Registry source identifier.
        raw_collection_id:  UUID hex of the raw storage collection (provenance link).
        field_path:         Dot-separated path to the failing field, e.g. ``"data[0].cmdCode"``.
        kind:               One of the ``ParseErrorKind`` members.
        detail:             Human-readable explanation; never contains the raw value.
    """

    source_id: str
    raw_collection_id: str
    field_path: str
    kind: ParseErrorKind
    detail: str

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"[{self.kind.value}] {self.source_id}/{self.raw_collection_id} "
            f"@ {self.field_path}: {self.detail}"
        )


# ---------------------------------------------------------------------------
# Shared provenance envelope (attached to every parsed record)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordProvenance:
    """Links a parsed record back to its raw storage entry and collection event."""

    source_id: str
    raw_collection_id: str
    collected_at_iso: str    # ISO-8601 string from manifest; not re-parsed
    source_url: Optional[str]  # endpoint or URL that produced the payload


# ---------------------------------------------------------------------------
# D5 — Trade (UN Comtrade, ITC Trade Map)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedTradeRecord:
    """Intermediate trade flow record.  Raw record preserved unchanged."""

    provenance: RecordProvenance
    raw_record: Dict[str, Any]            # original dict from JSON response

    # Fields extracted by parser — None when source did not supply the value
    reporter_code: Optional[str]
    partner_code: Optional[str]
    hs_code: Optional[str]
    period: Optional[str]                 # "2022" or "2022-01"
    flow_code: Optional[str]              # "M" / "X"
    net_weight_kg: Optional[float]
    trade_value_usd: Optional[float]      # CIF for imports, FOB for exports
    # ITC-specific — absent for UN Comtrade records
    reporter_name: Optional[str]
    partner_name: Optional[str]
    product_description: Optional[str]


@dataclass(frozen=True)
class ParsedTradePayload:
    """Result of parsing one raw trade payload (one collection event)."""

    provenance: RecordProvenance
    records: Tuple[ParsedTradeRecord, ...]
    record_count: int
    reported_count: Optional[int]         # from envelope; None for file datasets


# ---------------------------------------------------------------------------
# D6 — Marketplace products (Etsy, Amazon)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedPriceInfo:
    """A single price point; amount is kept as a string to avoid float rounding."""

    amount_str: str            # exact string from source, e.g. "24.99"
    currency_code: str
    basis: str                 # "minimum_listing_price" / "marketplace_offer"


@dataclass(frozen=True)
class ParsedProductRecord:
    """Intermediate marketplace product record."""

    provenance: RecordProvenance
    raw_record: Dict[str, Any]

    source_product_id: str
    product_url: Optional[str]
    name: Optional[str]
    category: Optional[str]
    category_id: Optional[str]
    prices: Tuple[ParsedPriceInfo, ...]


@dataclass(frozen=True)
class ParsedProductPayload:
    """Result of parsing one marketplace product payload."""

    provenance: RecordProvenance
    records: Tuple[ParsedProductRecord, ...]
    record_count: int
    reported_count: Optional[int]


# ---------------------------------------------------------------------------
# D7 — Reviews (Etsy)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedReviewRecord:
    """Intermediate review record; raw_record is the original JSON dict."""

    provenance: RecordProvenance
    raw_record: Dict[str, Any]

    product_reference: str             # listing_id as string
    rating: int                        # 1–5
    review_text: Optional[str]         # None when source sends null
    reviewed_at_iso: Optional[str]     # ISO-8601 UTC string; None if absent
    language: Optional[str]


@dataclass(frozen=True)
class ParsedReviewPayload:
    """Result of parsing one review page payload."""

    provenance: RecordProvenance
    records: Tuple[ParsedReviewRecord, ...]
    record_count: int
    reported_count: int


# ---------------------------------------------------------------------------
# D8 — Google Trends CSV
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedTrendsRow:
    """One data row from a Google Trends UI CSV export."""

    provenance: RecordProvenance
    raw_row: Dict[str, str]            # column→raw-string mapping, unchanged

    period_label: str                  # e.g. "2025-01-05" (week) or "2025-01"
    keyword_values: Tuple[Tuple[str, str], ...]
    # each entry: (keyword_column_header, raw_value_string)
    # Values are kept as strings — semantics documented in manifest, not assumed


@dataclass(frozen=True)
class ParsedTrendsPayload:
    """Result of parsing one Google Trends CSV export."""

    provenance: RecordProvenance
    keywords: Tuple[str, ...]          # column headers from the data section
    rows: Tuple[ParsedTrendsRow, ...]
    row_count: int
    data_type_hint: Optional[str]      # first header cell if present


# ---------------------------------------------------------------------------
# D9 — Domestic suppliers / products
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedCommercialInfo:
    """Commercial fields — all Optional; never inferred from context."""

    price_vnd_str: Optional[str]       # exact string from source
    currency: Optional[str]
    moq: Optional[int]
    lead_time_days: Optional[int]
    wholesale_available: Optional[bool]


@dataclass(frozen=True)
class ParsedSupplierInfo:
    """Business-entity fields separated from product and commercial fields."""

    supplier_name: str
    tax_code: Optional[str]
    address: Optional[str]
    province: Optional[str]
    website: Optional[str]
    phone: Optional[str]
    business_type: Optional[str]
    declared_capacity_note: Optional[str]


@dataclass(frozen=True)
class ParsedDomesticProductRecord:
    """Intermediate domestic product record."""

    provenance: RecordProvenance
    raw_record: Dict[str, Any]

    source_product_id: str
    product_url: Optional[str]
    name: Optional[str]
    description: Optional[str]
    category: Optional[str]
    material: Optional[str]
    origin_region: Optional[str]
    commercial: ParsedCommercialInfo


@dataclass(frozen=True)
class ParsedDomesticPayload:
    """Result of parsing one domestic supplier catalog payload."""

    provenance: RecordProvenance
    supplier: Optional[ParsedSupplierInfo]
    products: Tuple[ParsedDomesticProductRecord, ...]
    record_count: int
