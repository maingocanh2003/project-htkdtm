"""Atomic JSONL snapshots for validated, normalized ETL records."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


_SOURCE_ID_PATTERN = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")


class ProcessedStorageError(Exception):
    """Raised when a validated-record snapshot cannot be written safely."""


@dataclass(frozen=True)
class ProcessedSnapshot:
    """Summary of a completed processed-record snapshot."""

    path: Path
    record_count: int
    sha256: str


def json_safe(value: Any) -> Any:
    """Convert ETL records to JSON values without changing source values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {key: json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


class ProcessedStorage:
    """Replace one source snapshot atomically; raw collections remain untouched."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def source_snapshot_path(self, source_id: str) -> Path:
        """Return the deterministic JSONL path for one registered-style source ID."""
        if not isinstance(source_id, str) or not _SOURCE_ID_PATTERN.fullmatch(source_id):
            raise ValueError("source_id must be a lowercase snake_case identifier")
        return self._root / source_id / "records.jsonl"

    def write_source_snapshot(
        self,
        source_id: str,
        records: Iterable[Any],
    ) -> ProcessedSnapshot:
        """Atomically replace a source's complete processed JSONL snapshot."""
        path = self.source_snapshot_path(source_id)
        temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            lines = []
            for record in records:
                row = {
                    "record_type": type(record).__name__,
                    "record": json_safe(record),
                }
                lines.append(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        allow_nan=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary_path.open("xb") as output_file:
                output_file.write(payload)
                output_file.flush()
                os.fsync(output_file.fileno())
            os.replace(temporary_path, path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError as cleanup_error:
                raise ProcessedStorageError(
                    f"Failed to write '{path}': {exc}; temporary-file cleanup also failed: "
                    f"{cleanup_error}"
                ) from exc
            raise ProcessedStorageError(f"Failed to write '{path}': {exc}") from exc

        return ProcessedSnapshot(
            path=path,
            record_count=len(lines),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
