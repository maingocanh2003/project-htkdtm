"""D12 — Data quality validation layer for ETL records.

Quy định và yêu cầu kiểm tra:
1. Kiểm tra trường bắt buộc (Mandatory / NOT NULL constraints).
2. Kiểm tra kiểu dữ liệu (Data types: int, float, Decimal, str, date, bool).
3. Kiểm tra miền giá trị và định dạng (Check constraints: range, non-negative, regex).
4. Kiểm tra tính hợp lệ của ngày tháng, tiền tệ, quốc gia và category theo danh mục đã xác nhận.
5. Phân biệt rõ lỗi nghiêm trọng (ERROR - chặn nạp vào CSDL) và cảnh báo (WARNING - cảnh báo kiểm toán).
6. Trả về kết quả validation chi tiết theo từng record và theo lô (batch).
7. Tuyệt đối không tự thêm các quy tắc nghiệp vụ chưa được xác nhận trong tài liệu thiết kế CSDL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .normalizer import (
    CONFIRMED_CATEGORIES,
    CONFIRMED_COUNTRIES,
    CONFIRMED_CURRENCIES,
    CONFIRMED_HS_CODES,
    NormalizationStatus,
    NormalizedDomesticProductRecord,
    NormalizedField,
    NormalizedProductRecord,
    NormalizedReviewRecord,
    NormalizedTradeRecord,
    NormalizedTrendsRow,
)
from .parsed_record import (
    ParsedDomesticProductRecord,
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedTradeRecord,
    ParsedTrendsRow,
    RecordProvenance,
)


# ---------------------------------------------------------------------------
# Severity and Issue Codes
# ---------------------------------------------------------------------------


class ValidationSeverity(str, Enum):
    """Mức độ nghiêm trọng của vấn đề chất lượng dữ liệu."""

    ERROR = "error"  # Lỗi nghiêm trọng: vi phạm NOT NULL, sai kiểu, vi phạm CHECK constraint -> Chặn nạp
    WARNING = "warning"  # Cảnh báo: thiếu trường tùy chọn, giá trị unconfirmed, nghi vấn dữ liệu -> Cần rà soát


class ValidationIssueCode(str, Enum):
    """Mã định danh nhóm lỗi chất lượng dữ liệu."""

    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_DATA_TYPE = "invalid_data_type"
    VALUE_OUT_OF_RANGE = "value_out_of_range"
    INVALID_FORMAT = "invalid_format"
    INVALID_DATE = "invalid_date"
    INVALID_CURRENCY = "invalid_currency"
    INVALID_COUNTRY = "invalid_country"
    INVALID_CATEGORY = "invalid_category"
    INVALID_HS_CODE = "invalid_hs_code"
    UNCONFIRMED_REFERENCE = "unconfirmed_reference"
    SUSPICIOUS_DATA = "suspicious_data"


@dataclass(frozen=True)
class ValidationIssue:
    """Chi tiết một vấn đề phát hiện được khi kiểm tra chất lượng."""

    field_name: str
    severity: ValidationSeverity
    code: ValidationIssueCode
    message: str
    raw_value: Any


@dataclass(frozen=True)
class RecordValidationResult:
    """Kết quả kiểm tra chất lượng cho một bản ghi đơn lẻ."""

    record_id: Optional[str]
    entity_type: str
    is_valid: bool  # True nếu không có bất kỳ lỗi ERROR nào
    has_warnings: bool  # True nếu có ít nhất 1 cảnh báo WARNING
    issues: Tuple[ValidationIssue, ...]
    provenance: Optional[RecordProvenance] = None

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


@dataclass(frozen=True)
class BatchValidationResult:
    """Kết quả kiểm tra chất lượng tổng hợp theo lô."""

    entity_type: str
    total_records: int
    valid_records: int
    invalid_records: int
    records_with_warnings: int
    record_results: Tuple[RecordValidationResult, ...]


# ---------------------------------------------------------------------------
# Individual Domain Validators
# ---------------------------------------------------------------------------


class TradeQualityValidator:
    """Kiểm tra chất lượng dữ liệu thương mại quốc tế (Bảng trade_statistics).

    Ràng buộc CSDL (01_init_oltp_erd_schema.sql):
    - year: INTEGER NOT NULL CHECK (year >= 2000 AND year <= 2100)
    - trade_flow: VARCHAR(20) NOT NULL CHECK (trade_flow IN ('Export', 'Import'))
    - hs_code: VARCHAR(20) NOT NULL
    - trade_value_usd: NUMERIC(18,2) NOT NULL CHECK (trade_value_usd >= 0)
    - fob_value_usd: NUMERIC(18,2) CHECK (fob_value_usd >= 0)
    - cif_value_usd: NUMERIC(18,2) CHECK (cif_value_usd >= 0)
    - net_weight_kg: NUMERIC(18,2) CHECK (net_weight_kg >= 0)
    - qty_amount: NUMERIC(18,2) CHECK (qty_amount >= 0)
    - market_share_pct: NUMERIC(6,2) CHECK (market_share_pct >= 0 AND market_share_pct <= 100)
    """

    @classmethod
    def validate(
        cls,
        record: Union[NormalizedTradeRecord, ParsedTradeRecord, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        issues: List[ValidationIssue] = []
        provenance: Optional[RecordProvenance] = None

        if isinstance(record, NormalizedTradeRecord):
            provenance = record.provenance
            rec_id = record_id or record.hs_code.value or "trade_record"

            # 1. Country validation
            cls._check_normalized_country(record.reporter_country, "reporter_country", is_required=True, issues=issues)
            cls._check_normalized_country(record.partner_country, "partner_country", is_required=True, issues=issues)

            # 2. Year validation (2000 - 2100)
            cls._check_trade_year(record.period, issues)

            # 3. Trade flow validation IN ('Export', 'Import')
            cls._check_trade_flow(record.flow_code, issues)

            # 4. HS code validation
            cls._check_trade_hs_code(record.hs_code, issues)

            # 5. trade_value_usd >= 0
            cls._check_non_negative_number(
                record.trade_value_usd, "trade_value_usd", is_required=True, issues=issues
            )

            # 6. net_weight_kg >= 0 (optional)
            cls._check_non_negative_number(
                record.net_weight_kg, "net_weight_kg", is_required=False, issues=issues
            )

        elif isinstance(record, ParsedTradeRecord):
            provenance = record.provenance
            rec_id = record_id or record.hs_code or "trade_record"
            cls._validate_trade_dict(
                {
                    "reporter_code": record.reporter_code or record.reporter_name,
                    "partner_code": record.partner_code or record.partner_name,
                    "year": record.period,
                    "trade_flow": record.flow_code,
                    "hs_code": record.hs_code,
                    "trade_value_usd": record.trade_value_usd,
                    "net_weight_kg": record.net_weight_kg,
                },
                issues,
            )

        elif isinstance(record, dict):
            rec_id = record_id or str(record.get("hs_code") or "trade_record")
            cls._validate_trade_dict(record, issues)
        else:
            issues.append(
                ValidationIssue(
                    field_name="record",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_DATA_TYPE,
                    message=f"Kiểu bản ghi không hợp lệ: {type(record).__name__}",
                    raw_value=record,
                )
            )
            rec_id = record_id or "unknown"

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        has_warnings = any(i.severity == ValidationSeverity.WARNING for i in issues)
        return RecordValidationResult(
            record_id=rec_id,
            entity_type="trade_statistics",
            is_valid=is_valid,
            has_warnings=has_warnings,
            issues=tuple(issues),
            provenance=provenance,
        )

    @classmethod
    def _check_normalized_country(
        cls, field: NormalizedField[str], field_name: str, is_required: bool, issues: List[ValidationIssue]
    ) -> None:
        if field.status == NormalizationStatus.INVALID:
            issues.append(
                ValidationIssue(
                    field_name=field_name,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_COUNTRY,
                    message=f"Mã quốc gia không hợp lệ: '{field.raw}'",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
            issues.append(
                ValidationIssue(
                    field_name=field_name,
                    severity=ValidationSeverity.WARNING,
                    code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                    message=f"Mã quốc gia '{field.raw}' chưa được xác nhận trong danh mục Bảng 1",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.MISSING or field.value is None:
            if is_required:
                issues.append(
                    ValidationIssue(
                        field_name=field_name,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message=f"Trường bắt buộc '{field_name}' bị thiếu hoặc rỗng",
                        raw_value=field.raw,
                    )
                )

    @classmethod
    def _check_trade_year(cls, field: NormalizedField[str], issues: List[ValidationIssue]) -> None:
        if field.status == NormalizationStatus.INVALID:
            issues.append(
                ValidationIssue(
                    field_name="year",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_DATE,
                    message=f"Định dạng năm không hợp lệ: '{field.raw}'",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
            issues.append(
                ValidationIssue(
                    field_name="year",
                    severity=ValidationSeverity.WARNING,
                    code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                    message=f"Năm/thời kỳ '{field.raw}' chưa được xác nhận định dạng",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.MISSING or field.value is None:
            issues.append(
                ValidationIssue(
                    field_name="year",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'year' bị thiếu",
                    raw_value=field.raw,
                )
            )
        else:
            year_str = str(field.value)[:4]
            try:
                year_val = int(year_str)
                if not (2000 <= year_val <= 2100):
                    issues.append(
                        ValidationIssue(
                            field_name="year",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"Năm thống kê thương mại '{year_val}' vi phạm ràng buộc CHECK (2000 <= year <= 2100)",
                            raw_value=field.raw,
                        )
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        field_name="year",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATE,
                        message=f"Định dạng năm không hợp lệ: '{field.raw}'",
                        raw_value=field.raw,
                    )
                )

    @classmethod
    def _check_trade_flow(cls, field: NormalizedField[str], issues: List[ValidationIssue]) -> None:
        if field.status == NormalizationStatus.INVALID:
            issues.append(
                ValidationIssue(
                    field_name="trade_flow",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_FORMAT,
                    message=f"Luồng thương mại không hợp lệ: '{field.raw}'",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
            issues.append(
                ValidationIssue(
                    field_name="trade_flow",
                    severity=ValidationSeverity.WARNING,
                    code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                    message=f"Luồng thương mại '{field.raw}' chưa được xác nhận",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.MISSING or field.value is None:
            issues.append(
                ValidationIssue(
                    field_name="trade_flow",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'trade_flow' bị thiếu",
                    raw_value=field.raw,
                )
            )
        elif field.value not in ("Export", "Import"):
            issues.append(
                ValidationIssue(
                    field_name="trade_flow",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                    message=f"Luồng thương mại '{field.value}' vi phạm ràng buộc CHECK (trade_flow IN ('Export', 'Import'))",
                    raw_value=field.raw,
                )
            )

    @classmethod
    def _check_trade_hs_code(cls, field: NormalizedField[str], issues: List[ValidationIssue]) -> None:
        if field.status == NormalizationStatus.INVALID:
            issues.append(
                ValidationIssue(
                    field_name="hs_code",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_HS_CODE,
                    message=f"Mã HS không hợp lệ: '{field.raw}'",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
            issues.append(
                ValidationIssue(
                    field_name="hs_code",
                    severity=ValidationSeverity.WARNING,
                    code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                    message=f"Mã HS '{field.raw}' nằm ngoài danh mục Chương 69 xác nhận (6911, 6912, 6913)",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.MISSING or field.value is None:
            issues.append(
                ValidationIssue(
                    field_name="hs_code",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'hs_code' bị thiếu",
                    raw_value=field.raw,
                )
            )

    @classmethod
    def _check_non_negative_number(
        cls, field: NormalizedField[Any], field_name: str, is_required: bool, issues: List[ValidationIssue]
    ) -> None:
        if field.status == NormalizationStatus.INVALID:
            issues.append(
                ValidationIssue(
                    field_name=field_name,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_DATA_TYPE,
                    message=f"Giá trị số của '{field_name}' không hợp lệ: '{field.raw}'",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
            issues.append(
                ValidationIssue(
                    field_name=field_name,
                    severity=ValidationSeverity.WARNING,
                    code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                    message=f"Giá trị số của '{field_name}' chưa được xác nhận: '{field.raw}'",
                    raw_value=field.raw,
                )
            )
        elif field.status == NormalizationStatus.MISSING or field.value is None:
            if is_required:
                issues.append(
                    ValidationIssue(
                        field_name=field_name,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message=f"Trường bắt buộc '{field_name}' bị thiếu",
                        raw_value=field.raw,
                    )
                )
        else:
            try:
                val = float(field.value)
                if val < 0:
                    issues.append(
                        ValidationIssue(
                            field_name=field_name,
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"Giá trị '{field_name}' = {val} vi phạm ràng buộc CHECK ({field_name} >= 0)",
                            raw_value=field.raw,
                        )
                    )
            except (ValueError, TypeError):
                issues.append(
                    ValidationIssue(
                        field_name=field_name,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATA_TYPE,
                        message=f"Kiểu dữ liệu của '{field_name}' không phải số hợp lệ",
                        raw_value=field.raw,
                    )
                )

    @classmethod
    def _validate_trade_dict(cls, data: Dict[str, Any], issues: List[ValidationIssue]) -> None:
        # Mandatory: reporter_code, partner_code, year, trade_flow, hs_code, trade_value_usd
        for field in ("reporter_code", "partner_code", "year", "trade_flow", "hs_code", "trade_value_usd"):
            val = data.get(field)
            if val is None or str(val).strip() == "":
                issues.append(
                    ValidationIssue(
                        field_name=field,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message=f"Trường bắt buộc '{field}' bị thiếu hoặc null",
                        raw_value=val,
                    )
                )

        # Year range
        year_val = data.get("year")
        if year_val is not None and str(year_val).strip():
            try:
                y = int(str(year_val)[:4])
                if not (2000 <= y <= 2100):
                    issues.append(
                        ValidationIssue(
                            field_name="year",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"Năm '{y}' vi phạm ràng buộc CHECK (2000 <= year <= 2100)",
                            raw_value=year_val,
                        )
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        field_name="year",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATE,
                        message=f"Năm không hợp lệ: '{year_val}'",
                        raw_value=year_val,
                    )
                )

        # Trade flow
        flow_val = data.get("trade_flow")
        if flow_val is not None and str(flow_val).strip():
            flow_str = str(flow_val).strip()
            if flow_str.upper() in ("M", "IMPORT"):
                flow_norm = "Import"
            elif flow_str.upper() in ("X", "EXPORT"):
                flow_norm = "Export"
            else:
                flow_norm = flow_str

            if flow_norm not in ("Export", "Import"):
                issues.append(
                    ValidationIssue(
                        field_name="trade_flow",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                        message=f"trade_flow '{flow_val}' vi phạm ràng buộc CHECK ('Export', 'Import')",
                        raw_value=flow_val,
                    )
                )

        # Trade value
        t_val = data.get("trade_value_usd")
        if t_val is not None and str(t_val).strip():
            try:
                val_f = float(str(t_val).replace(",", ""))
                if val_f < 0:
                    issues.append(
                        ValidationIssue(
                            field_name="trade_value_usd",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"trade_value_usd '{val_f}' vi phạm CHECK (trade_value_usd >= 0)",
                            raw_value=t_val,
                        )
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        field_name="trade_value_usd",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATA_TYPE,
                        message=f"trade_value_usd không phải số hợp lệ: '{t_val}'",
                        raw_value=t_val,
                    )
                )


class MarketProductQualityValidator:
    """Kiểm tra chất lượng dữ liệu sản phẩm quốc tế (Bảng market_products).

    Ràng buộc CSDL (01_init_oltp_erd_schema.sql):
    - platform_source: VARCHAR(50) NOT NULL
    - target_country_id: INTEGER NOT NULL
    - category_id: INTEGER NOT NULL
    - product_name: VARCHAR(300) NOT NULL
    - price_usd: NUMERIC(10,2) NOT NULL CHECK (price_usd >= 0)
    - avg_rating: NUMERIC(3,2) CHECK (avg_rating BETWEEN 0 AND 5)
    - review_count: INTEGER DEFAULT 0 CHECK (review_count >= 0)
    """

    @classmethod
    def validate(
        cls,
        record: Union[NormalizedProductRecord, ParsedProductRecord, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        issues: List[ValidationIssue] = []
        provenance: Optional[RecordProvenance] = None

        if isinstance(record, NormalizedProductRecord):
            provenance = record.provenance
            rec_id = record_id or record.source_product_id.value or "market_product"

            # 1. Mandatory product_name
            if record.product_name.status == NormalizationStatus.MISSING or not record.product_name.value:
                issues.append(
                    ValidationIssue(
                        field_name="product_name",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'product_name' bị thiếu hoặc rỗng",
                        raw_value=record.product_name.raw,
                    )
                )

            # 2. Category check
            if record.category.status == NormalizationStatus.INVALID:
                issues.append(
                    ValidationIssue(
                        field_name="category",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_CATEGORY,
                        message=f"Danh mục sản phẩm không hợp lệ: '{record.category.raw}'",
                        raw_value=record.category.raw,
                    )
                )
            elif record.category.status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
                issues.append(
                    ValidationIssue(
                        field_name="category",
                        severity=ValidationSeverity.WARNING,
                        code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                        message=f"Dòng sản phẩm '{record.category.raw}' chưa được xác nhận trong 4 dòng chủ lực",
                        raw_value=record.category.raw,
                    )
                )
            elif record.category.status == NormalizationStatus.MISSING or not record.category.value:
                issues.append(
                    ValidationIssue(
                        field_name="category",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'category' bị thiếu",
                        raw_value=record.category.raw,
                    )
                )

            # 3. Price check: price_usd >= 0
            if record.price.amount is None:
                issues.append(
                    ValidationIssue(
                        field_name="price_usd",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'price_usd' bị thiếu hoặc sai định dạng",
                        raw_value=record.price.raw_amount,
                    )
                )
            elif record.price.amount < 0:
                issues.append(
                    ValidationIssue(
                        field_name="price_usd",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                        message=f"price_usd '{record.price.amount}' vi phạm ràng buộc CHECK (price_usd >= 0)",
                        raw_value=record.price.raw_amount,
                    )
                )

            # 4. Currency check
            if record.price.currency_status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
                issues.append(
                    ValidationIssue(
                        field_name="currency",
                        severity=ValidationSeverity.WARNING,
                        code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                        message=f"Mã tiền tệ '{record.price.raw_currency}' chưa được xác nhận trong ISO 4217",
                        raw_value=record.price.raw_currency,
                    )
                )

        elif isinstance(record, ParsedProductRecord):
            provenance = record.provenance
            rec_id = record_id or record.source_product_id or "market_product"
            cls._validate_product_dict(
                {
                    "source_product_id": record.source_product_id,
                    "product_name": record.name,
                    "category": record.category,
                    "price": record.prices[0].amount_str if record.prices else None,
                    "currency": record.prices[0].currency_code if record.prices else None,
                },
                issues,
            )

        elif isinstance(record, dict):
            rec_id = record_id or str(record.get("source_product_id") or "market_product")
            cls._validate_product_dict(record, issues)
        else:
            issues.append(
                ValidationIssue(
                    field_name="record",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_DATA_TYPE,
                    message=f"Kiểu bản ghi không hợp lệ: {type(record).__name__}",
                    raw_value=record,
                )
            )
            rec_id = record_id or "unknown"

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        has_warnings = any(i.severity == ValidationSeverity.WARNING for i in issues)
        return RecordValidationResult(
            record_id=rec_id,
            entity_type="market_products",
            is_valid=is_valid,
            has_warnings=has_warnings,
            issues=tuple(issues),
            provenance=provenance,
        )

    @classmethod
    def _validate_product_dict(cls, data: Dict[str, Any], issues: List[ValidationIssue]) -> None:
        name = data.get("product_name") or data.get("name")
        if not name or not str(name).strip():
            issues.append(
                ValidationIssue(
                    field_name="product_name",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'product_name' bị thiếu hoặc rỗng",
                    raw_value=name,
                )
            )

        price = data.get("price") or data.get("price_usd")
        if price is None:
            issues.append(
                ValidationIssue(
                    field_name="price_usd",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'price_usd' bị thiếu",
                    raw_value=price,
                )
            )
        else:
            try:
                p_val = float(str(price).replace(",", ""))
                if p_val < 0:
                    issues.append(
                        ValidationIssue(
                            field_name="price_usd",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"price_usd '{p_val}' vi phạm ràng buộc CHECK (price_usd >= 0)",
                            raw_value=price,
                        )
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        field_name="price_usd",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATA_TYPE,
                        message=f"price_usd không phải số hợp lệ: '{price}'",
                        raw_value=price,
                    )
                )

        cat = data.get("category")
        if not cat:
            issues.append(
                ValidationIssue(
                    field_name="category",
                    severity=ValidationSeverity.WARNING,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Danh mục sản phẩm quốc tế bị trống",
                    raw_value=cat,
                )
            )


class ReviewQualityValidator:
    """Kiểm tra chất lượng dữ liệu đánh giá sản phẩm (Bảng product_reviews).

    Ràng buộc CSDL (01_init_oltp_erd_schema.sql):
    - market_product_id: INTEGER NOT NULL
    - rating_stars: INTEGER NOT NULL CHECK (rating_stars BETWEEN 1 AND 5)
    - review_text: TEXT NOT NULL
    """

    @classmethod
    def validate(
        cls,
        record: Union[NormalizedReviewRecord, ParsedReviewRecord, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        issues: List[ValidationIssue] = []
        provenance: Optional[RecordProvenance] = None

        if isinstance(record, NormalizedReviewRecord):
            provenance = record.provenance
            rec_id = record_id or record.product_reference.value or "product_review"

            # 1. Mandatory product_reference
            if record.product_reference.status == NormalizationStatus.MISSING or not record.product_reference.value:
                issues.append(
                    ValidationIssue(
                        field_name="product_reference",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'product_reference' bị thiếu",
                        raw_value=record.product_reference.raw,
                    )
                )

            # 2. Mandatory & Range: rating_stars BETWEEN 1 AND 5
            if record.rating.status == NormalizationStatus.MISSING or record.rating.value is None:
                issues.append(
                    ValidationIssue(
                        field_name="rating_stars",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'rating_stars' bị thiếu",
                        raw_value=record.rating.raw,
                    )
                )
            elif not (1 <= record.rating.value <= 5):
                issues.append(
                    ValidationIssue(
                        field_name="rating_stars",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                        message=f"rating_stars = {record.rating.value} vi phạm ràng buộc CHECK (rating_stars BETWEEN 1 AND 5)",
                        raw_value=record.rating.raw,
                    )
                )

            # 3. Mandatory review_text (NOT NULL)
            if record.review_text.status == NormalizationStatus.MISSING or not record.review_text.value:
                issues.append(
                    ValidationIssue(
                        field_name="review_text",
                        severity=ValidationSeverity.WARNING,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Nội dung review_text bị trống (nguồn gửi null/rỗng)",
                        raw_value=record.review_text.raw,
                    )
                )

            # 4. Review date if present
            if record.reviewed_at_iso.status == NormalizationStatus.INVALID:
                issues.append(
                    ValidationIssue(
                        field_name="review_date",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATE,
                        message=f"Ngày đánh giá không hợp lệ: '{record.reviewed_at_iso.raw}'",
                        raw_value=record.reviewed_at_iso.raw,
                    )
                )

        elif isinstance(record, ParsedReviewRecord):
            provenance = record.provenance
            rec_id = record_id or record.product_reference or "product_review"
            cls._validate_review_dict(
                {
                    "product_reference": record.product_reference,
                    "rating_stars": record.rating,
                    "review_text": record.review_text,
                    "review_date": record.reviewed_at_iso,
                },
                issues,
            )

        elif isinstance(record, dict):
            rec_id = record_id or str(record.get("product_reference") or "product_review")
            cls._validate_review_dict(record, issues)
        else:
            issues.append(
                ValidationIssue(
                    field_name="record",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_DATA_TYPE,
                    message=f"Kiểu bản ghi không hợp lệ: {type(record).__name__}",
                    raw_value=record,
                )
            )
            rec_id = record_id or "unknown"

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        has_warnings = any(i.severity == ValidationSeverity.WARNING for i in issues)
        return RecordValidationResult(
            record_id=rec_id,
            entity_type="product_reviews",
            is_valid=is_valid,
            has_warnings=has_warnings,
            issues=tuple(issues),
            provenance=provenance,
        )

    @classmethod
    def _validate_review_dict(cls, data: Dict[str, Any], issues: List[ValidationIssue]) -> None:
        ref = data.get("product_reference") or data.get("market_product_id")
        if not ref or not str(ref).strip():
            issues.append(
                ValidationIssue(
                    field_name="product_reference",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'product_reference' bị thiếu",
                    raw_value=ref,
                )
            )

        rating = data.get("rating_stars") or data.get("rating")
        if rating is None:
            issues.append(
                ValidationIssue(
                    field_name="rating_stars",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'rating_stars' bị thiếu",
                    raw_value=rating,
                )
            )
        else:
            try:
                r_int = int(rating)
                if not (1 <= r_int <= 5):
                    issues.append(
                        ValidationIssue(
                            field_name="rating_stars",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"rating_stars = {r_int} vi phạm ràng buộc CHECK (rating_stars BETWEEN 1 AND 5)",
                            raw_value=rating,
                        )
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        field_name="rating_stars",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATA_TYPE,
                        message=f"rating_stars không phải số nguyên: '{rating}'",
                        raw_value=rating,
                    )
                )


class SearchTrendsQualityValidator:
    """Kiểm tra chất lượng dữ liệu Google Trends (Bảng search_trends).

    Ràng buộc CSDL (01_init_oltp_erd_schema.sql):
    - search_term: VARCHAR(150) NOT NULL
    - week_start_date: DATE NOT NULL
    - interest_score: INTEGER NOT NULL CHECK (interest_score BETWEEN 0 AND 100)
    - week_number: INTEGER CHECK (week_number BETWEEN 1 AND 53)
    """

    @classmethod
    def validate(
        cls,
        record: Union[NormalizedTrendsRow, ParsedTrendsRow, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        issues: List[ValidationIssue] = []
        provenance: Optional[RecordProvenance] = None

        if isinstance(record, NormalizedTrendsRow):
            provenance = record.provenance
            rec_id = record_id or record.period_label.value or "search_trend"

            is_text_period = record.period_kind in {"region", "related_term"}
            if is_text_period:
                if (
                    record.period_label.status == NormalizationStatus.MISSING
                    or not record.period_label.value
                ):
                    issues.append(
                        ValidationIssue(
                            field_name="period_label",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                            message="Trường nhãn khu vực/related bị thiếu",
                            raw_value=record.period_label.raw,
                        )
                    )
                elif record.period_label.status == NormalizationStatus.INVALID:
                    issues.append(
                        ValidationIssue(
                            field_name="period_label",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.INVALID_FORMAT,
                            message=f"Nhãn khu vực/related không hợp lệ: '{record.period_label.raw}'",
                            raw_value=record.period_label.raw,
                        )
                    )
            elif record.period_label.status == NormalizationStatus.INVALID:
                issues.append(
                    ValidationIssue(
                        field_name="week_start_date",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATE,
                        message=f"week_start_date không hợp lệ: '{record.period_label.raw}'",
                        raw_value=record.period_label.raw,
                    )
                )
            elif record.period_label.status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
                issues.append(
                    ValidationIssue(
                        field_name="week_start_date",
                        severity=ValidationSeverity.WARNING,
                        code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                        message=f"week_start_date chưa được xác nhận định dạng: '{record.period_label.raw}'",
                        raw_value=record.period_label.raw,
                    )
                )
            elif record.period_label.status == NormalizationStatus.MISSING or not record.period_label.value:
                issues.append(
                    ValidationIssue(
                        field_name="week_start_date",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'week_start_date' bị thiếu",
                        raw_value=record.period_label.raw,
                    )
                )

            if record.period_kind == "related_term":
                data_type = (record.data_type_hint or "").casefold()
                if not (
                    "related queries" in data_type
                    or "related topics" in data_type
                ):
                    issues.append(
                        ValidationIssue(
                            field_name="data_type",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.INVALID_FORMAT,
                            message="Related record thiếu loại Queries/Topics hợp lệ",
                            raw_value=record.data_type_hint,
                        )
                    )
                if record.related_section not in {"top", "rising"}:
                    issues.append(
                        ValidationIssue(
                            field_name="related_section",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.INVALID_FORMAT,
                            message="Related record thiếu phân loại Top/Rising hợp lệ",
                            raw_value=record.related_section,
                        )
                    )
                if not record.source_keyword:
                    issues.append(
                        ValidationIssue(
                            field_name="source_keyword",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                            message="Related record thiếu từ khóa nguồn",
                            raw_value=record.source_keyword,
                        )
                    )
                if not record.keyword_scores:
                    issues.append(
                        ValidationIssue(
                            field_name="related_values",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                            message="Related record thiếu các trường dữ liệu",
                            raw_value=None,
                        )
                    )
                for kw, score_field in record.keyword_scores:
                    if score_field.raw is None or not str(score_field.raw).strip():
                        issues.append(
                            ValidationIssue(
                                field_name=f"related_value[{kw}]",
                                severity=ValidationSeverity.ERROR,
                                code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                                message=f"Giá trị Related '{kw}' bị thiếu",
                                raw_value=score_field.raw,
                            )
                        )
            else:
                if not record.keyword_scores:
                    issues.append(
                        ValidationIssue(
                            field_name="keyword_scores",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                            message="Bản ghi thiếu giá trị theo từ khóa",
                            raw_value=None,
                        )
                    )
                for kw, score_field in record.keyword_scores:
                    if score_field.status == NormalizationStatus.INVALID:
                        issues.append(
                            ValidationIssue(
                                field_name=f"interest_score[{kw}]",
                                severity=ValidationSeverity.ERROR,
                                code=ValidationIssueCode.INVALID_DATA_TYPE,
                                message=f"interest_score không hợp lệ: '{score_field.raw}'",
                                raw_value=score_field.raw,
                            )
                        )
                    elif score_field.status == NormalizationStatus.MISSING:
                        issues.append(
                            ValidationIssue(
                                field_name=f"interest_score[{kw}]",
                                severity=ValidationSeverity.ERROR,
                                code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                                message=f"interest_score của '{kw}' bị thiếu",
                                raw_value=score_field.raw,
                            )
                        )
                    elif score_field.value is not None and not (
                        0 <= score_field.value <= 100
                    ):
                        issues.append(
                            ValidationIssue(
                                field_name=f"interest_score[{kw}]",
                                severity=ValidationSeverity.ERROR,
                                code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                                message=f"interest_score = {score_field.value} vi phạm CHECK (interest_score BETWEEN 0 AND 100)",
                                raw_value=score_field.raw,
                            )
                        )

        elif isinstance(record, ParsedTrendsRow):
            provenance = record.provenance
            rec_id = record_id or record.period_label or "search_trend"
            cls._validate_trends_dict(
                {
                    "week_start_date": record.period_label,
                    "keyword_values": record.keyword_values,
                },
                issues,
            )

        elif isinstance(record, dict):
            rec_id = record_id or str(record.get("week_start_date") or "search_trend")
            cls._validate_trends_dict(record, issues)
        else:
            issues.append(
                ValidationIssue(
                    field_name="record",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_DATA_TYPE,
                    message=f"Kiểu bản ghi không hợp lệ: {type(record).__name__}",
                    raw_value=record,
                )
            )
            rec_id = record_id or "unknown"

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        has_warnings = any(i.severity == ValidationSeverity.WARNING for i in issues)
        return RecordValidationResult(
            record_id=rec_id,
            entity_type="search_trends",
            is_valid=is_valid,
            has_warnings=has_warnings,
            issues=tuple(issues),
            provenance=provenance,
        )

    @classmethod
    def _validate_trends_dict(cls, data: Dict[str, Any], issues: List[ValidationIssue]) -> None:
        dt = data.get("week_start_date") or data.get("period")
        if not dt or not str(dt).strip():
            issues.append(
                ValidationIssue(
                    field_name="week_start_date",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'week_start_date' bị thiếu",
                    raw_value=dt,
                )
            )


class DomesticProductQualityValidator:
    """Kiểm tra chất lượng dữ liệu sản phẩm nhà cung cấp nội địa (Bảng supplier_products).

    Ràng buộc CSDL (01_init_oltp_erd_schema.sql):
    - supplier_id: INTEGER NOT NULL
    - category_id: INTEGER NOT NULL
    - product_name: VARCHAR(300) NOT NULL
    - price_vnd: NUMERIC(14,2) NOT NULL CHECK (price_vnd >= 0)
    - price_usd_equiv: NUMERIC(10,2) CHECK (price_usd_equiv >= 0)
    - min_order_qty: INTEGER DEFAULT 100 CHECK (min_order_qty > 0)
    """

    @classmethod
    def validate(
        cls,
        record: Union[NormalizedDomesticProductRecord, ParsedDomesticProductRecord, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        issues: List[ValidationIssue] = []
        provenance: Optional[RecordProvenance] = None

        if isinstance(record, NormalizedDomesticProductRecord):
            provenance = record.provenance
            rec_id = record_id or record.source_product_id.value or "domestic_product"

            # 1. Mandatory product_name
            if record.product_name.status == NormalizationStatus.MISSING or not record.product_name.value:
                issues.append(
                    ValidationIssue(
                        field_name="product_name",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'product_name' bị thiếu hoặc rỗng",
                        raw_value=record.product_name.raw,
                    )
                )

            # 2. Mandatory category & confirmed lines
            if record.category.status == NormalizationStatus.INVALID:
                issues.append(
                    ValidationIssue(
                        field_name="category",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_CATEGORY,
                        message=f"Danh mục sản phẩm không hợp lệ: '{record.category.raw}'",
                        raw_value=record.category.raw,
                    )
                )
            elif record.category.status == NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1:
                issues.append(
                    ValidationIssue(
                        field_name="category",
                        severity=ValidationSeverity.WARNING,
                        code=ValidationIssueCode.UNCONFIRMED_REFERENCE,
                        message=f"Dòng sản phẩm '{record.category.raw}' chưa được xác nhận trong 4 dòng chủ lực",
                        raw_value=record.category.raw,
                    )
                )
            elif record.category.status == NormalizationStatus.MISSING or not record.category.value:
                issues.append(
                    ValidationIssue(
                        field_name="category",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'category' bị thiếu",
                        raw_value=record.category.raw,
                    )
                )

            # 3. Mandatory price_vnd: CHECK (price_vnd >= 0)
            if record.price_vnd.status == NormalizationStatus.INVALID:
                issues.append(
                    ValidationIssue(
                        field_name="price_vnd",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATA_TYPE,
                        message=f"price_vnd không phải số hợp lệ: '{record.price_vnd.raw}'",
                        raw_value=record.price_vnd.raw,
                    )
                )
            elif record.price_vnd.status == NormalizationStatus.MISSING or record.price_vnd.value is None:
                issues.append(
                    ValidationIssue(
                        field_name="price_vnd",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                        message="Trường bắt buộc 'price_vnd' bị thiếu",
                        raw_value=record.price_vnd.raw,
                    )
                )
            elif record.price_vnd.value < 0:
                issues.append(
                    ValidationIssue(
                        field_name="price_vnd",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                        message=f"price_vnd '{record.price_vnd.value}' vi phạm ràng buộc CHECK (price_vnd >= 0)",
                        raw_value=record.price_vnd.raw,
                    )
                )

            # 4. Optional MOQ: CHECK (min_order_qty > 0)
            if record.moq.value is not None:
                if record.moq.value <= 0:
                    issues.append(
                        ValidationIssue(
                            field_name="min_order_qty",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"min_order_qty = {record.moq.value} vi phạm ràng buộc CHECK (min_order_qty > 0)",
                            raw_value=record.moq.raw,
                        )
                    )

            # 5. Optional Lead time: > 0
            if record.lead_time_days.value is not None:
                if record.lead_time_days.value <= 0:
                    issues.append(
                        ValidationIssue(
                            field_name="avg_lead_time_days",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"lead_time_days = {record.lead_time_days.value} vi phạm điều kiện phải > 0",
                            raw_value=record.lead_time_days.raw,
                        )
                    )

        elif isinstance(record, ParsedDomesticProductRecord):
            provenance = record.provenance
            rec_id = record_id or record.source_product_id or "domestic_product"
            cls._validate_domestic_dict(
                {
                    "source_product_id": record.source_product_id,
                    "product_name": record.name,
                    "category": record.category,
                    "price_vnd": record.commercial.price_vnd_str,
                    "min_order_qty": record.commercial.moq,
                },
                issues,
            )

        elif isinstance(record, dict):
            rec_id = record_id or str(record.get("source_product_id") or "domestic_product")
            cls._validate_domestic_dict(record, issues)
        else:
            issues.append(
                ValidationIssue(
                    field_name="record",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.INVALID_DATA_TYPE,
                    message=f"Kiểu bản ghi không hợp lệ: {type(record).__name__}",
                    raw_value=record,
                )
            )
            rec_id = record_id or "unknown"

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        has_warnings = any(i.severity == ValidationSeverity.WARNING for i in issues)
        return RecordValidationResult(
            record_id=rec_id,
            entity_type="supplier_products",
            is_valid=is_valid,
            has_warnings=has_warnings,
            issues=tuple(issues),
            provenance=provenance,
        )

    @classmethod
    def _validate_domestic_dict(cls, data: Dict[str, Any], issues: List[ValidationIssue]) -> None:
        name = data.get("product_name") or data.get("name")
        if not name or not str(name).strip():
            issues.append(
                ValidationIssue(
                    field_name="product_name",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'product_name' bị thiếu hoặc rỗng",
                    raw_value=name,
                )
            )

        price = data.get("price_vnd")
        if price is None:
            issues.append(
                ValidationIssue(
                    field_name="price_vnd",
                    severity=ValidationSeverity.ERROR,
                    code=ValidationIssueCode.MISSING_REQUIRED_FIELD,
                    message="Trường bắt buộc 'price_vnd' bị thiếu",
                    raw_value=price,
                )
            )
        else:
            try:
                p_val = float(str(price).replace(",", ""))
                if p_val < 0:
                    issues.append(
                        ValidationIssue(
                            field_name="price_vnd",
                            severity=ValidationSeverity.ERROR,
                            code=ValidationIssueCode.VALUE_OUT_OF_RANGE,
                            message=f"price_vnd '{p_val}' vi phạm ràng buộc CHECK (price_vnd >= 0)",
                            raw_value=price,
                        )
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        field_name="price_vnd",
                        severity=ValidationSeverity.ERROR,
                        code=ValidationIssueCode.INVALID_DATA_TYPE,
                        message=f"price_vnd không phải số hợp lệ: '{price}'",
                        raw_value=price,
                    )
                )


# ---------------------------------------------------------------------------
# Unified DataQualityValidator Orchestrator
# ---------------------------------------------------------------------------


class DataQualityValidator:
    """Bộ kiểm tra chất lượng dữ liệu tổng hợp cho toàn bộ luồng ETL."""

    @staticmethod
    def validate_trade_record(
        record: Union[NormalizedTradeRecord, ParsedTradeRecord, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        return TradeQualityValidator.validate(record, record_id)

    @staticmethod
    def validate_product_record(
        record: Union[NormalizedProductRecord, ParsedProductRecord, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        return MarketProductQualityValidator.validate(record, record_id)

    @staticmethod
    def validate_review_record(
        record: Union[NormalizedReviewRecord, ParsedReviewRecord, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        return ReviewQualityValidator.validate(record, record_id)

    @staticmethod
    def validate_trends_row(
        row: Union[NormalizedTrendsRow, ParsedTrendsRow, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        return SearchTrendsQualityValidator.validate(row, record_id)

    @staticmethod
    def validate_domestic_product(
        record: Union[NormalizedDomesticProductRecord, ParsedDomesticProductRecord, Dict[str, Any]],
        record_id: Optional[str] = None,
    ) -> RecordValidationResult:
        return DomesticProductQualityValidator.validate(record, record_id)

    @classmethod
    def validate_batch(
        cls,
        records: Sequence[Any],
        entity_type: str,
    ) -> BatchValidationResult:
        """Kiểm tra chất lượng cho một danh sách bản ghi và tổng hợp kết quả theo lô."""
        results: List[RecordValidationResult] = []

        for idx, rec in enumerate(records):
            rec_id = f"{entity_type}_{idx + 1}"
            if entity_type == "trade_statistics":
                res = cls.validate_trade_record(rec, record_id=rec_id)
            elif entity_type == "market_products":
                res = cls.validate_product_record(rec, record_id=rec_id)
            elif entity_type == "product_reviews":
                res = cls.validate_review_record(rec, record_id=rec_id)
            elif entity_type == "search_trends":
                res = cls.validate_trends_row(rec, record_id=rec_id)
            elif entity_type == "supplier_products":
                res = cls.validate_domestic_product(rec, record_id=rec_id)
            else:
                raise ValueError(f"Loại thực thể chưa được hỗ trợ: {entity_type}")
            results.append(res)

        total = len(results)
        valid_cnt = sum(1 for r in results if r.is_valid)
        invalid_cnt = total - valid_cnt
        warn_cnt = sum(1 for r in results if r.has_warnings)

        return BatchValidationResult(
            entity_type=entity_type,
            total_records=total,
            valid_records=valid_cnt,
            invalid_records=invalid_cnt,
            records_with_warnings=warn_cnt,
            record_results=tuple(results),
        )
