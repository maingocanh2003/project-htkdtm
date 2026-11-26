"""Unit tests for D14 — Source-to-Target Mapping into the 13 OLTP tables."""

import unittest
from datetime import date
from pathlib import Path

from etl.domestic_parser import DomesticSupplierCatalogParser
from etl.marketplace_parser import AmazonCreatorsParser, EtsyListingParser
from etl.parsed_record import (
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedTradeRecord,
    ParsedTrendsRow,
    RecordProvenance,
)
from etl.review_parser import EtsyReviewParser
from etl.source_to_target_mapping import (
    OLTP_TABLE_SPECS,
    MappingIssueKind,
    MappingStatus,
    ReferenceLookup,
    map_market_product_record,
    map_product_review_record,
    map_search_trend_row,
    map_supplier_product_record,
    map_supplier_record,
    map_trade_record,
)
from etl.trade_parser import ITCTradeMapParser, UNComtradeParser
from etl.trends_parser import GoogleTrendsParser


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _make_lookup() -> ReferenceLookup:
    return ReferenceLookup(
        countries_by_code={"USA": 1, "VNM": 2, "WLD": 3, "JPN": 4},
        market_regions_by_key={(1, "US-CA"): 10},
        categories_by_code={
            "TEA_SET": 1,
            "MUG_CUP": 2,
            "DINNERWARE": 3,
            "VASE_DECOR": 4,
        },
        suppliers_by_code={"NCC_THEGIOIGOM": 100, "NCC_MINHLONG1": 101},
        market_products_by_sku={"987654321": 500, "123456789": 501, "FIXTURE-ASIN-001": 502},
    )


class OltpSpecificationCompletenessTests(unittest.TestCase):
    """Verify D14 mapping spec covers all 13 OLTP tables and 125 columns."""

    def test_all_13_tables_present_with_exact_column_counts(self):
        expected_counts = {
            "countries": 6,
            "market_regions": 4,
            "product_categories": 5,
            "trade_statistics": 16,
            "search_trends": 8,
            "trending_keywords": 8,
            "market_products": 18,
            "customers": 6,
            "product_reviews": 9,
            "review_aspects": 5,
            "suppliers": 12,
            "supplier_products": 16,
            "order_recommendations": 12,
        }
        self.assertEqual(set(OLTP_TABLE_SPECS.keys()), set(expected_counts.keys()))
        total_cols = 0
        for table, expected_cnt in expected_counts.items():
            spec = OLTP_TABLE_SPECS[table]
            self.assertEqual(len(spec.columns), expected_cnt, msg=f"Column count mismatch for {table}")
            total_cols += len(spec.columns)
            for col in spec.columns:
                self.assertIsInstance(col.mapping_status, MappingStatus)
                self.assertEqual(col.target_table, table)
        self.assertEqual(total_cols, 125)

    def test_out_of_scope_tables_marked_not_applicable(self):
        for table in ("review_aspects", "order_recommendations"):
            spec = OLTP_TABLE_SPECS[table]
            for col in spec.columns:
                self.assertEqual(col.mapping_status, MappingStatus.NOT_APPLICABLE)


