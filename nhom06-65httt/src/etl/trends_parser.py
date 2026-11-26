"""D10 parser for D8 raw Google Trends CSV export payloads.

Design rules:
- Values stay as raw strings — semantics (0–100 index, rank, growth) must NOT
  be inferred; they are documented in the manifest's value_semantics field.
- raw_row is the original DictReader row dict; never mutated.
- ParseError.kind distinguishes MISSING / NULL / WRONG_TYPE / WRONG_FORMAT.
- The CSV structure exported by the Trends UI includes a metadata header
  (1–4 lines before the data header row).  We skip non-data lines by detecting
  the header that contains the period column.
"""

from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional, Tuple

from .parsed_record import (
    ParseError,
    ParseErrorKind,
    ParsedTrendsPayload,
    ParsedTrendsRow,
    RecordProvenance,
)


# Column names that Google Trends uses for the period dimension
_PERIOD_COLUMN_CANDIDATES = ("Week", "Day", "Month", "week", "day", "month")


class GoogleTrendsParser:
    """Parse a Google Trends UI CSV export into ParsedTrendsPayload.

    The export CSV starts with metadata comment lines before the actual data
    header.  This parser skips leading lines until it finds one containing a
    recognised period column name, then treats that as the header.

    If no recognised period column is found the first non-empty row is used as
    the header with the first column acting as the period column.
    """

    def parse(
        self,
        payload: bytes,
        raw_collection_id: str,
        source_id: str = "google_trends",
        collected_at_iso: str = "",
        source_url: Optional[str] = None,
    ) -> ParsedTrendsPayload:
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

        lines = text.splitlines()
        header_index, period_col, keyword_cols, data_type_hint = (
            _locate_header(lines, source_id, raw_collection_id)
        )

        data_lines = lines[header_index:]
        reader = csv.DictReader(io.StringIO("\n".join(data_lines)))

        try:
            raw_rows: List[Dict[str, str]] = list(reader)
        except csv.Error as exc:
            raise ParseError(
                source_id, raw_collection_id, "",
                ParseErrorKind.INVALID_STRUCTURE,
                f"CSV parse error: {exc}",
            ) from exc

        rows = tuple(
            self._parse_row(row, i, provenance, period_col, keyword_cols)
            for i, row in enumerate(raw_rows)
        )
        return ParsedTrendsPayload(
            provenance=provenance,
            keywords=tuple(keyword_cols),
            rows=rows,
            row_count=len(rows),
            data_type_hint=data_type_hint,
        )

    def _parse_row(
        self,
        raw: Dict[str, str],
        index: int,
        provenance: RecordProvenance,
        period_col: str,
        keyword_cols: List[str],
    ) -> ParsedTrendsRow:
        sid = provenance.source_id
        cid = provenance.raw_collection_id
        prefix = f"row[{index}]"

        # period — required non-empty string
        period = raw.get(period_col, "").strip()
        if not period:
            raise ParseError(
                sid, cid, f"{prefix}.{period_col}",
                ParseErrorKind.MISSING_FIELD,
                f"period column '{period_col}' is empty",
            )

        # keyword values — keep as raw strings, no numeric validation
        keyword_values: List[Tuple[str, str]] = []
        for kw in keyword_cols:
            raw_val = raw.get(kw, "")
            # Empty string is allowed (may mean no data for that period)
            keyword_values.append((kw, raw_val))

        return ParsedTrendsRow(
            provenance=provenance,
            raw_row=dict(raw),
            period_label=period,
            keyword_values=tuple(keyword_values),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _locate_header(
    lines: List[str],
    source_id: str,
    raw_collection_id: str,
) -> Tuple[int, str, List[str], Optional[str]]:
    """Find the data-header line; return (line_index, period_col, keyword_cols, hint).

    ``hint`` is the content of the first non-empty line before the header,
    which in Trends exports is the data-type label (e.g. 'Interest over time').
    """
    data_type_hint: Optional[str] = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this line contains a period column candidate
        try:
            reader = csv.reader(io.StringIO(stripped))
            cols = next(reader)
        except (csv.Error, StopIteration):
            continue

        period_col: Optional[str] = None
        for cand in _PERIOD_COLUMN_CANDIDATES:
            if cand in cols:
                period_col = cand
                break

        if period_col is not None:
            keyword_cols = [c for c in cols if c != period_col and c.strip()]
            return i, period_col, keyword_cols, data_type_hint

        # Not a data header — record as hint if it's the first text line
        if data_type_hint is None:
            data_type_hint = stripped

    # Fallback: use the first non-empty line as header; first column = period
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            reader = csv.reader(io.StringIO(stripped))
            cols = next(reader)
        except (csv.Error, StopIteration):
            continue
        if cols:
            period_col = cols[0]
            keyword_cols = [c for c in cols[1:] if c.strip()]
            return i, period_col, keyword_cols, data_type_hint

    raise ParseError(
        source_id, raw_collection_id, "",
        ParseErrorKind.MISSING_FIELD,
        "CSV contains no recognisable data header row",
    )
