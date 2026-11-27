"""D10 parser tests for D8 — Google Trends CSV exports."""

import codecs
import unittest
from pathlib import Path

from etl.parsed_record import ParseError, ParseErrorKind
from etl.trends_parser import GoogleTrendsParser

FIXTURES = Path(__file__).parent / "fixtures"
TRENDS_FIXTURE = FIXTURES / "google_trends_ui_export_fixture.csv"

CID = "facefeed" * 4


class GoogleTrendsParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = GoogleTrendsParser()

    # --- valid data ---

    def test_parses_fixture_csv(self):
        payload = TRENDS_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)

        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.provenance.source_id, "google_trends")

    def test_keywords_extracted_from_header(self):
        result = self.parser.parse(TRENDS_FIXTURE.read_bytes(), CID)
        self.assertIn("ceramic_dinnerware", result.keywords)
        self.assertIn("handmade_pottery_mug", result.keywords)

    def test_period_label_preserved_as_string(self):
        result = self.parser.parse(TRENDS_FIXTURE.read_bytes(), CID)
        periods = [row.period_label for row in result.rows]
        self.assertIn("2025-01-05", periods)
        self.assertIn("2025-01-12", periods)

    def test_values_kept_as_raw_strings(self):
        result = self.parser.parse(TRENDS_FIXTURE.read_bytes(), CID)
        row = result.rows[0]
        # First row: ceramic_dinnerware=100, handmade_pottery_mug=0
        kv = dict(row.keyword_values)
        self.assertEqual(kv["ceramic_dinnerware"], "100")
        self.assertEqual(kv["handmade_pottery_mug"], "0")

    def test_raw_row_preserved_unchanged(self):
        result = self.parser.parse(TRENDS_FIXTURE.read_bytes(), CID)
        row = result.rows[0]
        # raw_row is the original DictReader dict
        self.assertIn("week", row.raw_row)
        self.assertEqual(row.raw_row["week"], "2025-01-05")

    def test_provenance_carried_in_rows(self):
        result = self.parser.parse(TRENDS_FIXTURE.read_bytes(), CID)
        for row in result.rows:
            self.assertEqual(row.provenance.raw_collection_id, CID)

    def test_standard_trends_csv_with_metadata_header(self):
        """Simulate a real Trends export with a comment line before the data header."""
        csv_bytes = (
            b"Interest over time\n"
            b"Week,ceramic bowls\n"
            b"2025-01-05,75\n"
            b"2025-01-12,80\n"
        )
        result = self.parser.parse(csv_bytes, CID)
        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.data_type_hint, "Interest over time")
        self.assertIn("ceramic bowls", result.keywords)

    def test_decodes_utf8_without_bom(self):
        payload = "Week,ceramic\n2025-01-05,55\n".encode("utf-8")
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.rows[0].period_label, "2025-01-05")

    def test_decodes_utf8_bom(self):
        payload = codecs.BOM_UTF8 + "Week,ceramic\n2025-01-05,55\n".encode("utf-8")
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.keywords, ("ceramic",))

    def test_decodes_utf16_little_endian_with_bom(self):
        text = "Week,ceramic\n2025-01-05,55\n"
        payload = codecs.BOM_UTF16_LE + text.encode("utf-16-le")
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.rows[0].period_label, "2025-01-05")

    def test_decodes_utf16_big_endian_with_bom(self):
        text = "Week,ceramic\n2025-01-05,55\n"
        payload = codecs.BOM_UTF16_BE + text.encode("utf-16-be")
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.rows[0].period_label, "2025-01-05")

    def test_month_column_recognised_as_period(self):
        csv_bytes = b"Month,keyword_a\n2025-01,55\n2025-02,60\n"
        result = self.parser.parse(csv_bytes, CID)
        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.rows[0].period_label, "2025-01")

    def test_day_column_recognised_as_period(self):
        csv_bytes = b"Day,kw\n2025-01-01,10\n"
        result = self.parser.parse(csv_bytes, CID)
        self.assertEqual(result.rows[0].period_label, "2025-01-01")

    def test_header_only_gives_zero_rows(self):
        csv_bytes = b"Week,kw_a\n"
        result = self.parser.parse(csv_bytes, CID)
        self.assertEqual(result.row_count, 0)

    # --- missing field ---

    def test_empty_payload_raises_missing_field(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_whitespace_payload_raises_missing_field(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"   \n  ", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_empty_period_cell_raises_missing_field(self):
        csv_bytes = b"Week,kw\n,100\n"
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(csv_bytes, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    # --- invalid structure ---

    def test_non_utf8_without_bom_raises_invalid_structure(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"\xffnot utf-8", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)

    def test_malformed_bom_marked_utf16_raises_invalid_structure(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(codecs.BOM_UTF16_LE + b"\x00", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)
        self.assertIn("BOM-marked UTF-16", ctx.exception.detail)

    def test_unmarked_utf16_is_not_guessed(self):
        payload = "Week,kw\n2025-01-05,55\n".encode("utf-16-le")
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)

    def test_malformed_csv_quoting_raises_invalid_structure(self):
        payload = b'Week,kw\n2025-01-05,"55\n'
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)
        self.assertIn("CSV syntax error", ctx.exception.detail)

    def test_csv_row_with_wrong_number_of_columns_raises_invalid_structure(self):
        payload = b"Week,kw\n2025-01-05,55,extra\n"
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)
        self.assertIn("different number of columns", ctx.exception.detail)

    # --- no mutations: values stay as strings ---

    def test_values_not_scaled_or_converted(self):
        """Verify parser does NOT convert "100" to int or scale it."""
        csv_bytes = b"Week,kw\n2025-01-05,100\n2025-01-12,0\n"
        result = self.parser.parse(csv_bytes, CID)
        kv0 = dict(result.rows[0].keyword_values)
        kv1 = dict(result.rows[1].keyword_values)
        self.assertIsInstance(kv0["kw"], str)
        self.assertEqual(kv0["kw"], "100")
        self.assertEqual(kv1["kw"], "0")

    # --- additional boundary checks ---

    def test_period_only_header_produces_empty_keywords_tuple(self):
        """When the CSV has only a period column, keywords should be an empty tuple."""
        csv_bytes = b"Week\n2025-01-01\n"
        result = self.parser.parse(csv_bytes, CID)
        self.assertEqual(result.keywords, ())
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.rows[0].period_label, "2025-01-01")

    def test_single_keyword_column_parsed_correctly(self):
        """A CSV with exactly one keyword column works correctly."""
        csv_bytes = b"Week,kw_a\n2025-01-05,55\n"
        result = self.parser.parse(csv_bytes, CID)
        self.assertEqual(result.keywords, ("kw_a",))
        self.assertEqual(result.row_count, 1)
        kv = dict(result.rows[0].keyword_values)
        self.assertEqual(kv["kw_a"], "55")


if __name__ == "__main__":
    unittest.main()
