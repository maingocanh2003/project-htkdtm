import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from etl.pipeline import EtlPipeline
from etl.processed_storage import ProcessedStorage
from etl.raw_storage import RawStorage
from etl.source_registry import (
    CollectionMetadata,
    create_project_source_registry,
)


_CSV_HEADER = (
    "Interest Over Time\n"
    "Week,ceramic,ceramics,pottery,porcelain,stoneware\n"
)
_CSV_ROW = "2025-01-05,10,20,30,40,50\n"


class EtlPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.raw_root = root / "raw"
        self.processed_root = root / "processed"
        self.quarantine_root = root / "quarantine"
        self.raw_storage = RawStorage(
            self.raw_root,
            create_project_source_registry(),
        )
        self.pipeline = EtlPipeline(
            self.raw_root,
            self.processed_root,
            self.quarantine_root,
        )

    def _save_trends(self, payload, collected_at):
        return self.raw_storage.save(
            payload,
            CollectionMetadata(
                collected_at=collected_at,
                source_id="google_trends",
                data_format="csv",
            ),
            {
                "geo": "VN",
                "data_type": "interest_over_time",
                "group_id": "g1",
            },
        )

    def _save_trade(self, payload, collected_at):
        return self.raw_storage.save(
            payload,
            CollectionMetadata(
                collected_at=collected_at,
                source_id="un_comtrade",
                data_format="json",
                endpoint="/public/v1/preview/C/A/HS",
            ),
            {
                "reporterCode": "842",
                "partnerCode": "0",
                "cmdCode": "6911",
                "flowCode": "M",
                "period": "2022",
            },
        )

    @staticmethod
    def _collected_at(day):
        return datetime(2026, 11, day, 9, 0, tzinfo=timezone.utc)

    def test_pipeline_quarantines_same_collection_duplicate_once_on_rerun(self):
        payload = (_CSV_HEADER + _CSV_ROW + _CSV_ROW).encode("utf-8")
        collection_id = self._save_trends(payload, self._collected_at(1))
        raw_payload = self.raw_storage.read_payload("google_trends", collection_id)

        first = self.pipeline.run(["google_trends"])[0]
        quarantine_files = list(
            (self.quarantine_root / "google_trends" / "entries").glob("*.json")
        )
        second = self.pipeline.run(["google_trends"])[0]
        snapshot_path = self.processed_root / "google_trends" / "records.jsonl"

        self.assertEqual(first.parsed_records, 2)
        self.assertEqual(first.duplicate_candidates, 1)
        self.assertEqual(first.quarantined_new, 1)
        self.assertEqual(first.processed_records, 1)
        self.assertEqual(second.already_quarantined, 1)
        self.assertEqual(second.quarantined_new, 0)
        self.assertEqual(len(quarantine_files), 1)
        self.assertEqual(
            len(snapshot_path.read_text(encoding="utf-8").splitlines()),
            1,
        )
        self.assertEqual(
            self.raw_storage.read_payload("google_trends", collection_id),
            raw_payload,
        )

    def test_identical_rows_from_distinct_collections_are_preserved(self):
        payload = (_CSV_HEADER + _CSV_ROW).encode("utf-8")
        first_id = self._save_trends(payload, self._collected_at(1))
        second_id = self._save_trends(payload, self._collected_at(2))

        result = self.pipeline.run(["google_trends"])[0]
        snapshot = self.processed_root / "google_trends" / "records.jsonl"

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(result.duplicate_candidates, 0)
        self.assertEqual(result.processed_records, 2)
        self.assertEqual(len(snapshot.read_text(encoding="utf-8").splitlines()), 2)
        self.assertFalse((self.quarantine_root / "google_trends").exists())

    def test_dry_run_does_not_write_processed_or_quarantine_data(self):
        payload = (_CSV_HEADER + _CSV_ROW + _CSV_ROW).encode("utf-8")
        self._save_trends(payload, self._collected_at(1))

        result = self.pipeline.run(["google_trends"], dry_run=True)[0]

        self.assertEqual(result.would_process, 1)
        self.assertEqual(result.would_quarantine, 1)
        self.assertFalse(result.snapshot_written)
        self.assertFalse(self.processed_root.exists())
        self.assertFalse(self.quarantine_root.exists())

    def test_unconfirmed_cross_collection_trade_candidate_is_preserved(self):
        payload = (
            Path(__file__).parent / "fixtures" / "un_comtrade_preview_response.json"
        ).read_bytes()
        self._save_trade(payload, self._collected_at(1))
        self._save_trade(payload, self._collected_at(2))

        result = self.pipeline.run(["un_comtrade"])[0]

        self.assertEqual(result.duplicate_candidates, 1)
        self.assertEqual(result.unresolved_duplicate_candidates, 1)
        self.assertEqual(result.processed_records, 2)
        self.assertFalse((self.quarantine_root / "un_comtrade").exists())

    def test_collection_error_does_not_replace_last_processed_snapshot(self):
        storage = ProcessedStorage(self.processed_root)
        path = storage.write_source_snapshot(
            "google_trends",
            [{"value": "last-good-snapshot"}],
        ).path
        original = path.read_bytes()
        self._save_trends(b"\xffnot utf-8", self._collected_at(1))

        result = self.pipeline.run(["google_trends"])[0]

        self.assertEqual(result.parser_errors, 1)
        self.assertFalse(result.snapshot_written)
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(result.errors)

    def test_error_in_one_source_does_not_block_another_source(self):
        self._save_trends(b"\xffnot utf-8", self._collected_at(1))
        trade_payload = (
            Path(__file__).parent / "fixtures" / "un_comtrade_preview_response.json"
        ).read_bytes()
        self._save_trade(trade_payload, self._collected_at(2))

        results = self.pipeline.run(
            ["google_trends", "un_comtrade"],
        )

        self.assertEqual(results[0].parser_errors, 1)
        self.assertFalse(results[0].snapshot_written)
        self.assertTrue(results[1].snapshot_written)
        self.assertEqual(results[1].processed_records, 1)


if __name__ == "__main__":
    unittest.main()
