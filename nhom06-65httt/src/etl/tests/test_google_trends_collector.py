import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from etl.google_trends_collector import (
    GoogleTrendsExportAdapter,
    GoogleTrendsExportError,
    GoogleTrendsRequest,
    TrendsDataType,
)
from etl.raw_storage import CollectionStatus, RawStorage
from etl.source_registry import create_project_source_registry


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "google_trends_ui_export_fixture.csv"
)


class GoogleTrendsExportAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.registry = create_project_source_registry()
        self.storage = RawStorage(Path(self.temp_dir.name), self.registry)
        self.adapter = GoogleTrendsExportAdapter(self.storage, self.registry)
        self.request = GoogleTrendsRequest(
            keywords=("ceramic dinnerware", "handmade pottery mug"),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            geo="US",
            data_type=TrendsDataType.INTEREST_OVER_TIME,
            search_type="web",
            interval="weekly",
        )

    def test_ingest_preserves_export_bytes_and_records_provenance(self):
        raw_payload = FIXTURE_PATH.read_bytes()

        collection_id = self.adapter.ingest(raw_payload, self.request)

        self.assertEqual(
            self.storage.read_payload("google_trends", collection_id),
            raw_payload,
        )
        manifest = self.storage.read_manifest("google_trends", collection_id)
        metadata = manifest["metadata"]
        self.assertEqual(metadata["source_id"], "google_trends")
        self.assertEqual(metadata["data_format"], "csv")
        self.assertEqual(metadata["status"], "success")
        self.assertEqual(metadata["request_parameters"]["keywords"], list(self.request.keywords))
        self.assertEqual(metadata["request_parameters"]["period_start"], "2025-01-01")
        self.assertEqual(metadata["request_parameters"]["period_end"], "2025-12-31")
        self.assertEqual(metadata["request_parameters"]["geo"], "US")
        self.assertEqual(
            metadata["request_parameters"]["data_type"],
            "interest_over_time",
        )
        self.assertEqual(
            metadata["request_parameters"]["interval"],
            "weekly",
        )
        self.assertEqual(
            metadata["request_parameters"]["value_semantics"]["scale"],
            "0-100 per selected query, geography, and time range",
        )
        self.assertIn(
            "not the Google Trends API alpha",
            metadata["request_parameters"]["value_semantics"]["scope"],
        )
        self.assertTrue(metadata["request_parameters"]["attribution_required"])
        self.assertIn(
            "Google Trends",
            metadata["request_parameters"]["attribution_text"],
        )

    def test_adapter_passes_fixture_and_provenance_to_raw_storage_mock(self):
        raw_storage = Mock(spec=RawStorage)
        raw_storage.save.return_value = "mock-collection-id"
        adapter = GoogleTrendsExportAdapter(raw_storage, self.registry)
        payload = FIXTURE_PATH.read_bytes()

        collection_id = adapter.ingest(payload, self.request)

        self.assertEqual(collection_id, "mock-collection-id")
        args, kwargs = raw_storage.save.call_args
        self.assertEqual(args[0], payload)
        self.assertEqual(args[1].source_id, "google_trends")
        self.assertEqual(args[1].data_format, "csv")
        self.assertEqual(args[2]["geo"], "US")
        self.assertEqual(kwargs["status"], CollectionStatus.SUCCESS)

    def test_related_query_scale_is_not_assumed_to_be_zero_to_one_hundred(self):
        request = GoogleTrendsRequest(
            keywords=("ceramic dinnerware",),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            geo="US",
            data_type=TrendsDataType.RELATED_QUERIES,
            search_type="web",
        )

        collection_id = self.adapter.ingest(
            b"synthetic,uninterpreted related-query fixture",
            request,
        )
        manifest = self.storage.read_manifest("google_trends", collection_id)

        semantics = manifest["metadata"]["request_parameters"]["value_semantics"]
        self.assertEqual(semantics["scale"], "not_assumed")
        self.assertEqual(semantics["unit"], "not_interpreted")

    def test_empty_export_is_preserved_and_marked_failed(self):
        with self.assertRaises(GoogleTrendsExportError) as raised:
            self.adapter.ingest(b"", self.request)

        self.assertEqual(
            self.storage.read_payload(
                "google_trends", raised.exception.collection_id
            ),
            b"",
        )
        manifest = self.storage.read_manifest(
            "google_trends", raised.exception.collection_id
        )
        self.assertEqual(manifest["metadata"]["status"], "failed")

    def test_request_requires_keywords_period_geo_and_data_type(self):
        with self.assertRaisesRegex(ValueError, "keywords"):
            GoogleTrendsRequest(
                keywords=(),
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
                geo="US",
                data_type=TrendsDataType.INTEREST_OVER_TIME,
                search_type="web",
                interval="weekly",
            )
        with self.assertRaisesRegex(ValueError, "period_start"):
            GoogleTrendsRequest(
                keywords=("ceramic dinnerware",),
                period_start=date(2025, 12, 31),
                period_end=date(2025, 1, 1),
                geo="US",
                data_type=TrendsDataType.INTEREST_OVER_TIME,
                search_type="web",
                interval="weekly",
            )
        with self.assertRaisesRegex(ValueError, "explicit interval"):
            GoogleTrendsRequest(
                keywords=("ceramic dinnerware",),
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
                geo="US",
                data_type=TrendsDataType.INTEREST_OVER_TIME,
                search_type="web",
            )

    def test_invalid_export_type_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "payload must be bytes"):
            self.adapter.ingest("not bytes", self.request)


if __name__ == "__main__":
    unittest.main()
