"""Unit tests for D12 — Data quality validation layer."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from etl.normalizer import (
    NormalizationStatus,
    NormalizedCurrency,
    NormalizedDomesticProductRecord,
    NormalizedField,
    NormalizedProductRecord,
    NormalizedReviewRecord,
    NormalizedTradeRecord,
    NormalizedTrendsRow,
)
from etl.parsed_record import RecordProvenance
from etl.quality_validator import (
    DataQualityValidator,
    DomesticProductQualityValidator,
    MarketProductQualityValidator,
    ReviewQualityValidator,
    SearchTrendsQualityValidator,
    TradeQualityValidator,
    ValidationIssueCode,
    ValidationSeverity,
)


class BaseQualityValidatorTest(unittest.TestCase):
    def setUp(self):
        self.provenance = RecordProvenance(
            source_id="test_source",
            raw_collection_id="11223344" * 4,
            collected_at_iso="2026-01-01T00:00:00+00:00",
            source_url="https://example.invalid",
        )


class RequiredFieldsValidationTests(BaseQualityValidatorTest):
    """Yêu cầu 1: Kiểm tra trường bắt buộc."""

    def test_trade_missing_required_fields_fails(self):
        # Missing reporter_country and trade_value_usd
        rec = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField(None, None, NormalizationStatus.MISSING),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(None, None, NormalizationStatus.MISSING),
            product_description=NormalizedField("Desc", "Desc", NormalizationStatus.CONFIRMED),
        )
        res = TradeQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        error_fields = [e.field_name for e in res.errors]
        self.assertIn("reporter_country", error_fields)
        self.assertIn("trade_value_usd", error_fields)
        self.assertTrue(all(e.code == ValidationIssueCode.MISSING_REQUIRED_FIELD for e in res.errors))

    def test_product_missing_name_and_price_fails(self):
        rec = NormalizedProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id=NormalizedField("P1", "P1", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField("", None, NormalizationStatus.MISSING),
            product_url=NormalizedField("url", "url", NormalizationStatus.CONFIRMED),
            category=NormalizedField("Bát đĩa", "DINNERWARE", NormalizationStatus.CONFIRMED),
            price=NormalizedCurrency(
                raw_amount=None,
                raw_currency=None,
                amount=None,
                currency_code=None,
                currency_status=NormalizationStatus.MISSING,
                converted_amount=None,
                target_currency=None,
                conversion_status=NormalizationStatus.MISSING,
            ),
        )
        res = MarketProductQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        error_fields = [e.field_name for e in res.errors]
        self.assertIn("product_name", error_fields)
        self.assertIn("price_usd", error_fields)

    def test_review_missing_rating_fails(self):
        rec = NormalizedReviewRecord(
            provenance=self.provenance,
            raw_record={},
            product_reference=NormalizedField("P1", "P1", NormalizationStatus.CONFIRMED),
            rating=NormalizedField(None, None, NormalizationStatus.MISSING),
            review_text=NormalizedField("Tốt", "Tốt", NormalizationStatus.CONFIRMED),
            reviewed_at_iso=NormalizedField(
                "2023-11-15T00:00:00+00:00",
                "2023-11-15T00:00:00+00:00",
                NormalizationStatus.CONFIRMED,
            ),
            language=NormalizedField("vi", "vi", NormalizationStatus.CONFIRMED),
        )
        res = ReviewQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.errors[0].field_name, "rating_stars")


class DataTypeValidationTests(BaseQualityValidatorTest):
    """Yêu cầu 2: Kiểm tra kiểu dữ liệu."""

    def test_invalid_numeric_data_type_fails(self):
        rec = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(None, None, NormalizationStatus.MISSING),
            trade_value_usd=NormalizedField(
                "chữ_không_phải_số", None, NormalizationStatus.INVALID
            ),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res = TradeQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        self.assertIn(
            ValidationIssueCode.INVALID_DATA_TYPE,
            [e.code for e in res.errors],
        )

    def test_invalid_date_type_fails(self):
        rec = NormalizedTrendsRow(
            provenance=self.provenance,
            raw_row={},
            period_label=NormalizedField(
                "ngay_sai_dinh_dang", None, NormalizationStatus.INVALID
            ),
            keyword_scores=(),
        )
        res = SearchTrendsQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.errors[0].code, ValidationIssueCode.INVALID_DATE)


class ValueRangeAndFormatValidationTests(BaseQualityValidatorTest):
    """Yêu cầu 3: Kiểm tra miền giá trị và định dạng."""

    def test_trade_year_out_of_range(self):
        # year outside 2000 - 2100 (CSDL CHECK year >= 2000 AND year <= 2100)
        rec = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("1995", "1995", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(500.0, 500.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res = TradeQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        self.assertIn(
            ValidationIssueCode.VALUE_OUT_OF_RANGE,
            [e.code for e in res.errors],
        )

    def test_trade_flow_invalid_value(self):
        # trade_flow NOT IN ('Export', 'Import')
        rec = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("UNKNOWN", "UNKNOWN", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(500.0, 500.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res = TradeQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        self.assertIn(
            ValidationIssueCode.VALUE_OUT_OF_RANGE,
            [e.code for e in res.errors],
        )

    def test_trade_value_negative_fails(self):
        rec = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(-50.0, -50.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res = TradeQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        self.assertIn(
            ValidationIssueCode.VALUE_OUT_OF_RANGE,
            [e.code for e in res.errors],
        )

    def test_review_rating_out_of_range(self):
        # rating must be 1 to 5 (CSDL CHECK rating_stars BETWEEN 1 AND 5)
        for bad_rating in (0, 6, -1):
            with self.subTest(rating=bad_rating):
                rec = NormalizedReviewRecord(
                    provenance=self.provenance,
                    raw_record={},
                    product_reference=NormalizedField("P1", "P1", NormalizationStatus.CONFIRMED),
                    rating=NormalizedField(bad_rating, bad_rating, NormalizationStatus.CONFIRMED),
                    review_text=NormalizedField("Review", "Review", NormalizationStatus.CONFIRMED),
                    reviewed_at_iso=NormalizedField(None, None, NormalizationStatus.MISSING),
                    language=NormalizedField("vi", "vi", NormalizationStatus.CONFIRMED),
                )
                res = ReviewQualityValidator.validate(rec)
                self.assertFalse(res.is_valid)
                self.assertIn(
                    ValidationIssueCode.VALUE_OUT_OF_RANGE,
                    [e.code for e in res.errors],
                )

    def test_trends_interest_score_out_of_range(self):
        # interest_score BETWEEN 0 AND 100
        rec = NormalizedTrendsRow(
            provenance=self.provenance,
            raw_row={},
            period_label=NormalizedField("2023-10-01", "2023-10-01", NormalizationStatus.CONFIRMED),
            keyword_scores=(
                ("ceramic_mug", NormalizedField(105.0, 105.0, NormalizationStatus.CONFIRMED)),
            ),
        )
        res = SearchTrendsQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.errors[0].code, ValidationIssueCode.VALUE_OUT_OF_RANGE)

    def test_domestic_product_moq_and_lead_time_out_of_range(self):
        # min_order_qty > 0, avg_lead_time_days > 0
        rec = NormalizedDomesticProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id=NormalizedField("D1", "D1", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField("Chén cơm", "Chén cơm", NormalizationStatus.CONFIRMED),
            category=NormalizedField("DINNERWARE", "DINNERWARE", NormalizationStatus.CONFIRMED),
            material=NormalizedField(None, None, NormalizationStatus.MISSING),
            origin_region=NormalizedField(None, None, NormalizationStatus.MISSING),
            price_vnd=NormalizedField(Decimal("50000"), Decimal("50000"), NormalizationStatus.CONFIRMED),
            moq=NormalizedField(0, 0, NormalizationStatus.CONFIRMED),  # Invalid: must be > 0
            lead_time_days=NormalizedField(-5, -5, NormalizationStatus.CONFIRMED),  # Invalid: must be > 0
            wholesale_available=NormalizedField(True, True, NormalizationStatus.CONFIRMED),
        )
        res = DomesticProductQualityValidator.validate(rec)
        self.assertFalse(res.is_valid)
        err_fields = [e.field_name for e in res.errors]
        self.assertIn("min_order_qty", err_fields)
        self.assertIn("avg_lead_time_days", err_fields)


class ValidityAndUnconfirmedReferenceTests(BaseQualityValidatorTest):
    """Yêu cầu 4 & 5: Kiểm tra tính hợp lệ của ngày, tiền tệ, quốc gia, category và phân biệt ERROR vs WARNING."""

    def test_unconfirmed_country_gives_warning(self):
        rec = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField(
                "Atlantis",
                None,
                NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
            ),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(500.0, 500.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res = TradeQualityValidator.validate(rec)
        # Record hợp lệ (is_valid=True) nhưng có WARNING để rà soát
        self.assertTrue(res.is_valid)
        self.assertTrue(res.has_warnings)
        self.assertEqual(res.warnings[0].severity, ValidationSeverity.WARNING)
        self.assertEqual(
            res.warnings[0].code,
            ValidationIssueCode.UNCONFIRMED_REFERENCE,
        )

    def test_unconfirmed_hs_code_gives_warning(self):
        rec = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField(
                "8471",
                None,
                NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
            ),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(500.0, 500.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res = TradeQualityValidator.validate(rec)
        self.assertTrue(res.is_valid)
        self.assertTrue(res.has_warnings)
        self.assertEqual(
            res.warnings[0].code,
            ValidationIssueCode.UNCONFIRMED_REFERENCE,
        )

    def test_unconfirmed_category_gives_warning(self):
        rec = NormalizedProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id=NormalizedField("P1", "P1", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField("Đồ lưu niệm", "Đồ lưu niệm", NormalizationStatus.CONFIRMED),
            product_url=NormalizedField(None, None, NormalizationStatus.MISSING),
            category=NormalizedField(
                "Đồ chơi lưu niệm",
                None,
                NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
            ),
            price=NormalizedCurrency(
                raw_amount="20.0",
                raw_currency="USD",
                amount=Decimal("20.0"),
                currency_code="USD",
                currency_status=NormalizationStatus.CONFIRMED,
                converted_amount=Decimal("20.0"),
                target_currency="USD",
                conversion_status=NormalizationStatus.CONFIRMED,
            ),
        )
        res = MarketProductQualityValidator.validate(rec)
        self.assertTrue(res.is_valid)
        self.assertTrue(res.has_warnings)
        self.assertEqual(
            res.warnings[0].code,
            ValidationIssueCode.UNCONFIRMED_REFERENCE,
        )

    def test_unconfirmed_currency_gives_warning(self):
        rec = NormalizedProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id=NormalizedField("P1", "P1", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField("Ấm chén", "Ấm chén", NormalizationStatus.CONFIRMED),
            product_url=NormalizedField(None, None, NormalizationStatus.MISSING),
            category=NormalizedField("TEA_SET", "TEA_SET", NormalizationStatus.CONFIRMED),
            price=NormalizedCurrency(
                raw_amount="20.0",
                raw_currency="XYZ",
                amount=Decimal("20.0"),
                currency_code=None,
                currency_status=NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
                converted_amount=None,
                target_currency=None,
                conversion_status=NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
            ),
        )
        res = MarketProductQualityValidator.validate(rec)
        self.assertTrue(res.is_valid)
        self.assertTrue(res.has_warnings)
        self.assertEqual(
            res.warnings[0].code,
            ValidationIssueCode.UNCONFIRMED_REFERENCE,
        )


class RecordAndBatchValidationTests(BaseQualityValidatorTest):
    """Yêu cầu 6: Có kết quả validation theo từng record và tổng hợp batch."""

    def test_record_validation_result_methods(self):
        rec = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField(
                "Atlantis",
                None,
                NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
            ),  # Warning
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("1990", "1990", NormalizationStatus.CONFIRMED),  # Error: out of range
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(500.0, 500.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res = DataQualityValidator.validate_trade_record(rec, record_id="REC_001")
        self.assertEqual(res.record_id, "REC_001")
        self.assertEqual(res.entity_type, "trade_statistics")
        self.assertFalse(res.is_valid)
        self.assertTrue(res.has_warnings)
        self.assertEqual(len(res.errors), 1)
        self.assertEqual(len(res.warnings), 1)
        self.assertEqual(res.provenance, self.provenance)

    def test_validate_batch_aggregation(self):
        # Tạo lô gồm 1 record valid, 1 record invalid, 1 record valid with warning
        rec_valid = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(500.0, 500.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        rec_invalid = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField(None, None, NormalizationStatus.MISSING),  # Error
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(500.0, 500.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        rec_warn = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField(
                "Atlantis",
                None,
                NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1,
            ),  # Warning
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(500.0, 500.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )

        batch_res = DataQualityValidator.validate_batch(
            [rec_valid, rec_invalid, rec_warn],
            entity_type="trade_statistics",
        )
        self.assertEqual(batch_res.total_records, 3)
        self.assertEqual(batch_res.valid_records, 2)
        self.assertEqual(batch_res.invalid_records, 1)
        self.assertEqual(batch_res.records_with_warnings, 1)
        self.assertEqual(len(batch_res.record_results), 3)

    def test_validate_dict_payload(self):
        # Hỗ trợ validation trực tiếp trên dict thô
        raw_dict = {
            "reporter_code": "842",
            "partner_code": "704",
            "year": "2022",
            "trade_flow": "Export",
            "hs_code": "6911",
            "trade_value_usd": "1500000.00",
        }
        res = DataQualityValidator.validate_trade_record(raw_dict, record_id="RAW_001")
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.errors), 0)

    def test_validate_batch_all_entity_types_and_unknown_type(self):
        # market_products
        prod = NormalizedProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id=NormalizedField("P1", "P1", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField("Bowl", "Bowl", NormalizationStatus.CONFIRMED),
            product_url=NormalizedField(None, None, NormalizationStatus.MISSING),
            category=NormalizedField("DINNERWARE", "DINNERWARE", NormalizationStatus.CONFIRMED),
            price=NormalizedCurrency(
                raw_amount="15.00",
                raw_currency="USD",
                amount=Decimal("15.00"),
                currency_code="USD",
                currency_status=NormalizationStatus.CONFIRMED,
                converted_amount=Decimal("15.00"),
                target_currency="USD",
                conversion_status=NormalizationStatus.CONFIRMED,
            ),
        )
        self.assertEqual(DataQualityValidator.validate_batch([prod], "market_products").valid_records, 1)

        # product_reviews
        rev = NormalizedReviewRecord(
            provenance=self.provenance,
            raw_record={},
            product_reference=NormalizedField("P1", "P1", NormalizationStatus.CONFIRMED),
            rating=NormalizedField(5, 5, NormalizationStatus.CONFIRMED),
            review_text=NormalizedField(None, None, NormalizationStatus.MISSING),  # WARNING only
            reviewed_at_iso=NormalizedField(None, None, NormalizationStatus.MISSING),
            language=NormalizedField("en", "en", NormalizationStatus.CONFIRMED),
        )
        rev_batch = DataQualityValidator.validate_batch([rev], "product_reviews")
        self.assertEqual(rev_batch.valid_records, 1)
        self.assertEqual(rev_batch.records_with_warnings, 1)

        # search_trends
        trend = NormalizedTrendsRow(
            provenance=self.provenance,
            raw_row={},
            period_label=NormalizedField("2025-01-05", "2025-01-05", NormalizationStatus.CONFIRMED),
            keyword_scores=(("mug", NormalizedField(0.0, 0.0, NormalizationStatus.CONFIRMED)),),
        )
        self.assertEqual(DataQualityValidator.validate_batch([trend], "search_trends").valid_records, 1)

        # supplier_products
        dom = NormalizedDomesticProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id=NormalizedField("D1", "D1", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField("Cốc sứ", "Cốc sứ", NormalizationStatus.CONFIRMED),
            category=NormalizedField("MUG_CUP", "MUG_CUP", NormalizationStatus.CONFIRMED),
            material=NormalizedField(None, None, NormalizationStatus.MISSING),
            origin_region=NormalizedField(None, None, NormalizationStatus.MISSING),
            price_vnd=NormalizedField(Decimal("0"), Decimal("0"), NormalizationStatus.CONFIRMED),
            moq=NormalizedField(None, None, NormalizationStatus.MISSING),
            lead_time_days=NormalizedField(None, None, NormalizationStatus.MISSING),
            wholesale_available=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        self.assertEqual(DataQualityValidator.validate_batch([dom], "supplier_products").valid_records, 1)

        # Unknown entity_type raises ValueError
        with self.assertRaises(ValueError):
            DataQualityValidator.validate_batch([prod], "unknown_table")

    def test_parsed_records_and_unsupported_types_across_validators(self):
        from etl.parsed_record import (
            ParsedCommercialInfo,
            ParsedDomesticProductRecord,
            ParsedPriceInfo,
            ParsedProductRecord,
            ParsedReviewRecord,
            ParsedTradeRecord,
            ParsedTrendsRow,
        )

        # ParsedTradeRecord
        pt = ParsedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_code="842",
            partner_code="704",
            hs_code="6911",
            period="2022",
            flow_code="X",
            net_weight_kg=10.0,
            trade_value_usd=100.0,
            reporter_name=None,
            partner_name=None,
            product_description=None,
        )
        self.assertTrue(TradeQualityValidator.validate(pt).is_valid)

        # ParsedProductRecord
        pp = ParsedProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id="P1",
            product_url=None,
            name="Tea Set",
            category="TEA_SET",
            category_id=None,
            prices=(ParsedPriceInfo("25.00", "USD", "offer"),),
        )
        self.assertTrue(MarketProductQualityValidator.validate(pp).is_valid)

        # ParsedReviewRecord
        pr = ParsedReviewRecord(
            provenance=self.provenance,
            raw_record={},
            product_reference="P1",
            rating=4,
            review_text="Nice",
            reviewed_at_iso=None,
            language="en",
        )
        self.assertTrue(ReviewQualityValidator.validate(pr).is_valid)

        # ParsedTrendsRow
        ptr = ParsedTrendsRow(
            provenance=self.provenance,
            raw_row={},
            period_label="2025-01-05",
            keyword_values=(("mug", "50"),),
        )
        self.assertTrue(SearchTrendsQualityValidator.validate(ptr).is_valid)

        # ParsedDomesticProductRecord
        pd = ParsedDomesticProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id="D1",
            product_url=None,
            name="Bình hoa",
            description=None,
            category="VASE_DECOR",
            material=None,
            origin_region=None,
            commercial=ParsedCommercialInfo("120000", "VND", 10, 7, True),
        )
        self.assertTrue(DomesticProductQualityValidator.validate(pd).is_valid)

        # Unsupported record types -> is_valid=False, INVALID_DATA_TYPE, provenance=None
        for validator in (
            TradeQualityValidator,
            MarketProductQualityValidator,
            ReviewQualityValidator,
            SearchTrendsQualityValidator,
            DomesticProductQualityValidator,
        ):
            res = validator.validate("unsupported_type")  # type: ignore[arg-type]
            self.assertFalse(res.is_valid)
            self.assertIsNone(res.provenance)
            self.assertEqual(res.errors[0].code, ValidationIssueCode.INVALID_DATA_TYPE)

    def test_additional_domain_error_and_warning_branches(self):
        # Trade: negative net_weight_kg, unconfirmed flow_code, and invalid dict fields
        trade_bad_wgt = NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2101", "2101", NormalizationStatus.CONFIRMED),  # > 2100
            flow_code=NormalizedField("RE", None, NormalizationStatus.WAITING_CONFIRMATION_MEMBER_1),
            net_weight_kg=NormalizedField(-1.0, -1.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(100.0, 100.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res_t = TradeQualityValidator.validate(trade_bad_wgt)
        self.assertFalse(res_t.is_valid)
        self.assertTrue(res_t.has_warnings)
        err_fields = {e.field_name for e in res_t.errors}
        self.assertEqual(err_fields, {"year", "net_weight_kg"})

        # Review: missing product_reference and invalid review_date
        rev_bad = NormalizedReviewRecord(
            provenance=self.provenance,
            raw_record={},
            product_reference=NormalizedField(None, None, NormalizationStatus.MISSING),
            rating=NormalizedField(5, 5, NormalizationStatus.CONFIRMED),
            review_text=NormalizedField(None, None, NormalizationStatus.MISSING),
            reviewed_at_iso=NormalizedField("bad-date", None, NormalizationStatus.INVALID),
            language=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res_r = ReviewQualityValidator.validate(rev_bad)
        self.assertFalse(res_r.is_valid)
        self.assertTrue(res_r.has_warnings)
        self.assertEqual({e.field_name for e in res_r.errors}, {"product_reference", "review_date"})

        # Trends: missing period, invalid score type, negative score
        trend_bad = NormalizedTrendsRow(
            provenance=self.provenance,
            raw_row={},
            period_label=NormalizedField(None, None, NormalizationStatus.MISSING),
            keyword_scores=(
                ("kw_bad", NormalizedField("abc", None, NormalizationStatus.INVALID)),
                ("kw_neg", NormalizedField(-5.0, -5.0, NormalizationStatus.CONFIRMED)),
            ),
        )
        res_tr = SearchTrendsQualityValidator.validate(trend_bad)
        self.assertFalse(res_tr.is_valid)
        self.assertEqual(len(res_tr.errors), 3)

        # Domestic: missing name, missing category, invalid price_vnd
        dom_bad = NormalizedDomesticProductRecord(
            provenance=self.provenance,
            raw_record={},
            source_product_id=NormalizedField("D1", "D1", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField(None, None, NormalizationStatus.MISSING),
            category=NormalizedField(None, None, NormalizationStatus.MISSING),
            material=NormalizedField(None, None, NormalizationStatus.MISSING),
            origin_region=NormalizedField(None, None, NormalizationStatus.MISSING),
            price_vnd=NormalizedField("abc", None, NormalizationStatus.INVALID),
            moq=NormalizedField(None, None, NormalizationStatus.MISSING),
            lead_time_days=NormalizedField(None, None, NormalizationStatus.MISSING),
            wholesale_available=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        res_d = DomesticProductQualityValidator.validate(dom_bad)
        self.assertFalse(res_d.is_valid)
        self.assertEqual({e.field_name for e in res_d.errors}, {"product_name", "category", "price_vnd"})


if __name__ == "__main__":
    unittest.main()
