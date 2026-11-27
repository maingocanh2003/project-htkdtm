"""D13 — Deduplication engine for ETL records.

Design rules:
- Confirmed business keys come strictly from the confirmed OLTP schema
  (01_init_oltp_erd_schema.sql):
  - market_products: (source_id, source_product_id) -> external_sku UNIQUE
  - supplier_products: (source_id, source_product_id) -> product_code UNIQUE
  - suppliers: supplier_code -> supplier_code UNIQUE
  - countries: country_code -> country_code UNIQUE
  - product_categories: category_code -> category_code UNIQUE
  - market_regions: (country_id, region_code) -> uq_country_region_code UNIQUE
- Never use product_name alone as a unique business key. Matching product_name
  without a matching confirmed ID yields POTENTIAL_DUPLICATE, never EXACT_DUPLICATE.
- Entities without a confirmed composite UNIQUE key in the schema
  (trade_statistics, product_reviews, search_trends) do not invent new unique keys;
  candidate matches are flagged as POTENTIAL_DUPLICATE with needs_confirmation=True,
  and first-seen records without a confirmed key are marked PENDING_KEY_CONFIRMATION.
- Never deletes or overwrites original records or D3 raw storage.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple, Union

from .normalizer import (
    NormalizationStatus,
    NormalizedDomesticProductRecord,
    NormalizedProductRecord,
    NormalizedReviewRecord,
    NormalizedTradeRecord,
    NormalizedTrendsRow,
    normalize_category,
    normalize_country,
    normalize_text,
)
from .parsed_record import (
    ParsedDomesticProductRecord,
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedSupplierInfo,
    ParsedTradeRecord,
    ParsedTrendsRow,
    RecordProvenance,
)

if os.name == "nt":
    import msvcrt
else:  # pragma: no cover - POSIX fallback
    import fcntl


class DeduplicationStorageError(Exception):
    """Raised when the deduplication index file cannot be read or written safely."""


class DuplicateStatus(str, Enum):
    """Classification of deduplication check for a single record."""

    UNIQUE = "unique"
    EXACT_DUPLICATE = "exact_duplicate"
    POTENTIAL_DUPLICATE = "potential_duplicate"
    PENDING_KEY_CONFIRMATION = "pending_key_confirmation"


@dataclass(frozen=True)
class DeduplicationResult:
    """Outcome of checking a record against the deduplication index."""

    entity_type: str
    status: DuplicateStatus
    is_duplicate: bool
    key_used: Optional[str]
    key_confirmed: bool
    needs_confirmation: bool
    matched_record_id: Optional[str]
    matched_collection_id: Optional[str]
    reason: str
    provenance: Optional[RecordProvenance] = None


@dataclass
class _IndexedEntry:
    record_id: str
    collection_id: Optional[str]
    source_id: Optional[str]
    confirmed_key: Optional[str]
    candidate_key: Optional[str]
    normalized_name: Optional[str]


def _clean_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    res = normalize_text(val)
    return res.value


def _norm_name(val: Any) -> Optional[str]:
    cleaned = _clean_str(val)
    if not cleaned:
        return None
    return unicodedata.normalize("NFC", cleaned).lower()


def _extract_provenance(record: Any) -> Optional[RecordProvenance]:
    prov = getattr(record, "provenance", None)
    return prov if isinstance(prov, RecordProvenance) else None


def _hash_candidate(parts: Tuple[str, ...]) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]


def _raw_record_fingerprint(raw_record: Dict[str, Any]) -> str:
    serialized = json.dumps(
        raw_record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _hash_candidate((serialized,))


def _product_content_fingerprint(
    raw_record: Dict[str, Any],
    product_fields: Dict[str, Any],
) -> str:
    return _raw_record_fingerprint(
        {
            "raw_record": raw_record,
            "product_fields": product_fields,
        }
    )


class DeduplicationIndex:
    """Non-destructive deduplication index supporting in-memory or locked JSON storage."""

    def __init__(self, index_file: Optional[Path] = None) -> None:
        self._index_file = Path(index_file) if index_file is not None else None
        self._thread_lock = threading.RLock()
        self._confirmed: Dict[str, Dict[str, _IndexedEntry]] = {}
        self._candidates: Dict[str, Dict[str, _IndexedEntry]] = {}
        self._names: Dict[str, Dict[str, _IndexedEntry]] = {}

        if self._index_file is not None and self._index_file.exists():
            with self._locked():
                self._load()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Synchronize thread and process access when index_file is configured."""
        with self._thread_lock:
            if self._index_file is None:
                yield
                return

            self._index_file.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self._index_file.with_name(f"{self._index_file.name}.lock")
            try:
                lock_fh = lock_path.open("a+b")
            except OSError as exc:
                raise DeduplicationStorageError(
                    f"Unable to open deduplication lock file '{lock_path}': {exc}"
                ) from exc

            try:
                if os.name == "nt":
                    lock_fh.seek(0)
                    deadline = time.monotonic() + 5.0
                    while True:
                        try:
                            msvcrt.locking(lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError as exc:
                            if time.monotonic() >= deadline:
                                raise DeduplicationStorageError(
                                    f"Timed out waiting for lock on '{lock_path}': {exc}"
                                ) from exc
                            time.sleep(0.01)
                else:  # pragma: no cover
                    fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)

                yield
            finally:
                try:
                    if os.name == "nt":
                        lock_fh.seek(0)
                        try:
                            msvcrt.locking(lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
                        except OSError:
                            pass
                    else:  # pragma: no cover
                        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
                finally:
                    lock_fh.close()

    def check_and_register(
        self,
        record: Union[
            NormalizedProductRecord,
            ParsedProductRecord,
            NormalizedDomesticProductRecord,
            ParsedDomesticProductRecord,
            NormalizedTradeRecord,
            ParsedTradeRecord,
            NormalizedReviewRecord,
            ParsedReviewRecord,
            NormalizedTrendsRow,
            ParsedTrendsRow,
            ParsedSupplierInfo,
            Dict[str, Any],
        ],
        entity_type: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> DeduplicationResult:
        """Check whether ``record`` is a duplicate and register it non-destructively.

        Original records and D3 raw payloads are never modified or deleted.
        """
        resolved_type, confirmed_key, candidate_key, norm_name, key_desc = (
            self._extract_keys(record, entity_type)
        )
        provenance = _extract_provenance(record)
        collection_id = provenance.raw_collection_id if provenance else None
        source_id = provenance.source_id if provenance else (
            record.get("source_id") if isinstance(record, dict) else None
        )
        rec_id = record_id or confirmed_key or candidate_key or "unknown"

        with self._locked():
            if self._index_file is not None and self._index_file.exists():
                self._load()

            confirmed_map = self._confirmed.setdefault(resolved_type, {})
            candidate_map = self._candidates.setdefault(resolved_type, {})
            name_map = self._names.setdefault(resolved_type, {})

            # 1. Exact duplicate check on confirmed Source ID / Business Key
            if confirmed_key is not None:
                existing = confirmed_map.get(confirmed_key)
                if existing is not None:
                    if existing.candidate_key != candidate_key:
                        return DeduplicationResult(
                            entity_type=resolved_type,
                            status=DuplicateStatus.POTENTIAL_DUPLICATE,
                            is_duplicate=True,
                            key_used=key_desc,
                            key_confirmed=False,
                            needs_confirmation=True,
                            matched_record_id=existing.record_id,
                            matched_collection_id=existing.collection_id,
                            reason=(
                                "Confirmed business key matches, but source values differ; "
                                "retained as a potential duplicate for review"
                            ),
                            provenance=provenance,
                        )
                    return DeduplicationResult(
                        entity_type=resolved_type,
                        status=DuplicateStatus.EXACT_DUPLICATE,
                        is_duplicate=True,
                        key_used=key_desc,
                        key_confirmed=True,
                        needs_confirmation=False,
                        matched_record_id=existing.record_id,
                        matched_collection_id=existing.collection_id,
                        reason=f"Exact match on confirmed key ({key_desc})",
                        provenance=provenance,
                    )

                # Different/new confirmed key: check if name alone matches -> POTENTIAL_DUPLICATE
                if norm_name is not None and norm_name in name_map:
                    existing_name = name_map[norm_name]
                    entry = _IndexedEntry(
                        record_id=rec_id,
                        collection_id=collection_id,
                        source_id=source_id,
                        confirmed_key=confirmed_key,
                        candidate_key=candidate_key,
                        normalized_name=norm_name,
                    )
                    confirmed_map[confirmed_key] = entry
                    self._persist()
                    return DeduplicationResult(
                        entity_type=resolved_type,
                        status=DuplicateStatus.POTENTIAL_DUPLICATE,
                        is_duplicate=True,
                        key_used="product_name (unconfirmed similarity)",
                        key_confirmed=False,
                        needs_confirmation=True,
                        matched_record_id=existing_name.record_id,
                        matched_collection_id=existing_name.collection_id,
                        reason=(
                            "Confirmed ID differs, but normalized name matches an existing record; "
                            "not treated as exact duplicate on name alone"
                        ),
                        provenance=provenance,
                    )

                # Brand-new unique record with confirmed key
                entry = _IndexedEntry(
                    record_id=rec_id,
                    collection_id=collection_id,
                    source_id=source_id,
                    confirmed_key=confirmed_key,
                    candidate_key=candidate_key,
                    normalized_name=norm_name,
                )
                confirmed_map[confirmed_key] = entry
                if norm_name is not None and norm_name not in name_map:
                    name_map[norm_name] = entry
                self._persist()
                return DeduplicationResult(
                    entity_type=resolved_type,
                    status=DuplicateStatus.UNIQUE,
                    is_duplicate=False,
                    key_used=key_desc,
                    key_confirmed=True,
                    needs_confirmation=False,
                    matched_record_id=None,
                    matched_collection_id=None,
                    reason=f"Unique record registered under confirmed key ({key_desc})",
                    provenance=provenance,
                )

            # 2. No confirmed key available (either missing ID or entity lacks confirmed UNIQUE key)
            if candidate_key is not None:
                existing_cand = candidate_map.get(candidate_key)
                if existing_cand is not None:
                    return DeduplicationResult(
                        entity_type=resolved_type,
                        status=DuplicateStatus.POTENTIAL_DUPLICATE,
                        is_duplicate=True,
                        key_used=key_desc,
                        key_confirmed=False,
                        needs_confirmation=True,
                        matched_record_id=existing_cand.record_id,
                        matched_collection_id=existing_cand.collection_id,
                        reason=(
                            f"Candidate attributes match ({key_desc}), but business key is "
                            "not confirmed in schema; awaiting confirmation from Member 1"
                        ),
                        provenance=provenance,
                    )

            if norm_name is not None and norm_name in name_map:
                existing_name = name_map[norm_name]
                return DeduplicationResult(
                    entity_type=resolved_type,
                    status=DuplicateStatus.POTENTIAL_DUPLICATE,
                    is_duplicate=True,
                    key_used="product_name (unconfirmed similarity)",
                    key_confirmed=False,
                    needs_confirmation=True,
                    matched_record_id=existing_name.record_id,
                    matched_collection_id=existing_name.collection_id,
                    reason=(
                        "Missing confirmed identifier; normalized name matches an existing "
                        "record (flagged as potential duplicate only)"
                    ),
                    provenance=provenance,
                )

            # First time seen without a confirmed key -> PENDING_KEY_CONFIRMATION
            entry = _IndexedEntry(
                record_id=rec_id,
                collection_id=collection_id,
                source_id=source_id,
                confirmed_key=None,
                candidate_key=candidate_key,
                normalized_name=norm_name,
            )
            if candidate_key is not None:
                candidate_map[candidate_key] = entry
            if norm_name is not None and norm_name not in name_map:
                name_map[norm_name] = entry
            self._persist()

            return DeduplicationResult(
                entity_type=resolved_type,
                status=DuplicateStatus.PENDING_KEY_CONFIRMATION,
                is_duplicate=False,
                key_used=key_desc,
                key_confirmed=False,
                needs_confirmation=True,
                matched_record_id=None,
                matched_collection_id=None,
                reason=(
                    "No confirmed unique business key available for this record/entity; "
                    "awaiting confirmation from Member 1"
                ),
                provenance=provenance,
            )

    def _extract_keys(
        self,
        record: Any,
        entity_type: Optional[str],
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Return (entity_type, confirmed_key, candidate_key, norm_name, key_description)."""
        # --- Market Products (external_sku UNIQUE) ---
        if isinstance(record, (NormalizedProductRecord, ParsedProductRecord)):
            src = record.provenance.source_id
            if isinstance(record, NormalizedProductRecord):
                pid = record.source_product_id.value
                name = _norm_name(record.product_name.value)
                product_fields = {
                    "product_url": record.product_url.value,
                    "name": record.product_name.value,
                    "category": record.category.value,
                    "price_amount": (
                        str(record.price.amount)
                        if record.price.amount is not None
                        else None
                    ),
                    "price_currency": record.price.currency_code,
                    "converted_amount": (
                        str(record.price.converted_amount)
                        if record.price.converted_amount is not None
                        else None
                    ),
                    "target_currency": record.price.target_currency,
                }
            else:
                pid = _clean_str(record.source_product_id)
                name = _norm_name(record.name)
                product_fields = {
                    "product_url": record.product_url,
                    "name": record.name,
                    "category": record.category,
                    "category_id": record.category_id,
                    "prices": [
                        {
                            "amount": price.amount_str,
                            "currency": price.currency_code,
                            "basis": price.basis,
                        }
                        for price in record.prices
                    ],
                }
            confirmed = f"{src}:{pid}" if pid else None
            return (
                "market_products",
                confirmed,
                _product_content_fingerprint(record.raw_record, product_fields),
                name,
                "source_id+source_product_id",
            )

        # --- Domestic Supplier Products (product_code UNIQUE) ---
        if isinstance(record, (NormalizedDomesticProductRecord, ParsedDomesticProductRecord)):
            src = record.provenance.source_id
            if isinstance(record, NormalizedDomesticProductRecord):
                pid = record.source_product_id.value
                name = _norm_name(record.product_name.value)
                product_fields = {
                    "name": record.product_name.value,
                    "category": record.category.value,
                    "material": record.material.value,
                    "origin_region": record.origin_region.value,
                    "price_vnd": (
                        str(record.price_vnd.value)
                        if record.price_vnd.value is not None
                        else None
                    ),
                    "moq": record.moq.value,
                    "lead_time_days": record.lead_time_days.value,
                    "wholesale_available": record.wholesale_available.value,
                }
            else:
                pid = _clean_str(record.source_product_id)
                name = _norm_name(record.name)
                product_fields = {
                    "product_url": record.product_url,
                    "name": record.name,
                    "description": record.description,
                    "category": record.category,
                    "material": record.material,
                    "origin_region": record.origin_region,
                    "price_vnd": record.commercial.price_vnd_str,
                    "currency": record.commercial.currency,
                    "moq": record.commercial.moq,
                    "lead_time_days": record.commercial.lead_time_days,
                    "wholesale_available": record.commercial.wholesale_available,
                }
            confirmed = f"{src}:{pid}" if pid else None
            return (
                "supplier_products",
                confirmed,
                _product_content_fingerprint(record.raw_record, product_fields),
                name,
                "source_id+source_product_id",
            )

        # --- Suppliers (supplier_code UNIQUE; tax_code/name unconfirmed) ---
        if isinstance(record, ParsedSupplierInfo):
            cand = None
            if _clean_str(record.tax_code):
                cand = f"tax:{_clean_str(record.tax_code)}"
            return (
                "suppliers",
                None,
                cand,
                _norm_name(record.supplier_name),
                "tax_code/supplier_name (unconfirmed)",
            )

        # --- Trade Statistics (no composite UNIQUE constraint in OLTP DDL) ---
        if isinstance(record, (NormalizedTradeRecord, ParsedTradeRecord)):
            src = record.provenance.source_id
            if isinstance(record, NormalizedTradeRecord):
                identity_parts = (
                    src,
                    record.reporter_country.value or "",
                    record.partner_country.value or "",
                    record.period.value or "",
                    record.flow_code.value or "",
                    record.hs_code.value or "",
                )
                value_parts = (
                    str(record.net_weight_kg.value or ""),
                    str(record.trade_value_usd.value or ""),
                    record.product_description.value or "",
                )
            else:
                identity_parts = (
                    src,
                    _clean_str(record.reporter_code or record.reporter_name) or "",
                    _clean_str(record.partner_code or record.partner_name) or "",
                    _clean_str(record.period) or "",
                    _clean_str(record.flow_code) or "",
                    _clean_str(record.hs_code) or "",
                )
                value_parts = (
                    str(record.net_weight_kg or ""),
                    str(record.trade_value_usd or ""),
                    _clean_str(record.product_description) or "",
                )
            raw_record = json.dumps(
                record.raw_record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            cand = (
                _hash_candidate((*identity_parts, *value_parts, raw_record))
                if all(identity_parts[1:])
                else None
            )
            return (
                "trade_statistics",
                None,
                cand,
                None,
                "reporter+partner+period+flow+hs_code (unconfirmed)",
            )

        # --- Product Reviews (no external_review_id / UNIQUE constraint in OLTP DDL) ---
        if isinstance(record, (NormalizedReviewRecord, ParsedReviewRecord)):
            src = record.provenance.source_id
            if isinstance(record, NormalizedReviewRecord):
                parts = (
                    src,
                    record.product_reference.value or "",
                    str(record.rating.value or ""),
                    record.reviewed_at_iso.value or "",
                    record.review_text.value or "",
                )
            else:
                parts = (
                    src,
                    _clean_str(record.product_reference) or "",
                    str(record.rating),
                    _clean_str(record.reviewed_at_iso) or "",
                    _clean_str(record.review_text) or "",
                )
            cand = _hash_candidate(parts) if any(parts[1:]) else None
            return (
                "product_reviews",
                None,
                cand,
                None,
                "product_reference+rating+reviewed_at+review_text (unconfirmed)",
            )

        # --- Google Trends (no UNIQUE constraint in OLTP DDL) ---
        if isinstance(record, (NormalizedTrendsRow, ParsedTrendsRow)):
            src = record.provenance.source_id
            if isinstance(record, NormalizedTrendsRow):
                period = record.period_label.value or ""
                kws = ",".join(
                    f"{k}={_clean_str(v.raw) or ''}"
                    for k, v in record.keyword_scores
                )
            else:
                period = _clean_str(record.period_label) or ""
                kws = ",".join(f"{k}={v}" for k, v in record.keyword_values)
            provenance = record.provenance
            data_type = _clean_str(record.data_type_hint) or ""
            period_kind = _clean_str(record.period_kind) or ""
            source_keyword = _clean_str(record.source_keyword) or ""
            related_section = _clean_str(record.related_section) or ""
            has_related_context = period_kind != "related_term" or (
                bool(source_keyword) and related_section in {"top", "rising"}
            )
            context = (
                src,
                provenance.raw_collection_id,
                provenance.collected_at_iso,
                period_kind,
                data_type,
                source_keyword,
                related_section,
                period,
                kws,
            )
            cand = (
                _hash_candidate(context)
                if period and data_type and period_kind and kws and has_related_context
                else None
            )
            return (
                "search_trends",
                None,
                cand,
                None,
                "source+collection+collected_at+period_kind+data_type+keyword+section+period+values (unconfirmed)",
            )

        # --- Generic Dict Payload ---
        if isinstance(record, dict):
            etype = entity_type or str(record.get("entity_type") or "unknown")
            src = _clean_str(record.get("source_id")) or "unknown"

            if etype in ("market_products", "supplier_products"):
                pid = _clean_str(
                    record.get("source_product_id")
                    or record.get("external_sku")
                    or record.get("product_code")
                )
                name = _norm_name(record.get("product_name") or record.get("name"))
                confirmed = f"{src}:{pid}" if pid else None
                return (
                    etype,
                    confirmed,
                    _raw_record_fingerprint(record),
                    name,
                    "source_id+source_product_id",
                )

            if etype == "suppliers":
                scode = _clean_str(record.get("supplier_code"))
                confirmed = f"supplier_code:{scode}" if scode else None
                cand = (
                    f"tax:{_clean_str(record.get('tax_code'))}"
                    if _clean_str(record.get("tax_code"))
                    else None
                )
                name = _norm_name(record.get("supplier_name"))
                return (etype, confirmed, cand, name, "supplier_code")

            if etype == "countries":
                raw_code = _clean_str(record.get("country_code"))
                if raw_code is None:
                    return (etype, None, None, None, "countries.country_code")
                norm = normalize_country(raw_code)
                code = (
                    norm.value
                    if norm.status == NormalizationStatus.CONFIRMED and norm.value
                    else raw_code.upper()
                )
                return (etype, f"countries:{code}", None, None, "countries.country_code")

            if etype == "product_categories":
                raw_code = _clean_str(record.get("category_code"))
                if raw_code is None:
                    return (etype, None, None, None, "product_categories.category_code")
                norm = normalize_category(raw_code)
                code = (
                    norm.value
                    if norm.status == NormalizationStatus.CONFIRMED and norm.value
                    else raw_code.upper()
                )
                return (etype, f"product_categories:{code}", None, None, "product_categories.category_code")

            if etype == "market_regions":
                cid_val = record.get("country_id")
                country_part = (
                    str(cid_val).strip()
                    if cid_val is not None and str(cid_val).strip()
                    else None
                )
                region_code = _clean_str(record.get("region_code"))
                if country_part and region_code:
                    confirmed = f"market_regions:{country_part}:{region_code.upper()}"
                else:
                    confirmed = None
                return (etype, confirmed, None, None, "market_regions.(country_id,region_code)")

            return (etype, None, None, None, "unconfirmed_entity")

        raise TypeError(f"Unsupported record type for deduplication: {type(record).__name__}")

    def _persist(self) -> None:
        if self._index_file is None:
            return
        self._index_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "confirmed": {
                et: {k: vars(v) for k, v in m.items()}
                for et, m in self._confirmed.items()
            },
            "candidates": {
                et: {k: vars(v) for k, v in m.items()}
                for et, m in self._candidates.items()
            },
            "names": {
                et: {k: vars(v) for k, v in m.items()}
                for et, m in self._names.items()
            },
        }
        tmp_path = self._index_file.with_name(
            f"{self._index_file.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tmp_path.replace(self._index_file)
        except OSError as exc:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise DeduplicationStorageError(
                f"Failed to persist deduplication index '{self._index_file}': {exc}"
            ) from exc

    def _load(self) -> None:
        try:
            text = self._index_file.read_text(encoding="utf-8")
            raw = json.loads(text)
            if not isinstance(raw, dict):
                raise ValueError("index root must be a JSON object")
            confirmed = {
                et: {k: _IndexedEntry(**v) for k, v in m.items()}
                for et, m in raw.get("confirmed", {}).items()
            }
            candidates = {
                et: {k: _IndexedEntry(**v) for k, v in m.items()}
                for et, m in raw.get("candidates", {}).items()
            }
            names = {
                et: {k: _IndexedEntry(**v) for k, v in m.items()}
                for et, m in raw.get("names", {}).items()
            }
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise DeduplicationStorageError(
                f"Failed to load deduplication index '{self._index_file}': {exc}"
            ) from exc

        self._confirmed = confirmed
        self._candidates = candidates
        self._names = names
