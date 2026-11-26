"""D13 — Quarantine and Recovery storage for failed or suspect ETL records.

Design rules:
- Quarantine storage is completely independent of OLTP/OLAP databases (local JSON files).
- Reuses D3 RecordProvenance (source_id, raw_collection_id, collected_at_iso, source_url).
- Never modifies, overwrites, or deletes raw payloads stored by D3 RawStorage.
- Separates validation errors (QuarantineReasonType.VALIDATION_ERROR) from
  duplicate suspects (QuarantineReasonType.POTENTIAL_DUPLICATE).
- Preserves ``record_type`` and rehydrates ``Parsed*Record`` and ``Normalized*Record``
  snapshots during Recovery without inventing missing values.
- Never deletes or overwrites corrupted JSON files; raises explicit storage/recovery
  errors and skips invalid files safely during directory queries.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .deduplicator import DeduplicationResult
from .normalizer import (
    NormalizationStatus,
    NormalizedCurrency,
    NormalizedDomesticProductRecord,
    NormalizedField,
    NormalizedProductRecord,
    NormalizedReviewRecord,
    NormalizedTradeRecord,
    NormalizedTrendsRow,
)
from .parsed_record import (
    ParsedCommercialInfo,
    ParsedDomesticProductRecord,
    ParsedPriceInfo,
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedTradeRecord,
    ParsedTrendsRow,
    RecordProvenance,
)
from .quality_validator import RecordValidationResult

_logger = logging.getLogger(__name__)
_QUARANTINE_ID_PATTERN = re.compile(r"[a-f0-9]{32}")


class QuarantineStorageError(Exception):
    """Raised when a quarantine entry file cannot be read, parsed, or written."""


class QuarantineRecoveryError(Exception):
    """Raised when a quarantined snapshot cannot be rehydrated into its target type."""


class QuarantineReasonType(str, Enum):
    """Distinguishes validation failures from duplicate suspects."""

    VALIDATION_ERROR = "validation_error"
    POTENTIAL_DUPLICATE = "potential_duplicate"


class QuarantineStatus(str, Enum):
    """Lifecycle states for a quarantined record."""

    QUARANTINED = "quarantined"
    RECOVERED = "recovered"
    RECOVERY_FAILED = "recovery_failed"


@dataclass(frozen=True)
class RecoveryAttempt:
    """Immutable audit record of one recovery attempt."""

    attempt_number: int
    attempted_at_iso: str
    previous_status: QuarantineStatus
    new_status: QuarantineStatus
    outcome_message: str
    remaining_error_codes: Tuple[str, ...]
    raw_collection_id: str


@dataclass(frozen=True)
class QuarantineEntry:
    """One quarantined record with full provenance, error details, and history."""

    quarantine_id: str
    entity_type: str
    record_type: str
    reason_type: QuarantineReasonType
    source_id: str
    raw_collection_id: str
    collected_at_iso: str
    source_url: Optional[str]
    record_snapshot: Dict[str, Any]
    error_codes: Tuple[str, ...]
    error_reasons: Tuple[str, ...]
    quarantined_at_iso: str
    status: QuarantineStatus
    history: Tuple[RecoveryAttempt, ...]


@dataclass(frozen=True)
class QuarantineQueryResult:
    """Result of querying quarantine entries along with any corrupted-file errors."""

    entries: Tuple[QuarantineEntry, ...]
    errors: Tuple[Tuple[Path, str], ...]


@dataclass(frozen=True)
class RecoveryResult:
    """Result returned by QuarantineStore.recover()."""

    quarantine_id: str
    recovered: bool
    new_status: QuarantineStatus
    validation_result: RecordValidationResult
    normalized_record: Any
    entry: QuarantineEntry


def _json_safe(obj: Any) -> Any:
    """Convert dataclasses, Decimals, Enums, and tuples into JSON-serializable types."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _json_safe(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _rehydrate_provenance(raw: Any) -> RecordProvenance:
    if not isinstance(raw, dict):
        raise QuarantineRecoveryError("provenance must be a dict")
    return RecordProvenance(
        source_id=str(raw["source_id"]),
        raw_collection_id=str(raw["raw_collection_id"]),
        collected_at_iso=str(raw["collected_at_iso"]),
        source_url=raw.get("source_url"),
    )


