import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from etl.config import Settings
from etl.raw_storage import CollectionStatus, RawStorage
from etl.source_registry import (
    CollectionMetadata,
    create_project_source_registry,
)


class RawStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "raw"
        self.registry = create_project_source_registry()
        self.storage = RawStorage(self.root, self.registry)

    def make_metadata(self):
        return CollectionMetadata(
            collected_at=datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc),
            source_id="un_comtrade",
            data_format="json",
            version="v1",
            endpoint="/public/v1/preview/C/A/HS",
        )

    def test_save_separates_raw_payload_and_manifest(self):
        payload = b'\x00{"raw":"\xff"}'
        parameters = {"reporterCode": "704", "period": "2023"}

        collection_id = self.storage.save(
            payload,
            self.make_metadata(),
            parameters,
            status=CollectionStatus.PARTIAL,
        )
        collection_dir = self.root / "un_comtrade" / collection_id
        manifest_path = collection_dir / "manifest.json"
        payload_path = collection_dir / "payload.bin"

        self.assertTrue(manifest_path.is_file())
        self.assertTrue(payload_path.is_file())
        self.assertEqual(payload_path.read_bytes(), payload)
        manifest = self.storage.read_manifest("un_comtrade", collection_id)
        metadata = manifest["metadata"]
        self.assertEqual(metadata["source_id"], "un_comtrade")
        self.assertEqual(
            metadata["collected_at"],
            self.make_metadata().collected_at.isoformat(),
        )
        self.assertEqual(metadata["request_parameters"], parameters)
        self.assertEqual(metadata["status"], "partial")
        self.assertEqual(metadata["data_format"], "json")
        self.assertEqual(metadata["version"], "v1")
        self.assertEqual(metadata["endpoint"], "/public/v1/preview/C/A/HS")
        self.assertEqual(
            metadata["checksum"],
            {
                "algorithm": "sha256",
                "value": hashlib.sha256(payload).hexdigest(),
            },
        )
        self.assertEqual(manifest["payload_file"], "payload.bin")

    def test_payload_can_be_retrieved_by_collection_id(self):
        payload = b"original raw bytes"
        first_id = self.storage.save(payload, self.make_metadata(), {})
        second_id = self.storage.save(b"another run", self.make_metadata(), {})

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(self.storage.read_payload("un_comtrade", first_id), payload)
        self.assertEqual(
            self.storage.read_payload("un_comtrade", second_id),
            b"another run",
        )

    def test_collection_id_collision_does_not_overwrite_existing_payload(self):
        fixed_uuid = type("FixedUUID", (), {"hex": "a" * 32})()
        with patch("etl.raw_storage.uuid.uuid4", return_value=fixed_uuid):
            collection_id = self.storage.save(
                b"original", self.make_metadata(), {}
            )
            with self.assertRaises(FileExistsError):
                self.storage.save(b"replacement", self.make_metadata(), {})

        self.assertEqual(
            self.storage.read_payload("un_comtrade", collection_id),
            b"original",
        )

    def test_read_detects_payload_checksum_mismatch(self):
        collection_id = self.storage.save(
            b"saved payload", self.make_metadata(), {}
        )
        payload_path = self.root / "un_comtrade" / collection_id / "payload.bin"
        payload_path.write_bytes(b"modified payload")

        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.storage.read_payload("un_comtrade", collection_id)

    def test_invalid_source_or_collection_id_cannot_be_used_as_a_path(self):
        with self.assertRaises(KeyError):
            self.storage.read_payload("../../outside", "a" * 32)
        with self.assertRaisesRegex(ValueError, "collection_id"):
            self.storage.read_payload("un_comtrade", "../outside")

    def test_non_bytes_payload_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "payload must be bytes"):
            self.storage.save("raw text", self.make_metadata(), {})

    def test_request_parameters_must_be_json_serializable(self):
        with self.assertRaises(TypeError):
            self.storage.save(
                b"payload",
                self.make_metadata(),
                {"invalid": object()},
            )
        self.assertFalse((self.root / "un_comtrade").exists())

    def test_write_error_is_reported_and_partial_run_is_removed(self):
        original_open = Path.open

        def fail_payload_open(path, *args, **kwargs):
            if path.name == "payload.bin":
                raise PermissionError("test write failure")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", fail_payload_open):
            with self.assertRaisesRegex(PermissionError, "test write failure"):
                self.storage.save(b"payload", self.make_metadata(), {})

        source_dir = self.root / "un_comtrade"
        self.assertTrue(source_dir.is_dir())
        self.assertEqual(list(source_dir.iterdir()), [])

    def test_from_settings_uses_configured_local_directory(self):
        configured = Path(self.temp_dir.name) / "configured-raw"
        storage = RawStorage.from_settings(
            Settings(raw_data_dir=configured), self.registry
        )
        collection_id = storage.save(b"payload", self.make_metadata(), {})

        self.assertTrue(
            (configured / "un_comtrade" / collection_id / "payload.bin").is_file()
        )


if __name__ == "__main__":
    unittest.main()
