"""D10 parser tests for D7 — Etsy listing reviews."""

import json
import unittest
from pathlib import Path

from etl.parsed_record import ParseError, ParseErrorKind
from etl.review_parser import EtsyReviewParser

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_0 = FIXTURES / "etsy_listing_reviews_page_0.json"
PAGE_1 = FIXTURES / "etsy_listing_reviews_page_1.json"

CID = "deadbeef" * 4
LISTING_ID = 987654321


class EtsyReviewParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = EtsyReviewParser()

    # --- valid data ---

    def test_parses_page0_fixture(self):
        payload = PAGE_0.read_bytes()
        result = self.parser.parse(payload, CID, expected_listing_id=LISTING_ID)

        self.assertEqual(result.record_count, 1)
        self.assertEqual(result.reported_count, 2)
        self.assertEqual(result.provenance.source_id, "etsy")

    def test_review_text_preserved_with_whitespace(self):
        result = self.parser.parse(PAGE_0.read_bytes(), CID, expected_listing_id=LISTING_ID)
        rec = result.records[0]

        self.assertEqual(rec.review_text, "  Raw\nreview — synthetic fixture. ")
        self.assertEqual(rec.rating, 5)
        self.assertEqual(rec.product_reference, str(LISTING_ID))

    def test_reviewed_at_is_iso_utc_string(self):
        result = self.parser.parse(PAGE_0.read_bytes(), CID, expected_listing_id=LISTING_ID)
        rec = result.records[0]
        # 1760000000 → "2025-10-09T...+00:00" (exact value tested below)
        self.assertIsNotNone(rec.reviewed_at_iso)
        self.assertIn("+00:00", rec.reviewed_at_iso)

    def test_null_review_text_preserved_as_none(self):
        result = self.parser.parse(PAGE_1.read_bytes(), CID, expected_listing_id=LISTING_ID)
        rec = result.records[0]
        self.assertIsNone(rec.review_text)

    def test_language_field_carried(self):
        result = self.parser.parse(PAGE_0.read_bytes(), CID, expected_listing_id=LISTING_ID)
        self.assertEqual(result.records[0].language, "en")

    def test_raw_record_preserved_unchanged(self):
        payload = PAGE_0.read_bytes()
        result = self.parser.parse(payload, CID, expected_listing_id=LISTING_ID)
        original = json.loads(payload)["results"][0]
        self.assertEqual(result.records[0].raw_record, original)

    def test_provenance_link_carried(self):
        result = self.parser.parse(PAGE_0.read_bytes(), CID)
        self.assertEqual(result.records[0].provenance.raw_collection_id, CID)

    def test_no_expected_listing_id_accepts_any(self):
        # Should not raise even without cross-reference check
        result = self.parser.parse(PAGE_0.read_bytes(), CID)
        self.assertEqual(result.record_count, 1)

    def test_empty_results_list(self):
        payload = json.dumps({"count": 0, "results": []}).encode()
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.record_count, 0)
        self.assertEqual(result.reported_count, 0)

    # --- missing field ---

    def test_missing_count_raises_missing_field(self):
        payload = json.dumps({"results": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_missing_results_raises_missing_field(self):
        payload = json.dumps({"count": 1}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_missing_listing_id_raises_missing_field(self):
        payload = json.dumps({"count": 1, "results": [{"rating": 5}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)
        self.assertIn("listing_id", ctx.exception.field_path)

    def test_missing_rating_raises_missing_field(self):
        payload = json.dumps({"count": 1, "results": [{"listing_id": 1}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)
        self.assertIn("rating", ctx.exception.field_path)

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
        payload = json.dumps({
            "count": 1, "results": [{"listing_id": None, "rating": 5}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    def test_null_rating_raises_null_field(self):
        payload = json.dumps({
            "count": 1, "results": [{"listing_id": 1, "rating": None}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    # --- wrong type ---

    def test_string_rating_raises_wrong_type(self):
        payload = json.dumps({
            "count": 1, "results": [{"listing_id": 1, "rating": "5"}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_int_review_text_raises_wrong_type(self):
        payload = json.dumps({
            "count": 1, "results": [{"listing_id": 1, "rating": 5, "review": 42}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_float_timestamp_raises_wrong_type(self):
        payload = json.dumps({
            "count": 1,
            "results": [{"listing_id": 1, "rating": 5, "created_timestamp": 1.5}],
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    # --- wrong format ---

    def test_rating_zero_raises_wrong_format(self):
        payload = json.dumps({
            "count": 1, "results": [{"listing_id": 1, "rating": 0}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_rating_six_raises_wrong_format(self):
        payload = json.dumps({
            "count": 1, "results": [{"listing_id": 1, "rating": 6}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_mismatched_listing_id_raises_wrong_format(self):
        payload = json.dumps({
            "count": 1, "results": [{"listing_id": 999, "rating": 5}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, expected_listing_id=LISTING_ID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_negative_timestamp_raises_wrong_format(self):
        payload = json.dumps({
            "count": 1,
            "results": [{"listing_id": 1, "rating": 5, "created_timestamp": -1}],
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    # --- invalid structure ---

    def test_non_json_raises_invalid_structure(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"\xff bad", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)

    def test_json_array_at_root_raises_invalid_structure(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"[]", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)


if __name__ == "__main__":
    unittest.main()
