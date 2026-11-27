"""Tests for the read-only ETL pipeline audit."""

import base64
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from etl.pipeline_audit import EtlPipelineAudit
from etl.raw_storage import RawStorage
from etl.source_registry import CollectionMetadata, create_project_source_registry


class PipelineAuditTests(unittest.TestCase):
    def test_empty_raw_root_reports_zero_collections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = EtlPipelineAudit(Path(tmpdir))
            result = audit.audit_source("google_trends")

        self.assertEqual(result.source_id, "google_trends")
        self.assertEqual(result.collections, 0)
        self.assertEqual(result.parsed_records, 0)
        self.assertEqual(result.valid_records, 0)
        self.assertEqual(result.invalid_records, 0)

    def test_unknown_source_returns_collection_count_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "unknown_source"
            (source_dir / "collection-1").mkdir(parents=True)

            result = EtlPipelineAudit(Path(tmpdir)).audit_source("unknown_source")

        self.assertEqual(result.collections, 1)
        self.assertEqual(result.parsed_records, 0)

    def test_audits_lossless_bat_trang_api_envelope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_root = Path(tmpdir) / "raw"
            registry = create_project_source_registry()
            storage = RawStorage(raw_root, registry)
            items = [
                {
                    "id": 1001,
                    "sku": "BT-1001",
                    "name": "Valid product",
                    "prices": {
                        "price": "120000",
                        "currency_code": "VND",
                        "currency_minor_unit": 0,
                    },
                    "categories": [{"name": "Gia dung"}],
                },
                {"name": "Incomplete source item"},
            ]
            response_body = json.dumps(items, ensure_ascii=False).encode("utf-8")
            raw_envelope = json.dumps(
                {
                    "format": "woocommerce_store_api_raw_v1",
                    "responses": [
                        {
                            "page": 1,
                            "status_code": 200,
                            "items_valid": True,
                            "body_base64": base64.b64encode(
                                response_body
                            ).decode("ascii"),
                        }
                    ],
                }
            ).encode("utf-8")
            storage.save(
                raw_envelope,
                CollectionMetadata(
                    collected_at=datetime(2026, 11, 27, tzinfo=timezone.utc),
                    source_id="bat_trang",
                    data_format="json",
                ),
                {},
            )

            result = EtlPipelineAudit(raw_root).audit_source("bat_trang")

        self.assertEqual(result.collections, 1)
        self.assertEqual(result.parser_errors, 0)
        self.assertEqual(result.parsed_records, 1)
        self.assertEqual(result.valid_records, 1)
        self.assertEqual(result.invalid_records, 0)


if __name__ == "__main__":
    unittest.main()
