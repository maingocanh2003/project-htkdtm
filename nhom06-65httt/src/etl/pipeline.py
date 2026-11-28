"""Re-runnable ETL pipeline for collections already present in RawStorage."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from .bat_trang_collector import wc_store_raw_payload_to_d9
    from .deduplicator import DeduplicationIndex
    from .domestic_parser import DomesticSupplierCatalogParser
    from .marketplace_parser import AmazonCreatorsParser, EtsyListingParser
    from .normalizer import (
        NormalizedProductRecord,
        NormalizedReviewRecord,
        normalize_domestic_product,
        normalize_product_record,
        normalize_review_record,
        normalize_trade_record,
        normalize_trends_row,
    )
    from .processed_storage import ProcessedStorage, json_safe
    from .quality_validator import DataQualityValidator
    from .quarantine import QuarantineReasonType, QuarantineStore
    from .raw_storage import RawStorage
    from .review_parser import EtsyReviewParser
    from .source_registry import create_project_source_registry
    from .trade_parser import ITCTradeMapParser, UNComtradeParser
    from .trends_parser import GoogleTrendsParser
except ImportError:
    _SRC = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_SRC))
    from etl.bat_trang_collector import wc_store_raw_payload_to_d9
    from etl.deduplicator import DeduplicationIndex
    from etl.domestic_parser import DomesticSupplierCatalogParser
    from etl.marketplace_parser import AmazonCreatorsParser, EtsyListingParser
    from etl.normalizer import (
        NormalizedProductRecord,
        NormalizedReviewRecord,
        normalize_domestic_product,
        normalize_product_record,
        normalize_review_record,
        normalize_trade_record,
        normalize_trends_row,
    )
    from etl.processed_storage import ProcessedStorage, json_safe
    from etl.quality_validator import DataQualityValidator
    from etl.quarantine import QuarantineReasonType, QuarantineStore
    from etl.raw_storage import RawStorage
    from etl.review_parser import EtsyReviewParser
    from etl.source_registry import create_project_source_registry
    from etl.trade_parser import ITCTradeMapParser, UNComtradeParser
    from etl.trends_parser import GoogleTrendsParser


_LOGGER = logging.getLogger(__name__)


@dataclass
class SourcePipelineResult:
    """Counts and errors for one source pipeline run."""

    source_id: str
    collections: int = 0
    parsed_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicate_candidates: int = 0
    unresolved_duplicate_candidates: int = 0
    pending_key_confirmation: int = 0
    processed_records: int = 0
    would_process: int = 0
    quarantined_new: int = 0
    would_quarantine: int = 0
    already_quarantined: int = 0
    parser_errors: int = 0
    snapshot_written: bool = False
    snapshot_path: Optional[str] = None
    snapshot_sha256: Optional[str] = None
    errors: List[str] = field(default_factory=list)


class EtlPipeline:
    """Parse, normalize, validate, deduplicate and store raw collections."""

    def __init__(
        self,
        raw_root: Path,
        processed_root: Path,
        quarantine_root: Path,
    ) -> None:
        self.raw_root = Path(raw_root)
        self.processed_storage = ProcessedStorage(Path(processed_root))
        self.quarantine_root = Path(quarantine_root)
        self.registry = create_project_source_registry()
        self.raw_storage = RawStorage(self.raw_root, self.registry)

    def run(
        self,
        source_ids: Optional[Iterable[str]] = None,
        dry_run: bool = False,
    ) -> List[SourcePipelineResult]:
        """Process each selected source independently from its immutable raw data."""
        if source_ids is None:
            selected = (
                sorted(path.name for path in self.raw_root.iterdir() if path.is_dir())
                if self.raw_root.is_dir()
                else []
            )
        else:
            selected = list(dict.fromkeys(source_ids))

        results = []
        for source_id in selected:
            self.registry.get(source_id)
            results.append(self._run_source(source_id, dry_run))
        return results

    def _run_source(self, source_id: str, dry_run: bool) -> SourcePipelineResult:
        result = SourcePipelineResult(source_id=source_id)
        source_dir = self.raw_root / source_id
        if not source_dir.is_dir():
            return result

        collection_dirs = sorted(path for path in source_dir.iterdir() if path.is_dir())
        result.collections = len(collection_dirs)
        eligible_records: List[Any] = []
        source_failed = False
        dedup_indexes: Dict[str, DeduplicationIndex] = {}
        quarantine_root = self.quarantine_root / source_id
        entries_dir = quarantine_root / "entries"
        quarantine_store: Optional[QuarantineStore] = None
        quarantine_fingerprints = set()

        if entries_dir.is_dir():
            quarantine_store = QuarantineStore(quarantine_root)
            existing = quarantine_store.query_with_errors(source_id=source_id)
            if existing.errors:
                for path, error in existing.errors:
                    result.errors.append(f"Unreadable quarantine entry {path.name}: {error}")
                return result
            quarantine_fingerprints = {
                _quarantine_fingerprint(
                    entry.reason_type.value,
                    entry.source_id,
                    entry.raw_collection_id,
                    entry.record_type,
                    entry.record_snapshot,
                )
                for entry in existing.entries
            }

        for collection_dir in collection_dirs:
            collection_id = collection_dir.name
            try:
                manifest = self.raw_storage.read_manifest(source_id, collection_id)
                payload = self.raw_storage.read_payload(source_id, collection_id)
                metadata = manifest["metadata"]
                normalized_records = self._parse_normalize(
                    source_id, collection_id, payload, metadata
                )
            except Exception as exc:
                result.parser_errors += 1
                result.errors.append(f"{collection_id}: {type(exc).__name__}: {exc}")
                _LOGGER.exception(
                    "Failed to parse raw collection %s/%s", source_id, collection_id
                )
                source_failed = True
                continue

            result.parsed_records += len(normalized_records)
            request = metadata.get("request_parameters", {})
            dedup_scope = (
                str(request.get("geo") or "unknown")
                if source_id == "google_trends"
                else source_id
            )
            dedup = dedup_indexes.setdefault(dedup_scope, DeduplicationIndex())

            for record_index, normalized in enumerate(normalized_records, start=1):
                record_id = f"{collection_id}:{record_index}"
                try:
                    validation = self._validate(source_id, normalized, record_id)
                except Exception as exc:
                    result.errors.append(
                        f"{collection_id}:{record_index}: validation failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    source_failed = True
                    break

                if not validation.is_valid:
                    result.invalid_records += 1
                    codes = tuple(issue.code.value for issue in validation.errors)
                    try:
                        created = self._quarantine_once(
                            quarantine_store,
                            quarantine_root,
                            quarantine_fingerprints,
                            QuarantineReasonType.VALIDATION_ERROR,
                            source_id,
                            collection_id,
                            normalized,
                            codes,
                            validation,
                            None,
                            dry_run,
                        )
                    except Exception as exc:
                        result.errors.append(
                            f"{collection_id}:{record_index}: quarantine write failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        _LOGGER.exception(
                            "Failed to quarantine invalid record %s/%s:%s",
                            source_id,
                            collection_id,
                            record_index,
                        )
                        source_failed = True
                        break
                    if created == "new":
                        result.quarantined_new += 1
                    elif created == "would":
                        result.would_quarantine += 1
                    else:
                        result.already_quarantined += 1
                    continue

                result.valid_records += 1
                try:
                    duplicate = dedup.check_and_register(
                        normalized,
                        record_id=record_id,
                    )
                except Exception as exc:
                    result.errors.append(
                        f"{collection_id}:{record_index}: deduplication failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    _LOGGER.exception(
                        "Failed to deduplicate record %s/%s:%s",
                        source_id,
                        collection_id,
                        record_index,
                    )
                    source_failed = True
                    break
                if duplicate.is_duplicate:
                    result.duplicate_candidates += 1
                    is_actionable_duplicate = (
                        duplicate.key_confirmed
                        or duplicate.matched_collection_id == collection_id
                    )
                    if not is_actionable_duplicate:
                        result.unresolved_duplicate_candidates += 1
                        result.pending_key_confirmation += 1
                        eligible_records.append(normalized)
                        continue

                    try:
                        created = self._quarantine_once(
                            quarantine_store,
                            quarantine_root,
                            quarantine_fingerprints,
                            QuarantineReasonType.POTENTIAL_DUPLICATE,
                            source_id,
                            collection_id,
                            normalized,
                            (duplicate.status.value,),
                            None,
                            duplicate,
                            dry_run,
                        )
                    except Exception as exc:
                        result.errors.append(
                            f"{collection_id}:{record_index}: quarantine write failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        _LOGGER.exception(
                            "Failed to quarantine duplicate record %s/%s:%s",
                            source_id,
                            collection_id,
                            record_index,
                        )
                        source_failed = True
                        break
                    if created == "new":
                        result.quarantined_new += 1
                    elif created == "would":
                        result.would_quarantine += 1
                    else:
                        result.already_quarantined += 1
                    continue

                if duplicate.needs_confirmation:
                    result.pending_key_confirmation += 1
                eligible_records.append(normalized)

            if source_failed:
                break

        result.would_process = len(eligible_records)
        if source_failed:
            return result
        if dry_run:
            return result

        try:
            snapshot = self.processed_storage.write_source_snapshot(
                source_id, eligible_records
            )
        except Exception as exc:
            result.errors.append(f"Processed snapshot write failed: {type(exc).__name__}: {exc}")
            _LOGGER.exception("Failed to persist processed snapshot for %s", source_id)
            return result

        result.processed_records = snapshot.record_count
        result.snapshot_written = True
        result.snapshot_path = str(snapshot.path)
        result.snapshot_sha256 = snapshot.sha256
        return result

    def _parse_normalize(
        self,
        source_id: str,
        collection_id: str,
        payload: bytes,
        metadata: Dict[str, Any],
    ) -> List[Any]:
        collected_at = metadata["collected_at"]
        endpoint = metadata.get("endpoint")
        if source_id == "un_comtrade":
            parsed = UNComtradeParser().parse(
                payload,
                collection_id,
                collected_at_iso=collected_at,
                source_url=endpoint,
            )
            return [normalize_trade_record(record) for record in parsed.records]
        if source_id == "itc_trade_map":
            parsed = ITCTradeMapParser().parse(
                payload,
                collection_id,
                collected_at_iso=collected_at,
                source_url=endpoint,
            )
            return [normalize_trade_record(record) for record in parsed.records]
        if source_id == "google_trends":
            request = metadata.get("request_parameters", {})
            parsed = GoogleTrendsParser().parse(
                payload,
                collection_id,
                collected_at_iso=collected_at,
                source_url=endpoint,
                related_section=request.get("related_section"),
                source_keyword=request.get("keyword"),
            )
            return [normalize_trends_row(row) for row in parsed.rows]
        if source_id == "amazon":
            parsed = AmazonCreatorsParser().parse(
                payload,
                collection_id,
                collected_at_iso=collected_at,
                source_url=endpoint,
            )
            return [normalize_product_record(record) for record in parsed.records]
        if source_id == "etsy":
            request = metadata.get("request_parameters", {})
            is_reviews = (
                (isinstance(endpoint, str) and endpoint.endswith("/reviews"))
                or request.get("record_type") == "reviews"
            )
            if is_reviews:
                parsed = EtsyReviewParser().parse(
                    payload,
                    collection_id,
                    collected_at_iso=collected_at,
                    source_url=endpoint,
                )
                return [normalize_review_record(record) for record in parsed.records]
            parsed = EtsyListingParser().parse(
                payload,
                collection_id,
                collected_at_iso=collected_at,
                source_url=endpoint,
            )
            return [normalize_product_record(record) for record in parsed.records]
        if source_id in {
            "minh_long_1",
            "thegioigom",
            "bat_trang",
            "goc_gom_viet",
        }:
            request = metadata.get("request_parameters", {})
            source_url = endpoint or request.get("source_url")
            if source_id == "bat_trang":
                payload = wc_store_raw_payload_to_d9(payload)
            parsed = DomesticSupplierCatalogParser().parse(
                payload,
                collection_id,
                source_id=source_id,
                collected_at_iso=collected_at,
                source_url=source_url,
            )
            return [normalize_domestic_product(item) for item in parsed.products]
        raise NotImplementedError(
            f"No raw parser is configured for source '{source_id}'"
        )

    @staticmethod
    def _validate(source_id: str, record: Any, record_id: str):
        if source_id in {"un_comtrade", "itc_trade_map"}:
            return DataQualityValidator.validate_trade_record(record, record_id)
        if source_id == "google_trends":
            return DataQualityValidator.validate_trends_row(record, record_id)
        if isinstance(record, NormalizedReviewRecord):
            return DataQualityValidator.validate_review_record(record, record_id)
        if isinstance(record, NormalizedProductRecord) or source_id in {"amazon", "etsy"}:
            return DataQualityValidator.validate_product_record(record, record_id)
        return DataQualityValidator.validate_domestic_product(record, record_id)

    @staticmethod
    def _quarantine_once(
        store: Optional[QuarantineStore],
        quarantine_root: Path,
        known_fingerprints: set,
        reason_type: QuarantineReasonType,
        source_id: str,
        collection_id: str,
        record: Any,
        error_codes: Tuple[str, ...],
        validation: Any,
        duplicate: Any,
        dry_run: bool,
    ) -> str:
        fingerprint = _quarantine_fingerprint(
            reason_type.value,
            source_id,
            collection_id,
            type(record).__name__,
            record,
        )
        if fingerprint in known_fingerprints:
            return "existing"
        if dry_run:
            return "would"

        if store is None:
            store = QuarantineStore(quarantine_root)
        if store is None:
            store = QuarantineStore(quarantine_root)
        if reason_type is QuarantineReasonType.VALIDATION_ERROR:
            store.quarantine_from_validation(validation, record)
        else:
            store.quarantine_duplicate(duplicate, record)
        known_fingerprints.add(fingerprint)
        return "new"


def _quarantine_fingerprint(
    reason_type: str,
    source_id: str,
    collection_id: str,
    record_type: str,
    record_snapshot: Any,
) -> str:
    snapshot = json_safe(record_snapshot)
    if isinstance(snapshot, dict):
        source_row = snapshot.get("raw_record", snapshot.get("raw_row"))
        if source_row is not None:
            snapshot = source_row
    return json.dumps(
        [
            reason_type,
            source_id,
            collection_id,
            record_type,
            snapshot,
        ],
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def main() -> int:
    default_data_root = Path(__file__).resolve().parents[2] / "data"
    parser = argparse.ArgumentParser(
        description="Process existing raw ETL collections into processed JSONL snapshots."
    )
    parser.add_argument("--raw", type=Path, default=default_data_root / "raw")
    parser.add_argument(
        "--processed", type=Path, default=default_data_root / "processed"
    )
    parser.add_argument(
        "--quarantine", type=Path, default=default_data_root / "quarantine"
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="Source ID to process; repeat to select multiple sources",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without writing processed or quarantine files",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        results = EtlPipeline(
            args.raw, args.processed, args.quarantine
        ).run(args.sources, dry_run=args.dry_run)
    except (KeyError, OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            [asdict(result) for result in results],
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
    )
    return 1 if any(result.errors for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