class TradeMappingTests(unittest.TestCase):
    """D5 + D10–D12 -> trade_statistics mapping tests."""

    def test_un_comtrade_fixture_maps_successfully(self):
        payload = (FIXTURES_DIR / "un_comtrade_preview_response.json").read_bytes()
        parsed = UNComtradeParser().parse(payload, "col_trade_01", collected_at_iso="2026-11-26T00:00:00Z")
        res = map_trade_record(parsed.records[0], _make_lookup())

        self.assertTrue(res.is_mappable, msg=res.issues)
        self.assertEqual(res.target_table, "trade_statistics")
        self.assertEqual(res.record_dict["reporter_country_id"], 1)  # 842 -> USA -> 1
        self.assertEqual(res.record_dict["partner_country_id"], 3)   # 0 -> WLD -> 3
        self.assertEqual(res.record_dict["year"], 2022)
        self.assertEqual(res.record_dict["trade_flow"], "Import")
        self.assertEqual(res.record_dict["hs_code"], "6911")
        self.assertEqual(res.record_dict["data_source"], "UN Comtrade")
        self.assertEqual(res.fields["fob_value_usd"].status, MappingStatus.NO_SOURCE)
        self.assertEqual(res.fields["market_share_pct"].status, MappingStatus.PENDING_CONFIRMATION)

    def test_itc_fixture_fails_due_to_missing_partner_and_flow(self):
        payload = (FIXTURES_DIR / "itc_trade_map_export_fixture.csv").read_bytes()
        parsed = ITCTradeMapParser().parse(payload, "col_itc_01")
        res = map_trade_record(parsed.records[0], _make_lookup())

        self.assertFalse(res.is_mappable)
        issue_cols = {i.column for i in res.issues}
        self.assertIn("partner_country_id", issue_cols)
        self.assertIn("trade_flow", issue_cols)

    def test_trade_invalid_year_and_unresolved_fk(self):
        prov = RecordProvenance("un_comtrade", "col_bad_01", "2026-11-26T00:00:00Z", None)
        rec = ParsedTradeRecord(
            provenance=prov,
            raw_record={},
            reporter_code="999",  # unknown country
            partner_code="842",
            hs_code="6911",
            period="1995",        # violates CHECK (year >= 2000)
            flow_code="M",
            net_weight_kg=10.0,
            trade_value_usd=-5.0, # violates CHECK (>= 0)
            reporter_name=None,
            partner_name=None,
            product_description=None,
        )
        res = map_trade_record(rec, _make_lookup())
        self.assertFalse(res.is_mappable)
        kinds = {i.kind for i in res.issues}
        self.assertIn(MappingIssueKind.VALIDATION_ERROR, kinds)
        self.assertIn(MappingIssueKind.UNRESOLVED_FK, kinds)


class SearchTrendsMappingTests(unittest.TestCase):
    """D6 + D10–D12 -> search_trends mapping tests."""

    def test_google_trends_fixture_unpivots_and_maps(self):
        payload = (FIXTURES_DIR / "google_trends_ui_export_fixture.csv").read_bytes()
        parsed = GoogleTrendsParser().parse(payload, "col_gt_01")
        mapped_rows = map_search_trend_row(
            parsed.rows[0],
            _make_lookup(),
            country_code="USA",
            region_code="US-CA",
            category_code="DINNERWARE",
        )
        self.assertEqual(len(mapped_rows), 2)
        first = mapped_rows[0]
        self.assertTrue(first.is_mappable, msg=first.issues)
        self.assertEqual(first.record_dict["country_id"], 1)
        self.assertEqual(first.record_dict["region_id"], 10)
        self.assertEqual(first.record_dict["category_id"], 3)
        self.assertEqual(first.record_dict["search_term"], "ceramic_dinnerware")
        self.assertEqual(first.record_dict["week_start_date"], date(2025, 1, 5))
        self.assertEqual(first.record_dict["week_number"], 1)
        self.assertEqual(first.record_dict["interest_score"], 100)

    def test_trends_missing_request_context_fails_fk(self):
        prov = RecordProvenance("google_trends", "col_gt_02", "2026-11-26T00:00:00Z", None)
        row = ParsedTrendsRow(prov, {}, "2025-01-05", (("ceramic mug", "150"),))
        res_list = map_search_trend_row(row, _make_lookup())
        res = res_list[0]
        self.assertFalse(res.is_mappable)
        cols = {i.column for i in res.issues}
        self.assertIn("country_id", cols)
        self.assertIn("category_id", cols)
        self.assertIn("interest_score[ceramic mug]", cols)


