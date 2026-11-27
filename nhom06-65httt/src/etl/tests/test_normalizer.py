"""Unit tests for D11 — Cleaning and normalization layer."""

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from etl.normalizer import (
    NormalizationStatus,
    NormalizedField,
    normalize_category,
    normalize_country,
    normalize_currency,
    normalize_date,
    normalize_domestic_product,
    normalize_hs_code,
    normalize_number,
    normalize_product_record,
    normalize_review_record,
    normalize_text,
    normalize_trade_record,
    normalize_trends_row,
    normalize_unit,
)
from etl.parsed_record import (
    ParsedCommercialInfo,
    ParsedDomesticProductRecord,
    ParsedPriceInfo,
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedTradeRecord,
    ParsedTrendsRow,
    RecordProvenance,
)


class NormalizeTextTests(unittest.TestCase):
    """Yêu cầu 1: Chuẩn hóa khoảng trắng, chuỗi và ký tự."""

    def test_strip_and_collapse_whitespace(self):
        raw = "  Bộ   ấm\t\nchén   gốm   sứ  "
        res = normalize_text(raw)
        self.assertEqual(res.value, "Bộ ấm chén gốm sứ")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)
        self.assertEqual(res.raw, raw)

    def test_unicode_nfc_normalization(self):
        # NFD: e + combining acute accent -> NFC: é
        decomposed = "g\u006f\u0301m"  # g + o + acute accent
        res = normalize_text(decomposed)
        self.assertEqual(res.value, "góm")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

    def test_strip_control_characters(self):
        raw_with_ctrl = "Sản phẩm\x00 gốm\x1f sứ\x08 cao cấp"
        res = normalize_text(raw_with_ctrl)
        self.assertEqual(res.value, "Sản phẩm gốm sứ cao cấp")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

    def test_none_input_gives_missing_status(self):
        # Yêu cầu 6: Không tự suy đoán giá trị bị thiếu
        res = normalize_text(None)
        self.assertIsNone(res.value)
        self.assertEqual(res.status, NormalizationStatus.MISSING)
        self.assertIsNone(res.raw)

    def test_empty_string_gives_missing_status(self):
        res = normalize_text("   \t  \n  ")
        self.assertIsNone(res.value)
        self.assertEqual(res.status, NormalizationStatus.MISSING)

    def test_non_string_converted_cleanly(self):
        res = normalize_text(12345)
        self.assertEqual(res.value, "12345")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)


