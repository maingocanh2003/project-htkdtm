"""D11 — Cleaning and normalization layer for parsed ETL data.

Quy tắc thực hiện:
1. Chuẩn hóa khoảng trắng, chuỗi và ký tự (NFC unicode, xóa ký tự điều khiển, gom khoảng trắng).
2. Chuẩn hóa ngày tháng, số và đơn vị đo.
3. Xử lý tiền tệ nhưng không quy đổi nếu thiếu tỷ giá và thời điểm tỷ giá đáng tin cậy.
4. Chuẩn hóa quốc gia, category và HS code theo danh mục đã được xác nhận trong tài liệu.
5. Giữ lại raw value và normalized value khi cần truy vết (thông qua NormalizedField).
6. Không tự suy đoán giá trị bị thiếu (missing remains None với status MISSING).
7. Mọi quy tắc chưa được tài liệu xác nhận phải được đánh dấu chờ xác nhận từ thành viên 1 (Trần Mai Ngọc Anh).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar, Union

from .parsed_record import (
    ParsedCommercialInfo,
    ParsedDomesticProductRecord,
    ParsedPriceInfo,
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedSupplierInfo,
    ParsedTradeRecord,
    ParsedTrendsRow,
    RecordProvenance,
)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Status and Traceability Envelope
# ---------------------------------------------------------------------------


class NormalizationStatus(str, Enum):
    """Trạng thái chuẩn hóa của từng trường dữ liệu."""

    CONFIRMED = "confirmed"  # Quy tắc đã được xác nhận theo tài liệu
    WAITING_CONFIRMATION_MEMBER_1 = "waiting_confirmation_member_1"  # Chưa xác nhận bởi Thành viên 1 (Trần Mai Ngọc Anh)
    MISSING = "missing"  # Dữ liệu nguồn không cung cấp (không tự suy đoán)
    INVALID = "invalid"  # Dữ liệu không hợp lệ / không thể parse


@dataclass(frozen=True)
class NormalizedField(Generic[T]):
    """Gói lưu trữ giá trị thô (raw) và giá trị chuẩn hóa (value) để truy vết."""

    raw: Any
    value: Optional[T]
    status: NormalizationStatus
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Catalogs đã được xác nhận trong tài liệu dự án (Confirmed Reference Catalogs)
# ---------------------------------------------------------------------------

# Bảng 1: countries — Mã ISO 3166-1 alpha-3, UN M49 numeric codes, và tên phổ biến
CONFIRMED_COUNTRIES: Dict[str, str] = {
    # Hoa Kỳ / United States
    "USA": "USA",
    "US": "USA",
    "842": "USA",
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    "MỸ": "USA",
    "HOA KỲ": "USA",
    # Việt Nam
    "VNM": "VNM",
    "VN": "VNM",
    "704": "VNM",
    "VIET NAM": "VNM",
    "VIETNAM": "VNM",
    "VIỆT NAM": "VNM",
    # Nhật Bản / Japan
    "JPN": "JPN",
    "JP": "JPN",
    "392": "JPN",
    "JAPAN": "JPN",
    "NHẬT BẢN": "JPN",
    # Đức / Germany
    "DEU": "DEU",
    "DE": "DEU",
    "276": "DEU",
    "GERMANY": "DEU",
    "ĐỨC": "DEU",
    # Trung Quốc / China
    "CHN": "CHN",
    "CN": "CHN",
    "156": "CHN",
    "CHINA": "CHN",
    "TRUNG QUỐC": "CHN",
    # Pháp / France
    "FRA": "FRA",
    "FR": "FRA",
    "250": "FRA",
    "FRANCE": "FRA",
    "PHÁP": "FRA",
    # Ấn Độ / India
    "IND": "IND",
    "IN": "IND",
    "356": "IND",
    "INDIA": "IND",
    "ẤN ĐỘ": "IND",
    # Toàn cầu / World (UN Comtrade code 0)
    "0": "WLD",
    "WLD": "WLD",
    "WORLD": "WLD",
    "THẾ GIỚI": "WLD",
}

# Bảng 6: product_categories — 4 dòng sản phẩm gốm sứ chủ lực đã xác nhận
CONFIRMED_CATEGORIES: Dict[str, str] = {
    # 1. Bộ ấm chén / Ceramic Tea Set
    "tea_set": "TEA_SET",
    "tea set": "TEA_SET",
    "ceramic tea set": "TEA_SET",
    "bộ ấm chén": "TEA_SET",
    "bộ trà": "TEA_SET",
    "ấm trà": "TEA_SET",
    "ấm chén": "TEA_SET",
    "ấm chén bát tràng": "TEA_SET",
    # 2. Ly cốc sứ / Ceramic Mug & Cup
    "mug_cup": "MUG_CUP",
    "mug": "MUG_CUP",
    "cup": "MUG_CUP",
    "ceramic mug & cup": "MUG_CUP",
    "ly cốc sứ": "MUG_CUP",
    "ly cốc": "MUG_CUP",
    "cốc sứ": "MUG_CUP",
    "ly sứ": "MUG_CUP",
    "cốc": "MUG_CUP",
    "ly": "MUG_CUP",
    # 3. Bát đĩa bàn ăn / Dinnerware Set
    "dinnerware": "DINNERWARE",
    "dinnerware set": "DINNERWARE",
    "tableware": "DINNERWARE",
    "bát đĩa bàn ăn": "DINNERWARE",
    "bát đĩa": "DINNERWARE",
    "bộ chén cơm": "DINNERWARE",
    "bát ăn cơm": "DINNERWARE",
    "chén dĩa": "DINNERWARE",
    "chén": "DINNERWARE",
    "dĩa": "DINNERWARE",
    "đĩa": "DINNERWARE",
    "bát": "DINNERWARE",
    "serving bowl": "DINNERWARE",
    "dinner set": "DINNERWARE",
    # 4. Lọ hoa mỹ nghệ / Decorative Vase
    "vase_decor": "VASE_DECOR",
    "vase": "VASE_DECOR",
    "decorative vase": "VASE_DECOR",
    "lọ hoa mỹ nghệ": "VASE_DECOR",
    "bình hoa": "VASE_DECOR",
    "lọ hoa": "VASE_DECOR",
    "lọ": "VASE_DECOR",
    "đồ trang trí": "VASE_DECOR",
}

# HS Codes Chương 69 gốm sứ đã xác nhận trong tài liệu
CONFIRMED_HS_CODES: Dict[str, str] = {
    "6911": "6911",  # Tableware, kitchenware, of porcelain or china
    "6912": "6912",  # Ceramic tableware, kitchenware, other than porcelain
    "6913": "6913",  # Statuettes and other ornamental ceramic articles
}

# Đơn vị tính (Units of Measure) đã xác nhận
CONFIRMED_UNITS: Dict[str, str] = {
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "kgs": "kg",
    "kilo": "kg",
    "item": "item",
    "items": "item",
    "number of items": "item",
    "piece": "item",
    "pieces": "item",
    "pcs": "item",
    "sản phẩm": "item",
    "sp": "item",
    "chếc": "item",
    "chiếc": "item",
    "cái": "item",
    "%": "%",
    "pct": "%",
    "percent": "%",
    "percentage": "%",
}

# Mã tiền tệ ISO 4217 đã xác nhận
CONFIRMED_CURRENCIES: Dict[str, str] = {
    "USD": "USD",
    "$": "USD",
    "US DOLLAR": "USD",
    "VND": "VND",
    "VNĐ": "VND",
    "Đ": "VND",
    "D": "VND",
    "VIETNAMESE DONG": "VND",
    "EUR": "EUR",
    "€": "EUR",
    "EURO": "EUR",
    "JPY": "JPY",
    "¥": "JPY",
    "JAPANESE YEN": "JPY",
}

# Ký tự điều khiển cần loại bỏ (trừ tab và newline hợp lệ nếu cần)
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
_MULTI_WHITESPACE_PATTERN = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# 1. Chuẩn hóa khoảng trắng, chuỗi và ký tự
# ---------------------------------------------------------------------------


def normalize_text(raw: Any) -> NormalizedField[str]:
    """Chuẩn hóa chuỗi văn bản:

    - Kiểm tra missing / null
    - Chuẩn hóa Unicode theo dạng NFC (canonical composition)
    - Loại bỏ ký tự điều khiển (control characters)
    - Gom nhiều khoảng trắng / tabs / newlines liên tiếp thành 1 dấu cách duy nhất
    - Trim khoảng trắng ở đầu và cuối chuỗi
    """
    if raw is None:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Giá trị văn bản bị thiếu",
        )

    if not isinstance(raw, str):
        raw_str = str(raw)
    else:
        raw_str = raw

    # Unicode NFC normalization
    normalized = unicodedata.normalize("NFC", raw_str)
    # Loại bỏ control characters
    cleaned = _CONTROL_CHARS_PATTERN.sub("", normalized)
    # Gom khoảng trắng
    collapsed = _MULTI_WHITESPACE_PATTERN.sub(" ", cleaned).strip()

    if not collapsed:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Chuỗi rỗng hoặc chỉ chứa khoảng trắng",
        )

    return NormalizedField(
        raw=raw,
        value=collapsed,
        status=NormalizationStatus.CONFIRMED,
    )


# ---------------------------------------------------------------------------
# 2. Chuẩn hóa ngày tháng, số và đơn vị đo
# ---------------------------------------------------------------------------


def normalize_date(raw: Any) -> NormalizedField[str]:
    """Chuẩn hóa ngày tháng về định dạng ISO-8601 (YYYY-MM-DD hoặc YYYY-MM hoặc YYYY).

    Không tự suy đoán phần ngày/tháng bị thiếu (ví dụ năm 2022 giữ '2022', không tự điền '2022-01-01').
    """
    if raw is None:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Giá trị ngày tháng bị thiếu",
        )

    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            raw = raw.replace(tzinfo=timezone.utc)
        return NormalizedField(
            raw=raw,
            value=raw.isoformat(),
            status=NormalizationStatus.CONFIRMED,
        )

    if isinstance(raw, date):
        return NormalizedField(
            raw=raw,
            value=raw.isoformat(),
            status=NormalizationStatus.CONFIRMED,
        )

    if isinstance(raw, (int, float)):
        # Trường hợp timestamp int lớn hoặc năm 4 chữ số
        val_int = int(raw)
        if 1900 <= val_int <= 2100:
            return NormalizedField(
                raw=raw,
                value=str(val_int),
                status=NormalizationStatus.CONFIRMED,
            )
        # Giả định Unix timestamp tính theo giây nếu > 100000000
        if val_int >= 100_000_000:
            try:
                dt = datetime.fromtimestamp(val_int, timezone.utc)
                return NormalizedField(
                    raw=raw,
                    value=dt.isoformat(),
                    status=NormalizationStatus.CONFIRMED,
                )
            except (OverflowError, OSError, ValueError):
                return NormalizedField(
                    raw=raw,
                    value=None,
                    status=NormalizationStatus.INVALID,
                    note=f"Timestamp ngoài khoảng cho phép: {raw}",
                )

    if not isinstance(raw, str):
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.INVALID,
            note=f"Kiểu dữ liệu ngày tháng không hợp lệ: {type(raw).__name__}",
        )

    text = raw.strip()
    if not text:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Chuỗi ngày tháng rỗng",
        )

    # 1. Khớp YYYY
    if re.fullmatch(r"\d{4}", text):
        year = int(text)
        if 1900 <= year <= 2100:
            return NormalizedField(
                raw=raw, value=text, status=NormalizationStatus.CONFIRMED
            )

    # 2. Khớp YYYY-MM hoặc YYYY/MM hoặc YYYYMM
    if re.fullmatch(r"\d{4}[-/]\d{2}", text):
        norm = text.replace("/", "-")
        return NormalizedField(
            raw=raw, value=norm, status=NormalizationStatus.CONFIRMED
        )
    if re.fullmatch(r"\d{6}", text):
        norm = f"{text[:4]}-{text[4:6]}"
        return NormalizedField(
            raw=raw, value=norm, status=NormalizationStatus.CONFIRMED
        )

    # 3. Khớp YYYY-MM-DD hoặc YYYY/MM/DD hoặc YYYYMMDD
    if re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{2}", text):
        norm = text.replace("/", "-")
        try:
            datetime.strptime(norm, "%Y-%m-%d")
            return NormalizedField(
                raw=raw, value=norm, status=NormalizationStatus.CONFIRMED
            )
        except ValueError:
            return NormalizedField(
                raw=raw,
                value=None,
                status=NormalizationStatus.INVALID,
                note=f"Ngày không hợp lệ: {text}",
            )

    if re.fullmatch(r"\d{8}", text):
        norm = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
        try:
            datetime.strptime(norm, "%Y-%m-%d")
            return NormalizedField(
                raw=raw, value=norm, status=NormalizationStatus.CONFIRMED
            )
        except ValueError:
            return NormalizedField(
                raw=raw,
                value=None,
                status=NormalizationStatus.INVALID,
                note=f"Ngày không hợp lệ: {text}",
            )

    # 4. ISO-8601 full timestamp
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return NormalizedField(
            raw=raw,
            value=dt.isoformat(),
            status=NormalizationStatus.CONFIRMED,
        )
    except ValueError:
        pass

    # Nếu không khớp định dạng đã biết -> Chờ xác nhận từ thành viên 1
    return NormalizedField(
        raw=raw,
        value=None,
        status=NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        note="Định dạng ngày chưa có trong danh mục xác nhận (chờ xác nhận từ Thành viên 1)",
    )


def normalize_number(
    raw: Any,
    allow_negative: bool = False,
    as_decimal: bool = False,
) -> NormalizedField[Union[float, Decimal]]:
    """Chuẩn hóa giá trị số (xử lý dấu phẩy phân tách hàng nghìn, kiểm tra hữu hạn)."""
    if raw is None:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Giá trị số bị thiếu",
        )

    if isinstance(raw, bool):
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.INVALID,
            note="Boolean không phải giá trị số hợp lệ",
        )

    try:
        if isinstance(raw, (int, float)):
            val_str = str(raw)
        elif isinstance(raw, Decimal):
            val_str = str(raw)
        elif isinstance(raw, str):
            clean_str = raw.strip().replace(",", "").replace(" ", "")
            if not clean_str:
                return NormalizedField(
                    raw=raw,
                    value=None,
                    status=NormalizationStatus.MISSING,
                    note="Chuỗi số rỗng",
                )
            val_str = clean_str
        else:
            return NormalizedField(
                raw=raw,
                value=None,
                status=NormalizationStatus.INVALID,
                note=f"Kiểu dữ liệu không hỗ trợ: {type(raw).__name__}",
            )

        dec_val = Decimal(val_str)
        if not dec_val.is_finite():
            return NormalizedField(
                raw=raw,
                value=None,
                status=NormalizationStatus.INVALID,
                note="Số không hữu hạn (NaN hoặc Infinity)",
            )

        if not allow_negative and dec_val < 0:
            return NormalizedField(
                raw=raw,
                value=None,
                status=NormalizationStatus.INVALID,
                note="Giá trị số không được âm",
            )

        val_result = dec_val if as_decimal else float(dec_val)
        return NormalizedField(
            raw=raw,
            value=val_result,
            status=NormalizationStatus.CONFIRMED,
        )
    except (InvalidOperation, ValueError, TypeError) as exc:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.INVALID,
            note=f"Không thể chuyển đổi thành số: {exc}",
        )


def normalize_unit(raw: Any) -> NormalizedField[str]:
    """Chuẩn hóa đơn vị đo lường theo danh mục đã được xác nhận (kg, item, %).

    Nếu đơn vị chưa được xác nhận trong tài liệu -> WAITING_CONFIRMATION_MEMBER_1.
    """
    if raw is None:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Đơn vị tính bị thiếu",
        )

    raw_str = str(raw).strip()
    if not raw_str:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Đơn vị tính rỗng",
        )

    key = raw_str.lower()
    if key in CONFIRMED_UNITS:
        return NormalizedField(
            raw=raw,
            value=CONFIRMED_UNITS[key],
            status=NormalizationStatus.CONFIRMED,
        )

    return NormalizedField(
        raw=raw,
        value=None,
        status=NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        note=(
            f"Đơn vị '{raw_str}' chưa được xác nhận trong tài liệu; "
            "chờ xác nhận từ Thành viên 1 (Trần Mai Ngọc Anh)"
        ),
    )


# ---------------------------------------------------------------------------
# 3. Xử lý tiền tệ nhưng không quy đổi nếu thiếu tỷ giá & thời điểm tin cậy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedCurrency:
    """Kết quả chuẩn hóa tiền tệ với truy vết tỷ giá và quy đổi."""

    raw_amount: Any
    raw_currency: Any
    amount: Optional[Decimal]
    currency_code: Optional[str]
    currency_status: NormalizationStatus
    # Kết quả quy đổi (chỉ có khi tỷ giá VÀ thời điểm tỷ giá đáng tin cậy)
    converted_amount: Optional[Decimal]
    target_currency: Optional[str]
    conversion_status: NormalizationStatus
    conversion_note: Optional[str] = None


def normalize_currency(
    amount_raw: Any,
    currency_raw: Any,
    exchange_rate: Optional[Decimal] = None,
    rate_timestamp: Optional[datetime] = None,
    target_currency: Optional[str] = None,
) -> NormalizedCurrency:
    """Xử lý tiền tệ:

    - Chuẩn hóa mã tiền tệ (USD, VND, EUR, JPY) theo ISO 4217.
    - Chuẩn hóa số tiền thành Decimal.
    - KHÔNG quy đổi nếu thiếu tỷ giá hoặc thiếu thời điểm tỷ giá đáng tin cậy.
      Trường hợp thiếu -> converted_amount=None và conversion_status=WAITING_CONFIRMATION_MEMBER_1.
    """
    # 1. Parse amount
    num_res = normalize_number(amount_raw, allow_negative=False, as_decimal=True)
    amount = num_res.value if isinstance(num_res.value, Decimal) else None

    # 2. Parse currency code
    if currency_raw is None or not str(currency_raw).strip():
        currency_code = None
        currency_status = NormalizationStatus.MISSING
    else:
        clean_curr = str(currency_raw).strip().upper()
        clean_curr_key = str(currency_raw).strip().lower()
        if clean_curr in CONFIRMED_CURRENCIES:
            currency_code = CONFIRMED_CURRENCIES[clean_curr]
            currency_status = NormalizationStatus.CONFIRMED
        elif clean_curr_key in CONFIRMED_CURRENCIES:
            currency_code = CONFIRMED_CURRENCIES[clean_curr_key]
            currency_status = NormalizationStatus.CONFIRMED
        else:
            currency_code = None
            currency_status = NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1

    # 3. Xử lý quy đổi tiền tệ
    # Yêu cầu: "Không quy đổi nếu thiếu tỷ giá và thời điểm tỷ giá đáng tin cậy."
    if amount is None or currency_code is None:
        return NormalizedCurrency(
            raw_amount=amount_raw,
            raw_currency=currency_raw,
            amount=amount,
            currency_code=currency_code,
            currency_status=currency_status,
            converted_amount=None,
            target_currency=target_currency,
            conversion_status=NormalizationStatus.MISSING,
            conversion_note="Thiếu số tiền hoặc mã tiền tệ gốc hợp lệ",
        )

    # Nếu không yêu cầu quy đổi hoặc đã cùng loại tiền
    if target_currency is None or target_currency.upper() == currency_code:
        return NormalizedCurrency(
            raw_amount=amount_raw,
            raw_currency=currency_raw,
            amount=amount,
            currency_code=currency_code,
            currency_status=currency_status,
            converted_amount=amount,
            target_currency=currency_code,
            conversion_status=NormalizationStatus.CONFIRMED,
            conversion_note="Không yêu cầu quy đổi (cùng loại tiền tệ)",
        )

    # Nếu yêu cầu quy đổi: BẮT BUỘC có cả tỷ giá hợp lệ VÀ thời điểm tỷ giá
    target_curr_norm = target_currency.upper()
    if (
        exchange_rate is not None
        and exchange_rate > 0
        and rate_timestamp is not None
        and isinstance(rate_timestamp, datetime)
    ):
        try:
            converted = (amount * exchange_rate).quantize(Decimal("0.01"))
            return NormalizedCurrency(
                raw_amount=amount_raw,
                raw_currency=currency_raw,
                amount=amount,
                currency_code=currency_code,
                currency_status=currency_status,
                converted_amount=converted,
                target_currency=target_curr_norm,
                conversion_status=NormalizationStatus.CONFIRMED,
                conversion_note=(
                    f"Quy đổi với tỷ giá {exchange_rate} tại thời điểm "
                    f"{rate_timestamp.isoformat()}"
                ),
            )
        except Exception as exc:
            return NormalizedCurrency(
                raw_amount=amount_raw,
                raw_currency=currency_raw,
                amount=amount,
                currency_code=currency_code,
                currency_status=currency_status,
                converted_amount=None,
                target_currency=target_curr_norm,
                conversion_status=NormalizationStatus.INVALID,
                conversion_note=f"Lỗi tính toán quy đổi: {exc}",
            )

    # Thiếu tỷ giá HOẶC thiếu thời điểm tỷ giá đáng tin cậy -> KHÔNG quy đổi
    return NormalizedCurrency(
        raw_amount=amount_raw,
        raw_currency=currency_raw,
        amount=amount,
        currency_code=currency_code,
        currency_status=currency_status,
        converted_amount=None,
        target_currency=target_curr_norm,
        conversion_status=NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        conversion_note=(
            "Không quy đổi do thiếu tỷ giá hoặc thiếu thời điểm tỷ giá đáng tin cậy "
            "(chờ xác nhận từ Thành viên 1 - Trần Mai Ngọc Anh)"
        ),
    )


# ---------------------------------------------------------------------------
# 4. Chuẩn hóa quốc gia, category và HS code theo danh mục đã được xác nhận
# ---------------------------------------------------------------------------


def normalize_country(raw: Any) -> NormalizedField[str]:
    """Chuẩn hóa quốc gia về mã ISO 3166-1 alpha-3 theo danh mục Bảng 1 (countries).

    Nếu quốc gia chưa có trong danh mục xác nhận -> WAITING_CONFIRMATION_MEMBER_1.
    Không tự suy đoán nếu thiếu.
    """
    if raw is None:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Mã/tên quốc gia bị thiếu",
        )

    raw_str = str(raw).strip()
    if not raw_str:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Mã/tên quốc gia rỗng",
        )

    key = raw_str.upper()
    if key in CONFIRMED_COUNTRIES:
        return NormalizedField(
            raw=raw,
            value=CONFIRMED_COUNTRIES[key],
            status=NormalizationStatus.CONFIRMED,
        )

    return NormalizedField(
        raw=raw,
        value=None,
        status=NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        note=(
            f"Quốc gia '{raw_str}' chưa được xác nhận trong danh mục; "
            "chờ xác nhận từ Thành viên 1 (Trần Mai Ngọc Anh)"
        ),
    )


def normalize_category(raw: Any) -> NormalizedField[str]:
    """Chuẩn hóa dòng sản phẩm về 1 trong 4 danh mục cốt lõi theo Bảng 6 (product_categories):

    - TEA_SET: Bộ ấm chén
    - MUG_CUP: Ly cốc sứ
    - DINNERWARE: Bát đĩa bàn ăn
    - VASE_DECOR: Lọ hoa mỹ nghệ

    Nếu không thuộc 4 danh mục này -> WAITING_CONFIRMATION_MEMBER_1.
    """
    if raw is None:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Dòng sản phẩm bị thiếu",
        )

    raw_str = str(raw).strip()
    if not raw_str:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Dòng sản phẩm rỗng",
        )

    # Chuẩn hóa unicode và lowercase
    key = unicodedata.normalize("NFC", raw_str).lower()
    # Loại bỏ dấu câu thừa
    key_clean = re.sub(r"[^\w\s&]", "", key).strip()

    if key in CONFIRMED_CATEGORIES:
        return NormalizedField(
            raw=raw,
            value=CONFIRMED_CATEGORIES[key],
            status=NormalizationStatus.CONFIRMED,
        )

    if key_clean in CONFIRMED_CATEGORIES:
        return NormalizedField(
            raw=raw,
            value=CONFIRMED_CATEGORIES[key_clean],
            status=NormalizationStatus.CONFIRMED,
        )

    # Tìm kiếm theo từ khóa đã xác nhận
    for pattern, code in CONFIRMED_CATEGORIES.items():
        if pattern in key:
            return NormalizedField(
                raw=raw,
                value=code,
                status=NormalizationStatus.CONFIRMED,
            )

    return NormalizedField(
        raw=raw,
        value=None,
        status=NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        note=(
            f"Dòng sản phẩm '{raw_str}' chưa được xác nhận trong danh mục 4 dòng chủ lực; "
            "chờ xác nhận từ Thành viên 1 (Trần Mai Ngọc Anh)"
        ),
    )


def normalize_hs_code(raw: Any) -> NormalizedField[str]:
    """Chuẩn hóa mã HS về Chương 69 gốm sứ đã xác nhận: '6911', '6912', '6913'.

    Nếu mã HS ngoài danh mục xác nhận -> WAITING_CONFIRMATION_MEMBER_1.
    """
    if raw is None:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Mã HS bị thiếu",
        )

    raw_str = str(raw).strip().replace(".", "").replace(" ", "")
    if not raw_str:
        return NormalizedField(
            raw=raw,
            value=None,
            status=NormalizationStatus.MISSING,
            note="Mã HS rỗng",
        )

    # Lấy 4 chữ số đầu
    prefix_4 = raw_str[:4]
    if prefix_4 in CONFIRMED_HS_CODES:
        return NormalizedField(
            raw=raw,
            value=CONFIRMED_HS_CODES[prefix_4],
            status=NormalizationStatus.CONFIRMED,
        )

    return NormalizedField(
        raw=raw,
        value=None,
        status=NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        note=(
            f"Mã HS '{raw_str}' chưa được xác nhận trong danh mục gốm sứ Chương 69; "
            "chờ xác nhận từ Thành viên 1 (Trần Mai Ngọc Anh)"
        ),
    )


# ---------------------------------------------------------------------------
# 5. Các cấu trúc Normalized Record đầy đủ phục vụ chuyển tiếp ETL
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedTradeRecord:
    """Bản ghi giao thương quốc tế đã được làm sạch và chuẩn hóa."""

    provenance: RecordProvenance
    raw_record: Dict[str, Any]

    reporter_country: NormalizedField[str]
    partner_country: NormalizedField[str]
    hs_code: NormalizedField[str]
    period: NormalizedField[str]
    flow_code: NormalizedField[str]
    net_weight_kg: NormalizedField[float]
    trade_value_usd: NormalizedField[float]
    product_description: NormalizedField[str]


@dataclass(frozen=True)
class NormalizedProductRecord:
    """Bản ghi sản phẩm sàn quốc tế đã chuẩn hóa."""

    provenance: RecordProvenance
    raw_record: Dict[str, Any]

    source_product_id: NormalizedField[str]
    product_name: NormalizedField[str]
    product_url: NormalizedField[str]
    category: NormalizedField[str]
    price: NormalizedCurrency


@dataclass(frozen=True)
class NormalizedReviewRecord:
    """Bản ghi đánh giá sản phẩm đã chuẩn hóa."""

    provenance: RecordProvenance
    raw_record: Dict[str, Any]

    product_reference: NormalizedField[str]
    rating: NormalizedField[int]
    review_text: NormalizedField[str]
    reviewed_at_iso: NormalizedField[str]
    language: NormalizedField[str]


@dataclass(frozen=True)
class NormalizedTrendsRow:
    """Dòng dữ liệu xu hướng Google Trends đã chuẩn hóa."""

    provenance: RecordProvenance
    raw_row: Dict[str, str]

    period_label: NormalizedField[str]
    keyword_scores: Tuple[Tuple[str, NormalizedField[float]], ...]


@dataclass(frozen=True)
class NormalizedDomesticProductRecord:
    """Bản ghi sản phẩm nhà cung cấp nội địa đã chuẩn hóa."""

    provenance: RecordProvenance
    raw_record: Dict[str, Any]

    source_product_id: NormalizedField[str]
    product_name: NormalizedField[str]
    category: NormalizedField[str]
    material: NormalizedField[str]
    origin_region: NormalizedField[str]
    price_vnd: NormalizedField[Decimal]
    moq: NormalizedField[int]
    lead_time_days: NormalizedField[int]
    wholesale_available: NormalizedField[bool]


# ---------------------------------------------------------------------------
# 6. Các hàm Adapter chuẩn hóa từ Parsed Record -> Normalized Record
# ---------------------------------------------------------------------------


def normalize_trade_record(parsed: ParsedTradeRecord) -> NormalizedTradeRecord:
    """Chuẩn hóa một bản ghi ParsedTradeRecord."""
    flow = parsed.flow_code.upper() if parsed.flow_code else None
    flow_field: NormalizedField[str]
    if flow in ("M", "IMPORT"):
        flow_field = NormalizedField(parsed.flow_code, "Import", NormalizationStatus.CONFIRMED)
    elif flow in ("X", "EXPORT"):
        flow_field = NormalizedField(parsed.flow_code, "Export", NormalizationStatus.CONFIRMED)
    elif flow is None:
        flow_field = NormalizedField(None, None, NormalizationStatus.MISSING)
    else:
        flow_field = NormalizedField(
            parsed.flow_code,
            None,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
            note="Luồng thương mại chưa được xác nhận",
        )

    return NormalizedTradeRecord(
        provenance=parsed.provenance,
        raw_record=parsed.raw_record,
        reporter_country=normalize_country(parsed.reporter_code or parsed.reporter_name),
        partner_country=normalize_country(parsed.partner_code or parsed.partner_name),
        hs_code=normalize_hs_code(parsed.hs_code),
        period=normalize_date(parsed.period),
        flow_code=flow_field,
        net_weight_kg=normalize_number(parsed.net_weight_kg),
        trade_value_usd=normalize_number(parsed.trade_value_usd),
        product_description=normalize_text(parsed.product_description),
    )


def normalize_product_record(parsed: ParsedProductRecord) -> NormalizedProductRecord:
    """Chuẩn hóa một bản ghi ParsedProductRecord."""
    first_price = parsed.prices[0] if parsed.prices else None
    if first_price:
        curr = normalize_currency(first_price.amount_str, first_price.currency_code)
    else:
        curr = normalize_currency(None, None)

    return NormalizedProductRecord(
        provenance=parsed.provenance,
        raw_record=parsed.raw_record,
        source_product_id=normalize_text(parsed.source_product_id),
        product_name=normalize_text(parsed.name),
        product_url=normalize_text(parsed.product_url),
        category=normalize_category(parsed.category),
        price=curr,
    )


def normalize_review_record(parsed: ParsedReviewRecord) -> NormalizedReviewRecord:
    """Chuẩn hóa một bản ghi ParsedReviewRecord."""
    rating_field: NormalizedField[int]
    if parsed.rating is not None and 1 <= parsed.rating <= 5:
        rating_field = NormalizedField(parsed.rating, parsed.rating, NormalizationStatus.CONFIRMED)
    elif parsed.rating is None:
        rating_field = NormalizedField(None, None, NormalizationStatus.MISSING)
    else:
        rating_field = NormalizedField(
            parsed.rating,
            None,
            NormalizationStatus.INVALID,
            note="Số sao phải từ 1 đến 5",
        )

    return NormalizedReviewRecord(
        provenance=parsed.provenance,
        raw_record=parsed.raw_record,
        product_reference=normalize_text(parsed.product_reference),
        rating=rating_field,
        review_text=normalize_text(parsed.review_text),
        reviewed_at_iso=normalize_date(parsed.reviewed_at_iso),
        language=normalize_text(parsed.language),
    )


def normalize_trends_row(parsed: ParsedTrendsRow) -> NormalizedTrendsRow:
    """Chuẩn hóa một dòng ParsedTrendsRow."""
    keyword_scores = tuple(
        (kw, normalize_number(score_str))
        for kw, score_str in parsed.keyword_values
    )
    return NormalizedTrendsRow(
        provenance=parsed.provenance,
        raw_row=parsed.raw_row,
        period_label=normalize_date(parsed.period_label),
        keyword_scores=keyword_scores,
    )


def normalize_domestic_product(parsed: ParsedDomesticProductRecord) -> NormalizedDomesticProductRecord:
    """Chuẩn hóa một bản ghi ParsedDomesticProductRecord."""
    comm = parsed.commercial

    # Price VND
    price_field = normalize_number(comm.price_vnd_str, as_decimal=True)

    # MOQ
    moq_num = normalize_number(comm.moq)
    moq_field: NormalizedField[int] = NormalizedField(
        raw=comm.moq,
        value=int(moq_num.value) if moq_num.value is not None else None,
        status=moq_num.status,
        note=moq_num.note,
    )

    # Lead time
    lt_num = normalize_number(comm.lead_time_days)
    lt_field: NormalizedField[int] = NormalizedField(
        raw=comm.lead_time_days,
        value=int(lt_num.value) if lt_num.value is not None else None,
        status=lt_num.status,
        note=lt_num.note,
    )

    # Wholesale
    ws_field: NormalizedField[bool]
    if comm.wholesale_available is None:
        ws_field = NormalizedField(None, None, NormalizationStatus.MISSING)
    elif isinstance(comm.wholesale_available, bool):
        ws_field = NormalizedField(
            comm.wholesale_available,
            comm.wholesale_available,
            NormalizationStatus.CONFIRMED,
        )
    else:
        ws_field = NormalizedField(
            comm.wholesale_available,
            None,
            NormalizationStatus.INVALID,
            note="wholesale_available phải là boolean",
        )

    return NormalizedDomesticProductRecord(
        provenance=parsed.provenance,
        raw_record=parsed.raw_record,
        source_product_id=normalize_text(parsed.source_product_id),
        product_name=normalize_text(parsed.name),
        category=normalize_category(parsed.category),
        material=normalize_text(parsed.material),
        origin_region=normalize_text(parsed.origin_region),
        price_vnd=price_field,
        moq=moq_field,
        lead_time_days=lt_field,
        wholesale_available=ws_field,
    )