class MarketProductAndReviewMappingTests(unittest.TestCase):
    """D7/D8 + D10–D12 -> market_products & product_reviews mapping tests."""

    def test_amazon_product_without_target_country_is_pending_confirmation(self):
        payload = (FIXTURES_DIR / "amazon_creators_search_items_response.json").read_bytes()
        parsed = AmazonCreatorsParser().parse(payload, "col_amz_01")
        res = map_market_product_record(parsed.records[0], _make_lookup())
        self.assertFalse(res.is_mappable)
        self.assertTrue(any(i.column == "target_country_id" and i.kind == MappingIssueKind.PENDING_CONFIRMATION for i in res.issues))

    def test_etsy_product_with_confirmed_overrides_maps_cleanly(self):
        payload = (FIXTURES_DIR / "etsy_active_listings_response.json").read_bytes()
        parsed = EtsyListingParser().parse(payload, "col_etsy_01")
        res = map_market_product_record(
            parsed.records[0],
            _make_lookup(),
            target_country_code="USA",
            category_code_override="DINNERWARE",
        )
        self.assertTrue(res.is_mappable, msg=res.issues)
        self.assertEqual(res.record_dict["external_sku"], "123456789")
        self.assertEqual(res.record_dict["platform_source"], "Etsy")
        self.assertEqual(res.record_dict["target_country_id"], 1)
        self.assertEqual(res.record_dict["category_id"], 3)
        self.assertEqual(res.fields["color"].status, MappingStatus.NO_SOURCE)

    def test_etsy_review_fixture_maps_with_ai_fields_not_applicable(self):
        payload = (FIXTURES_DIR / "etsy_listing_reviews_page_0.json").read_bytes()
        parsed = EtsyReviewParser().parse(payload, "col_rev_01")
        res = map_product_review_record(parsed.records[0], _make_lookup())
        self.assertTrue(res.is_mappable, msg=res.issues)
        self.assertEqual(res.record_dict["market_product_id"], 500)
        self.assertEqual(res.record_dict["rating_stars"], 5)
        self.assertEqual(res.fields["sentiment_label"].status, MappingStatus.NOT_APPLICABLE)
        self.assertEqual(res.fields["customer_id"].status, MappingStatus.NO_SOURCE)

    def test_review_with_null_text_is_blocked_for_not_null_column(self):
        prov = RecordProvenance("etsy", "col_rev_02", "2026-11-26T00:00:00Z", None)
        rec = ParsedReviewRecord(prov, {}, "987654321", 4, None, "2025-10-09T00:00:00+00:00", "en")
        res = map_product_review_record(rec, _make_lookup())
        self.assertFalse(res.is_mappable)
        self.assertTrue(any(i.column == "review_text" and i.kind == MappingIssueKind.SOURCE_NULL for i in res.issues))


class DomesticSupplierMappingTests(unittest.TestCase):
    """D9 + D10–D12 -> suppliers & supplier_products mapping tests."""

    def test_supplier_blocked_due_to_missing_capacity_and_lead_time(self):
        payload = (FIXTURES_DIR / "thegioigom_products_response.json").read_bytes()
        parsed = DomesticSupplierCatalogParser().parse(payload, "col_dom_01", "thegioigom")
        self.assertIsNotNone(parsed.supplier)
        sup_res = map_supplier_record(parsed.supplier, supplier_code="NCC_THEGIOIGOM")
        self.assertFalse(sup_res.is_mappable)
        missing_cols = {i.column for i in sup_res.issues}
        self.assertIn("min_monthly_capacity", missing_cols)
        self.assertIn("max_monthly_capacity", missing_cols)
        self.assertIn("avg_lead_time_days", missing_cols)

    def test_thegioigom_product_maps_cleanly(self):
        payload = (FIXTURES_DIR / "thegioigom_products_response.json").read_bytes()
        parsed = DomesticSupplierCatalogParser().parse(payload, "col_dom_01", "thegioigom")
        prod_res = map_supplier_product_record(parsed.products[0], _make_lookup(), supplier_code="NCC_THEGIOIGOM")
        self.assertTrue(prod_res.is_mappable, msg=prod_res.issues)
        self.assertEqual(prod_res.record_dict["supplier_id"], 100)
        self.assertEqual(prod_res.record_dict["category_id"], 3)
        self.assertEqual(prod_res.record_dict["product_code"], "TGG-001")
        self.assertEqual(prod_res.fields["price_usd_equiv"].status, MappingStatus.PENDING_CONFIRMATION)
        self.assertEqual(prod_res.fields["color"].status, MappingStatus.NO_SOURCE)

    def test_minh_long_fixture_null_price_is_rejected(self):
        payload = (FIXTURES_DIR / "minh_long_1_file_catalog.json").read_bytes()
        parsed = DomesticSupplierCatalogParser().parse(payload, "col_ml_01", "minh_long_1")
        prod_res = map_supplier_product_record(parsed.products[0], _make_lookup(), supplier_code="NCC_MINHLONG1")
        self.assertFalse(prod_res.is_mappable)
        self.assertTrue(any(i.column == "price_vnd" for i in prod_res.issues))


if __name__ == "__main__":
    unittest.main()
