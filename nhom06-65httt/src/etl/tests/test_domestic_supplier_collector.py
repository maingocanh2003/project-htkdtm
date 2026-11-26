"""Tests for the D9 domestic supplier and product collector."""

import json
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from etl.domestic_supplier_collector import (
    CommercialInfo,
    DomesticSupplierCollectionResult,
    DomesticSupplierFileAdapter,
    DomesticSupplierHttpCollector,
    DomesticSupplierResponseError,
    SupplierProductRecord,
    SupplierRecord,
    _parse_supplier_response,
)
from etl.http_client import HttpResponse
from etl.raw_storage import CollectionStatus, RawStorage
from etl.source_registry import (
    SourceRegistry,
    SourceStatus,
    create_project_source_registry,
)


FIXTURES = Path(__file__).parent / "fixtures"
THEGIOIGOM_FIXTURE = FIXTURES / "thegioigom_products_response.json"
GOC_GOM_FIXTURE = FIXTURES / "goc_gom_viet_products_response.json"
MINH_LONG_FIXTURE = FIXTURES / "minh_long_1_file_catalog.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_active_registry(*source_ids: str) -> SourceRegistry:
    """Return a registry with selected sources set to ACTIVE."""
    registry = SourceRegistry()
    for source in create_project_source_registry().list_sources():
        if source.source_id in source_ids:
            source = replace(source, status=SourceStatus.ACTIVE)
        registry.register(source)
    return registry


# ---------------------------------------------------------------------------
# Parser unit tests (no I/O)
# ---------------------------------------------------------------------------


