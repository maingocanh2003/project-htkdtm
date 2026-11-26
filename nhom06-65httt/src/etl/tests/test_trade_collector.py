import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import Mock

from etl.http_client import HttpResponse
from etl.raw_storage import CollectionStatus, RawStorage
from etl.source_registry import create_project_source_registry
from etl.trade_collector import (
    ITCTradeMapFileAdapter,
    TradeFlow,
    TradeResponseError,
    UNComtradeCollector,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "un_comtrade_preview_response.json"
)


class TradeCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.registry = create_project_source_registry()
        self.storage = RawStorage(Path(self.temp_dir.name), self.registry)
        self.http_client = Mock()
        self.collector = UNComtradeCollector(
            self.http_client,
            self.storage,
            self.registry,
        )

    def fixture_response(self):
        payload = FIXTURE_PATH.read_bytes()
        self.http_client.get.return_value = HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=payload,
            url="https://comtradeapi.un.org/public/v1/preview/C/A/HS",
        )
        return payload

    def test_collect_builds_documented_request_and_saves_raw_provenance(self):
        raw_payload = self.fixture_response()

        result = self.collector.collect(
            reporter_code="842",
            partner_code="0",
            hs_code="6911",
            year=2022,
            flow=TradeFlow.IMPORT,
        )

        self.http_client.get.assert_called_once_with(
            "https://comtradeapi.un.org/public/v1/preview/C/A/HS",
            params={
                "reporterCode": "842",
                "period": "2022",
                "cmdCode": "6911",
                "flowCode": "M",
                "partnerCode": "0",
            },
        )
        self.assertEqual(result.status, CollectionStatus.SUCCESS)
        self.assertEqual(result.reported_count, 1)
        self.assertEqual(result.record_count, 1)
        self.assertEqual(result.records[0]["cmdCode"], "6911")
        self.assertEqual(
            self.storage.read_payload("un_comtrade", result.collection_id),
            raw_payload,
        )
        manifest = self.storage.read_manifest("un_comtrade", result.collection_id)
        self.assertEqual(manifest["metadata"]["source_id"], "un_comtrade")
        self.assertEqual(manifest["metadata"]["data_format"], "json")
        self.assertEqual(manifest["metadata"]["version"], "public/v1")
        self.assertEqual(
            manifest["metadata"]["endpoint"],
            "/public/v1/preview/C/A/HS",
        )
        self.assertEqual(manifest["metadata"]["status"], "success")

    def test_preview_limit_marks_payload_as_partial(self):
        records = [{"cmdCode": str(index)} for index in range(500)]
        raw_payload = json.dumps(
            {"count": 500, "data": records, "error": ""}
        ).encode("utf-8")
        self.http_client.get.return_value = HttpResponse(
            200, {}, raw_payload, "https://comtradeapi.un.org/preview"
        )

        result = self.collector.collect("842", "6911", 2022, TradeFlow.EXPORT)

        self.assertEqual(result.status, CollectionStatus.PARTIAL)
        self.assertEqual(result.record_count, 500)
        manifest = self.storage.read_manifest("un_comtrade", result.collection_id)
        self.assertEqual(manifest["metadata"]["status"], "partial")

    def test_invalid_success_body_is_preserved_as_failed_raw(self):
        raw_payload = b'{"error":"fixture upstream error","count":0,"data":[]}'
        self.http_client.get.return_value = HttpResponse(
            200, {}, raw_payload, "https://comtradeapi.un.org/preview"
        )

        with self.assertRaisesRegex(TradeResponseError, "upstream error") as raised:
            self.collector.collect("842", "6911", 2022, TradeFlow.EXPORT)

        self.assertEqual(
            self.storage.read_payload("un_comtrade", raised.exception.collection_id),
            raw_payload,
        )
        manifest = self.storage.read_manifest(
            "un_comtrade", raised.exception.collection_id
        )
        self.assertEqual(manifest["metadata"]["status"], "failed")

    def test_invalid_json_body_is_preserved_as_failed_raw(self):
        raw_payload = b"\xffnot-json"
        self.http_client.get.return_value = HttpResponse(
            200, {}, raw_payload, "https://comtradeapi.un.org/preview"
        )

        with self.assertRaisesRegex(TradeResponseError, "not valid JSON") as raised:
            self.collector.collect("842", "6911", 2022, TradeFlow.EXPORT)

        self.assertEqual(
            self.storage.read_payload("un_comtrade", raised.exception.collection_id),
            raw_payload,
        )

    def test_invalid_query_values_do_not_issue_http_requests(self):
        with self.assertRaisesRegex(ValueError, "reporter_code"):
            self.collector.collect("../842", "6911", 2022, TradeFlow.EXPORT)
        with self.assertRaisesRegex(ValueError, "year"):
            self.collector.collect("842", "6911", 22, TradeFlow.EXPORT)

        self.http_client.get.assert_not_called()

    def test_http_errors_from_shared_client_are_not_hidden(self):
        self.http_client.get.side_effect = HTTPError(
            "https://comtradeapi.un.org",
            429,
            "rate limited",
            Message(),
            io.BytesIO(),
        )

        with self.assertRaises(HTTPError):
            self.collector.collect("842", "6911", 2022, TradeFlow.EXPORT)

    def test_itc_file_adapter_preserves_bytes_without_assuming_schema(self):
        adapter = ITCTradeMapFileAdapter(self.storage, self.registry)
        export_bytes = b"fixture file bytes, format intentionally unspecified"

        collection_id = adapter.ingest(export_bytes, data_format="csv")

        self.assertEqual(
            self.storage.read_payload("itc_trade_map", collection_id),
            export_bytes,
        )
        manifest = self.storage.read_manifest("itc_trade_map", collection_id)
        self.assertEqual(manifest["metadata"]["data_format"], "csv")
        self.assertEqual(
            manifest["metadata"]["request_parameters"],
            {"ingestion_method": "local_file"},
        )


if __name__ == "__main__":
    unittest.main()