def _rehydrate_field(raw: Any, as_decimal: bool = False) -> NormalizedField[Any]:
    if not isinstance(raw, dict):
        raise QuarantineRecoveryError("NormalizedField snapshot must be a dict")
    val = raw.get("value")
    if as_decimal and val is not None:
        try:
            val = Decimal(str(val))
        except (InvalidOperation, ValueError) as exc:
            raise QuarantineRecoveryError(f"Invalid Decimal value '{val}': {exc}") from exc
    return NormalizedField(
        raw=raw.get("raw"),
        value=val,
        status=NormalizationStatus(raw["status"]),
        note=raw.get("note"),
    )


def _rehydrate_currency(raw: Any) -> NormalizedCurrency:
    if not isinstance(raw, dict):
        raise QuarantineRecoveryError("NormalizedCurrency snapshot must be a dict")
    amt = raw.get("amount")
    conv = raw.get("converted_amount")
    try:
        amt_dec = Decimal(str(amt)) if amt is not None else None
        conv_dec = Decimal(str(conv)) if conv is not None else None
    except (InvalidOperation, ValueError) as exc:
        raise QuarantineRecoveryError(f"Invalid currency Decimal: {exc}") from exc
    return NormalizedCurrency(
        raw_amount=raw.get("raw_amount"),
        raw_currency=raw.get("raw_currency"),
        amount=amt_dec,
        currency_code=raw.get("currency_code"),
        currency_status=NormalizationStatus(raw["currency_status"]),
        converted_amount=conv_dec,
        target_currency=raw.get("target_currency"),
        conversion_status=NormalizationStatus(raw["conversion_status"]),
        conversion_note=raw.get("conversion_note"),
    )


