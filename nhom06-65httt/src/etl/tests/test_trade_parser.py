"""D10 parser tests for D5 — UN Comtrade JSON and ITC Trade Map CSV."""

import json
import unittest
from pathlib import Path

from etl.parsed_record import ParseErrorKind
from etl.trade_parser import ITCTradeMapParser, UNComtradeParser

FIXTURES = Path(__file__).parent / "fixtures"
COMTRADE_FIXTURE = FIXTURES / "un_comtrade_preview_response.json"
ITC_FIXTURE = FIXTURES / "itc_trade_map_export_fixture.csv"

CID = "aabbccdd" * 4   # 32-char hex


class UNComtradeParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = UNComtradeParser()

    # --- valid data ---

    def test_parses_fixture_into_payload_with_correct_counts(self):
        payload = COMTRADE_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID, collected_at_iso="2026-01-01T00:00:00+00:00")

        self.assertEqual(result.record_count, 1)
        self.assertEqual(result.reported_count, 1)
        self.assertEqual(result.provenance.source_id, "un_comtrade")
        self.assertEqual(result.provenance.raw_collection_id, CID)

    def test_parsed_record_carries_all_fields(self):
        payload = COMTRADE_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)
        rec = result.records[0]

        self.assertEqual(rec.hs_code, "6911")
        self.assertEqual(rec.flow_code, "M")
        self.assertEqual(rec.period, "2022")
        self.assertAlmostEqual(rec.net_weight_kg, 12.5)
        self.assertAlmostEqual(rec.trade_value_usd, 20.0)
        self.assertEqual(rec.product_description, "synthetic fixture record")

    def test_raw_record_is_preserved_unchanged(self):
        payload = COMTRADE_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)
        rec = result.records[0]

        # Verify the raw dict matches the original JSON exactly
        original = json.loads(payload)["data"][0]
        self.assertEqual(rec.raw_record, original)

    def test_provenance_link_is_set(self):
        result = self.parser.parse(COMTRADE_FIXTURE.read_bytes(), CID)
        self.assertEqual(result.records[0].provenance.raw_collection_id, CID)
        self.assertEqual(result.records[0].provenance.source_id, "un_comtrade")

    # --- empty data list ---

    def test_empty_data_list_gives_zero_records(self):
        payload = json.dumps({"count": 0, "data": [], "error": ""}).encode()
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.record_count, 0)
        self.assertEqual(result.reported_count, 0)

    # --- missing field errors ---

    def test_missing_count_raises_missing_field(self):
        payload = json.dumps({"data": []}).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)
        self.assertIn("count", ctx.exception.field_path)

    def test_missing_data_raises_missing_field(self):
        payload = json.dumps({"count": 0}).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_missing_cmd_code_raises_missing_field(self):
        payload = json.dumps({
            "count": 1,
            "data": [{"reporterCode": 842, "flowCode": "M"}],
            "error": "",
        }).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)
        self.assertIn("cmdCode", ctx.exception.field_path)

    # --- null field errors ---

    def test_null_count_raises_null_field(self):
        payload = json.dumps({"count": None, "data": []}).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    def test_null_data_raises_null_field(self):
        payload = json.dumps({"count": 0, "data": None}).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    def test_null_cmd_code_raises_null_field(self):
        payload = json.dumps({
            "count": 1,
            "data": [{"cmdCode": None}],
            "error": "",
        }).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    # --- wrong type errors ---

    def test_wrong_type_count_raises_wrong_type(self):
        payload = json.dumps({"count": "1", "data": []}).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_wrong_type_data_raises_wrong_type(self):
        payload = json.dumps({"count": 0, "data": "not-a-list"}).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_wrong_type_record_in_data_raises_wrong_type(self):
        payload = json.dumps({"count": 1, "data": ["not-an-object"]}).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    # --- wrong format errors ---

    def test_negative_count_raises_wrong_format(self):
        payload = json.dumps({"count": -1, "data": []}).encode()
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    # --- invalid structure ---

    def test_non_json_raises_invalid_structure(self):
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"\xff not json", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)

    def test_json_array_at_root_raises_invalid_structure(self):
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"[1, 2]", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)


class ITCTradeMapParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = ITCTradeMapParser()

    def test_parses_fixture_csv_into_records(self):
        payload = ITC_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID, collected_at_iso="2026-01-01T00:00:00+00:00")

        self.assertEqual(result.record_count, 2)
        self.assertIsNone(result.reported_count)  # file datasets have no envelope count

    def test_first_record_has_correct_fields(self):
        result = self.parser.parse(ITC_FIXTURE.read_bytes(), CID)
        rec = result.records[0]

        self.assertEqual(rec.hs_code, "6911")
        self.assertEqual(rec.period, "2022")
        self.assertAlmostEqual(rec.trade_value_usd, 15230000.0)
        self.assertEqual(rec.reporter_name, "Viet Nam")

    def test_raw_record_is_preserved_unchanged(self):
        result = self.parser.parse(ITC_FIXTURE.read_bytes(), CID)
        rec = result.records[0]
        self.assertIn("Commodity code", rec.raw_record)
        self.assertEqual(rec.raw_record["Commodity code"], "6911")

    def test_provenance_carried_in_records(self):
        result = self.parser.parse(ITC_FIXTURE.read_bytes(), CID)
        for rec in result.records:
            self.assertEqual(rec.provenance.raw_collection_id, CID)

    def test_empty_payload_raises_missing_field(self):
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_whitespace_only_payload_raises_missing_field(self):
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"   \n  ", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)

    def test_non_utf8_payload_raises_invalid_structure(self):
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"\xff\xfe", CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)

    def test_invalid_trade_value_raises_wrong_format(self):
        csv_bytes = b"Reporter,Commodity code,Period,Trade Value (USD)\nVN,6911,2022,not-a-number\n"
        from etl.parsed_record import ParseError
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(csv_bytes, CID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_header_only_gives_zero_records(self):
        csv_bytes = b"Reporter,Commodity code,Period,Trade Value (USD)\n"
        result = self.parser.parse(csv_bytes, CID)
        self.assertEqual(result.record_count, 0)


if __name__ == "__main__":
    unittest.main()
