"""Read-only end-to-end audit for raw ETL collections.

This module does not write RawStorage, quarantine, processed tables, or
PostgreSQL.  It runs the existing parser, normalizer, validator, and dedup
candidate checks against collections already present on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    from .bat_trang_collector import wc_store_raw_payload_to_d9
    from .deduplicator import DeduplicationIndex
    from .domestic_parser import DomesticSupplierCatalogParser
    from .normalizer import (
        normalize_domestic_product,
        normalize_trade_record,
        normalize_trends_row,
    )
    from .quality_validator import DataQualityValidator
    from .raw_storage import RawStorage
    from .source_registry import create_project_source_registry
    from .trade_parser import UNComtradeParser
    from .trends_parser import GoogleTrendsParser
except ImportError:
    _SRC = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_SRC))
    from etl.bat_trang_collector import wc_store_raw_payload_to_d9
    from etl.deduplicator import DeduplicationIndex
    from etl.domestic_parser import DomesticSupplierCatalogParser
    from etl.normalizer import (
        normalize_domestic_product,
        normalize_trade_record,
        normalize_trends_row,
    )
    from etl.quality_validator import DataQualityValidator
    from etl.raw_storage import RawStorage
    from etl.source_registry import create_project_source_registry
    from etl.trade_parser import UNComtradeParser
    from etl.trends_parser import GoogleTrendsParser


@dataclass
class PipelineAuditResult:
    source_id: str
    collections: int = 0
    parsed_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicate_candidates: int = 0
    parser_errors: int = 0


class EtlPipelineAudit:
    """Audit raw collections without mutating source or processed data."""

    def __init__(self, raw_root: Path) -> None:
        self.raw_root = Path(raw_root)
        self.registry = create_project_source_registry()
        self.storage = RawStorage(self.raw_root, self.registry)

    def audit_source(self, source_id: str) -> PipelineAuditResult:
        result = PipelineAuditResult(source_id=source_id)
        source_dir = self.raw_root / source_id
        if not source_dir.is_dir():
            return result

        collection_dirs = sorted(
            path for path in source_dir.iterdir() if path.is_dir()
        )
        result.collections = len(collection_dirs)

        if source_id == "google_trends":
            return self._audit_google(collection_dirs, result)
        if source_id == "un_comtrade":
            return self._audit_un_comtrade(collection_dirs, result)
        if source_id in {
            "minh_long_1",
            "thegioigom",
            "bat_trang",
            "goc_gom_viet",
        }:
            return self._audit_domestic(collection_dirs, result, source_id)
        return result

    def audit_all(self, source_ids: Optional[Iterable[str]] = None) -> list[PipelineAuditResult]:
        selected = (
            tuple(source_ids)
            if source_ids is not None
            else (
                "un_comtrade",
                "google_trends",
                "minh_long_1",
                "thegioigom",
                "bat_trang",
            )
        )
        return [self.audit_source(source_id) for source_id in selected]

    def _audit_google(
        self,
        collection_dirs: list[Path],
        result: PipelineAuditResult,
    ) -> PipelineAuditResult:
        dedup_by_geo: dict[str, DeduplicationIndex] = {}
        parser = GoogleTrendsParser()

        for collection_dir in collection_dirs:
            collection_id = collection_dir.name
            try:
                manifest = self.storage.read_manifest("google_trends", collection_id)
                payload = self.storage.read_payload("google_trends", collection_id)
                metadata = manifest["metadata"]
                request = metadata["request_parameters"]
                geo = str(request.get("geo") or "unknown")
                parsed = parser.parse(
                    payload,
                    collection_id,
                    collected_at_iso=metadata["collected_at"],
                    related_section=request.get("related_section"),
                    source_keyword=request.get("keyword"),
                )
            except Exception:
                result.parser_errors += 1
                continue

            result.parsed_records += parsed.row_count
            dedup = dedup_by_geo.setdefault(geo, DeduplicationIndex())
            for index, parsed_row in enumerate(parsed.rows, 1):
                normalized = normalize_trends_row(parsed_row)
                validation = DataQualityValidator.validate_trends_row(
                    normalized,
                    record_id=f"{collection_id}:{index}",
                )
                if validation.is_valid:
                    result.valid_records += 1
                    duplicate = dedup.check_and_register(
                        normalized,
                        record_id=f"{collection_id}:{index}",
                    )
                    if duplicate.is_duplicate:
                        result.duplicate_candidates += 1
                else:
                    result.invalid_records += 1
        return result

    def _audit_un_comtrade(
        self,
        collection_dirs: list[Path],
        result: PipelineAuditResult,
    ) -> PipelineAuditResult:
        parser = UNComtradeParser()
        for collection_dir in collection_dirs:
            collection_id = collection_dir.name
            try:
                manifest = self.storage.read_manifest("un_comtrade", collection_id)
                payload = self.storage.read_payload("un_comtrade", collection_id)
                parsed = parser.parse(
                    payload,
                    collection_id,
                    collected_at_iso=manifest["metadata"]["collected_at"],
                )
            except Exception:
                result.parser_errors += 1
                continue

            result.parsed_records += parsed.record_count
            for index, parsed_row in enumerate(parsed.records, 1):
                normalized = normalize_trade_record(parsed_row)
                validation = DataQualityValidator.validate_trade_record(
                    normalized,
                    record_id=f"{collection_id}:{index}",
                )
                if validation.is_valid:
                    result.valid_records += 1
                else:
                    result.invalid_records += 1
        return result

    def _audit_domestic(
        self,
        collection_dirs: list[Path],
        result: PipelineAuditResult,
        source_id: str,
    ) -> PipelineAuditResult:
        parser = DomesticSupplierCatalogParser()
        for collection_dir in collection_dirs:
            collection_id = collection_dir.name
            try:
                manifest = self.storage.read_manifest(source_id, collection_id)
                payload = self.storage.read_payload(source_id, collection_id)
                metadata = manifest["metadata"]
                if source_id == "bat_trang":
                    payload = wc_store_raw_payload_to_d9(payload)
                parsed = parser.parse(
                    payload,
                    collection_id,
                    source_id=source_id,
                    collected_at_iso=metadata["collected_at"],
                    source_url=(
                        metadata.get("endpoint")
                        or metadata.get("request_parameters", {}).get("source_url")
                    ),
                )
            except Exception:
                result.parser_errors += 1
                continue

            result.parsed_records += parsed.record_count
            for index, parsed_row in enumerate(parsed.products, 1):
                normalized = normalize_domestic_product(parsed_row)
                validation = DataQualityValidator.validate_domestic_product(
                    normalized,
                    record_id=f"{collection_id}:{index}",
                )
                if validation.is_valid:
                    result.valid_records += 1
                else:
                    result.invalid_records += 1
        return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only audit of existing ETL raw collections."
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("nhom06-65httt/data/raw"),
        help="RawStorage root",
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="Source ID to audit; repeat to audit multiple sources",
    )
    args = parser.parse_args()

    audit = EtlPipelineAudit(args.raw)
    results = audit.audit_all(args.sources)
    print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