class NormalizeDateAndNumberTests(unittest.TestCase):
    """Yêu cầu 2: Chuẩn hóa ngày tháng, số và đơn vị đo."""

    def test_normalize_month_period_boundaries(self):
        for raw, expected in (
            ("2025-01", "2025-01"),
            ("2025-12", "2025-12"),
            ("202501", "2025-01"),
            ("202512", "2025-12"),
            ("2025/01", "2025-01"),
            ("1900-01", "1900-01"),
            ("2100-12", "2100-12"),
        ):
            with self.subTest(raw=raw):
                result = normalize_date(raw)
                self.assertEqual(result.value, expected)
                self.assertEqual(result.status, NormalizationStatus.CONFIRMED)
                self.assertEqual(result.raw, raw)

        for raw in (
            "2025-13",
            "2025-00",
            "202513",
            "202500",
            "1899-12",
            "2101-01",
            "2025/13",
            "2025/01-15",
        ):
            with self.subTest(raw=raw):
                result = normalize_date(raw)
                self.assertIsNone(result.value)
                self.assertEqual(result.status, NormalizationStatus.INVALID)
                self.assertEqual(result.raw, raw)

    def test_normalize_date_rejects_out_of_range_years_and_invalid_months(self):
        for raw in (
            "1899",
            "2101",
            "2025-13-01",
            "2025/00/01",
            "20251301",
            "1899-12-31",
            "2101-01-01T00:00:00Z",
            "2025-02-29",
            2025.5,
            float("nan"),
            int(datetime(2101, 1, 1, tzinfo=timezone.utc).timestamp()),
        ):
            with self.subTest(raw=raw):
                result = normalize_date(raw)
                self.assertIsNone(result.value)
                self.assertEqual(result.status, NormalizationStatus.INVALID)

        unicode_digits = normalize_date("٢٠٢٥-٠١")
        self.assertNotEqual(unicode_digits.status, NormalizationStatus.CONFIRMED)

        leap_day = normalize_date("2024-02-29")
        self.assertEqual(leap_day.value, "2024-02-29")
        self.assertEqual(leap_day.status, NormalizationStatus.CONFIRMED)

    def test_normalize_date_iso_and_year(self):
        # YYYY
        res = normalize_date("2022")
        self.assertEqual(res.value, "2022")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

        # YYYY-MM
        res = normalize_date("2023/10")
        self.assertEqual(res.value, "2023-10")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

        # YYYYMM
        res = normalize_date("202310")
        self.assertEqual(res.value, "2023-10")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

        # YYYY-MM-DD
        res = normalize_date("2023/11/15")
        self.assertEqual(res.value, "2023-11-15")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

        # YYYYMMDD
        res = normalize_date("20231115")
        self.assertEqual(res.value, "2023-11-15")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

        # datetime object
        dt = datetime(2023, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
        res = normalize_date(dt)
        self.assertEqual(res.value, dt.isoformat())
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

        # date object
        d = date(2023, 11, 15)
        res = normalize_date(d)
        self.assertEqual(res.value, "2023-11-15")
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

        # Unix timestamp int
        res = normalize_date(1700000000)
        self.assertIn("2023", res.value)
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

    def test_normalize_date_missing_and_invalid(self):
        res_none = normalize_date(None)
        self.assertIsNone(res_none.value)
        self.assertEqual(res_none.status, NormalizationStatus.MISSING)

        # Invalid date
        res_inv = normalize_date("2023-02-30")
        self.assertIsNone(res_inv.value)
        self.assertEqual(res_inv.status, NormalizationStatus.INVALID)

        # Invalid YYYYMMDD date
        res_inv8 = normalize_date("20230230")
        self.assertIsNone(res_inv8.value)
        self.assertEqual(res_inv8.status, NormalizationStatus.INVALID)

        # Empty/whitespace string -> MISSING
        res_blank = normalize_date("   ")
        self.assertIsNone(res_blank.value)
        self.assertEqual(res_blank.status, NormalizationStatus.MISSING)

        # Naive datetime -> assumes UTC
        naive_dt = datetime(2023, 11, 15, 12, 0, 0)
        res_naive = normalize_date(naive_dt)
        self.assertEqual(res_naive.value, "2023-11-15T12:00:00+00:00")
        self.assertEqual(res_naive.status, NormalizationStatus.CONFIRMED)

        # ISO-8601 with trailing Z
        res_z = normalize_date("2023-11-15T08:00:00Z")
        self.assertEqual(res_z.value, "2023-11-15T08:00:00+00:00")
        self.assertEqual(res_z.status, NormalizationStatus.CONFIRMED)

        # Int year & out-of-range timestamp & unsupported type
        res_int_yr = normalize_date(2022)
        self.assertEqual(res_int_yr.value, "2022")
        self.assertEqual(res_int_yr.status, NormalizationStatus.CONFIRMED)

        res_big_ts = normalize_date(10**20)
        self.assertIsNone(res_big_ts.value)
        self.assertEqual(res_big_ts.status, NormalizationStatus.INVALID)

        res_bad_type = normalize_date(["2023-01-01"])
        self.assertIsNone(res_bad_type.value)
        self.assertEqual(res_bad_type.status, NormalizationStatus.INVALID)

        # Unconfirmed format
        res_unconfirmed = normalize_date("Hôm qua")
        self.assertIsNone(res_unconfirmed.value)
        self.assertEqual(
            res_unconfirmed.status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )

    def test_normalize_number_formats(self):
        # String with commas
        res = normalize_number(" 145,230,000.50 ")
        self.assertAlmostEqual(res.value, 145230000.50)
        self.assertEqual(res.status, NormalizationStatus.CONFIRMED)

        # As Decimal
        res_dec = normalize_number("48.99", as_decimal=True)
        self.assertEqual(res_dec.value, Decimal("48.99"))
        self.assertEqual(res_dec.status, NormalizationStatus.CONFIRMED)

        # Int & float
        self.assertEqual(normalize_number(100).value, 100.0)
        self.assertEqual(normalize_number(12.5).value, 12.5)

        # Missing
        res_none = normalize_number(None)
        self.assertIsNone(res_none.value)
        self.assertEqual(res_none.status, NormalizationStatus.MISSING)

        # Invalid boolean
        res_bool = normalize_number(True)
        self.assertIsNone(res_bool.value)
        self.assertEqual(res_bool.status, NormalizationStatus.INVALID)

        # Negative when not allowed
        res_neg = normalize_number("-50.0", allow_negative=False)
        self.assertIsNone(res_neg.value)
        self.assertEqual(res_neg.status, NormalizationStatus.INVALID)

        # Negative when allowed
        res_neg_allowed = normalize_number("-50.0", allow_negative=True)
        self.assertEqual(res_neg_allowed.value, -50.0)
        self.assertEqual(res_neg_allowed.status, NormalizationStatus.CONFIRMED)

        # Decimal input, whitespace string, NaN/Inf, invalid string, unsupported type
        self.assertEqual(normalize_number(Decimal("12.34"), as_decimal=True).value, Decimal("12.34"))
        self.assertEqual(normalize_number("   ").status, NormalizationStatus.MISSING)
        self.assertEqual(normalize_number(float("nan")).status, NormalizationStatus.INVALID)
        self.assertEqual(normalize_number(float("inf")).status, NormalizationStatus.INVALID)
        self.assertEqual(normalize_number("not-a-num").status, NormalizationStatus.INVALID)
        self.assertEqual(normalize_number([1, 2]).status, NormalizationStatus.INVALID)

    def test_normalize_unit(self):
        # Confirmed units
        self.assertEqual(normalize_unit("kg").value, "kg")
        self.assertEqual(normalize_unit("kilograms").value, "kg")
        self.assertEqual(normalize_unit("KGS").value, "kg")
        self.assertEqual(normalize_unit("Number of items").value, "item")
        self.assertEqual(normalize_unit("pcs").value, "item")
        self.assertEqual(normalize_unit("Sản phẩm").value, "item")
        self.assertEqual(normalize_unit("%").value, "%")

        # Missing / blank unit
        res_none = normalize_unit(None)
        self.assertIsNone(res_none.value)
        self.assertEqual(res_none.status, NormalizationStatus.MISSING)
        self.assertEqual(normalize_unit("   ").status, NormalizationStatus.MISSING)

        # Unconfirmed unit -> WAITING_CONFIRMATION_MEMBER_1
        res_unconfirmed = normalize_unit("thùng gỗ")
        self.assertIsNone(res_unconfirmed.value)
        self.assertEqual(
            res_unconfirmed.status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )


class NormalizeCurrencyTests(unittest.TestCase):
    """Yêu cầu 3: Xử lý tiền tệ nhưng không quy đổi nếu thiếu tỷ giá và thời điểm tỷ giá."""

    def test_currency_code_normalization(self):
        curr = normalize_currency("100.0", "usd")
        self.assertEqual(curr.currency_code, "USD")
        self.assertEqual(curr.amount, Decimal("100.0"))
        self.assertEqual(curr.currency_status, NormalizationStatus.CONFIRMED)

        curr_vnd = normalize_currency("450000", "đ")
        self.assertEqual(curr_vnd.currency_code, "VND")
        self.assertEqual(curr_vnd.amount, Decimal("450000"))
        self.assertEqual(curr_vnd.currency_status, NormalizationStatus.CONFIRMED)

    def test_no_conversion_when_target_is_same_or_none(self):
        curr = normalize_currency("50.0", "USD", target_currency="USD")
        self.assertEqual(curr.converted_amount, Decimal("50.0"))
        self.assertEqual(curr.conversion_status, NormalizationStatus.CONFIRMED)

    def test_no_conversion_if_rate_or_timestamp_missing(self):
        # Thiếu tỷ giá
        curr_no_rate = normalize_currency(
            amount_raw="450000",
            currency_raw="VND",
            target_currency="USD",
            exchange_rate=None,
            rate_timestamp=datetime.now(timezone.utc),
        )
        self.assertIsNone(curr_no_rate.converted_amount)
        self.assertEqual(
            curr_no_rate.conversion_status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )

        # Thiếu thời điểm tỷ giá
        curr_no_ts = normalize_currency(
            amount_raw="450000",
            currency_raw="VND",
            target_currency="USD",
            exchange_rate=Decimal("0.00004"),
            rate_timestamp=None,
        )
        self.assertIsNone(curr_no_ts.converted_amount)
        self.assertEqual(
            curr_no_ts.conversion_status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )

    def test_conversion_succeeds_when_both_rate_and_timestamp_present(self):
        rate_time = datetime(2023, 11, 15, 8, 0, 0, tzinfo=timezone.utc)
        curr = normalize_currency(
            amount_raw="450000",
            currency_raw="VND",
            target_currency="USD",
            exchange_rate=Decimal("0.00004"),
            rate_timestamp=rate_time,
        )
        self.assertEqual(curr.amount, Decimal("450000"))
        self.assertEqual(curr.converted_amount, Decimal("18.00"))
        self.assertEqual(curr.conversion_status, NormalizationStatus.CONFIRMED)

    def test_unconfirmed_currency_code(self):
        curr = normalize_currency("100", "XYZ")
        self.assertIsNone(curr.currency_code)
        self.assertEqual(
            curr.currency_status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )

    def test_currency_edge_cases_zero_missing_and_invalid_rate(self):
        # Zero amount is valid
        curr_zero = normalize_currency("0", "$")
        self.assertEqual(curr_zero.amount, Decimal("0"))
        self.assertEqual(curr_zero.currency_code, "USD")
        self.assertEqual(curr_zero.currency_status, NormalizationStatus.CONFIRMED)

        # Missing currency or missing amount -> conversion_status=MISSING
        curr_no_curr = normalize_currency("100", None)
        self.assertIsNone(curr_no_curr.currency_code)
        self.assertEqual(curr_no_curr.currency_status, NormalizationStatus.MISSING)
        self.assertEqual(curr_no_curr.conversion_status, NormalizationStatus.MISSING)

        curr_no_amt = normalize_currency(None, "EUR")
        self.assertIsNone(curr_no_amt.amount)
        self.assertEqual(curr_no_amt.currency_code, "EUR")
        self.assertEqual(curr_no_amt.conversion_status, NormalizationStatus.MISSING)

        # Zero / negative exchange_rate or non-datetime timestamp -> NO conversion
        curr_zero_rate = normalize_currency(
            "450000",
            "VND",
            target_currency="USD",
            exchange_rate=Decimal("0"),
            rate_timestamp=datetime.now(timezone.utc),
        )
        self.assertIsNone(curr_zero_rate.converted_amount)
        self.assertEqual(
            curr_zero_rate.conversion_status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )

        curr_bad_ts = normalize_currency(
            "450000",
            "VND",
            target_currency="USD",
            exchange_rate=Decimal("0.00004"),
            rate_timestamp="2023-11-15",  # type: ignore[arg-type]
        )
        self.assertIsNone(curr_bad_ts.converted_amount)
        self.assertEqual(
            curr_bad_ts.conversion_status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )


class NormalizeCountryCategoryHSTests(unittest.TestCase):
    """Yêu cầu 4: Chuẩn hóa quốc gia, category và HS code theo danh mục đã được xác nhận."""

    def test_normalize_country_confirmed(self):
        self.assertEqual(normalize_country("USA").value, "USA")
        self.assertEqual(normalize_country("US").value, "USA")
        self.assertEqual(normalize_country("842").value, "USA")
        self.assertEqual(normalize_country("United States").value, "USA")
        self.assertEqual(normalize_country("Hoa Kỳ").value, "USA")

        self.assertEqual(normalize_country("VNM").value, "VNM")
        self.assertEqual(normalize_country("704").value, "VNM")
        self.assertEqual(normalize_country("Việt Nam").value, "VNM")

        self.assertEqual(normalize_country("JPN").value, "JPN")
        self.assertEqual(normalize_country("DEU").value, "DEU")
        self.assertEqual(normalize_country("CHN").value, "CHN")
        self.assertEqual(normalize_country("FRA").value, "FRA")
        self.assertEqual(normalize_country("IND").value, "IND")
        self.assertEqual(normalize_country("0").value, "WLD")

    def test_normalize_country_unconfirmed(self):
        res = normalize_country("Atlantis")
        self.assertIsNone(res.value)
        self.assertEqual(
            res.status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )

        res_none = normalize_country(None)
        self.assertIsNone(res_none.value)
        self.assertEqual(res_none.status, NormalizationStatus.MISSING)

    def test_normalize_category_confirmed_4_lines(self):
        # 1. TEA_SET
        self.assertEqual(normalize_category("Bộ ấm chén").value, "TEA_SET")
        self.assertEqual(normalize_category("Ceramic Tea Set").value, "TEA_SET")
        self.assertEqual(normalize_category("Ấm trà gốm").value, "TEA_SET")

        # 2. MUG_CUP
        self.assertEqual(normalize_category("Ly cốc sứ").value, "MUG_CUP")
        self.assertEqual(normalize_category("Ceramic Mug & Cup").value, "MUG_CUP")
        self.assertEqual(normalize_category("Cốc").value, "MUG_CUP")

        # 3. DINNERWARE
        self.assertEqual(normalize_category("Bát đĩa bàn ăn").value, "DINNERWARE")
        self.assertEqual(normalize_category("Dinnerware Set").value, "DINNERWARE")
        self.assertEqual(normalize_category("Bộ chén cơm").value, "DINNERWARE")
        self.assertEqual(normalize_category("Serving Bowl").value, "DINNERWARE")

        # 4. VASE_DECOR
        self.assertEqual(normalize_category("Lọ hoa mỹ nghệ").value, "VASE_DECOR")
        self.assertEqual(normalize_category("Decorative Vase").value, "VASE_DECOR")
        self.assertEqual(normalize_category("Bình hoa").value, "VASE_DECOR")

    def test_normalize_category_unconfirmed(self):
        res = normalize_category("Đồ chơi trẻ em")
        self.assertIsNone(res.value)
        self.assertEqual(
            res.status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )

        res_none = normalize_category(None)
        self.assertIsNone(res_none.value)
        self.assertEqual(res_none.status, NormalizationStatus.MISSING)

    def test_normalize_hs_code_confirmed_chapter_69(self):
        self.assertEqual(normalize_hs_code("6911").value, "6911")
        self.assertEqual(normalize_hs_code("6911.10.00").value, "6911")
        self.assertEqual(normalize_hs_code("6912").value, "6912")
        self.assertEqual(normalize_hs_code("6913").value, "6913")

    def test_normalize_hs_code_unconfirmed(self):
        # Mã ngoài 6911, 6912, 6913
        res = normalize_hs_code("8471")
        self.assertIsNone(res.value)
        self.assertEqual(
            res.status,
            NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
        )

        res_none = normalize_hs_code(None)
        self.assertIsNone(res_none.value)
        self.assertEqual(res_none.status, NormalizationStatus.MISSING)

    def test_country_category_hs_whitespace_and_boundary_cases(self):
        # Whitespace-only -> MISSING
        self.assertEqual(normalize_country("   ").status, NormalizationStatus.MISSING)
        self.assertEqual(normalize_category("   ").status, NormalizationStatus.MISSING)
        self.assertEqual(normalize_hs_code(" . . ").status, NormalizationStatus.MISSING)

        # Category punctuation cleanup
        self.assertEqual(normalize_category("Tea Set!").value, "TEA_SET")

        # HS code with spaces and truncated 2-digit HS code
        self.assertEqual(normalize_hs_code("6911 10 00").value, "6911")
        res_short = normalize_hs_code("69")
        self.assertIsNone(res_short.value)
        self.assertEqual(res_short.status, NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1)


class NormalizeRecordAdaptersTests(unittest.TestCase):
    """Yêu cầu 5 & 6: Giữ raw value và normalized value, không suy đoán giá trị thiếu."""

    def setUp(self):
        self.provenance = RecordProvenance(
            source_id="test_source",
            raw_collection_id="11223344" * 4,
            collected_at_iso="2026-01-01T00:00:00+00:00",
            source_url="https://example.invalid",
        )

    def test_normalize_trade_record(self):
        raw_dict = {
            "cmdCode": "6911",
            "reporterCode": "842",
            "partnerCode": "704",
            "flowCode": "M",
            "netWgt": 12.5,
            "primaryValue": 20.0,
            "cmdDesc": "  Porcelain tableware  ",
        }
        parsed = ParsedTradeRecord(
            provenance=self.provenance,
            raw_record=raw_dict,
            reporter_code="842",
            partner_code="704",
            hs_code="6911",
            period="2022",
            flow_code="M",
            net_weight_kg=12.5,
            trade_value_usd=20.0,
            reporter_name=None,
            partner_name=None,
            product_description="  Porcelain tableware  ",
        )
        norm = normalize_trade_record(parsed)

        # Traceability: Raw record and provenance kept intact
        self.assertEqual(norm.provenance, self.provenance)
        self.assertEqual(norm.raw_record, raw_dict)

        # Fields normalized
        self.assertEqual(norm.reporter_country.value, "USA")
        self.assertEqual(norm.partner_country.value, "VNM")
        self.assertEqual(norm.hs_code.value, "6911")
        self.assertEqual(norm.period.value, "2022")
        self.assertEqual(norm.flow_code.value, "Import")
        self.assertEqual(norm.net_weight_kg.value, 12.5)
        self.assertEqual(norm.trade_value_usd.value, 20.0)
        self.assertEqual(norm.product_description.value, "Porcelain tableware")

    def test_normalize_product_record(self):
        raw_dict = {"listing_id": 123456, "title": "  White Vase  "}
        parsed = ParsedProductRecord(
            provenance=self.provenance,
            raw_record=raw_dict,
            source_product_id="123456",
            product_url="https://example.invalid/p/1",
            name="  White Vase  ",
            category="Bình hoa",
            category_id="4321",
            prices=(
                ParsedPriceInfo(
                    amount_str="24.99",
                    currency_code="USD",
                    basis="minimum_listing_price",
                ),
            ),
        )
        norm = normalize_product_record(parsed)

        self.assertEqual(norm.source_product_id.value, "123456")
        self.assertEqual(norm.product_name.value, "White Vase")
        self.assertEqual(norm.category.value, "VASE_DECOR")
        self.assertEqual(norm.price.amount, Decimal("24.99"))
        self.assertEqual(norm.price.currency_code, "USD")

    def test_normalize_review_record(self):
        raw_dict = {"listing_id": 123, "rating": 5, "review": "  Tuyệt vời!  "}
        parsed = ParsedReviewRecord(
            provenance=self.provenance,
            raw_record=raw_dict,
            product_reference="123",
            rating=5,
            review_text="  Tuyệt vời!  ",
            reviewed_at_iso="2023-11-15T08:00:00+00:00",
            language="vi",
        )
        norm = normalize_review_record(parsed)

        self.assertEqual(norm.product_reference.value, "123")
        self.assertEqual(norm.rating.value, 5)
        self.assertEqual(norm.review_text.value, "Tuyệt vời!")
        self.assertEqual(norm.reviewed_at_iso.value, "2023-11-15T08:00:00+00:00")

    def test_normalize_trends_row(self):
        raw_dict = {"week": "2023-10-01", "ceramic_mug": "84"}
        parsed = ParsedTrendsRow(
            provenance=self.provenance,
            raw_row=raw_dict,
            period_label="2023-10-01",
            keyword_values=(("ceramic_mug", "84"),),
        )
        norm = normalize_trends_row(parsed)

        self.assertEqual(norm.period_label.value, "2023-10-01")
        self.assertEqual(norm.keyword_scores[0][0], "ceramic_mug")
        self.assertEqual(norm.keyword_scores[0][1].value, 84.0)

    def test_normalize_domestic_product(self):
        raw_dict = {"source_product_id": "ML-01", "name": "Bộ ấm chén"}
        parsed = ParsedDomesticProductRecord(
            provenance=self.provenance,
            raw_record=raw_dict,
            source_product_id="ML-01",
            product_url=None,
            name="  Bộ ấm chén Minh Long  ",
            description=None,
            category="Bộ ấm chén",
            material="Sứ cao cấp",
            origin_region="Bình Dương",
            commercial=ParsedCommercialInfo(
                price_vnd_str="450000",
                currency="VND",
                moq=100,
                lead_time_days=14,
                wholesale_available=True,
            ),
        )
        norm = normalize_domestic_product(parsed)

        self.assertEqual(norm.source_product_id.value, "ML-01")
        self.assertEqual(norm.product_name.value, "Bộ ấm chén Minh Long")
        self.assertEqual(norm.category.value, "TEA_SET")
        self.assertEqual(norm.price_vnd.value, Decimal("450000"))
        self.assertEqual(norm.moq.value, 100)
        self.assertEqual(norm.lead_time_days.value, 14)
        self.assertTrue(norm.wholesale_available.value)

    def test_adapters_missing_and_edge_branches(self):
        # Trade record: Export flow, missing flow, unconfirmed flow, reporter_name fallback
        trade_export = ParsedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_code=None,
            partner_code=None,
            hs_code=None,
            period=None,
            flow_code="X",
            net_weight_kg=None,
            trade_value_usd=None,
            reporter_name="Viet Nam",
            partner_name=None,
            product_description=None,
        )
        norm_export = normalize_trade_record(trade_export)
        self.assertEqual(norm_export.reporter_country.value, "VNM")
        self.assertEqual(norm_export.flow_code.value, "Export")
        self.assertEqual(norm_export.partner_country.status, NormalizationStatus.MISSING)

        trade_unknown_flow = ParsedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_code=None,
            partner_code=None,
            hs_code=None,
            period=None,
            flow_code="REEXPORT",
            net_weight_kg=None,
            trade_value_usd=None,
            reporter_name=None,
            partner_name=None,
            product_description=None,
        )
        norm_unk = normalize_trade_record(trade_unknown_flow)
        self.assertEqual(norm_unk.flow_code.status, NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1)

        # Product record with empty prices tuple
        prod_no_price = ParsedProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id="P-0",
            product_url=None,
            name=None,
            category=None,
            category_id=None,
            prices=(),
        )
        norm_prod = normalize_product_record(prod_no_price)
        self.assertIsNone(norm_prod.price.amount)
        self.assertEqual(norm_prod.price.currency_status, NormalizationStatus.MISSING)

        # Review record: invalid rating (0 and 6) and missing rating (None)
        rev_invalid = ParsedReviewRecord(
            provenance=self.provenance,
            raw_record={},
            product_reference="123",
            rating=6,
            review_text=None,
            reviewed_at_iso=None,
            language=None,
        )
        norm_rev_inv = normalize_review_record(rev_invalid)
        self.assertIsNone(norm_rev_inv.rating.value)
        self.assertEqual(norm_rev_inv.rating.status, NormalizationStatus.INVALID)

        rev_missing = ParsedReviewRecord(
            provenance=self.provenance,
            raw_record={},
            product_reference="123",
            rating=None,  # type: ignore[arg-type]
            review_text=None,
            reviewed_at_iso=None,
            language=None,
        )
        norm_rev_miss = normalize_review_record(rev_missing)
        self.assertEqual(norm_rev_miss.rating.status, NormalizationStatus.MISSING)

        # Domestic product: all optional commercial fields None + invalid wholesale_available type
        dom_missing = ParsedDomesticProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id="D-0",
            product_url=None,
            name=None,
            description=None,
            category=None,
            material=None,
            origin_region=None,
            commercial=ParsedCommercialInfo(
                price_vnd_str=None,
                currency=None,
                moq=None,
                lead_time_days=None,
                wholesale_available="yes",  # type: ignore[arg-type]
            ),
        )
        norm_dom = normalize_domestic_product(dom_missing)
        self.assertEqual(norm_dom.price_vnd.status, NormalizationStatus.MISSING)
        self.assertEqual(norm_dom.moq.status, NormalizationStatus.MISSING)
        self.assertEqual(norm_dom.lead_time_days.status, NormalizationStatus.MISSING)
        self.assertEqual(norm_dom.wholesale_available.status, NormalizationStatus.INVALID)


if __name__ == "__main__":
    unittest.main()