def rehydrate_record(record_type: str, snapshot: Dict[str, Any]) -> Any:
    """Restore a serialized ``record_snapshot`` back into its original Python record type."""
    if not isinstance(snapshot, dict):
        raise QuarantineRecoveryError("record_snapshot must be a dict")

    try:
        if record_type == "dict":
            return dict(snapshot)

        prov = _rehydrate_provenance(snapshot["provenance"])

        if record_type == "ParsedTradeRecord":
            return ParsedTradeRecord(
                provenance=prov,
                raw_record=dict(snapshot["raw_record"]),
                reporter_code=snapshot.get("reporter_code"),
                partner_code=snapshot.get("partner_code"),
                hs_code=snapshot.get("hs_code"),
                period=snapshot.get("period"),
                flow_code=snapshot.get("flow_code"),
                net_weight_kg=snapshot.get("net_weight_kg"),
                trade_value_usd=snapshot.get("trade_value_usd"),
                reporter_name=snapshot.get("reporter_name"),
                partner_name=snapshot.get("partner_name"),
                product_description=snapshot.get("product_description"),
            )

        if record_type == "NormalizedTradeRecord":
            return NormalizedTradeRecord(
                provenance=prov,
                raw_record=dict(snapshot["raw_record"]),
                reporter_country=_rehydrate_field(snapshot["reporter_country"]),
                partner_country=_rehydrate_field(snapshot["partner_country"]),
                hs_code=_rehydrate_field(snapshot["hs_code"]),
                period=_rehydrate_field(snapshot["period"]),
                flow_code=_rehydrate_field(snapshot["flow_code"]),
                net_weight_kg=_rehydrate_field(snapshot["net_weight_kg"]),
                trade_value_usd=_rehydrate_field(snapshot["trade_value_usd"]),
                product_description=_rehydrate_field(snapshot["product_description"]),
            )

        if record_type == "ParsedProductRecord":
            prices = tuple(
                ParsedPriceInfo(
                    amount_str=str(p["amount_str"]),
                    currency_code=str(p["currency_code"]),
                    basis=str(p["basis"]),
                )
                for p in snapshot.get("prices", [])
            )
            return ParsedProductRecord(
                provenance=prov,
                raw_record=dict(snapshot["raw_record"]),
                source_product_id=str(snapshot["source_product_id"]),
                product_url=snapshot.get("product_url"),
                name=snapshot.get("name"),
                category=snapshot.get("category"),
                category_id=snapshot.get("category_id"),
                prices=prices,
            )

        if record_type == "NormalizedProductRecord":
            return NormalizedProductRecord(
                provenance=prov,
                raw_record=dict(snapshot["raw_record"]),
                source_product_id=_rehydrate_field(snapshot["source_product_id"]),
                product_name=_rehydrate_field(snapshot["product_name"]),
                product_url=_rehydrate_field(snapshot["product_url"]),
                category=_rehydrate_field(snapshot["category"]),
                price=_rehydrate_currency(snapshot["price"]),
            )

        if record_type == "ParsedReviewRecord":
            return ParsedReviewRecord(
                provenance=prov,
                raw_record=dict(snapshot["raw_record"]),
                product_reference=str(snapshot["product_reference"]),
                rating=snapshot["rating"],
                review_text=snapshot.get("review_text"),
                reviewed_at_iso=snapshot.get("reviewed_at_iso"),
                language=snapshot.get("language"),
            )

        if record_type == "NormalizedReviewRecord":
            return NormalizedReviewRecord(
                provenance=prov,
                raw_record=dict(snapshot["raw_record"]),
                product_reference=_rehydrate_field(snapshot["product_reference"]),
                rating=_rehydrate_field(snapshot["rating"]),
                review_text=_rehydrate_field(snapshot["review_text"]),
                reviewed_at_iso=_rehydrate_field(snapshot["reviewed_at_iso"]),
                language=_rehydrate_field(snapshot["language"]),
            )

        if record_type == "ParsedTrendsRow":
            kv = tuple((str(pair[0]), str(pair[1])) for pair in snapshot.get("keyword_values", []))
            return ParsedTrendsRow(
                provenance=prov,
                raw_row=dict(snapshot["raw_row"]),
                period_label=str(snapshot["period_label"]),
                keyword_values=kv,
            )

        if record_type == "NormalizedTrendsRow":
            ks = tuple(
                (str(pair[0]), _rehydrate_field(pair[1]))
                for pair in snapshot.get("keyword_scores", [])
            )
            return NormalizedTrendsRow(
                provenance=prov,
                raw_row=dict(snapshot["raw_row"]),
                period_label=_rehydrate_field(snapshot["period_label"]),
                keyword_scores=ks,
            )

        if record_type == "ParsedDomesticProductRecord":
            comm_raw = snapshot["commercial"]
            comm = ParsedCommercialInfo(
                price_vnd_str=comm_raw.get("price_vnd_str"),
                currency=comm_raw.get("currency"),
                moq=comm_raw.get("moq"),
                lead_time_days=comm_raw.get("lead_time_days"),
                wholesale_available=comm_raw.get("wholesale_available"),
            )
            return ParsedDomesticProductRecord(
                provenance=prov,
                raw_record=dict(snapshot["raw_record"]),
                source_product_id=str(snapshot["source_product_id"]),
                product_url=snapshot.get("product_url"),
                name=snapshot.get("name"),
                description=snapshot.get("description"),
                category=snapshot.get("category"),
                material=snapshot.get("material"),
                origin_region=snapshot.get("origin_region"),
                commercial=comm,
            )

        if record_type == "NormalizedDomesticProductRecord":
            return NormalizedDomesticProductRecord(
                provenance=prov,
                raw_record=dict(snapshot["raw_record"]),
                source_product_id=_rehydrate_field(snapshot["source_product_id"]),
                product_name=_rehydrate_field(snapshot["product_name"]),
                category=_rehydrate_field(snapshot["category"]),
                material=_rehydrate_field(snapshot["material"]),
                origin_region=_rehydrate_field(snapshot["origin_region"]),
                price_vnd=_rehydrate_field(snapshot["price_vnd"], as_decimal=True),
                moq=_rehydrate_field(snapshot["moq"]),
                lead_time_days=_rehydrate_field(snapshot["lead_time_days"]),
                wholesale_available=_rehydrate_field(snapshot["wholesale_available"]),
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise QuarantineRecoveryError(
            f"Unable to rehydrate snapshot as '{record_type}': {exc}"
        ) from exc

    raise QuarantineRecoveryError(f"Unsupported record_type for recovery: '{record_type}'")


class QuarantineStore:
    """File-backed JSON store for quarantined records and recovery history."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._entries_dir = self._root / "entries"
        try:
            self._entries_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise QuarantineStorageError(
                f"Failed to initialize quarantine directory '{self._entries_dir}': {exc}"
            ) from exc

    def quarantine_from_validation(
        self,
        validation_result: RecordValidationResult,
        record_snapshot: Any,
        provenance: Optional[RecordProvenance] = None,
    ) -> QuarantineEntry:
        """Isolate a record that failed D12 validation."""
        if validation_result.is_valid:
            raise ValueError("Cannot quarantine a valid record as a validation_error")

        prov = provenance or validation_result.provenance
        if prov is None:
            raise ValueError("Provenance with raw_collection_id is required to quarantine")

        error_codes = tuple(e.code.value for e in validation_result.errors)
        error_reasons = tuple(e.message for e in validation_result.errors)

        return self._create_entry(
            entity_type=validation_result.entity_type,
            reason_type=QuarantineReasonType.VALIDATION_ERROR,
            provenance=prov,
            record_snapshot=record_snapshot,
            error_codes=error_codes,
            error_reasons=error_reasons,
        )

    def quarantine_duplicate(
        self,
        dedup_result: DeduplicationResult,
        record_snapshot: Any,
        provenance: Optional[RecordProvenance] = None,
    ) -> QuarantineEntry:
        """Isolate a duplicate or potential-duplicate record separately from validation errors."""
        prov = provenance or dedup_result.provenance
        if prov is None:
            raise ValueError("Provenance with raw_collection_id is required to quarantine")

        return self._create_entry(
            entity_type=dedup_result.entity_type,
            reason_type=QuarantineReasonType.POTENTIAL_DUPLICATE,
            provenance=prov,
            record_snapshot=record_snapshot,
            error_codes=(dedup_result.status.value,),
            error_reasons=(dedup_result.reason,),
        )

    def get(self, quarantine_id: str) -> QuarantineEntry:
        """Retrieve a quarantined entry by its quarantine_id."""
        path = self._entry_path(quarantine_id)
        if not path.exists():
            raise KeyError(f"Quarantine entry not found: {quarantine_id}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("entry root must be a JSON object")
            return self._deserialize_entry(raw)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise QuarantineStorageError(
                f"Failed to read quarantine entry '{path}': {exc}"
            ) from exc

    def query_with_errors(
        self,
        source_id: Optional[str] = None,
        status: Optional[QuarantineStatus] = None,
        reason_type: Optional[QuarantineReasonType] = None,
        entity_type: Optional[str] = None,
    ) -> QuarantineQueryResult:
        """Query quarantined entries and return both valid matches and corrupted-file errors."""
        matches: List[QuarantineEntry] = []
        errors: List[Tuple[Path, str]] = []
        try:
            paths = sorted(self._entries_dir.glob("*.json"))
        except OSError as exc:
            raise QuarantineStorageError(
                f"Failed to list quarantine directory '{self._entries_dir}': {exc}"
            ) from exc

        for path in paths:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("entry root must be a JSON object")
                entry = self._deserialize_entry(raw)
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                msg = f"Skipping unreadable or malformed quarantine file '{path.name}': {exc}"
                _logger.warning(msg)
                errors.append((path, str(exc)))
                continue

            if source_id is not None and entry.source_id != source_id:
                continue
            if status is not None and entry.status != status:
                continue
            if reason_type is not None and entry.reason_type != reason_type:
                continue
            if entity_type is not None and entry.entity_type != entity_type:
                continue
            matches.append(entry)

        return QuarantineQueryResult(entries=tuple(matches), errors=tuple(errors))

    def query(
        self,
        source_id: Optional[str] = None,
        status: Optional[QuarantineStatus] = None,
        reason_type: Optional[QuarantineReasonType] = None,
        entity_type: Optional[str] = None,
    ) -> Tuple[QuarantineEntry, ...]:
        """Query quarantined entries; malformed JSON files are logged and skipped safely."""
        return self.query_with_errors(
            source_id=source_id,
            status=status,
            reason_type=reason_type,
            entity_type=entity_type,
        ).entries

    def recover(
        self,
        quarantine_id: str,
        validator_fn: Callable[[Any], RecordValidationResult],
        normalizer_fn: Optional[Callable[[Any], Any]] = None,
    ) -> RecoveryResult:
        """Re-process a quarantined record using updated normalization/validation rules.

        Rehydrates ``record_snapshot`` into its original ``Parsed*Record`` /
        ``Normalized*Record`` / ``dict`` type, runs ``normalizer_fn`` before
        ``validator_fn``, preserves original ``raw_collection_id`` provenance,
        and appends the attempt to ``entry.history`` without losing prior runs.
        """
        entry = self.get(quarantine_id)
        rehydrated = rehydrate_record(entry.record_type, entry.record_snapshot)

        normalized_rec: Any = rehydrated
        if normalizer_fn is not None:
            normalized_rec = normalizer_fn(rehydrated)

        validation_result = validator_fn(normalized_rec)
        attempted_at = datetime.now(timezone.utc).isoformat()

        if validation_result.is_valid:
            new_status = QuarantineStatus.RECOVERED
            outcome_msg = "Record passed validation during recovery"
            rem_codes: Tuple[str, ...] = ()
        else:
            new_status = QuarantineStatus.RECOVERY_FAILED
            outcome_msg = "; ".join(e.message for e in validation_result.errors)
            rem_codes = tuple(e.code.value for e in validation_result.errors)

        attempt = RecoveryAttempt(
            attempt_number=len(entry.history) + 1,
            attempted_at_iso=attempted_at,
            previous_status=entry.status,
            new_status=new_status,
            outcome_message=outcome_msg,
            remaining_error_codes=rem_codes,
            raw_collection_id=entry.raw_collection_id,
        )

        updated_entry = QuarantineEntry(
            quarantine_id=entry.quarantine_id,
            entity_type=entry.entity_type,
            record_type=entry.record_type,
            reason_type=entry.reason_type,
            source_id=entry.source_id,
            raw_collection_id=entry.raw_collection_id,
            collected_at_iso=entry.collected_at_iso,
            source_url=entry.source_url,
            record_snapshot=entry.record_snapshot,
            error_codes=entry.error_codes,
            error_reasons=entry.error_reasons,
            quarantined_at_iso=entry.quarantined_at_iso,
            status=new_status,
            history=entry.history + (attempt,),
        )
        self._save_entry(updated_entry)

        return RecoveryResult(
            quarantine_id=quarantine_id,
            recovered=validation_result.is_valid,
            new_status=new_status,
            validation_result=validation_result,
            normalized_record=normalized_rec,
            entry=updated_entry,
        )

    def _create_entry(
        self,
        entity_type: str,
        reason_type: QuarantineReasonType,
        provenance: RecordProvenance,
        record_snapshot: Any,
        error_codes: Tuple[str, ...],
        error_reasons: Tuple[str, ...],
    ) -> QuarantineEntry:
        qid = uuid.uuid4().hex
        if isinstance(record_snapshot, dict):
            record_type = "dict"
        elif is_dataclass(record_snapshot) and not isinstance(record_snapshot, type):
            record_type = type(record_snapshot).__name__
        else:
            raise TypeError(
                f"Unsupported record_snapshot type for quarantine: {type(record_snapshot).__name__}"
            )

        snapshot = _json_safe(record_snapshot)

        entry = QuarantineEntry(
            quarantine_id=qid,
            entity_type=entity_type,
            record_type=record_type,
            reason_type=reason_type,
            source_id=provenance.source_id,
            raw_collection_id=provenance.raw_collection_id,
            collected_at_iso=provenance.collected_at_iso,
            source_url=provenance.source_url,
            record_snapshot=snapshot,
            error_codes=tuple(error_codes),
            error_reasons=tuple(error_reasons),
            quarantined_at_iso=datetime.now(timezone.utc).isoformat(),
            status=QuarantineStatus.QUARANTINED,
            history=(),
        )
        self._save_entry(entry)
        return entry

    def _entry_path(self, quarantine_id: str) -> Path:
        if not isinstance(quarantine_id, str) or not _QUARANTINE_ID_PATTERN.fullmatch(quarantine_id):
            raise ValueError("quarantine_id must be a 32-character UUID hex value")
        return self._entries_dir / f"{quarantine_id}.json"

    def _save_entry(self, entry: QuarantineEntry) -> None:
        path = self._entry_path(entry.quarantine_id)
        tmp_path = path.with_name(f".{entry.quarantine_id}.{uuid.uuid4().hex}.tmp")
        try:
            tmp_path.write_text(
                json.dumps(_json_safe(entry), ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tmp_path.replace(path)
        except OSError as exc:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise QuarantineStorageError(
                f"Failed to write quarantine entry '{path}': {exc}"
            ) from exc

    @staticmethod
    def _deserialize_entry(raw: Dict[str, Any]) -> QuarantineEntry:
        history = tuple(
            RecoveryAttempt(
                attempt_number=h["attempt_number"],
                attempted_at_iso=h["attempted_at_iso"],
                previous_status=QuarantineStatus(h["previous_status"]),
                new_status=QuarantineStatus(h["new_status"]),
                outcome_message=h["outcome_message"],
                remaining_error_codes=tuple(h["remaining_error_codes"]),
                raw_collection_id=h["raw_collection_id"],
            )
            for h in raw.get("history", [])
        )
        return QuarantineEntry(
            quarantine_id=raw["quarantine_id"],
            entity_type=raw["entity_type"],
            record_type=raw["record_type"],
            reason_type=QuarantineReasonType(raw["reason_type"]),
            source_id=raw["source_id"],
            raw_collection_id=raw["raw_collection_id"],
            collected_at_iso=raw["collected_at_iso"],
            source_url=raw.get("source_url"),
            record_snapshot=raw["record_snapshot"],
            error_codes=tuple(raw["error_codes"]),
            error_reasons=tuple(raw["error_reasons"]),
            quarantined_at_iso=raw["quarantined_at_iso"],
            status=QuarantineStatus(raw["status"]),
            history=history,
        )
