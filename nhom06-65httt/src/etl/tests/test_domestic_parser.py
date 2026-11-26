"""D10 parser tests for D9 — Domestic supplier catalog payloads."""

import json
import unittest
from pathlib import Path

from etl.parsed_record import ParseError, ParseErrorKind
from etl.domestic_parser import DomesticSupplierCatalogParser

FIXTURES = Path(__file__).parent / "fixtures"
THEGIOIGOM_FIXTURE = FIXTURES / "thegioigom_products_response.json"
GOC_GOM_FIXTURE = FIXTURES / "goc_gom_viet_products_response.json"
MINH_LONG_FIXTURE = FIXTURES / "minh_long_1_file_catalog.json"

CID = "b00bc0de" * 4
SID = "thegioigom"


class DomesticSupplierCatalogParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = DomesticSupplierCatalogParser()

    # -----------------------------------------------------------------------
    # Valid data
    # -----------------------------------------------------------------------

    def test_parses_full_supplier_and_two_products(self):
        payload = THEGIOIGOM_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID, SID)

        self.assertEqual(result.record_count, 2)
        self.assertIsNotNone(result.supplier)
        self.assertEqual(result.supplier.supplier_name, "Gốm Sứ Thế Giới Gốm")
        self.assertEqual(result.supplier.tax_code, "0314567890")
        self.assertEqual(result.supplier.province, "TP. Hồ Chí Minh")
        self.assertEqual(result.supplier.business_type, "sản xuất và phân phối")
        # capacity NOT declared — must be None
        self.assertIsNone(result.supplier.declared_capacity_note)

    def test_supplier_separated_from_products(self):
        result = self.parser.parse(THEGIOIGOM_FIXTURE.read_bytes(), CID, SID)
        p0 = result.products[0]

        self.assertEqual(p0.source_product_id, "TGG-001")
        self.assertEqual(p0.name, "Bát ăn cơm hoa đào men trắng")
        self.assertEqual(p0.material, "Sứ cao cấp")
        self.assertEqual(p0.origin_region, "Bình Dương")

    def test_commercial_info_populated_when_source_provides(self):
        result = self.parser.parse(THEGIOIGOM_FIXTURE.read_bytes(), CID, SID)
        c = result.products[0].commercial

        self.assertEqual(c.price_vnd_str, "45000")
        self.assertEqual(c.currency, "VND")
        self.assertEqual(c.moq, 12)
        # lead_time_days not provided by source — must remain None
        self.assertIsNone(c.lead_time_days)
        self.assertTrue(c.wholesale_available)

    def test_null_supplier_block_gives_none(self):
        result = self.parser.parse(GOC_GOM_FIXTURE.read_bytes(), CID, "goc_gom_viet")
        self.assertIsNone(result.supplier)

    def test_product_with_lead_time(self):
        result = self.parser.parse(GOC_GOM_FIXTURE.read_bytes(), CID, "goc_gom_viet")
        c = result.products[0].commercial
        self.assertEqual(c.lead_time_days, 14)
        self.assertEqual(c.moq, 6)

    def test_all_commercial_fields_null_when_source_omits(self):
        """Commercial info never inferred — all None when source omits."""
        result = self.parser.parse(MINH_LONG_FIXTURE.read_bytes(), CID, "minh_long_1")
        c = result.products[0].commercial
        self.assertIsNone(c.price_vnd_str)
        self.assertIsNone(c.currency)
        self.assertIsNone(c.moq)
        self.assertIsNone(c.lead_time_days)
        self.assertIsNone(c.wholesale_available)

    def test_raw_record_preserved_unchanged(self):
        payload = THEGIOIGOM_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID, SID)
        original = json.loads(payload)["products"][0]
        self.assertEqual(result.products[0].raw_record, original)

    def test_provenance_link_carried(self):
        result = self.parser.parse(THEGIOIGOM_FIXTURE.read_bytes(), CID, SID)
        for p in result.products:
            self.assertEqual(p.provenance.raw_collection_id, CID)
            self.assertEqual(p.provenance.source_id, SID)

    def test_absent_products_key_treated_as_empty(self):
        payload = json.dumps({"supplier": None}).encode()
        result = self.parser.parse(payload, CID, SID)
        self.assertEqual(result.record_count, 0)

    def test_empty_products_list_valid(self):
        payload = json.dumps({"products": []}).encode()
        result = self.parser.parse(payload, CID, SID)
        self.assertEqual(result.record_count, 0)

    def test_price_stored_as_string_no_float_rounding(self):
        payload = json.dumps({
            "products": [{"source_product_id": "X1", "price_vnd": 45000}]
        }).encode()
        result = self.parser.parse(payload, CID, SID)
        self.assertIsInstance(result.products[0].commercial.price_vnd_str, str)

    # -----------------------------------------------------------------------
    # Missing field errors
    # -----------------------------------------------------------------------

    def test_missing_source_product_id_raises_missing_field(self):
        payload = json.dumps({"products": [{"name": "No ID"}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)
        self.assertIn("source_product_id", ctx.exception.field_path)

    def test_missing_supplier_name_raises_missing_field(self):
        payload = json.dumps({"supplier": {"province": "HCM"}, "products": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.MISSING_FIELD)
        self.assertIn("supplier_name", ctx.exception.field_path)

    # -----------------------------------------------------------------------
    # Null field errors
    # -----------------------------------------------------------------------

    def test_null_source_product_id_raises_null_field(self):
        payload = json.dumps({
            "products": [{"source_product_id": None}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    def test_null_supplier_name_raises_null_field(self):
        payload = json.dumps({"supplier": {"supplier_name": None}, "products": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.NULL_FIELD)

    # -----------------------------------------------------------------------
    # Wrong type errors
    # -----------------------------------------------------------------------

    def test_int_source_product_id_raises_wrong_type(self):
        payload = json.dumps({"products": [{"source_product_id": 1}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_float_moq_raises_wrong_type(self):
        payload = json.dumps({
            "products": [{"source_product_id": "X1", "moq": 2.5}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_int_wholesale_available_raises_wrong_type(self):
        payload = json.dumps({
            "products": [{"source_product_id": "X1", "wholesale_available": 1}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_list_supplier_block_raises_wrong_type(self):
        payload = json.dumps({"supplier": ["list"], "products": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_int_supplier_name_raises_wrong_type(self):
        payload = json.dumps({"supplier": {"supplier_name": 123}, "products": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    def test_string_price_raises_wrong_type(self):
        payload = json.dumps({
            "products": [{"source_product_id": "X1", "price_vnd": "cheap"}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)

    # -----------------------------------------------------------------------
    # Wrong format errors
    # -----------------------------------------------------------------------

    def test_blank_source_product_id_raises_wrong_format(self):
        payload = json.dumps({"products": [{"source_product_id": "   "}]}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_blank_supplier_name_raises_wrong_format(self):
        payload = json.dumps({"supplier": {"supplier_name": "  "}, "products": []}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_invalid_tax_code_raises_wrong_format(self):
        payload = json.dumps({
            "supplier": {"supplier_name": "ABC", "tax_code": "INVALID"},
            "products": [],
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)
        self.assertIn("tax_code", ctx.exception.field_path)

    def test_negative_price_raises_wrong_format(self):
        payload = json.dumps({
            "products": [{"source_product_id": "X1", "price_vnd": -1}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_zero_moq_raises_wrong_format(self):
        payload = json.dumps({
            "products": [{"source_product_id": "X1", "moq": 0}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    def test_negative_lead_time_raises_wrong_format(self):
        payload = json.dumps({
            "products": [{"source_product_id": "X1", "lead_time_days": -1}]
        }).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_FORMAT)

    # -----------------------------------------------------------------------
    # Invalid structure
    # -----------------------------------------------------------------------

    def test_non_json_raises_invalid_structure(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"\xff bad", CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)

    def test_json_array_at_root_raises_invalid_structure(self):
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(b"[]", CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.INVALID_STRUCTURE)

    def test_products_not_a_list_raises_wrong_type(self):
        payload = json.dumps({"products": "not-a-list"}).encode()
        with self.assertRaises(ParseError) as ctx:
            self.parser.parse(payload, CID, SID)
        self.assertEqual(ctx.exception.kind, ParseErrorKind.WRONG_TYPE)


if __name__ == "__main__":
    unittest.main()
