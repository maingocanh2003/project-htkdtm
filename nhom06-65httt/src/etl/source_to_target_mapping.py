"""D14 — Source-to-Target Mapping from D5–D13 ETL outputs to the 13 OLTP tables.

Design rules:
- Strictly follows ``01_init_oltp_erd_schema.sql``, ``thiet_ke_erd.md``,
  ``ĐẶC TẢ TỪ ĐIỂN DỮ LIỆU.md``, and ``thiet_ke_star_schema.md``.
- Does NOT modify DDL, add columns/tables, invent fake values for NOT NULL
  fields, or connect to any database.
- Reuses D10 (``parsed_record``), D11 (``normalizer``), and D12
  (``quality_validator``).
- Distinguishes missing source data, source NULL, invalid format/validation,
  unresolved FK references, pending Member 1 confirmations, and out-of-scope
  (AI/NLP, DSS) fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from .normalizer import (
    NormalizationStatus,
    NormalizedDomesticProductRecord,
    NormalizedField,
    NormalizedProductRecord,
    NormalizedReviewRecord,
    NormalizedTradeRecord,
    NormalizedTrendsRow,
    normalize_category,
    normalize_country,
    normalize_date,
    normalize_domestic_product,
    normalize_product_record,
    normalize_review_record,
    normalize_text,
    normalize_trade_record,
    normalize_trends_row,
)
from .parsed_record import (
    ParsedDomesticProductRecord,
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedSupplierInfo,
    ParsedTradeRecord,
    ParsedTrendsRow,
)
from .quality_validator import (
    DataQualityValidator,
    RecordValidationResult,
    ValidationSeverity,
)


# ---------------------------------------------------------------------------
# Mapping Status & Specification Data Structures
# ---------------------------------------------------------------------------


class MappingStatus(str, Enum):
    """D14 field-level mapping classification."""

    DIRECT = "DIRECT"
    TRANSFORM = "TRANSFORM"
    DEPENDENCY = "DEPENDENCY"
    NO_SOURCE = "NO_SOURCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"


class MappingIssueKind(str, Enum):
    """Distinguishes why a record or field cannot be mapped cleanly."""

    MISSING_NOT_NULL = "missing_not_null"
    SOURCE_NULL = "source_null"
    NO_SOURCE = "no_source"
    UNRESOLVED_FK = "unresolved_fk"
    VALIDATION_ERROR = "validation_error"
    INVALID_TYPE = "invalid_type"
    PENDING_CONFIRMATION = "pending_confirmation"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class ColumnMappingSpec:
    """Formal D14 specification for a single OLTP target column."""

    target_table: str
    target_column: str
    target_type: str
    nullable: bool
    mapping_status: MappingStatus
    source_group: str
    source_field: Optional[str]
    collector_parser: str
    transformation: str
    normalization_rule: str
    validation_rule: str
    source_type: Optional[str]
    is_pk: bool = False
    fk_target: Optional[str] = None
    is_unique: bool = False
    is_natural_key: bool = False
    default_value: Optional[str] = None
    check_constraint: Optional[str] = None
    missing_invalid_handling: str = ""


@dataclass(frozen=True)
class TableMappingSpec:
    """Formal D14 specification for one OLTP table."""

    table_name: str
    business_purpose: str
    primary_key: str
    foreign_keys: Tuple[str, ...]
    unique_keys: Tuple[str, ...]
    natural_key: Optional[str]
    columns: Tuple[ColumnMappingSpec, ...]


def _col(
    table: str,
    col: str,
    target_type: str,
    nullable: bool,
    status: MappingStatus,
    source_group: str,
    source_field: Optional[str],
    collector_parser: str,
    transformation: str,
    normalization_rule: str,
    validation_rule: str,
    source_type: Optional[str],
    *,
    is_pk: bool = False,
    fk_target: Optional[str] = None,
    is_unique: bool = False,
    is_natural_key: bool = False,
    default_value: Optional[str] = None,
    check_constraint: Optional[str] = None,
    missing_invalid_handling: str = "",
) -> ColumnMappingSpec:
    return ColumnMappingSpec(
        target_table=table,
        target_column=col,
        target_type=target_type,
        nullable=nullable,
        mapping_status=status,
        source_group=source_group,
        source_field=source_field,
        collector_parser=collector_parser,
        transformation=transformation,
        normalization_rule=normalization_rule,
        validation_rule=validation_rule,
        source_type=source_type,
        is_pk=is_pk,
        fk_target=fk_target,
        is_unique=is_unique,
        is_natural_key=is_natural_key,
        default_value=default_value,
        check_constraint=check_constraint,
        missing_invalid_handling=missing_invalid_handling,
    )


# ---------------------------------------------------------------------------
# Complete 13-Table OLTP Mapping Specification (from 01_init_oltp_erd_schema.sql)
# ---------------------------------------------------------------------------

OLTP_TABLE_SPECS: Dict[str, TableMappingSpec] = {
    "countries": TableMappingSpec(
        table_name="countries",
        business_purpose="Danh mục >130 quốc gia/vùng lãnh thổ giao thương gốm sứ",
        primary_key="country_id",
        foreign_keys=(),
        unique_keys=("country_code",),
        natural_key="country_code (ISO 3166-1 alpha-3 / UN M49)",
        columns=(
            _col("countries", "country_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None,
                 is_pk=True, missing_invalid_handling="DB tự tăng"),
            _col("countries", "country_code", "VARCHAR(10)", False, MappingStatus.TRANSFORM,
                 "Reference / Nhóm 1-3", "country_code / reporterCode / partnerCode",
                 "normalizer.py (CONFIRMED_COUNTRIES)", "Chuẩn hóa về ISO3 (VD: 842 -> USA)",
                 "normalize_country()", "NOT NULL, UNIQUE", "str/int",
                 is_unique=True, is_natural_key=True,
                 missing_invalid_handling="Thiếu hoặc ngoài CONFIRMED_COUNTRIES -> WAITING_CONFIRMATION_MEMBER_1"),
            _col("countries", "country_name", "VARCHAR(150)", False, MappingStatus.PENDING_CONFIRMATION,
                 "Reference Seed", "country_name", "Chưa có seed file >130 nước",
                 "Chuẩn hóa chuỗi NFC", "normalize_text()", "NOT NULL", "str",
                 missing_invalid_handling="Chờ bảng seed >130 quốc gia từ Thành viên 1"),
            _col("countries", "region_continent", "VARCHAR(100)", True, MappingStatus.PENDING_CONFIRMATION,
                 "Reference Seed", "region_continent", "Chưa có seed file",
                 "Chuẩn hóa chuỗi NFC", "normalize_text()", "Cho phép NULL", "str",
                 missing_invalid_handling="Giữ NULL nếu chưa có seed"),
            _col("countries", "currency_code", "VARCHAR(10)", True, MappingStatus.PENDING_CONFIRMATION,
                 "Reference Seed", "currency_code", "Chưa có seed file",
                 "Chuẩn hóa ISO 4217", "CONFIRMED_CURRENCIES", "Cho phép NULL", "str",
                 missing_invalid_handling="Giữ NULL nếu chưa có seed"),
            _col("countries", "is_key_market", "BOOLEAN", True, MappingStatus.PENDING_CONFIRMATION,
                 "Reference Seed", "is_key_market", "Chưa có danh sách trọng điểm chuẩn hóa",
                 "Boolean", "Không áp dụng", "DEFAULT FALSE", "bool",
                 default_value="FALSE", missing_invalid_handling="Dùng DEFAULT FALSE khi chưa xác nhận"),
        ),
    ),
    "market_regions": TableMappingSpec(
        table_name="market_regions",
        business_purpose="Danh mục 51 bang/vùng lãnh thổ phục vụ Google Trends",
        primary_key="region_id",
        foreign_keys=("country_id -> countries(country_id)",),
        unique_keys=("uq_country_region_code (country_id, region_code)",),
        natural_key="(country_id, region_code)",
        columns=(
            _col("market_regions", "region_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None,
                 is_pk=True),
            _col("market_regions", "country_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Reference / Nhóm 2", "country_code / geo", "google_trends_collector.py",
                 "Tra cứu country_id từ countries", "normalize_country()", "NOT NULL, FK -> countries", "str",
                 fk_target="countries(country_id)", is_unique=True, is_natural_key=True,
                 missing_invalid_handling="Không tìm thấy countries -> UNRESOLVED_FK"),
            _col("market_regions", "region_code", "VARCHAR(20)", False, MappingStatus.NO_SOURCE,
                 "Nhóm 2 (Google Trends)", "region_code", "Chưa có parser INTEREST_BY_REGION",
                 "Chuẩn hóa mã vùng (VD: US-CA)", "normalize_text()", "NOT NULL, UNIQUE(country_id, region_code)", "str",
                 is_unique=True, is_natural_key=True,
                 missing_invalid_handling="Chưa có nguồn/seed 51 bang"),
            _col("market_regions", "region_name", "VARCHAR(150)", False, MappingStatus.NO_SOURCE,
                 "Nhóm 2 (Google Trends)", "region_name", "Chưa có parser INTEREST_BY_REGION",
                 "Chuẩn hóa chuỗi NFC", "normalize_text()", "NOT NULL", "str",
                 missing_invalid_handling="Chưa có nguồn/seed 51 bang"),
        ),
    ),
    "product_categories": TableMappingSpec(
        table_name="product_categories",
        business_purpose="Danh mục 4 dòng sản phẩm gốm sứ chuẩn hóa",
        primary_key="category_id",
        foreign_keys=(),
        unique_keys=("category_code",),
        natural_key="category_code (TEA_SET, MUG_CUP, DINNERWARE, VASE_DECOR)",
        columns=(
            _col("product_categories", "category_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("product_categories", "category_code", "VARCHAR(50)", False, MappingStatus.TRANSFORM,
                 "Reference (Data Dictionary)", "category_code", "normalizer.py (CONFIRMED_CATEGORIES)",
                 "Ánh xạ về 4 mã chuẩn", "normalize_category()", "NOT NULL, UNIQUE", "str",
                 is_unique=True, is_natural_key=True),
            _col("product_categories", "category_name_vi", "VARCHAR(150)", False, MappingStatus.DIRECT,
                 "Reference (Data Dictionary)", "category_name_vi", "Seed cố định",
                 "Chuẩn hóa chuỗi NFC", "normalize_text()", "NOT NULL", "str"),
            _col("product_categories", "category_name_en", "VARCHAR(150)", False, MappingStatus.DIRECT,
                 "Reference (Data Dictionary)", "category_name_en", "Seed cố định",
                 "Chuẩn hóa chuỗi NFC", "normalize_text()", "NOT NULL", "str"),
            _col("product_categories", "hs_code_mapping", "VARCHAR(20)", True, MappingStatus.DIRECT,
                 "Reference (Data Dictionary)", "hs_code_mapping", "Seed cố định / CONFIRMED_HS_CODES",
                 "Giữ mã HS Chương 69", "normalize_hs_code()", "Cho phép NULL", "str"),
        ),
    ),
    "trade_statistics": TableMappingSpec(
        table_name="trade_statistics",
        business_purpose="Dữ liệu giao thương gốm sứ quốc tế (UN Comtrade & ITC Trade Map)",
        primary_key="trade_id",
        foreign_keys=("reporter_country_id -> countries(country_id)", "partner_country_id -> countries(country_id)"),
        unique_keys=(),
        natural_key=None,  # PENDING_CONFIRMATION: chưa có UNIQUE constraint trong DDL
        columns=(
            _col("trade_statistics", "trade_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("trade_statistics", "reporter_country_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 1 (UN Comtrade / ITC)", "reporterCode / Reporter", "trade_parser.py",
                 "Chuẩn hóa ISO3 -> tra cứu countries.country_id", "normalize_country()", "NOT NULL, FK -> countries", "str/int",
                 fk_target="countries(country_id)",
                 missing_invalid_handling="Thiếu hoặc chưa có trong countries -> UNRESOLVED_FK / Quarantine"),
            _col("trade_statistics", "partner_country_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 1 (UN Comtrade / ITC)", "partnerCode / Partner", "trade_parser.py (ITC đang trả None)",
                 "Chuẩn hóa ISO3 -> tra cứu countries.country_id", "normalize_country()", "NOT NULL, FK -> countries", "str/int",
                 fk_target="countries(country_id)",
                 missing_invalid_handling="ITC chưa parse Partner; thiếu -> UNRESOLVED_FK / Quarantine"),
            _col("trade_statistics", "year", "INTEGER", False, MappingStatus.TRANSFORM,
                 "Nhóm 1", "period", "trade_parser.py", "Cắt 4 ký tự đầu -> int",
                 "normalize_date()", "NOT NULL, CHECK (year BETWEEN 2000 AND 2100)", "str",
                 check_constraint="year >= 2000 AND year <= 2100",
                 missing_invalid_handling="Thiếu/sai định dạng/ngoài khoảng -> Quarantine ERROR"),
            _col("trade_statistics", "trade_flow", "VARCHAR(20)", False, MappingStatus.TRANSFORM,
                 "Nhóm 1", "flowCode", "trade_parser.py (ITC đang trả None)", "M -> Import, X -> Export",
                 "normalize_trade_record()", "NOT NULL, CHECK IN ('Export','Import')", "str",
                 check_constraint="trade_flow IN ('Export', 'Import')",
                 missing_invalid_handling="ITC chưa parse flow_code; thiếu -> Quarantine ERROR"),
            _col("trade_statistics", "hs_code", "VARCHAR(20)", False, MappingStatus.TRANSFORM,
                 "Nhóm 1", "cmdCode / Commodity code", "trade_parser.py", "Cắt 4 chữ số đầu Chương 69",
                 "normalize_hs_code()", "NOT NULL", "str",
                 missing_invalid_handling="Ngoài 6911/6912/6913 -> WAITING_CONFIRMATION_MEMBER_1"),
            _col("trade_statistics", "cmd_desc", "TEXT", True, MappingStatus.DIRECT,
                 "Nhóm 1", "cmdDesc / Product description", "trade_parser.py (ITC đang trả None)",
                 "Chuẩn hóa khoảng trắng NFC", "normalize_text()", "Cho phép NULL", "str",
                 missing_invalid_handling="Cho phép NULL"),
            _col("trade_statistics", "trade_value_usd", "NUMERIC(18,2)", False, MappingStatus.DIRECT,
                 "Nhóm 1", "primaryValue / Trade Value (USD)", "trade_parser.py",
                 "Ép số thực/Decimal >= 0", "normalize_number()", "NOT NULL, CHECK >= 0", "float",
                 check_constraint="trade_value_usd >= 0",
                 missing_invalid_handling="Thiếu hoặc < 0 -> Quarantine ERROR"),
            _col("trade_statistics", "fob_value_usd", "NUMERIC(18,2)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 1 (UN Comtrade raw có fobvalue)", "fobvalue", "trade_parser.py chưa trích xuất",
                 "Ép số >= 0 khi bổ sung parser", "normalize_number()", "CHECK >= 0, cho phép NULL", "float",
                 check_constraint="fob_value_usd >= 0",
                 missing_invalid_handling="Hiện để NULL (chờ trích xuất ở parser)"),
            _col("trade_statistics", "cif_value_usd", "NUMERIC(18,2)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 1 (UN Comtrade raw có cifvalue)", "cifvalue", "trade_parser.py chưa trích xuất",
                 "Ép số >= 0 khi bổ sung parser", "normalize_number()", "CHECK >= 0, cho phép NULL", "float",
                 check_constraint="cif_value_usd >= 0",
                 missing_invalid_handling="Hiện để NULL (chờ trích xuất ở parser)"),
            _col("trade_statistics", "net_weight_kg", "NUMERIC(18,2)", True, MappingStatus.DIRECT,
                 "Nhóm 1 (UN Comtrade)", "netWgt", "trade_parser.py (ITC không có)",
                 "Ép số >= 0", "normalize_number()", "CHECK >= 0, cho phép NULL", "float",
                 check_constraint="net_weight_kg >= 0",
                 missing_invalid_handling="Cho phép NULL; nếu < 0 -> Quarantine ERROR"),
            _col("trade_statistics", "qty_unit", "VARCHAR(50)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 1", None, "trade_parser.py chưa trích xuất", "Chuẩn hóa đơn vị", "normalize_unit()",
                 "Cho phép NULL", None, missing_invalid_handling="Để NULL"),
            _col("trade_statistics", "qty_amount", "NUMERIC(18,2)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 1", None, "trade_parser.py chưa trích xuất", "Ép số >= 0", "normalize_number()",
                 "CHECK >= 0, cho phép NULL", None, check_constraint="qty_amount >= 0",
                 missing_invalid_handling="Để NULL"),
            _col("trade_statistics", "market_share_pct", "NUMERIC(6,2)", True, MappingStatus.PENDING_CONFIRMATION,
                 "Derived", None, "Chưa xác định tầng tính", "Tính tỷ trọng %", "Không áp dụng",
                 "CHECK (0..100), cho phép NULL", None, check_constraint="market_share_pct BETWEEN 0 AND 100",
                 missing_invalid_handling="Để NULL đến khi Thành viên 1 chốt tầng tính"),
            _col("trade_statistics", "yoy_growth_rate", "NUMERIC(8,2)", True, MappingStatus.PENDING_CONFIRMATION,
                 "Derived", None, "Chưa xác định tầng tính", "Tính % tăng trưởng YoY", "Không áp dụng",
                 "Cho phép NULL", None, missing_invalid_handling="Để NULL đến khi Thành viên 1 chốt tầng tính"),
            _col("trade_statistics", "data_source", "VARCHAR(50)", True, MappingStatus.TRANSFORM,
                 "Nhóm 1 (Provenance)", "provenance.source_id", "trade_parser.py",
                 "un_comtrade -> 'UN Comtrade'; itc_trade_map -> 'ITC Trade Map'", "Không áp dụng",
                 "DEFAULT 'UN Comtrade'", "str", default_value="'UN Comtrade'"),
        ),
    ),
    "search_trends": TableMappingSpec(
        table_name="search_trends",
        business_purpose="Chuỗi thời gian 52 tuần Google Trends",
        primary_key="trend_id",
        foreign_keys=("country_id -> countries(country_id)", "region_id -> market_regions(region_id)", "category_id -> product_categories(category_id)"),
        unique_keys=(),
        natural_key=None,
        columns=(
            _col("search_trends", "trend_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("search_trends", "country_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 2 (Manifest Request)", "GoogleTrendsRequest.geo", "google_trends_collector.py",
                 "Lấy mã quốc gia từ manifest/request -> tra countries", "normalize_country()",
                 "NOT NULL, FK -> countries", "str", fk_target="countries(country_id)",
                 missing_invalid_handling="ParsedTrendsRow chưa mang geo; thiếu -> UNRESOLVED_FK"),
            _col("search_trends", "region_id", "INTEGER", True, MappingStatus.DEPENDENCY,
                 "Nhóm 2 (Manifest Request)", "GoogleTrendsRequest.geo (cấp bang)", "google_trends_collector.py",
                 "Nếu geo cấp bang -> tra market_regions; cấp nước -> NULL", "Không áp dụng",
                 "FK -> market_regions, cho phép NULL", "str", fk_target="market_regions(region_id)",
                 missing_invalid_handling="Cho phép NULL ở cấp quốc gia"),
            _col("search_trends", "category_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 2 (Manifest / Keyword)", "GoogleTrendsRequest.category / search_term",
                 "google_trends_collector.py / trends_parser.py",
                 "Ánh xạ sang 4 mã category -> tra product_categories", "normalize_category()",
                 "NOT NULL, FK -> product_categories", "str", fk_target="product_categories(category_id)",
                 missing_invalid_handling="Thiếu hoặc ngoài 4 dòng -> UNRESOLVED_FK"),
            _col("search_trends", "search_term", "VARCHAR(150)", False, MappingStatus.TRANSFORM,
                 "Nhóm 2 (CSV Header)", "keyword_values[i][0]", "trends_parser.py",
                 "Unpivot cột từ khóa, chuẩn hóa NFC", "normalize_text()", "NOT NULL", "str"),
            _col("search_trends", "week_start_date", "DATE", False, MappingStatus.TRANSFORM,
                 "Nhóm 2", "period_label", "trends_parser.py",
                 "Parse ISO YYYY-MM-DD -> date", "normalize_date()", "NOT NULL", "str",
                 missing_invalid_handling="Sai định dạng ngày -> Quarantine ERROR"),
            _col("search_trends", "week_number", "INTEGER", True, MappingStatus.TRANSFORM,
                 "Nhóm 2 (Derived từ week_start_date)", "period_label", "trends_parser.py",
                 "week_start_date.isocalendar().week", "Không áp dụng", "CHECK (1..53), cho phép NULL", "date",
                 check_constraint="week_number BETWEEN 1 AND 53"),
            _col("search_trends", "interest_score", "INTEGER", False, MappingStatus.TRANSFORM,
                 "Nhóm 2", "keyword_values[i][1]", "trends_parser.py",
                 "Chuyển chuỗi số -> int", "normalize_number()", "NOT NULL, CHECK (0..100)", "str",
                 check_constraint="interest_score BETWEEN 0 AND 100",
                 missing_invalid_handling="Thiếu hoặc ngoài 0..100 -> Quarantine ERROR"),
        ),
    ),
    "trending_keywords": TableMappingSpec(
        table_name="trending_keywords",
        business_purpose="Từ khóa gốm sứ thịnh hành và tốc độ tăng trưởng bứt phá",
        primary_key="keyword_id",
        foreign_keys=("country_id -> countries(country_id)", "category_id -> product_categories(category_id)"),
        unique_keys=(),
        natural_key=None,
        columns=(
            _col("trending_keywords", "keyword_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("trending_keywords", "country_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 2", "GoogleTrendsRequest.geo", "google_trends_collector.py",
                 "Tra cứu countries", "normalize_country()", "NOT NULL, FK -> countries", "str",
                 fk_target="countries(country_id)"),
            _col("trending_keywords", "category_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 2", "GoogleTrendsRequest.category", "google_trends_collector.py",
                 "Tra cứu product_categories", "normalize_category()", "NOT NULL, FK -> product_categories", "str",
                 fk_target="product_categories(category_id)"),
            _col("trending_keywords", "keyword_text", "VARCHAR(200)", False, MappingStatus.NO_SOURCE,
                 "Nhóm 2 (RELATED_QUERIES)", None, "Chưa có parser cho RELATED_QUERIES CSV",
                 "Chuẩn hóa chuỗi", "normalize_text()", "NOT NULL", "str"),
            _col("trending_keywords", "related_attribute_type", "VARCHAR(50)", True, MappingStatus.PENDING_CONFIRMATION,
                 "Nhóm 2 / AI", None, "Chưa có quy tắc phân loại thuộc tính",
                 "Phân loại vào 6 nhóm", "Không áp dụng", "CHECK IN ('style','color','material','shape','feature','general')", "str",
                 check_constraint="related_attribute_type IN ('style', 'color', 'material', 'shape', 'feature', 'general')"),
            _col("trending_keywords", "growth_pct", "NUMERIC(10,2)", False, MappingStatus.PENDING_CONFIRMATION,
                 "Nhóm 2 (RELATED_QUERIES)", None, "Chưa có parser; giá trị 'Breakout' chưa có quy ước số",
                 "Chuyển % hoặc Breakout", "normalize_number()", "NOT NULL", "str"),
            _col("trending_keywords", "trend_classification", "VARCHAR(50)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 2 (RELATED_QUERIES)", None, "Chưa có parser", "Breakout/Rising/Top", "Không áp dụng",
                 "DEFAULT 'Rising', CHECK IN ('Breakout','Rising','Top')", "str", default_value="'Rising'"),
            _col("trending_keywords", "recorded_period", "VARCHAR(50)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 2 (Manifest)", "period_start..period_end", "google_trends_collector.py",
                 "Ghi nhận kỳ khảo sát", "normalize_text()", "DEFAULT 'Last 12 Months'", "str",
                 default_value="'Last 12 Months'"),
        ),
    ),
    "market_products": TableMappingSpec(
        table_name="market_products",
        business_purpose="Sản phẩm gốm sứ quốc tế trên Etsy, Amazon",
        primary_key="market_product_id",
        foreign_keys=("target_country_id -> countries(country_id)", "category_id -> product_categories(category_id)"),
        unique_keys=("external_sku",),
        natural_key="external_sku (Etsy listing_id / Amazon ASIN)",
        columns=(
            _col("market_products", "market_product_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("market_products", "external_sku", "VARCHAR(100)", True, MappingStatus.DIRECT,
                 "Nhóm 3 (Etsy / Amazon)", "source_product_id (listing_id / asin)", "marketplace_parser.py",
                 "Giữ nguyên chuỗi ID sàn", "normalize_text()", "UNIQUE (cho phép NULL trong DDL)", "str",
                 is_unique=True, is_natural_key=True),
            _col("market_products", "platform_source", "VARCHAR(50)", False, MappingStatus.TRANSFORM,
                 "Nhóm 3 (Provenance)", "provenance.source_id", "marketplace_parser.py",
                 "etsy -> 'Etsy'; amazon -> 'Amazon'", "Không áp dụng", "NOT NULL", "str"),
            _col("market_products", "target_country_id", "INTEGER", False, MappingStatus.PENDING_CONFIRMATION,
                 "Nhóm 3", None, "Etsy/Amazon parser chưa có trường quốc gia mục tiêu",
                 "Tra cứu countries theo thị trường truy vấn", "normalize_country()",
                 "NOT NULL, FK -> countries", None, fk_target="countries(country_id)",
                 missing_invalid_handling="Cần Thành viên 1 xác nhận quy tắc gán thị trường mục tiêu"),
            _col("market_products", "category_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 3", "category / category_id (taxonomy_id)", "marketplace_parser.py",
                 "Amazon dùng normalize_category(); Etsy mới có taxonomy_id cần bảng map",
                 "normalize_category()", "NOT NULL, FK -> product_categories", "str",
                 fk_target="product_categories(category_id)",
                 missing_invalid_handling="Thiếu/chưa map -> Quarantine / UNRESOLVED_FK"),
            _col("market_products", "product_name", "VARCHAR(300)", False, MappingStatus.DIRECT,
                 "Nhóm 3", "name (title / displayValue)", "marketplace_parser.py",
                 "Chuẩn hóa khoảng trắng NFC", "normalize_text()", "NOT NULL", "str",
                 missing_invalid_handling="Thiếu -> Quarantine ERROR"),
            _col("market_products", "price_usd", "NUMERIC(10,2)", False, MappingStatus.TRANSFORM,
                 "Nhóm 3", "prices[0].amount_str + currency_code", "marketplace_parser.py",
                 "Nếu USD dùng trực tiếp; ngoại tệ khác cần tỷ giá xác nhận", "normalize_currency()",
                 "NOT NULL, CHECK >= 0", "str", check_constraint="price_usd >= 0",
                 missing_invalid_handling="Thiếu giá hoặc thiếu tỷ giá quy đổi -> Quarantine / PENDING_CONFIRMATION"),
            _col("market_products", "price_segment", "VARCHAR(50)", True, MappingStatus.PENDING_CONFIRMATION,
                 "Derived từ price_usd", None, "Chưa triển khai ở D11",
                 "<20 Budget; 20-60 Mid-range; >60 Premium", "Không áp dụng", "Cho phép NULL", "Decimal"),
            _col("market_products", "color", "VARCHAR(100)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa trích xuất", "normalize_text()", "Cho phép NULL", None),
            _col("market_products", "shape", "VARCHAR(100)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa trích xuất", "normalize_text()", "Cho phép NULL", None),
            _col("market_products", "material", "VARCHAR(100)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa trích xuất", "normalize_text()", "Cho phép NULL", None),
            _col("market_products", "style", "VARCHAR(100)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa trích xuất", "normalize_text()", "Cho phép NULL", None),
            _col("market_products", "is_dishwasher_safe", "BOOLEAN", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa trích xuất", "Không áp dụng",
                 "DEFAULT FALSE", None, default_value="FALSE"),
            _col("market_products", "is_microwave_safe", "BOOLEAN", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa trích xuất", "Không áp dụng",
                 "DEFAULT FALSE", None, default_value="FALSE"),
            _col("market_products", "avg_rating", "NUMERIC(3,2)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa thu thập", "normalize_number()",
                 "CHECK (0..5), cho phép NULL", None, check_constraint="avg_rating BETWEEN 0 AND 5"),
            _col("market_products", "review_count", "INTEGER", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa thu thập", "normalize_number()",
                 "DEFAULT 0, CHECK >= 0", None, default_value="0", check_constraint="review_count >= 0"),
            _col("market_products", "image_url", "TEXT", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3", None, "Chưa có trong ParsedProductRecord", "Chưa thu thập", "normalize_text()", "Cho phép NULL", None),
            _col("market_products", "product_url", "TEXT", True, MappingStatus.DIRECT,
                 "Nhóm 3", "product_url (url / detailPageURL)", "marketplace_parser.py",
                 "Chuẩn hóa chuỗi", "normalize_text()", "Cho phép NULL", "str"),
        ),
    ),
    "customers": TableMappingSpec(
        table_name="customers",
        business_purpose="Thông tin khách hàng / người đánh giá trên Etsy, Amazon",
        primary_key="customer_id",
        foreign_keys=("country_id -> countries(country_id)",),
        unique_keys=(),
        natural_key=None,
        columns=(
            _col("customers", "customer_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("customers", "external_reviewer_id", "VARCHAR(100)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3 (Reviews)", None, "EtsyReviewCollector/Parser không có reviewer ID",
                 "Không có", "normalize_text()", "Cho phép NULL", None),
            _col("customers", "reviewer_name", "VARCHAR(150)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3 (Reviews)", None, "Etsy API không trả reviewer_name",
                 "Không có", "normalize_text()", "Cho phép NULL", None),
            _col("customers", "country_id", "INTEGER", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3 (Reviews)", None, "Etsy API không trả quốc gia người mua",
                 "Không có", "normalize_country()", "FK -> countries, cho phép NULL", None,
                 fk_target="countries(country_id)"),
            _col("customers", "platform_source", "VARCHAR(50)", False, MappingStatus.NO_SOURCE,
                 "Nhóm 3 (Reviews)", "provenance.source_id", "Chưa có bản ghi customer từ Etsy",
                 "Không tạo bản ghi giả", "Không áp dụng", "NOT NULL", "str"),
            _col("customers", "verified_purchase", "BOOLEAN", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3 (Reviews)", None, "Etsy API không cung cấp", "Không có", "Không áp dụng",
                 "DEFAULT TRUE", None, default_value="TRUE"),
        ),
    ),
    "product_reviews": TableMappingSpec(
        table_name="product_reviews",
        business_purpose="Đánh giá sản phẩm 1–5 sao & phân loại cảm xúc AI/NLP",
        primary_key="review_id",
        foreign_keys=("market_product_id -> market_products(market_product_id)", "customer_id -> customers(customer_id)"),
        unique_keys=(),
        natural_key=None,
        columns=(
            _col("product_reviews", "review_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("product_reviews", "market_product_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 3 (Etsy Reviews)", "product_reference (listing_id)", "review_parser.py",
                 "Tra cứu market_products.market_product_id theo external_sku", "normalize_text()",
                 "NOT NULL, FK -> market_products", "str", fk_target="market_products(market_product_id)",
                 missing_invalid_handling="Không tìm thấy market_product -> UNRESOLVED_FK"),
            _col("product_reviews", "customer_id", "INTEGER", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3 (Etsy Reviews)", None, "Chưa có bảng customers từ Etsy",
                 "Để NULL", "Không áp dụng", "FK -> customers, cho phép NULL", None,
                 fk_target="customers(customer_id)"),
            _col("product_reviews", "rating_stars", "INTEGER", False, MappingStatus.DIRECT,
                 "Nhóm 3 (Etsy Reviews)", "rating", "review_parser.py",
                 "Số nguyên 1..5", "normalize_review_record()", "NOT NULL, CHECK (1..5)", "int",
                 check_constraint="rating_stars BETWEEN 1 AND 5"),
            _col("product_reviews", "review_title", "VARCHAR(250)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 3 (Etsy Reviews)", None, "Etsy API không có tiêu đề review",
                 "Để NULL", "normalize_text()", "Cho phép NULL", None),
            _col("product_reviews", "review_text", "TEXT", False, MappingStatus.DIRECT,
                 "Nhóm 3 (Etsy Reviews)", "review", "review_parser.py",
                 "Chuẩn hóa khoảng trắng NFC", "normalize_text()", "NOT NULL", "str",
                 missing_invalid_handling="Etsy có thể trả null -> chặn/Quarantine khi nạp vào cột NOT NULL"),
            _col("product_reviews", "review_date", "DATE", True, MappingStatus.TRANSFORM,
                 "Nhóm 3 (Etsy Reviews)", "reviewed_at_iso", "review_parser.py",
                 "Cắt phần ngày YYYY-MM-DD từ ISO-8601", "normalize_date()", "Cho phép NULL", "str"),
            _col("product_reviews", "sentiment_label", "VARCHAR(20)", True, MappingStatus.NOT_APPLICABLE,
                 "AI/NLP (Thành viên 3)", None, "Ngoài phạm vi ETL D5–D13",
                 "Do mô hình AI/NLP cập nhật", "Không áp dụng", "CHECK IN ('Positive','Neutral','Negative')", None,
                 check_constraint="sentiment_label IN ('Positive', 'Neutral', 'Negative')"),
            _col("product_reviews", "sentiment_score", "NUMERIC(5,4)", True, MappingStatus.NOT_APPLICABLE,
                 "AI/NLP (Thành viên 3)", None, "Ngoài phạm vi ETL D5–D13",
                 "Do mô hình AI/NLP cập nhật", "Không áp dụng", "CHECK (0..1)", None,
                 check_constraint="sentiment_score BETWEEN 0 AND 1"),
        ),
    ),
    "review_aspects": TableMappingSpec(
        table_name="review_aspects",
        business_purpose="Khía cạnh khen/chê trích xuất bằng AI/NLP",
        primary_key="aspect_id",
        foreign_keys=("review_id -> product_reviews(review_id)",),
        unique_keys=(),
        natural_key=None,
        columns=(
            _col("review_aspects", "aspect_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("review_aspects", "review_id", "INTEGER", False, MappingStatus.NOT_APPLICABLE,
                 "AI/NLP (Thành viên 3)", None, "Ngoài phạm vi ETL D5–D13", "FK -> product_reviews", "Không áp dụng",
                 "NOT NULL, FK", None, fk_target="product_reviews(review_id)"),
            _col("review_aspects", "aspect_category", "VARCHAR(100)", False, MappingStatus.NOT_APPLICABLE,
                 "AI/NLP (Thành viên 3)", None, "Ngoài phạm vi ETL D5–D13", "Không áp dụng", "Không áp dụng", "NOT NULL", None),
            _col("review_aspects", "aspect_sentiment", "VARCHAR(20)", False, MappingStatus.NOT_APPLICABLE,
                 "AI/NLP (Thành viên 3)", None, "Ngoài phạm vi ETL D5–D13", "Không áp dụng", "Không áp dụng",
                 "NOT NULL, CHECK IN ('Positive','Neutral','Negative')", None),
            _col("review_aspects", "extracted_phrase", "VARCHAR(250)", True, MappingStatus.NOT_APPLICABLE,
                 "AI/NLP (Thành viên 3)", None, "Ngoài phạm vi ETL D5–D13", "Không áp dụng", "Không áp dụng", "Cho phép NULL", None),
        ),
    ),
    "suppliers": TableMappingSpec(
        table_name="suppliers",
        business_purpose="Hồ sơ năng lực nhà cung cấp nội địa (Minh Long 1, Bát Tràng...)",
        primary_key="supplier_id",
        foreign_keys=(),
        unique_keys=("supplier_code",),
        natural_key="supplier_code",
        columns=(
            _col("suppliers", "supplier_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("suppliers", "supplier_code", "VARCHAR(50)", False, MappingStatus.PENDING_CONFIRMATION,
                 "Nhóm 4 (Domestic)", "source_id (cần quy ước mã)", "domestic_parser.py chưa có supplier_code",
                 "Ánh xạ source_id -> mã NCC chuẩn", "normalize_text()", "NOT NULL, UNIQUE", "str",
                 is_unique=True, is_natural_key=True),
            _col("suppliers", "supplier_name", "VARCHAR(200)", False, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "supplier.supplier_name", "domestic_parser.py",
                 "Chuẩn hóa chuỗi NFC", "normalize_text()", "NOT NULL", "str",
                 missing_invalid_handling="Một số payload (minh_long_1, goc_gom_viet) có supplier=null -> cần seed hồ sơ chuẩn"),
            _col("suppliers", "address", "TEXT", False, MappingStatus.TRANSFORM,
                 "Nhóm 4 (Domestic)", "supplier.address + supplier.province", "domestic_parser.py",
                 "Ghép address và province nếu có", "normalize_text()", "NOT NULL", "str",
                 missing_invalid_handling="Thiếu khi supplier=null -> cần seed"),
            _col("suppliers", "hotline", "VARCHAR(50)", True, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "supplier.phone", "domestic_parser.py",
                 "Chuẩn hóa chuỗi", "normalize_text()", "Cho phép NULL", "str"),
            _col("suppliers", "website_url", "VARCHAR(250)", True, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "supplier.website", "domestic_parser.py",
                 "Chuẩn hóa chuỗi", "normalize_text()", "Cho phép NULL", "str"),
            _col("suppliers", "specialization", "VARCHAR(250)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 4 (Domestic)", None, "D9 không có trường specialization",
                 "Để NULL hoặc lấy từ seed", "normalize_text()", "Cho phép NULL", None),
            _col("suppliers", "min_monthly_capacity", "INTEGER", False, MappingStatus.NO_SOURCE,
                 "Nhóm 4 (Domestic)", None, "D9 chỉ có declared_capacity_note text",
                 "Không tự suy diễn", "Không áp dụng", "NOT NULL, CHECK >= 0", None,
                 check_constraint="min_monthly_capacity >= 0",
                 missing_invalid_handling="Thiếu -> cần hồ sơ chuẩn từ Thành viên 1"),
            _col("suppliers", "max_monthly_capacity", "INTEGER", False, MappingStatus.NO_SOURCE,
                 "Nhóm 4 (Domestic)", None, "D9 chỉ có declared_capacity_note text",
                 "Không tự suy diễn", "Không áp dụng", "NOT NULL, CHECK >= min", None,
                 missing_invalid_handling="Thiếu -> cần hồ sơ chuẩn từ Thành viên 1"),
            _col("suppliers", "avg_lead_time_days", "INTEGER", False, MappingStatus.NO_SOURCE,
                 "Nhóm 4 (Domestic)", None, "D9 không có ở cấp supplier",
                 "Không tự suy diễn", "Không áp dụng", "NOT NULL, CHECK > 0", None,
                 check_constraint="avg_lead_time_days > 0",
                 missing_invalid_handling="Thiếu -> cần hồ sơ chuẩn từ Thành viên 1"),
            _col("suppliers", "total_catalog_items", "INTEGER", True, MappingStatus.NOT_APPLICABLE,
                 "Derived / DB Default", None, "Tính tổng từ supplier_products", "COUNT hoặc DEFAULT 0",
                 "Không áp dụng", "DEFAULT 0, CHECK >= 0", None, default_value="0"),
            _col("suppliers", "reliability_rating", "NUMERIC(3,2)", True, MappingStatus.NOT_APPLICABLE,
                 "DB Default / Nội bộ", None, "Đánh giá nội bộ", "DEFAULT 4.50", "Không áp dụng",
                 "DEFAULT 4.50, CHECK (0..5)", None, default_value="4.50"),
        ),
    ),
    "supplier_products": TableMappingSpec(
        table_name="supplier_products",
        business_purpose="Danh mục 341 sản phẩm gốm sứ nội địa",
        primary_key="supplier_product_id",
        foreign_keys=("supplier_id -> suppliers(supplier_id)", "category_id -> product_categories(category_id)"),
        unique_keys=("product_code",),
        natural_key="product_code (source_product_id)",
        columns=(
            _col("supplier_products", "supplier_product_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("supplier_products", "supplier_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 4 (Domestic)", "provenance.source_id / supplier_code", "domestic_parser.py",
                 "Tra cứu suppliers.supplier_id", "Không áp dụng", "NOT NULL, FK -> suppliers", "str",
                 fk_target="suppliers(supplier_id)"),
            _col("supplier_products", "category_id", "INTEGER", False, MappingStatus.DEPENDENCY,
                 "Nhóm 4 (Domestic)", "category", "domestic_parser.py",
                 "normalize_category() -> tra product_categories", "normalize_category()",
                 "NOT NULL, FK -> product_categories", "str", fk_target="product_categories(category_id)"),
            _col("supplier_products", "product_code", "VARCHAR(100)", True, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "source_product_id", "domestic_parser.py",
                 "Chuẩn hóa chuỗi", "normalize_text()", "UNIQUE (cho phép NULL trong DDL)", "str",
                 is_unique=True, is_natural_key=True),
            _col("supplier_products", "product_name", "VARCHAR(300)", False, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "name", "domestic_parser.py",
                 "Chuẩn hóa chuỗi NFC", "normalize_text()", "NOT NULL", "str"),
            _col("supplier_products", "price_vnd", "NUMERIC(14,2)", False, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "commercial.price_vnd_str", "domestic_parser.py",
                 "Decimal >= 0", "normalize_number(as_decimal=True)", "NOT NULL, CHECK >= 0", "str",
                 check_constraint="price_vnd >= 0",
                 missing_invalid_handling="Thiếu (VD: minh_long_1 fixture) -> Quarantine ERROR"),
            _col("supplier_products", "price_usd_equiv", "NUMERIC(10,2)", True, MappingStatus.PENDING_CONFIRMATION,
                 "Nhóm 4 (Derived từ price_vnd)", "commercial.price_vnd_str", "normalizer.py (normalize_currency)",
                 "Chưa quy đổi vì thiếu tỷ giá VND/USD xác nhận", "normalize_currency()",
                 "CHECK >= 0, cho phép NULL", "Decimal", check_constraint="price_usd_equiv >= 0"),
            _col("supplier_products", "color", "VARCHAR(100)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 4", None, "Chưa có trong ParsedDomesticProductRecord", "Chưa trích xuất", "normalize_text()", "Cho phép NULL", None),
            _col("supplier_products", "shape", "VARCHAR(100)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 4", None, "Chưa có trong ParsedDomesticProductRecord", "Chưa trích xuất", "normalize_text()", "Cho phép NULL", None),
            _col("supplier_products", "material", "VARCHAR(100)", True, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "material", "domestic_parser.py",
                 "Chuẩn hóa chuỗi NFC", "normalize_text()", "Cho phép NULL", "str"),
            _col("supplier_products", "style", "VARCHAR(100)", True, MappingStatus.NO_SOURCE,
                 "Nhóm 4", None, "Chưa có trong ParsedDomesticProductRecord", "Chưa trích xuất", "normalize_text()", "Cho phép NULL", None),
            _col("supplier_products", "is_dishwasher_safe", "BOOLEAN", True, MappingStatus.NO_SOURCE,
                 "Nhóm 4", None, "Chưa có trong ParsedDomesticProductRecord", "Dùng DEFAULT TRUE hoặc để NULL", "Không áp dụng",
                 "DEFAULT TRUE", None, default_value="TRUE"),
            _col("supplier_products", "is_heat_resistant", "BOOLEAN", True, MappingStatus.NO_SOURCE,
                 "Nhóm 4", None, "Chưa có trong ParsedDomesticProductRecord", "Dùng DEFAULT TRUE hoặc để NULL", "Không áp dụng",
                 "DEFAULT TRUE", None, default_value="TRUE"),
            _col("supplier_products", "min_order_qty", "INTEGER", True, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "commercial.moq", "domestic_parser.py",
                 "Int > 0; nếu NULL dùng DEFAULT 100 của DB", "normalize_number()",
                 "DEFAULT 100, CHECK > 0", "int", default_value="100", check_constraint="min_order_qty > 0"),
            _col("supplier_products", "image_url", "TEXT", True, MappingStatus.NO_SOURCE,
                 "Nhóm 4", None, "Chưa có trong ParsedDomesticProductRecord", "Để NULL", "normalize_text()", "Cho phép NULL", None),
            _col("supplier_products", "product_url", "TEXT", True, MappingStatus.DIRECT,
                 "Nhóm 4 (Domestic)", "product_url", "domestic_parser.py",
                 "Chuẩn hóa chuỗi", "normalize_text()", "Cho phép NULL", "str"),
        ),
    ),
    "order_recommendations": TableMappingSpec(
        table_name="order_recommendations",
        business_purpose="Kết quả đối chiếu cung–cầu và đề xuất đặt hàng xuất khẩu (DSS)",
        primary_key="recommendation_id",
        foreign_keys=("target_country_id -> countries(country_id)", "supplier_product_id -> supplier_products(supplier_product_id)", "supplier_id -> suppliers(supplier_id)"),
        unique_keys=(),
        natural_key=None,
        columns=(
            _col("order_recommendations", "recommendation_id", "SERIAL", False, MappingStatus.NOT_APPLICABLE,
                 "DB", None, "PostgreSQL", "DB tự sinh SERIAL", "Không áp dụng", "PK", None, is_pk=True),
            _col("order_recommendations", "target_country_id", "INTEGER", False, MappingStatus.NOT_APPLICABLE,
                 "DSS (Thành viên 1 / 4)", None, "Ngoài phạm vi ETL D5–D13", "FK -> countries", "Không áp dụng", "NOT NULL, FK", None, fk_target="countries(country_id)"),
            _col("order_recommendations", "supplier_product_id", "INTEGER", False, MappingStatus.NOT_APPLICABLE,
                 "DSS (Thành viên 1 / 4)", None, "Ngoài phạm vi ETL D5–D13", "FK -> supplier_products", "Không áp dụng", "NOT NULL, FK", None, fk_target="supplier_products(supplier_product_id)"),
            _col("order_recommendations", "supplier_id", "INTEGER", False, MappingStatus.NOT_APPLICABLE,
                 "DSS (Thành viên 1 / 4)", None, "Ngoài phạm vi ETL D5–D13", "FK -> suppliers", "Không áp dụng", "NOT NULL, FK", None, fk_target="suppliers(supplier_id)"),
            _col("order_recommendations", "attribute_match_score", "NUMERIC(5,2)", True, MappingStatus.NOT_APPLICABLE,
                 "DSS", None, "Ngoài phạm vi ETL", "Thuật toán Matching", "Không áp dụng", "CHECK (0..100)", None),
            _col("order_recommendations", "market_demand_score", "NUMERIC(5,2)", True, MappingStatus.NOT_APPLICABLE,
                 "DSS", None, "Ngoài phạm vi ETL", "Thuật toán Matching", "Không áp dụng", "CHECK (0..100)", None),
            _col("order_recommendations", "estimated_margin_pct", "NUMERIC(6,2)", True, MappingStatus.NOT_APPLICABLE,
                 "DSS", None, "Ngoài phạm vi ETL", "Thuật toán Matching", "Không áp dụng", "Cho phép NULL", None),
            _col("order_recommendations", "overall_matching_score", "NUMERIC(5,2)", False, MappingStatus.NOT_APPLICABLE,
                 "DSS", None, "Ngoài phạm vi ETL", "Thuật toán Matching", "Không áp dụng", "NOT NULL, CHECK (0..100)", None),
            _col("order_recommendations", "recommended_order_qty", "INTEGER", False, MappingStatus.NOT_APPLICABLE,
                 "DSS", None, "Ngoài phạm vi ETL", "Thuật toán Matching", "Không áp dụng", "NOT NULL, CHECK > 0", None),
            _col("order_recommendations", "estimated_total_cost_vnd", "NUMERIC(18,2)", True, MappingStatus.NOT_APPLICABLE,
                 "DSS", None, "Ngoài phạm vi ETL", "Thuật toán Matching", "Không áp dụng", "CHECK >= 0", None),
            _col("order_recommendations", "quality_packaging_notes", "TEXT", True, MappingStatus.NOT_APPLICABLE,
                 "DSS + AI/NLP", None, "Ngoài phạm vi ETL", "Tổng hợp từ review_aspects", "Không áp dụng", "Cho phép NULL", None),
            _col("order_recommendations", "created_at", "TIMESTAMP", True, MappingStatus.NOT_APPLICABLE,
                 "DB Default", None, "PostgreSQL", "DEFAULT CURRENT_TIMESTAMP", "Không áp dụng", "DEFAULT CURRENT_TIMESTAMP", None, default_value="CURRENT_TIMESTAMP"),
        ),
    ),
}


# ---------------------------------------------------------------------------
# In-memory Reference Lookup (no database connection)
# ---------------------------------------------------------------------------


@dataclass
class ReferenceLookup:
    """In-memory reference ID lookup simulating pre-loaded OLTP reference tables."""

    countries_by_code: Dict[str, int] = field(default_factory=dict)
    market_regions_by_key: Dict[Tuple[int, str], int] = field(default_factory=dict)
    categories_by_code: Dict[str, int] = field(default_factory=dict)
    suppliers_by_code: Dict[str, int] = field(default_factory=dict)
    market_products_by_sku: Dict[str, int] = field(default_factory=dict)

    def resolve_country(self, raw_country: Any) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """Normalize country code and resolve country_id without inventing IDs."""
        norm = normalize_country(raw_country)
        if norm.status != NormalizationStatus.CONFIRMED or norm.value is None:
            return None, norm.value, norm.note or "Country not confirmed"
        cid = self.countries_by_code.get(norm.value)
        if cid is None:
            return None, norm.value, f"Country code '{norm.value}' not found in reference lookup"
        return cid, norm.value, None

    def resolve_category(self, raw_category: Any) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """Normalize category code and resolve category_id without inventing IDs."""
        norm = normalize_category(raw_category)
        if norm.status != NormalizationStatus.CONFIRMED or norm.value is None:
            return None, norm.value, norm.note or "Category not confirmed"
        cat_id = self.categories_by_code.get(norm.value)
        if cat_id is None:
            return None, norm.value, f"Category code '{norm.value}' not found in reference lookup"
        return cat_id, norm.value, None


# ---------------------------------------------------------------------------
# Mapped Record Output Structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MappingIssue:
    """Structured issue detected during Source-to-Target mapping."""

    column: str
    kind: MappingIssueKind
    message: str


@dataclass(frozen=True)
class MappedField:
    """Mapping outcome for one target column."""

    target_column: str
    value: Any
    status: MappingStatus
    source_field: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class MappedRecordResult:
    """Complete mapping result for one target OLTP record."""

    target_table: str
    is_mappable: bool
    fields: Dict[str, MappedField]
    record_dict: Dict[str, Any]
    issues: Tuple[MappingIssue, ...]
    validation_result: Optional[RecordValidationResult] = None


def _finalize_mapped_record(
    table_name: str,
    fields: Dict[str, MappedField],
    issues: List[MappingIssue],
    validation_result: Optional[RecordValidationResult] = None,
) -> MappedRecordResult:
    spec = OLTP_TABLE_SPECS[table_name]
    for col_spec in spec.columns:
        if col_spec.is_pk or col_spec.default_value is not None:
            continue
        if not col_spec.nullable:
            mf = fields.get(col_spec.target_column)
            if mf is None or mf.value is None:
                if not any(i.column == col_spec.target_column for i in issues):
                    issues.append(
                        MappingIssue(
                            column=col_spec.target_column,
                            kind=MappingIssueKind.MISSING_NOT_NULL,
                            message=f"Cột bắt buộc NOT NULL '{table_name}.{col_spec.target_column}' không có giá trị hợp lệ",
                        )
                    )

    record_dict = {
        col: mf.value
        for col, mf in fields.items()
        if mf.status != MappingStatus.NOT_APPLICABLE or mf.value is not None
    }
    is_mappable = len(issues) == 0
    return MappedRecordResult(
        target_table=table_name,
        is_mappable=is_mappable,
        fields=fields,
        record_dict=record_dict,
        issues=tuple(issues),
        validation_result=validation_result,
    )


# ---------------------------------------------------------------------------
# Concrete Mappers (D5–D13 -> OLTP Tables)
# ---------------------------------------------------------------------------


def map_trade_record(
    record: Union[NormalizedTradeRecord, ParsedTradeRecord],
    lookup: ReferenceLookup,
) -> MappedRecordResult:
    """Map D5/D10/D11 trade record into OLTP ``trade_statistics``."""
    norm = normalize_trade_record(record) if isinstance(record, ParsedTradeRecord) else record
    val_res = DataQualityValidator.validate_trade_record(norm)
    issues: List[MappingIssue] = []

    for err in val_res.errors:
        issues.append(MappingIssue(err.field_name, MappingIssueKind.VALIDATION_ERROR, err.message))

    # FK lookups
    rep_id, rep_code, rep_err = lookup.resolve_country(norm.reporter_country.raw)
    if rep_id is None:
        issues.append(MappingIssue("reporter_country_id", MappingIssueKind.UNRESOLVED_FK, rep_err or "Unresolved reporter country"))

    part_id, part_code, part_err = lookup.resolve_country(norm.partner_country.raw)
    if part_id is None:
        issues.append(MappingIssue("partner_country_id", MappingIssueKind.UNRESOLVED_FK, part_err or "Unresolved partner country"))

    # Year integer conversion
    year_int: Optional[int] = None
    if norm.period.status == NormalizationStatus.CONFIRMED and norm.period.value:
        try:
            year_int = int(str(norm.period.value)[:4])
            if not (2000 <= year_int <= 2100):
                issues.append(MappingIssue("year", MappingIssueKind.VALIDATION_ERROR, f"Year {year_int} out of 2000..2100"))
                year_int = None
        except ValueError:
            issues.append(MappingIssue("year", MappingIssueKind.INVALID_TYPE, f"Cannot convert period '{norm.period.value}' to int"))

    # Data source label
    src_id = norm.provenance.source_id
    data_source_map = {"un_comtrade": "UN Comtrade", "itc_trade_map": "ITC Trade Map"}
    data_source = data_source_map.get(src_id, src_id)

    trade_val = Decimal(str(norm.trade_value_usd.value)).quantize(Decimal("0.01")) if norm.trade_value_usd.value is not None else None
    net_wgt = Decimal(str(norm.net_weight_kg.value)).quantize(Decimal("0.01")) if norm.net_weight_kg.value is not None else None

    fields: Dict[str, MappedField] = {
        "trade_id": MappedField("trade_id", None, MappingStatus.NOT_APPLICABLE, note="DB SERIAL"),
        "reporter_country_id": MappedField("reporter_country_id", rep_id, MappingStatus.DEPENDENCY, "reporter_country", f"code={rep_code}"),
        "partner_country_id": MappedField("partner_country_id", part_id, MappingStatus.DEPENDENCY, "partner_country", f"code={part_code}"),
        "year": MappedField("year", year_int, MappingStatus.TRANSFORM, "period"),
        "trade_flow": MappedField("trade_flow", norm.flow_code.value, MappingStatus.TRANSFORM, "flow_code"),
        "hs_code": MappedField("hs_code", norm.hs_code.value, MappingStatus.TRANSFORM, "hs_code"),
        "cmd_desc": MappedField("cmd_desc", norm.product_description.value, MappingStatus.DIRECT, "product_description"),
        "trade_value_usd": MappedField("trade_value_usd", trade_val, MappingStatus.DIRECT, "trade_value_usd"),
        "fob_value_usd": MappedField("fob_value_usd", None, MappingStatus.NO_SOURCE, None, "UN Comtrade parser chưa trích xuất fobvalue"),
        "cif_value_usd": MappedField("cif_value_usd", None, MappingStatus.NO_SOURCE, None, "UN Comtrade parser chưa trích xuất cifvalue"),
        "net_weight_kg": MappedField("net_weight_kg", net_wgt, MappingStatus.DIRECT, "net_weight_kg"),
        "qty_unit": MappedField("qty_unit", None, MappingStatus.NO_SOURCE),
        "qty_amount": MappedField("qty_amount", None, MappingStatus.NO_SOURCE),
        "market_share_pct": MappedField("market_share_pct", None, MappingStatus.PENDING_CONFIRMATION, note="Derived KPI"),
        "yoy_growth_rate": MappedField("yoy_growth_rate", None, MappingStatus.PENDING_CONFIRMATION, note="Derived KPI"),
        "data_source": MappedField("data_source", data_source, MappingStatus.TRANSFORM, "provenance.source_id"),
    }
    return _finalize_mapped_record("trade_statistics", fields, issues, val_res)


def map_search_trend_row(
    row: Union[NormalizedTrendsRow, ParsedTrendsRow],
    lookup: ReferenceLookup,
    *,
    country_code: Optional[str] = None,
    region_code: Optional[str] = None,
    category_code: Optional[str] = None,
) -> List[MappedRecordResult]:
    """Unpivot and map one D6/D10/D11 Google Trends row into ``search_trends`` records."""
    norm = normalize_trends_row(row) if isinstance(row, ParsedTrendsRow) else row
    val_res = DataQualityValidator.validate_trends_row(norm)
    results: List[MappedRecordResult] = []

    # Parse week_start_date and week_number
    week_date: Optional[date] = None
    week_num: Optional[int] = None
    if norm.period_label.status == NormalizationStatus.CONFIRMED and norm.period_label.value:
        try:
            week_date = date.fromisoformat(str(norm.period_label.value)[:10])
            week_num = week_date.isocalendar().week
        except ValueError:
            week_date = None

    cid, norm_cc, c_err = lookup.resolve_country(country_code) if country_code else (None, None, "Missing country_code from request metadata")
    reg_id: Optional[int] = None
    if cid is not None and region_code:
        reg_id = lookup.market_regions_by_key.get((cid, region_code.upper()))
    cat_id, norm_cat, cat_err = lookup.resolve_category(category_code) if category_code else (None, None, "Missing category_code from request metadata")

    for kw, score_field in norm.keyword_scores:
        issues: List[MappingIssue] = []
        for err in val_res.errors:
            if err.field_name == "week_start_date" or err.field_name == f"interest_score[{kw}]":
                issues.append(MappingIssue(err.field_name, MappingIssueKind.VALIDATION_ERROR, err.message))

        if cid is None:
            issues.append(MappingIssue("country_id", MappingIssueKind.UNRESOLVED_FK, c_err or "Unresolved country_id"))
        if region_code and reg_id is None:
            issues.append(MappingIssue("region_id", MappingIssueKind.UNRESOLVED_FK, f"Region '{region_code}' not found for country_id={cid}"))
        if cat_id is None:
            issues.append(MappingIssue("category_id", MappingIssueKind.UNRESOLVED_FK, cat_err or "Unresolved category_id"))
        if week_date is None:
            issues.append(MappingIssue("week_start_date", MappingIssueKind.INVALID_TYPE, f"Invalid week_start_date: {norm.period_label.raw}"))

        score_int: Optional[int] = None
        if score_field.value is not None:
            score_int = int(round(score_field.value))
            if not (0 <= score_int <= 100):
                issues.append(MappingIssue("interest_score", MappingIssueKind.VALIDATION_ERROR, f"interest_score {score_int} out of 0..100"))
                score_int = None

        term_norm = normalize_text(kw)
        fields: Dict[str, MappedField] = {
            "trend_id": MappedField("trend_id", None, MappingStatus.NOT_APPLICABLE, note="DB SERIAL"),
            "country_id": MappedField("country_id", cid, MappingStatus.DEPENDENCY, "GoogleTrendsRequest.geo", f"code={norm_cc}"),
            "region_id": MappedField("region_id", reg_id, MappingStatus.DEPENDENCY, "GoogleTrendsRequest.geo"),
            "category_id": MappedField("category_id", cat_id, MappingStatus.DEPENDENCY, "GoogleTrendsRequest.category", f"code={norm_cat}"),
            "search_term": MappedField("search_term", term_norm.value, MappingStatus.TRANSFORM, "keyword_column"),
            "week_start_date": MappedField("week_start_date", week_date, MappingStatus.TRANSFORM, "period_label"),
            "week_number": MappedField("week_number", week_num, MappingStatus.TRANSFORM, "period_label"),
            "interest_score": MappedField("interest_score", score_int, MappingStatus.TRANSFORM, f"keyword_scores[{kw}]"),
        }
        results.append(_finalize_mapped_record("search_trends", fields, issues, val_res))

    return results


def map_market_product_record(
    record: Union[NormalizedProductRecord, ParsedProductRecord],
    lookup: ReferenceLookup,
    *,
    target_country_code: Optional[str] = None,
    category_code_override: Optional[str] = None,
) -> MappedRecordResult:
    """Map D7/D10/D11 marketplace product into OLTP ``market_products``."""
    norm = normalize_product_record(record) if isinstance(record, ParsedProductRecord) else record
    val_res = DataQualityValidator.validate_product_record(norm)
    issues: List[MappingIssue] = []

    for err in val_res.errors:
        # If category_code_override is supplied (e.g. Etsy taxonomy mapping), skip missing category error from raw
        if err.field_name == "category" and category_code_override:
            continue
        issues.append(MappingIssue(err.field_name, MappingIssueKind.VALIDATION_ERROR, err.message))

    # target_country_id (NOT NULL in DDL, absent in D7 API payload)
    if target_country_code:
        cid, norm_cc, c_err = lookup.resolve_country(target_country_code)
        if cid is None:
            issues.append(MappingIssue("target_country_id", MappingIssueKind.UNRESOLVED_FK, c_err or "Unresolved target_country_id"))
        country_status = MappingStatus.DEPENDENCY
    else:
        cid, norm_cc = None, None
        issues.append(MappingIssue("target_country_id", MappingIssueKind.PENDING_CONFIRMATION, "API D7 không trả target_country; cần quy tắc xác nhận từ Thành viên 1"))
        country_status = MappingStatus.PENDING_CONFIRMATION

    # category_id
    cat_input = category_code_override if category_code_override else norm.category.raw
    cat_id, norm_cat, cat_err = lookup.resolve_category(cat_input)
    if cat_id is None:
        issues.append(MappingIssue("category_id", MappingIssueKind.UNRESOLVED_FK, cat_err or "Unresolved category_id"))

    # price_usd
    price_usd: Optional[Decimal] = None
    if norm.price.amount is not None:
        if norm.price.currency_code == "USD":
            price_usd = norm.price.amount.quantize(Decimal("0.01"))
        else:
            issues.append(MappingIssue("price_usd", MappingIssueKind.PENDING_CONFIRMATION, f"Thiếu tỷ giá quy đổi từ {norm.price.currency_code} sang USD"))

    platform_map = {"etsy": "Etsy", "amazon": "Amazon"}
    platform_source = platform_map.get(norm.provenance.source_id, norm.provenance.source_id)

    fields: Dict[str, MappedField] = {
        "market_product_id": MappedField("market_product_id", None, MappingStatus.NOT_APPLICABLE, note="DB SERIAL"),
        "external_sku": MappedField("external_sku", norm.source_product_id.value, MappingStatus.DIRECT, "source_product_id"),
        "platform_source": MappedField("platform_source", platform_source, MappingStatus.TRANSFORM, "provenance.source_id"),
        "target_country_id": MappedField("target_country_id", cid, country_status, "target_country_code", f"code={norm_cc}"),
        "category_id": MappedField("category_id", cat_id, MappingStatus.DEPENDENCY, "category", f"code={norm_cat}"),
        "product_name": MappedField("product_name", norm.product_name.value, MappingStatus.DIRECT, "product_name"),
        "price_usd": MappedField("price_usd", price_usd, MappingStatus.TRANSFORM, "price"),
        "price_segment": MappedField("price_segment", None, MappingStatus.PENDING_CONFIRMATION, note="Chờ xác nhận quy tắc tính ở D11/SQL"),
        "color": MappedField("color", None, MappingStatus.NO_SOURCE),
        "shape": MappedField("shape", None, MappingStatus.NO_SOURCE),
        "material": MappedField("material", None, MappingStatus.NO_SOURCE),
        "style": MappedField("style", None, MappingStatus.NO_SOURCE),
        "is_dishwasher_safe": MappedField("is_dishwasher_safe", None, MappingStatus.NO_SOURCE, note="DB DEFAULT FALSE"),
        "is_microwave_safe": MappedField("is_microwave_safe", None, MappingStatus.NO_SOURCE, note="DB DEFAULT FALSE"),
        "avg_rating": MappedField("avg_rating", None, MappingStatus.NO_SOURCE),
        "review_count": MappedField("review_count", None, MappingStatus.NO_SOURCE, note="DB DEFAULT 0"),
        "image_url": MappedField("image_url", None, MappingStatus.NO_SOURCE),
        "product_url": MappedField("product_url", norm.product_url.value, MappingStatus.DIRECT, "product_url"),
    }
    return _finalize_mapped_record("market_products", fields, issues, val_res)


def map_product_review_record(
    record: Union[NormalizedReviewRecord, ParsedReviewRecord],
    lookup: ReferenceLookup,
) -> MappedRecordResult:
    """Map D8/D10/D11 Etsy review record into OLTP ``product_reviews``."""
    norm = normalize_review_record(record) if isinstance(record, ParsedReviewRecord) else record
    val_res = DataQualityValidator.validate_review_record(norm)
    issues: List[MappingIssue] = []

    for err in val_res.errors:
        issues.append(MappingIssue(err.field_name, MappingIssueKind.VALIDATION_ERROR, err.message))

    # Enforce DDL NOT NULL on review_text (Etsy API can return null)
    if norm.review_text.value is None:
        issues.append(MappingIssue("review_text", MappingIssueKind.SOURCE_NULL, "product_reviews.review_text là NOT NULL trong DDL nhưng nguồn trả null/rỗng"))

    # FK lookup: market_product_id via external_sku
    sku = norm.product_reference.value
    mp_id = lookup.market_products_by_sku.get(sku) if sku else None
    if mp_id is None:
        issues.append(MappingIssue("market_product_id", MappingIssueKind.UNRESOLVED_FK, f"Không tìm thấy market_products với external_sku='{sku}'"))

    review_date_val: Optional[date] = None
    if norm.reviewed_at_iso.status == NormalizationStatus.CONFIRMED and norm.reviewed_at_iso.value:
        try:
            review_date_val = date.fromisoformat(str(norm.reviewed_at_iso.value)[:10])
        except ValueError:
            issues.append(MappingIssue("review_date", MappingIssueKind.INVALID_TYPE, f"Invalid date '{norm.reviewed_at_iso.value}'"))

    fields: Dict[str, MappedField] = {
        "review_id": MappedField("review_id", None, MappingStatus.NOT_APPLICABLE, note="DB SERIAL"),
        "market_product_id": MappedField("market_product_id", mp_id, MappingStatus.DEPENDENCY, "product_reference"),
        "customer_id": MappedField("customer_id", None, MappingStatus.NO_SOURCE, note="Etsy API không trả thông tin khách hàng"),
        "rating_stars": MappedField("rating_stars", norm.rating.value, MappingStatus.DIRECT, "rating"),
        "review_title": MappedField("review_title", None, MappingStatus.NO_SOURCE),
        "review_text": MappedField("review_text", norm.review_text.value, MappingStatus.DIRECT, "review_text"),
        "review_date": MappedField("review_date", review_date_val, MappingStatus.TRANSFORM, "reviewed_at_iso"),
        "sentiment_label": MappedField("sentiment_label", None, MappingStatus.NOT_APPLICABLE, note="Thuộc AI/NLP (Thành viên 3)"),
        "sentiment_score": MappedField("sentiment_score", None, MappingStatus.NOT_APPLICABLE, note="Thuộc AI/NLP (Thành viên 3)"),
    }
    return _finalize_mapped_record("product_reviews", fields, issues, val_res)


def map_supplier_record(
    supplier: ParsedSupplierInfo,
    *,
    supplier_code: Optional[str] = None,
) -> MappedRecordResult:
    """Map D9/D10 ``ParsedSupplierInfo`` into OLTP ``suppliers``."""
    issues: List[MappingIssue] = []

    if not supplier_code:
        issues.append(MappingIssue("supplier_code", MappingIssueKind.PENDING_CONFIRMATION, "D9 không có supplier_code; cần quy ước mã NCC từ Thành viên 1"))

    name_norm = normalize_text(supplier.supplier_name)
    addr_parts = [p for p in (normalize_text(supplier.address).value, normalize_text(supplier.province).value) if p]
    full_address = ", ".join(addr_parts) if addr_parts else None
    if full_address is None:
        issues.append(MappingIssue("address", MappingIssueKind.MISSING_NOT_NULL, "suppliers.address là NOT NULL trong DDL"))

    # Capacity and lead time are NOT NULL in DDL but absent in D9 ParsedSupplierInfo
    issues.append(MappingIssue("min_monthly_capacity", MappingIssueKind.NO_SOURCE, "D9 không cung cấp min_monthly_capacity (NOT NULL)"))
    issues.append(MappingIssue("max_monthly_capacity", MappingIssueKind.NO_SOURCE, "D9 không cung cấp max_monthly_capacity (NOT NULL)"))
    issues.append(MappingIssue("avg_lead_time_days", MappingIssueKind.NO_SOURCE, "D9 không cung cấp avg_lead_time_days ở cấp nhà cung cấp (NOT NULL)"))

    fields: Dict[str, MappedField] = {
        "supplier_id": MappedField("supplier_id", None, MappingStatus.NOT_APPLICABLE, note="DB SERIAL"),
        "supplier_code": MappedField("supplier_code", supplier_code, MappingStatus.PENDING_CONFIRMATION),
        "supplier_name": MappedField("supplier_name", name_norm.value, MappingStatus.DIRECT, "supplier_name"),
        "address": MappedField("address", full_address, MappingStatus.TRANSFORM, "address + province"),
        "hotline": MappedField("hotline", normalize_text(supplier.phone).value, MappingStatus.DIRECT, "phone"),
        "website_url": MappedField("website_url", normalize_text(supplier.website).value, MappingStatus.DIRECT, "website"),
        "specialization": MappedField("specialization", None, MappingStatus.NO_SOURCE),
        "min_monthly_capacity": MappedField("min_monthly_capacity", None, MappingStatus.NO_SOURCE),
        "max_monthly_capacity": MappedField("max_monthly_capacity", None, MappingStatus.NO_SOURCE),
        "avg_lead_time_days": MappedField("avg_lead_time_days", None, MappingStatus.NO_SOURCE),
        "total_catalog_items": MappedField("total_catalog_items", None, MappingStatus.NOT_APPLICABLE, note="DB DEFAULT 0"),
        "reliability_rating": MappedField("reliability_rating", None, MappingStatus.NOT_APPLICABLE, note="DB DEFAULT 4.50"),
    }
    return _finalize_mapped_record("suppliers", fields, issues)


def map_supplier_product_record(
    record: Union[NormalizedDomesticProductRecord, ParsedDomesticProductRecord],
    lookup: ReferenceLookup,
    *,
    supplier_code: Optional[str] = None,
) -> MappedRecordResult:
    """Map D9/D10/D11 domestic product into OLTP ``supplier_products``."""
    norm = normalize_domestic_product(record) if isinstance(record, ParsedDomesticProductRecord) else record
    val_res = DataQualityValidator.validate_domestic_product(norm)
    issues: List[MappingIssue] = []

    for err in val_res.errors:
        issues.append(MappingIssue(err.field_name, MappingIssueKind.VALIDATION_ERROR, err.message))

    sup_id = lookup.suppliers_by_code.get(supplier_code) if supplier_code else None
    if sup_id is None:
        issues.append(MappingIssue("supplier_id", MappingIssueKind.UNRESOLVED_FK, f"Không tìm thấy supplier với supplier_code='{supplier_code}'"))

    cat_id, norm_cat, cat_err = lookup.resolve_category(norm.category.raw)
    if cat_id is None:
        issues.append(MappingIssue("category_id", MappingIssueKind.UNRESOLVED_FK, cat_err or "Unresolved category_id"))

    price_vnd = norm.price_vnd.value.quantize(Decimal("0.01")) if norm.price_vnd.value is not None else None
    prod_url = normalize_text(norm.raw_record.get("product_url")).value if isinstance(norm.raw_record, dict) else None

    fields: Dict[str, MappedField] = {
        "supplier_product_id": MappedField("supplier_product_id", None, MappingStatus.NOT_APPLICABLE, note="DB SERIAL"),
        "supplier_id": MappedField("supplier_id", sup_id, MappingStatus.DEPENDENCY, "supplier_code"),
        "category_id": MappedField("category_id", cat_id, MappingStatus.DEPENDENCY, "category", f"code={norm_cat}"),
        "product_code": MappedField("product_code", norm.source_product_id.value, MappingStatus.DIRECT, "source_product_id"),
        "product_name": MappedField("product_name", norm.product_name.value, MappingStatus.DIRECT, "product_name"),
        "price_vnd": MappedField("price_vnd", price_vnd, MappingStatus.DIRECT, "price_vnd"),
        "price_usd_equiv": MappedField("price_usd_equiv", None, MappingStatus.PENDING_CONFIRMATION, note="Chờ tỷ giá VND/USD xác nhận"),
        "color": MappedField("color", None, MappingStatus.NO_SOURCE),
        "shape": MappedField("shape", None, MappingStatus.NO_SOURCE),
        "material": MappedField("material", norm.material.value, MappingStatus.DIRECT, "material"),
        "style": MappedField("style", None, MappingStatus.NO_SOURCE),
        "is_dishwasher_safe": MappedField("is_dishwasher_safe", None, MappingStatus.NO_SOURCE, note="DB DEFAULT TRUE"),
        "is_heat_resistant": MappedField("is_heat_resistant", None, MappingStatus.NO_SOURCE, note="DB DEFAULT TRUE"),
        "min_order_qty": MappedField("min_order_qty", norm.moq.value, MappingStatus.DIRECT, "moq", note="DB DEFAULT 100 khi NULL"),
        "image_url": MappedField("image_url", None, MappingStatus.NO_SOURCE),
        "product_url": MappedField("product_url", prod_url, MappingStatus.DIRECT, "product_url"),
    }
    return _finalize_mapped_record("supplier_products", fields, issues, val_res)
