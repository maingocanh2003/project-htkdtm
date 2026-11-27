"""Local append-only storage for raw payloads and collection manifests."""

import hashlib
import json
import re
import shutil
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .config import Settings
from .source_registry import CollectionMetadata, SourceRegistry


_COLLECTION_ID_PATTERN = re.compile(r"[a-f0-9]{32}")
_PAYLOAD_FILENAME = "payload.bin"
_MANIFEST_FILENAME = "manifest.json"


class CollectionStatus(str, Enum):
    """Outcome recorded for a collection run."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class RawStorage:
    """Store immutable raw bytes separately from searchable JSON manifests."""

    def __init__(self, root: Path, source_registry: SourceRegistry) -> None:
        self._root = Path(root)
        self._source_registry = source_registry

    @classmethod
    def from_settings(
        cls, settings: Settings, source_registry: SourceRegistry
    ) -> "RawStorage":
        """Create storage using the configured local raw-data directory."""
        return cls(settings.raw_data_dir, source_registry)

    def save(
        self,
        payload: bytes,
        metadata: CollectionMetadata,
        request_parameters: Mapping[str, Any],
        status: CollectionStatus = CollectionStatus.SUCCESS,
    ) -> str:
        """Persist raw bytes and a separate manifest; return the collection ID."""
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes to preserve its raw representation")
        if not isinstance(request_parameters, Mapping):
            raise TypeError("request_parameters must be a mapping")
        if not isinstance(status, CollectionStatus):
            raise TypeError("status must be a CollectionStatus")

        self._source_registry.validate_metadata(metadata)
        serialized_parameters = json.dumps(
            dict(request_parameters),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        )
        checksum = hashlib.sha256(payload).hexdigest()

        source_dir = self._root / metadata.source_id
        source_dir.mkdir(parents=True, exist_ok=True)
        collection_id, collection_dir = self._create_collection_directory(source_dir)

        manifest: Dict[str, Any] = {
            "collection_id": collection_id,
            "metadata": {
                "source_id": metadata.source_id,
                "collected_at": metadata.collected_at.isoformat(),
                "request_parameters": json.loads(serialized_parameters),
                "status": status.value,
                "checksum": {
                    "algorithm": "sha256",
                    "value": checksum,
                },
                "data_format": metadata.data_format,
                "version": metadata.version,
                "endpoint": metadata.endpoint,
            },
            "payload_file": _PAYLOAD_FILENAME,
        }
        manifest_bytes = json.dumps(
            manifest,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")

        try:
            with (collection_dir / _PAYLOAD_FILENAME).open("xb") as payload_file:
                payload_file.write(payload)
            with (collection_dir / _MANIFEST_FILENAME).open("xb") as manifest_file:
                manifest_file.write(manifest_bytes)
        except OSError:
            shutil.rmtree(collection_dir)
            raise

        return collection_id

    def read_manifest(self, source_id: str, collection_id: str) -> Dict[str, Any]:
        """Read manifest metadata for one registered source collection."""
        collection_dir = self._collection_directory(source_id, collection_id)
        with (collection_dir / _MANIFEST_FILENAME).open(
            "r", encoding="utf-8"
        ) as manifest_file:
            manifest = json.load(manifest_file)

        if (
            manifest.get("collection_id") != collection_id
            or manifest.get("metadata", {}).get("source_id") != source_id
            or manifest.get("payload_file") != _PAYLOAD_FILENAME
        ):
            raise ValueError("manifest does not match the requested collection")
        return manifest

    def read_payload(self, source_id: str, collection_id: str) -> bytes:
        """Read raw payload bytes and reject data that no longer matches its checksum."""
        manifest = self.read_manifest(source_id, collection_id)
        collection_dir = self._collection_directory(source_id, collection_id)
        with (collection_dir / _PAYLOAD_FILENAME).open("rb") as payload_file:
            payload = payload_file.read()

        checksum = manifest["metadata"]["checksum"]
        if checksum.get("algorithm") != "sha256":
            raise ValueError("unsupported payload checksum algorithm")
        actual_checksum = hashlib.sha256(payload).hexdigest()
        if actual_checksum != checksum.get("value"):
            raise ValueError("raw payload checksum mismatch")
        return payload

    def _collection_directory(self, source_id: str, collection_id: str) -> Path:
        self._source_registry.get(source_id)
        if not _COLLECTION_ID_PATTERN.fullmatch(collection_id):
            raise ValueError("collection_id must be a 32-character UUID hex value")
        return self._root / source_id / collection_id

    @staticmethod
    def _create_collection_directory(source_dir: Path) -> tuple[str, Path]:
        for _ in range(10):
            collection_id = uuid.uuid4().hex
            collection_dir = source_dir / collection_id
            try:
                collection_dir.mkdir(exist_ok=False)
            except FileExistsError:
                continue
            return collection_id, collection_dir
        raise FileExistsError("unable to allocate a unique collection directory")