class ParseSupplierResponseTests(unittest.TestCase):
    """Test _parse_supplier_response in isolation."""

    def test_parses_full_supplier_and_two_products(self):
        payload = THEGIOIGOM_FIXTURE.read_bytes()
        products, supplier = _parse_supplier_response(payload, "thegioigom")

        self.assertIsNotNone(supplier)
        self.assertEqual(supplier.supplier_name, "Gốm Sứ Thế Giới Gốm")
        self.assertEqual(supplier.tax_code, "0314567890")
        self.assertEqual(supplier.province, "TP. Hồ Chí Minh")
        self.assertEqual(supplier.business_type, "sản xuất và phân phối")
        # Năng lực sản xuất không được khai báo — phải là None
        self.assertIsNone(supplier.declared_capacity_note)

        self.assertEqual(len(products), 2)
        p0 = products[0]
        self.assertEqual(p0.source_id, "thegioigom")
        self.assertEqual(p0.source_product_id, "TGG-001")
        self.assertEqual(p0.name, "Bát ăn cơm hoa đào men trắng")
        self.assertEqual(p0.material, "Sứ cao cấp")
        self.assertEqual(p0.origin_region, "Bình Dương")
        self.assertEqual(p0.commercial.price_vnd, Decimal("45000"))
        self.assertEqual(p0.commercial.currency, "VND")
        self.assertEqual(p0.commercial.moq, 12)
        # lead_time không được khai báo — không được suy diễn
        self.assertIsNone(p0.commercial.lead_time_days)
        self.assertTrue(p0.commercial.wholesale_available)

        p1 = products[1]
        self.assertEqual(p1.source_product_id, "TGG-002")
        self.assertFalse(p1.commercial.wholesale_available)
        self.assertIsNone(p1.commercial.moq)

    def test_parses_supplier_null_block_gives_none(self):
        payload = GOC_GOM_FIXTURE.read_bytes()
        products, supplier = _parse_supplier_response(payload, "goc_gom_viet")

        self.assertIsNone(supplier)
        self.assertEqual(len(products), 1)
        p = products[0]
        self.assertEqual(p.source_product_id, "GGV-BT-0045")
        self.assertEqual(p.commercial.price_vnd, Decimal("320000"))
        self.assertEqual(p.commercial.moq, 6)
        self.assertEqual(p.commercial.lead_time_days, 14)

    def test_parses_product_with_all_commercial_fields_null(self):
        """Thông tin thương mại hoàn toàn vắng không được suy diễn."""
        payload = MINH_LONG_FIXTURE.read_bytes()
        products, supplier = _parse_supplier_response(payload, "minh_long_1")

        self.assertIsNone(supplier)
        p = products[0]
        c = p.commercial
        self.assertIsNone(c.price_vnd)
        self.assertIsNone(c.currency)
        self.assertIsNone(c.moq)
        self.assertIsNone(c.lead_time_days)
        self.assertIsNone(c.wholesale_available)

    def test_missing_source_product_id_raises_error(self):
        payload = json.dumps({"products": [{"name": "No ID"}]}).encode()
        with self.assertRaisesRegex(
            DomesticSupplierResponseError, "source_product_id"
        ):
            _parse_supplier_response(payload, "thegioigom")

    def test_non_json_payload_raises_error(self):
        with self.assertRaisesRegex(DomesticSupplierResponseError, "valid JSON"):
            _parse_supplier_response(b"\xff not json", "thegioigom")

    def test_non_object_root_raises_error(self):
        with self.assertRaisesRegex(
            DomesticSupplierResponseError, "JSON object"
        ):
            _parse_supplier_response(b"[1, 2, 3]", "thegioigom")

    def test_products_field_not_a_list_raises_error(self):
        payload = json.dumps({"products": "not-a-list"}).encode()
        with self.assertRaisesRegex(DomesticSupplierResponseError, "array"):
            _parse_supplier_response(payload, "thegioigom")

    def test_negative_price_raises_error(self):
        payload = json.dumps(
            {"products": [{"source_product_id": "X1", "price_vnd": -1}]}
        ).encode()
        with self.assertRaisesRegex(DomesticSupplierResponseError, "nonnegative"):
            _parse_supplier_response(payload, "thegioigom")

    def test_non_integer_moq_raises_error(self):
        payload = json.dumps(
            {"products": [{"source_product_id": "X1", "moq": 2.5}]}
        ).encode()
        with self.assertRaisesRegex(DomesticSupplierResponseError, "moq"):
            _parse_supplier_response(payload, "thegioigom")

    def test_zero_moq_raises_error(self):
        payload = json.dumps(
            {"products": [{"source_product_id": "X1", "moq": 0}]}
        ).encode()
        with self.assertRaisesRegex(DomesticSupplierResponseError, "moq"):
            _parse_supplier_response(payload, "thegioigom")

    def test_non_boolean_wholesale_raises_error(self):
        payload = json.dumps(
            {"products": [{"source_product_id": "X1", "wholesale_available": 1}]}
        ).encode()
        with self.assertRaisesRegex(DomesticSupplierResponseError, "boolean"):
            _parse_supplier_response(payload, "thegioigom")

    def test_supplier_block_not_dict_raises_error(self):
        payload = json.dumps({"supplier": ["list"], "products": []}).encode()
        with self.assertRaisesRegex(DomesticSupplierResponseError, "object"):
            _parse_supplier_response(payload, "thegioigom")

    def test_supplier_name_empty_raises_error(self):
        payload = json.dumps(
            {"supplier": {"supplier_name": "   "}, "products": []}
        ).encode()
        with self.assertRaisesRegex(
            DomesticSupplierResponseError, "supplier_name"
        ):
            _parse_supplier_response(payload, "thegioigom")

    def test_invalid_tax_code_raises_error(self):
        payload = json.dumps(
            {
                "supplier": {
                    "supplier_name": "Công Ty ABC",
                    "tax_code": "INVALID",
                },
                "products": [],
            }
        ).encode()
        with self.assertRaisesRegex(DomesticSupplierResponseError, "tax_code"):
            _parse_supplier_response(payload, "thegioigom")

    def test_product_non_string_name_raises_error(self):
        payload = json.dumps(
            {"products": [{"source_product_id": "X1", "name": 123}]}
        ).encode()
        with self.assertRaisesRegex(DomesticSupplierResponseError, "name"):
            _parse_supplier_response(payload, "thegioigom")

    def test_empty_products_list_is_valid(self):
        payload = json.dumps({"products": []}).encode()
        products, supplier = _parse_supplier_response(payload, "thegioigom")
        self.assertEqual(products, [])
        self.assertIsNone(supplier)

    def test_products_field_absent_treated_as_empty(self):
        payload = json.dumps({}).encode()
        products, supplier = _parse_supplier_response(payload, "thegioigom")
        self.assertEqual(products, [])


# ---------------------------------------------------------------------------
# HTTP collector tests (mocked HTTP + temp storage)
# ---------------------------------------------------------------------------


class DomesticSupplierHttpCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.registry = _make_active_registry("thegioigom", "goc_gom_viet")
        self.storage = RawStorage(Path(self.temp_dir.name), self.registry)
        self.http_client = Mock()

    def _make_collector(self, source_id: str) -> DomesticSupplierHttpCollector:
        return DomesticSupplierHttpCollector(
            source_id, self.http_client, self.storage, self.registry
        )

    # -- happy path --

    def test_collect_products_saves_raw_payload_and_provenance(self):
        raw = THEGIOIGOM_FIXTURE.read_bytes()
        self.http_client.get.return_value = HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=raw,
            url="https://thegioigom.com/api/products",
        )

        collector = self._make_collector("thegioigom")
        result = collector.collect_products("/api/products", {"page": 1})

        self.assertIsInstance(result, DomesticSupplierCollectionResult)
        self.assertEqual(result.source_id, "thegioigom")
        self.assertEqual(result.status, CollectionStatus.SUCCESS)
        self.assertEqual(result.record_count, 2)
        self.assertEqual(result.source_url, "https://thegioigom.com/api/products")

        # Kiểm tra raw payload được lưu nguyên vẹn
        saved = self.storage.read_payload("thegioigom", result.collection_id)
        self.assertEqual(saved, raw)

        # Kiểm tra provenance manifest
        manifest = self.storage.read_manifest(
            "thegioigom", result.collection_id
        )
        self.assertEqual(manifest["metadata"]["source_id"], "thegioigom")
        self.assertEqual(manifest["metadata"]["data_format"], "json")
        self.assertEqual(manifest["metadata"]["status"], "success")
        self.assertEqual(
            manifest["metadata"]["endpoint"], "/api/products"
        )
        self.assertIn("collected_at", manifest["metadata"])

    def test_collect_products_calls_http_with_correct_url_and_params(self):
        raw = GOC_GOM_FIXTURE.read_bytes()
        self.http_client.get.return_value = HttpResponse(
            200, {}, raw, "https://gocgomviet.com/api/catalog"
        )

        collector = self._make_collector("goc_gom_viet")
        collector.collect_products("/api/catalog", {"category": "am-tra"})

        self.http_client.get.assert_called_once_with(
            "https://gocgomviet.com/api/catalog",
            params={"category": "am-tra"},
        )

    def test_collect_products_supplier_record_has_no_inferred_capacity(self):
        raw = THEGIOIGOM_FIXTURE.read_bytes()
        self.http_client.get.return_value = HttpResponse(
            200, {}, raw, "https://thegioigom.com/api/products"
        )
        collector = self._make_collector("thegioigom")
        result = collector.collect_products("/api/products")

        self.assertIsNotNone(result.supplier)
        # Nguồn không khai báo năng lực — phải là None
        self.assertIsNone(result.supplier.declared_capacity_note)

    def test_collect_products_commercial_info_not_inferred_when_absent(self):
        """MOQ, lead_time, giá không được tự khẳng định khi nguồn không cung cấp."""
        raw = MINH_LONG_FIXTURE.read_bytes()
        # Dùng file adapter source cho minh_long_1 nhưng kiểm tra parser riêng
        products, _ = _parse_supplier_response(raw, "minh_long_1")
        c = products[0].commercial
        self.assertIsNone(c.price_vnd)
        self.assertIsNone(c.moq)
        self.assertIsNone(c.lead_time_days)

    def test_malformed_response_saved_as_failed_and_error_carries_collection_id(self):
        bad_payload = b'{"products": [{"name": "no-id"}]}'
        self.http_client.get.return_value = HttpResponse(
            200, {}, bad_payload, "https://thegioigom.com/api/products"
        )
        collector = self._make_collector("thegioigom")

        with self.assertRaises(DomesticSupplierResponseError) as ctx:
            collector.collect_products("/api/products")

        err = ctx.exception
        self.assertIsNotNone(err.collection_id)
        saved = self.storage.read_payload("thegioigom", err.collection_id)
        self.assertEqual(saved, bad_payload)
        manifest = self.storage.read_manifest("thegioigom", err.collection_id)
        self.assertEqual(manifest["metadata"]["status"], "failed")

    def test_non_json_response_saved_as_failed(self):
        bad_payload = b"\xff\xfe not json"
        self.http_client.get.return_value = HttpResponse(
            200, {}, bad_payload, "https://thegioigom.com/api/products"
        )
        collector = self._make_collector("thegioigom")

        with self.assertRaisesRegex(DomesticSupplierResponseError, "valid JSON") as ctx:
            collector.collect_products("/api/products")

        self.assertIsNotNone(ctx.exception.collection_id)

    # -- guard tests --

    def test_planned_source_cannot_collect(self):
        planned_registry = create_project_source_registry()
        storage = RawStorage(Path(self.temp_dir.name), planned_registry)
        with self.assertRaisesRegex(ValueError, "ACTIVE"):
            DomesticSupplierHttpCollector(
                "thegioigom", self.http_client, storage, planned_registry
            )
        self.http_client.get.assert_not_called()

    def test_wrong_source_group_raises_error(self):
        active_registry = _make_active_registry("etsy")
        storage = RawStorage(Path(self.temp_dir.name), active_registry)
        with self.assertRaisesRegex(ValueError, "DOMESTIC_SUPPLIER_CATALOGS"):
            DomesticSupplierHttpCollector(
                "etsy", self.http_client, storage, active_registry
            )

    def test_empty_endpoint_raises_error(self):
        collector = self._make_collector("thegioigom")
        with self.assertRaisesRegex(ValueError, "endpoint"):
            collector.collect_products("")
        self.http_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# File adapter tests
