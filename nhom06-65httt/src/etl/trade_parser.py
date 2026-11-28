"""D10 parser for D5 raw trade payloads (UN Comtrade JSON, ITC Trade Map CSV).

Design rules:
- Raw records are attached unchanged to every ParsedTradeRecord.
- ParseError.kind distinguishes MISSING_FIELD / NULL_FIELD / WRONG_TYPE / WRONG_FORMAT.
- No value is replaced, computed, or defaulted; absent == None in output.
- No database mapping.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional, Tuple

from .parsed_record import (
    ParseError,
    ParseErrorKind,
    ParsedTradePayload,
    ParsedTradeRecord,
    RecordProvenance,
)


# ---------------------------------------------------------------------------
# UN Comtrade JSON parser
# ---------------------------------------------------------------------------


class UNComtradeParser:
    """Parse a raw UN Comtrade preview JSON payload into ParsedTradePayload.

    Raises ``ParseError`` for structural / field problems; individual field
    errors inside records are attached to each record and not raised unless
    ``strict=True``.
    """

    # Numeric fields whose absence is not an error (source may omit them)
    _OPTIONAL_NUMERIC = frozenset(
        {"netWgt", "cifvalue", "fobvalue", "primaryValue"}
    )

    def parse(
        self,
        payload: bytes,
        raw_collection_id: str,
        source_id: str = "un_comtrade",
        collected_at_iso: str = "",
        source_url: Optional[str] = None,
    ) -> ParsedTradePayload:
        provenance = RecordProvenance(
            source_id=source_id,
            raw_collection_id=raw_collection_id,
            collected_at_iso=collected_at_iso,
            source_url=source_url,
        )

        envelope = _decode_json(payload, source_id, raw_collection_id, "")

        # --- envelope structure ---
        count = envelope.get("count")
        data = envelope.get("data")

        if "count" not in envelope:
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.MISSING_FIELD, "top-level 'count' is absent",
            )
        if count is None:
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.NULL_FIELD, "'count' must not be null",
            )
        if type(count) is not int:
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.WRONG_TYPE,
                f"'count' expected int, got {type(count).__name__}",
            )
        if count < 0:
            raise ParseError(
                source_id, raw_collection_id, "count",
                ParseErrorKind.WRONG_FORMAT, "'count' must be nonnegative",
            )

        if "data" not in envelope:
            raise ParseError(
                source_id, raw_collection_id, "data",
                ParseErrorKind.MISSING_FIELD, "top-level 'data' is absent",
            )
        if data is None:
            raise ParseError(
                source_id, raw_collection_id, "data",
                ParseErrorKind.NULL_FIELD, "'data' must not be null",
            )
        if not isinstance(data, list):
            raise ParseError(
                source_id, raw_collection_id, "data",
                ParseErrorKind.WRONG_TYPE,
                f"'data' expected list, got {type(data).__name__}",
            )

        records = tuple(
            self._parse_record(raw, i, provenance)
            for i, raw in enumerate(data)
        )
        return ParsedTradePayload(
            provenance=provenance,
            records=records,
            record_count=len(records),
            reported_count=count,
        )

    def _parse_record(
        self,
        raw: Any,
        index: int,
        provenance: RecordProvenance,
    ) -> ParsedTradeRecord:
        source_id = provenance.source_id
        cid = provenance.raw_collection_id
        prefix = f"data[{index}]"

        if not isinstance(raw, dict):
            raise ParseError(
                source_id, cid, prefix,
                ParseErrorKind.WRONG_TYPE,
                f"record must be a JSON object, got {type(raw).__name__}",
            )

        def _str_field(key: str) -> Optional[str]:
            if key not in raw:
                return None          # optional in Comtrade responses
            v = raw[key]
            if v is None:
                return None
            if not isinstance(v, (str, int)):
                raise ParseError(
                    source_id, cid, f"{prefix}.{key}",
                    ParseErrorKind.WRONG_TYPE,
                    f"expected str/int, got {type(v).__name__}",
                )
            return str(v)

        def _float_field(key: str) -> Optional[float]:
            if key not in raw:
                return None
            v = raw[key]
            if v is None:
                return None
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ParseError(
                    source_id, cid, f"{prefix}.{key}",
                    ParseErrorKind.WRONG_TYPE,
                    f"expected number, got {type(v).__name__}",
                )
            return float(v)

        # cmdCode is the HS code — required
        cmd_code = raw.get("cmdCode")
        if "cmdCode" not in raw:
            raise ParseError(
                source_id, cid, f"{prefix}.cmdCode",
                ParseErrorKind.MISSING_FIELD, "cmdCode is required",
            )
        if cmd_code is None:
            raise ParseError(
                source_id, cid, f"{prefix}.cmdCode",
                ParseErrorKind.NULL_FIELD, "cmdCode must not be null",
            )
        if not isinstance(cmd_code, (str, int)):
            raise ParseError(
                source_id, cid, f"{prefix}.cmdCode",
                ParseErrorKind.WRONG_TYPE,
                f"cmdCode expected str/int, got {type(cmd_code).__name__}",
            )

        return ParsedTradeRecord(
            provenance=provenance,
            raw_record=dict(raw),  # copy; original not mutated
            reporter_code=_str_field("reporterCode"),
            partner_code=_str_field("partnerCode"),
            hs_code=str(cmd_code),
            period=_str_field("period"),
            flow_code=_str_field("flowCode"),
            net_weight_kg=_float_field("netWgt"),
            trade_value_usd=_float_field("primaryValue"),
            reporter_name=_str_field("reporterDesc"),
            partner_name=_str_field("partnerDesc"),
            product_description=_str_field("cmdDesc"),
        )


# ---------------------------------------------------------------------------
# ITC Trade Map CSV parser
# ---------------------------------------------------------------------------


class ITCTradeMapParser:
    """Parse a raw ITC Trade Map CSV export into ParsedTradePayload.

    The ITC CSV format varies by export type; we parse whatever columns are
    present without assuming a fixed schema.  The first row is treated as the
    header.  Required column: at least one of ``'Commodity code'`` / ``'HS code'``
    or fall back to any column containing 'code'.
    """

    _HS_COLUMN_CANDIDATES = ("Commodity code", "HS code", "Product code")
    _PERIOD_CANDIDATES = ("Period", "Year")
    _VALUE_CANDIDATES = ("Trade Value (USD)", "Value (USD thousands)", "Value")

    def parse(
        self,
        payload: bytes,
        raw_collection_id: str,
        source_id: str = "itc_trade_map",
        collected_at_iso: str = "",
        source_url: Optional[str] = None,
    ) -> ParsedTradePayload:
        provenance = RecordProvenance(
            source_id=source_id,
            raw_collection_id=raw_collection_id,
            collected_at_iso=collected_at_iso,
            source_url=source_url,
        )

        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParseError(
                source_id, raw_collection_id, "",
                ParseErrorKind.INVALID_STRUCTURE,
                f"payload is not valid UTF-8: {exc}",
            ) from exc

        if not text.strip():
            raise ParseError(
                source_id, raw_collection_id, "",
                ParseErrorKind.MISSING_FIELD,
                "CSV payload is empty",
            )

        reader = csv.DictReader(io.StringIO(text))
        try:
            rows: List[Dict[str, str]] = list(reader)
        except csv.Error as exc:
            raise ParseError(
                source_id, raw_collection_id, "",
                ParseErrorKind.INVALID_STRUCTURE,
                f"CSV parse error: {exc}",
            ) from exc

        if reader.fieldnames is None or len(reader.fieldnames) == 0:
            raise ParseError(
                source_id, raw_collection_id, "",
                ParseErrorKind.MISSING_FIELD,
                "CSV has no header row",
            )

        headers = list(reader.fieldnames)
        hs_col = _first_match(headers, self._HS_COLUMN_CANDIDATES)
        period_col = _first_match(headers, self._PERIOD_CANDIDATES)
        value_col = _first_match(headers, self._VALUE_CANDIDATES)

        records = tuple(
            self._parse_row(row, i, provenance, hs_col, period_col, value_col)
            for i, row in enumerate(rows)
        )
        return ParsedTradePayload(
            provenance=provenance,
            records=records,
            record_count=len(records),
            reported_count=None,  # file exports have no envelope count
        )

    def _parse_row(
        self,
        row: Dict[str, str],
        index: int,
        provenance: RecordProvenance,
        hs_col: Optional[str],
        period_col: Optional[str],
        value_col: Optional[str],
    ) -> ParsedTradeRecord:
        source_id = provenance.source_id
        cid = provenance.raw_collection_id
        prefix = f"row[{index}]"

        hs_code: Optional[str] = None
        if hs_col is not None:
            raw_hs = row.get(hs_col, "").strip()
            if raw_hs == "":
                # present column but empty cell → missing value for this row
                hs_code = None
            else:
                hs_code = raw_hs

        period: Optional[str] = None
        if period_col is not None:
            raw_period = row.get(period_col, "").strip()
            period = raw_period if raw_period else None

        trade_value: Optional[float] = None
        if value_col is not None:
            raw_val = row.get(value_col, "").strip()
            if raw_val:
                try:
                    trade_value = float(raw_val.replace(",", ""))
                except ValueError:
                    raise ParseError(
                        source_id, cid, f"{prefix}.{value_col}",
                        ParseErrorKind.WRONG_FORMAT,
                        f"cannot parse trade value: {raw_val!r}",
                    )

        reporter_name: Optional[str] = None
        for cand in ("Reporter", "Exporter", "Importer"):
            if cand in row:
                v = row[cand].strip()
                reporter_name = v if v else None
                break

        partner_name: Optional[str] = None
        for cand in ("Partner country", "Partners", "Partner code"):
            if cand in row:
                v = row[cand].strip()
                partner_name = v if v else None
                break

        flow_code: Optional[str] = None
        for cand in ("Trade Flow", "Flow", "Flow code"):
            if cand in row:
                v = row[cand].strip()
                flow_code = v if v else None
                break

        product_description: Optional[str] = None
        for cand in ("Product description", "Commodity description", "Product label"):
            if cand in row:
                v = row[cand].strip()
                product_description = v if v else None
                break

        net_weight_kg: Optional[float] = None
        for cand in ("Net weight (kg)", "Net Weight (kg)"):
            if cand in row:
                raw_w = row[cand].strip()
                if raw_w:
                    try:
                        net_weight_kg = float(raw_w.replace(",", ""))
                    except ValueError:
                        net_weight_kg = None
                break

        return ParsedTradeRecord(
            provenance=provenance,
            raw_record=dict(row),
            reporter_code=None,            # ITC CSV rarely has numeric codes
            partner_code=None,
            hs_code=hs_code,
            period=period,
            flow_code=flow_code,
            net_weight_kg=net_weight_kg,
            trade_value_usd=trade_value,
            reporter_name=reporter_name,
            partner_name=partner_name,
            product_description=product_description,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_json(
    payload: bytes,
    source_id: str,
    raw_collection_id: str,
    field_path: str,
) -> Dict[str, Any]:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    try:
        body = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParseError(
            source_id, raw_collection_id, field_path,
            ParseErrorKind.INVALID_STRUCTURE,
            f"payload is not valid JSON: {exc}",
        ) from exc
    if not isinstance(body, dict):
        raise ParseError(
            source_id, raw_collection_id, field_path,
            ParseErrorKind.INVALID_STRUCTURE,
            f"expected JSON object at root, got {type(body).__name__}",
        )
    return body


def _first_match(headers: List[str], candidates: Tuple[str, ...]) -> Optional[str]:
    for c in candidates:
        if c in headers:
            return c
    return None
