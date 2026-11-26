"""D10 parser tests for D6 — Etsy active listings and Amazon Creators items."""

import json
import unittest
from decimal import Decimal
from pathlib import Path

from etl.parsed_record import ParseError, ParseErrorKind
from etl.marketplace_parser import AmazonCreatorsParser, EtsyListingParser

FIXTURES = Path(__file__).parent / "fixtures"
ETSY_FIXTURE = FIXTURES / "etsy_active_listings_response.json"
AMAZON_FIXTURE = FIXTURES / "amazon_creators_search_items_response.json"

CID = "cafebabe" * 4


class EtsyListingParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = EtsyListingParser()

    # --- valid data ---

    def test_parses_fixture_listing(self):
        payload = ETSY_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)

        self.assertEqual(result.record_count, 1)
        self.assertEqual(result.reported_count, 1)
        self.assertEqual(result.provenance.source_id, "etsy")

    def test_parsed_listing_fields(self):
        result = self.parser.parse(ETSY_FIXTURE.read_bytes(), CID)
        rec = result.records[0]

        self.assertEqual(rec.source_product_id, "123456789")
        self.assertEqual(rec.name, "Synthetic Ceramic Serving Bowl")
        self.assertEqual(rec.product_url, "https://example.invalid/fixture/etsy-listing-1")
        self.assertEqual(rec.category_id, "4321")
        self.assertEqual(len(rec.prices), 1)
        # price: 2499 / 100 = 24.99
        self.assertEqual(Decimal(rec.prices[0].amount_str), Decimal("24.99"))
        self.assertEqual(rec.prices[0].currency_code, "USD")
        self.assertEqual(rec.prices[0].basis, "minimum_listing_price")

    def test_raw_record_preserved_unchanged(self):
        payload = ETSY_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)
        original = json.loads(payload)["results"][0]
        self.assertEqual(result.records[0].raw_record, original)

    def test_provenance_link_in_records(self):
        result = self.parser.parse(ETSY_FIXTURE.read_bytes(), CID)
        self.assertEqual(result.records[0].provenance.raw_collection_id, CID)

    def test_listing_without_price_gives_empty_prices(self):
        payload = json.dumps({
            "count": 1,
            "results": [{"listing_id": 111, "title": "No Price"}],
        }).encode()
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.records[0].prices, ())

    def test_listing_with_null_taxonomy_has_no_category_id(self):
        payload = json.dumps({
            "count": 1,
            "results": [{"listing_id": 222, "taxonomy_id": None}],
        }).encode()
        result = self.parser.parse(payload, CID)
        self.assertIsNone(result.records[0].category_id)

    def test_empty_results_gives_zero_records(self):
        payload = json.dumps({"count": 0, "results": []}).encode()
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.record_count, 0)

    # --- missing field ---

    def test_missing_count_raises_missing_field(self):
        payload = json.dumps({"results": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_missing_results_raises_missing_field(self):
        payload = json.dumps({"count": 0}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_missing_listing_id_raises_missing_field(self):
        payload = json.dumps({"count": 1, "results": [{"title": "No ID"}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_missing_etsy_money_amount_raises_missing_field(self):
        payload = json.dumps({
            "count": 1,
            "results": [{
                "listing_id": 1,
                "price": {"divisor": 100, "currency_code": "USD"},
            }],
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    # --- null field ---

    def test_null_count_raises_null_field(self):
        payload = json.dumps({"count": None, "results": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    def test_null_results_raises_null_field(self):
        payload = json.dumps({"count": 0, "results": None}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    def test_null_listing_id_raises_null_field(self):
        payload = json.dumps({"count": 1, "results": [{"listing_id": None}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    # --- wrong type ---

    def test_string_count_raises_wrong_type(self):
        payload = json.dumps({"count": "1", "results": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_non_dict_listing_raises_wrong_type(self):
        payload = json.dumps({"count": 1, "results": ["not-an-object"]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_float_listing_id_raises_wrong_type(self):
        payload = json.dumps({"count": 1, "results": [{"listing_id": 1.5}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_int_title_raises_wrong_type(self):
        payload = json.dumps({"count": 1, "results": [{"listing_id": 1, "title": 999}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    # --- wrong format ---

    def test_negative_listing_id_raises_wrong_format(self):
        payload = json.dumps({"count": 1, "results": [{"listing_id": -1}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_zero_divisor_raises_wrong_format(self):
        payload = json.dumps({
            "count": 1,
            "results": [{
                "listing_id": 1,
                "price": {"amount": 100, "divisor": 0, "currency_code": "USD"},
            }],
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    # --- invalid structure ---

    def test_non_json_raises_invalid_structure(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"\xff bad", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)


class AmazonCreatorsParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = AmazonCreatorsParser()

    # --- valid data ---

    def test_parses_fixture_item(self):
        payload = AMAZON_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)

        self.assertEqual(result.record_count, 1)
        self.assertIsNone(result.reported_count)

    def test_parsed_item_fields(self):
        result = self.parser.parse(AMAZON_FIXTURE.read_bytes(), CID)
        rec = result.records[0]

        self.assertEqual(rec.source_product_id, "FIXTURE-ASIN-001")
        self.assertEqual(rec.name, "Synthetic Porcelain Dinner Set")
        self.assertEqual(rec.category, "Synthetic tableware")
        self.assertIsNone(rec.category_id)
        self.assertEqual(len(rec.prices), 2)
        self.assertEqual(Decimal(rec.prices[0].amount_str), Decimal("39.95"))
        self.assertEqual(rec.prices[0].basis, "marketplace_offer")

    def test_raw_record_preserved_unchanged(self):
        payload = AMAZON_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)
        original = json.loads(payload)["itemsResult"]["items"][0]
        self.assertEqual(result.records[0].raw_record, original)

    def test_item_without_offers_has_empty_prices(self):
        payload = json.dumps({
            "itemsResult": {"items": [{"asin": "ASIN-1"}]}
        }).encode()
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.records[0].prices, ())

    def test_empty_items_list_gives_zero_records(self):
        payload = json.dumps({"itemsResult": {"items": []}}).encode()
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.record_count, 0)

    # --- missing field ---

    def test_missing_items_result_raises_missing_field(self):
        payload = json.dumps({}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_missing_items_raises_missing_field(self):
        payload = json.dumps({"itemsResult": {}}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_missing_asin_raises_missing_field(self):
        payload = json.dumps({"itemsResult": {"items": [{"detailPageURL": "x"}]}}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)
        self.assertIn("asin", ctx.exception.field_path)

    # --- null field ---

    def test_null_items_result_raises_null_field(self):
        payload = json.dumps({"itemsResult": None}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    def test_null_items_raises_null_field(self):
        payload = json.dumps({"itemsResult": {"items": None}}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    def test_null_asin_raises_null_field(self):
        payload = json.dumps({"itemsResult": {"items": [{"asin": None}]}}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    # --- wrong type ---

    def test_int_asin_raises_wrong_type(self):
        payload = json.dumps({"itemsResult": {"items": [{"asin": 123}]}}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_non_dict_item_raises_wrong_type(self):
        payload = json.dumps({"itemsResult": {"items": ["not-a-dict"]}}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    # --- wrong format ---

    def test_blank_asin_raises_wrong_format(self):
        payload = json.dumps({"itemsResult": {"items": [{"asin": "   "}]}}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    # --- invalid structure ---

    def test_non_json_raises_invalid_structure(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"\xff\xfe", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)


if __name__ == "__main__":
    unittest.main()