# ---------------------------------------------------------------------------


class DomesticSupplierFileAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.registry = create_project_source_registry()
        self.storage = RawStorage(Path(self.temp_dir.name), self.registry)

    def _make_adapter(self, source_id: str) -> DomesticSupplierFileAdapter:
        return DomesticSupplierFileAdapter(source_id, self.storage, self.registry)

    def test_ingest_preserves_bytes_without_parsing(self):
        payload = MINH_LONG_FIXTURE.read_bytes()
        adapter = self._make_adapter("minh_long_1")

        collection_id = adapter.ingest(
            payload,
            data_format="json",
            origin_url="https://minhlongceramics.com/catalog",
        )

        saved = self.storage.read_payload("minh_long_1", collection_id)
        self.assertEqual(saved, payload)

        manifest = self.storage.read_manifest("minh_long_1", collection_id)
        self.assertEqual(manifest["metadata"]["source_id"], "minh_long_1")
        self.assertEqual(manifest["metadata"]["data_format"], "json")
        self.assertEqual(manifest["metadata"]["status"], "success")
        self.assertEqual(
            manifest["metadata"]["request_parameters"]["ingestion_method"],
            "local_file",
        )
        self.assertEqual(
            manifest["metadata"]["request_parameters"]["origin_url"],
            "https://minhlongceramics.com/catalog",
        )

    def test_ingest_bat_trang_csv_catalog(self):
        payload = b"product_id,name,price\nBT-001,Am tra,320000"
        adapter = self._make_adapter("bat_trang")

        collection_id = adapter.ingest(payload, data_format="csv")

        saved = self.storage.read_payload("bat_trang", collection_id)
        self.assertEqual(saved, payload)
        manifest = self.storage.read_manifest("bat_trang", collection_id)
        self.assertEqual(manifest["metadata"]["data_format"], "csv")

    def test_ingest_non_bytes_raises_type_error(self):
        adapter = self._make_adapter("minh_long_1")
        with self.assertRaises(TypeError):
            adapter.ingest("not bytes", "json")  # type: ignore[arg-type]

    def test_ingest_empty_data_format_raises_error(self):
        adapter = self._make_adapter("minh_long_1")
        with self.assertRaises(ValueError):
            adapter.ingest(b"some bytes", "")

    def test_wrong_source_group_raises_error(self):
        with self.assertRaisesRegex(ValueError, "DOMESTIC_SUPPLIER_CATALOGS"):
            DomesticSupplierFileAdapter("etsy", self.storage, self.registry)


# ---------------------------------------------------------------------------
# Source registry integration: new domestic sources are present
# ---------------------------------------------------------------------------


class DomesticSourceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = create_project_source_registry()

    def test_all_domestic_sources_registered(self):
        for sid in ("minh_long_1", "bat_trang", "thegioigom", "goc_gom_viet"):
            with self.subTest(source_id=sid):
                source = self.registry.get(sid)
                from etl.source_registry import SourceGroup
                self.assertEqual(
                    source.source_group, SourceGroup.DOMESTIC_SUPPLIER_CATALOGS
                )

    def test_http_capable_domestic_sources_have_base_url(self):
        for sid in ("thegioigom", "goc_gom_viet"):
            with self.subTest(source_id=sid):
                source = self.registry.get(sid)
                self.assertIsNotNone(source.base_url)
                self.assertTrue(source.base_url.startswith("https://"))

    def test_file_dataset_sources_may_have_no_base_url(self):
        for sid in ("minh_long_1", "bat_trang"):
            with self.subTest(source_id=sid):
                source = self.registry.get(sid)
                # base_url is optional for FILE_DATASET sources
                from etl.source_registry import SourceType
                self.assertEqual(source.source_type, SourceType.FILE_DATASET)


if __name__ == "__main__":
    unittest.main()
