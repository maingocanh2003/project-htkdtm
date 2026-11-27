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

import codecs
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


# Google Trends uses date columns for time series and location columns for
# regional exports.
_PERIOD_COLUMN_CANDIDATES = (
    "Week", "Day", "Month", "Time", "Region", "Subregion", "City", "Metro",
    "week", "day", "month", "time", "region", "subregion", "city", "metro",
)


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
        related_section: Optional[str] = None,
        source_keyword: Optional[str] = None,
    ) -> ParsedTrendsPayload:
        if related_section is not None:
            if (
                not isinstance(related_section, str)
                or related_section.strip().lower() not in {"top", "rising"}
            ):
                raise ValueError("related_section must be 'top', 'rising', or None")
            related_section = related_section.strip().lower()
        if source_keyword is not None and (
            not isinstance(source_keyword, str) or not source_keyword.strip()
        ):
            raise ValueError("source_keyword must be a non-empty string or None")

        provenance = RecordProvenance(
            source_id=source_id,
            raw_collection_id=raw_collection_id,
            collected_at_iso=collected_at_iso,
            source_url=source_url,
        )

        if payload.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
            raise ParseError(
                source_id, raw_collection_id, "",
                ParseErrorKind.INVALID_STRUCTURE,
                "UTF-32 BOM is unsupported; expected UTF-8 or BOM-marked UTF-16",
            )

        is_utf16 = payload.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE))
        encoding = "utf-16" if is_utf16 else "utf-8-sig"
        encoding_label = "BOM-marked UTF-16" if is_utf16 else "UTF-8"
        try:
            text = payload.decode(encoding)
        except UnicodeDecodeError as exc:
            raise ParseError(
                source_id,
                raw_collection_id,
                "",
                ParseErrorKind.INVALID_STRUCTURE,
                f"payload is not valid {encoding_label}: {exc}",
            ) from exc

        if not text.strip():
            raise ParseError(
                source_id, raw_collection_id, "",
                ParseErrorKind.MISSING_FIELD,
                "CSV payload is empty",
            )

        if "\x00" in text:
            raise ParseError(
                source_id,
                raw_collection_id,
                "",
                ParseErrorKind.INVALID_STRUCTURE,
                "CSV text contains NUL characters",
            )

        try:
            for _ in csv.reader(io.StringIO(text, newline=""), strict=True):
                pass
        except csv.Error as exc:
            raise ParseError(
                source_id,
                raw_collection_id,
                "",
                ParseErrorKind.INVALID_STRUCTURE,
                f"CSV syntax error: {exc}",
            ) from exc

        lines = text.splitlines()
        header_index, period_col, keyword_cols, data_type_hint = (
            _locate_header(lines, source_id, raw_collection_id)
        )

        normalized_hint = (data_type_hint or "").strip().lower()
        period_kind = _period_kind(period_col, normalized_hint)
        if related_section is not None and normalized_hint not in {
            "related queries",
            "related topics",
        }:
            raise ValueError(
                "related_section can only be supplied for related queries or topics"
            )
        if normalized_hint in {"related queries", "related topics"}:
            if period_col.strip().lower() in {"query", "topic"}:
                reader = csv.DictReader(
                    io.StringIO("\n".join(lines[header_index:])),
                    strict=True,
                )
                try:
                    raw_rows = _validated_dict_rows(reader)
                except csv.Error as exc:
                    raise ParseError(
                        source_id,
                        raw_collection_id,
                        "",
                        ParseErrorKind.INVALID_STRUCTURE,
                        f"CSV parse error: {exc}",
                    ) from exc

                rows = tuple(
                    self._parse_row(
                        row,
                        i,
                        provenance,
                        period_col,
                        keyword_cols,
                        related_section=related_section,
                        period_kind="related_term",
                        source_keyword=source_keyword,
                        data_type_hint=data_type_hint,
                    )
                    for i, row in enumerate(raw_rows)
                )
                return ParsedTrendsPayload(
                    provenance=provenance,
                    keywords=tuple(keyword_cols),
                    rows=rows,
                    row_count=len(rows),
                    data_type_hint=data_type_hint,
                    dimension_column=period_col,
                    source_keyword=source_keyword,
                )

            return _parse_related_rows(
                lines[header_index + 1:],
                provenance,
                data_type_hint,
                source_id,
                raw_collection_id,
                related_section=related_section,
                source_keyword=source_keyword,
            )

        data_lines = lines[header_index:]
        reader = csv.DictReader(
            io.StringIO("\n".join(data_lines)),
            strict=True,
        )

        try:
            raw_rows = _validated_dict_rows(reader)
        except csv.Error as exc:
            raise ParseError(
                source_id, raw_collection_id, "",
                ParseErrorKind.INVALID_STRUCTURE,
                f"CSV parse error: {exc}",
            ) from exc

        rows = tuple(
            self._parse_row(
                row,
                i,
                provenance,
                period_col,
                keyword_cols,
                period_kind=period_kind,
                data_type_hint=data_type_hint,
            )
            for i, row in enumerate(raw_rows)
        )
        return ParsedTrendsPayload(
            provenance=provenance,
            keywords=tuple(keyword_cols),
            rows=rows,
            row_count=len(rows),
            data_type_hint=data_type_hint,
            dimension_column=period_col,
        )

    def _parse_row(
        self,
        raw: Dict[str, str],
        index: int,
        provenance: RecordProvenance,
        period_col: str,
        keyword_cols: List[str],
        related_section: Optional[str] = None,
        period_kind: str = "date",
        source_keyword: Optional[str] = None,
        data_type_hint: Optional[str] = None,
    ) -> ParsedTrendsRow:
        sid = provenance.source_id
        cid = provenance.raw_collection_id
        prefix = f"row[{index}]"

        # period — required non-empty string
        period_value = raw.get(period_col, "")
        period = period_value.strip() if isinstance(period_value, str) else ""
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
            related_section=related_section,
            period_kind=period_kind,
            source_keyword=source_keyword,
            data_type_hint=data_type_hint,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _locate_header(
    lines: List[str],
    source_id: str,
    raw_collection_id: str,
) -> Tuple[int, str, List[str], Optional[str]]:
    """Find a chart/table header after optional Google Trends metadata lines."""
    first_non_empty: Optional[Tuple[int, List[str]]] = None
    first_hint: Optional[str] = None
    chart_hint: Optional[str] = None
    related_title: Optional[Tuple[int, str]] = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            cols = next(csv.reader(io.StringIO(stripped), strict=True))
        except (csv.Error, StopIteration):
            continue
        if first_non_empty is None and cols:
            first_non_empty = (i, cols)
            first_hint = stripped

        normalized_line = stripped.casefold()
        if "interest over time" in normalized_line:
            chart_hint = stripped
        elif "interest by region" in normalized_line:
            chart_hint = stripped
        elif normalized_line == "related queries":
            related_title = (i, stripped)
            chart_hint = stripped
        elif normalized_line == "related topics":
            related_title = (i, stripped)
            chart_hint = stripped

        if (
            len(cols) >= 2
            and cols[0].strip().casefold() in {"query", "topic"}
            and cols[1].strip().casefold()
            in {"search interest", "search volume", "value"}
        ):
            if related_title is not None and any(
                line.strip().split(",", 1)[0].casefold() in {"top", "rising"}
                for line in lines[related_title[0] + 1:i]
                if line.strip()
            ):
                return (
                    related_title[0],
                    related_title[1],
                    [],
                    related_title[1],
                )
            kind = "queries" if cols[0].strip().casefold() == "query" else "topics"
            return (
                i,
                cols[0],
                [column for column in cols[1:] if column.strip()],
                chart_hint or f"Related {kind}",
            )

        period_col = next(
            (
                column
                for column in cols
                if column.strip().casefold()
                in {candidate.casefold() for candidate in _PERIOD_COLUMN_CANDIDATES}
            ),
            None,
        )
        if period_col is not None:
            keyword_cols = [column for column in cols if column != period_col and column.strip()]
            inferred_hint = (
                "Interest by region"
                if period_col.strip().casefold()
                in {"region", "subregion", "city", "metro"}
                else "Interest over time"
            )
            return i, period_col, keyword_cols, chart_hint or inferred_hint

    if related_title is not None:
        return related_title[0], related_title[1], [], chart_hint or related_title[1]

    # Fallback: use the first non-empty line as header; first column = period
    if first_non_empty is not None:
        i, cols = first_non_empty
        if cols:
            period_col = cols[0]
            keyword_cols = [column for column in cols[1:] if column.strip()]
            return i, period_col, keyword_cols, first_hint

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            reader = csv.reader(io.StringIO(stripped), strict=True)
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


def _period_kind(period_col: str, data_type_hint: str) -> str:
    normalized = period_col.strip().lower()
    if normalized in {"region", "subregion", "city", "metro"}:
        return "region"
    if normalized in {"query", "topic", "related query", "related topic"}:
        return "related_term"
    if data_type_hint.strip().lower() in {"related queries", "related topics"}:
        return "related_term"
    return "date"


def _validated_dict_rows(reader: csv.DictReader) -> List[Dict[str, str]]:
    headers = reader.fieldnames
    if not headers or any(not header or not header.strip() for header in headers):
        raise csv.Error("CSV header contains an empty column")
    if len(set(headers)) != len(headers):
        raise csv.Error("CSV header contains duplicate columns")

    rows: List[Dict[str, str]] = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise csv.Error("CSV row has a different number of columns than its header")
        rows.append(row)
    return rows


def _parse_related_rows(
    lines: List[str],
    provenance: RecordProvenance,
    data_type_hint: str,
    source_id: str,
    raw_collection_id: str,
    related_section: Optional[str] = None,
    source_keyword: Optional[str] = None,
) -> ParsedTrendsPayload:
    """Parse Google Trends Top/Rising tables without interpreting their values."""
    section = related_section.title() if related_section is not None else None
    keyword = "Value"
    value_columns = (keyword,)
    csv_source_keyword: Optional[str] = None
    rows: List[ParsedTrendsRow] = []

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            fields = next(csv.reader([line], strict=True))
        except csv.Error as exc:
            raise ParseError(
                source_id,
                raw_collection_id,
                f"line[{line_number}]",
                ParseErrorKind.INVALID_STRUCTURE,
                f"CSV parse error: {exc}",
            ) from exc

        fields = [field.strip() for field in fields]
        if not fields:
            continue

        first = fields[0].lower()
        if first in {"top", "rising"}:
            section = fields[0]
            if len(fields) > 1 and fields[1]:
                keyword = fields[1]
                value_columns = (keyword,)
                if csv_source_keyword is not None and (
                    csv_source_keyword.casefold() != keyword.casefold()
                ):
                    raise ParseError(
                        source_id,
                        raw_collection_id,
                        f"line[{line_number}]",
                        ParseErrorKind.INVALID_STRUCTURE,
                        "related section headers identify different source keywords",
                    )
                csv_source_keyword = keyword
            continue

        if first in {"query", "topic", "related query", "related topic"}:
            if len(fields) > 1 and fields[1].lower() in {
                "value",
                "search volume",
                "search interest",
            }:
                value_columns = tuple(fields[1:])
                keyword = value_columns[0]
                continue

        if section is None:
            continue
        if len(fields) < 2:
            raise ParseError(
                source_id,
                raw_collection_id,
                f"line[{line_number}]",
                ParseErrorKind.INVALID_STRUCTURE,
                "related query/topic row must contain a label and value",
            )

        label = fields[0]
        if len(fields) - 1 != len(value_columns):
            raise ParseError(
                source_id,
                raw_collection_id,
                f"line[{line_number}]",
                ParseErrorKind.INVALID_STRUCTURE,
                "related query/topic row does not match its value-column header",
            )
        if not label:
            raise ParseError(
                source_id,
                raw_collection_id,
                f"line[{line_number}]",
                ParseErrorKind.MISSING_FIELD,
                "related query/topic label is empty",
            )

        row_label = "query" if "quer" in data_type_hint.lower() else "topic"
        raw_row = {"section": section, row_label: label}
        raw_row.update(zip(value_columns, fields[1:]))
        rows.append(
            ParsedTrendsRow(
                provenance=provenance,
                raw_row=raw_row,
                period_label=label,
                keyword_values=tuple(zip(value_columns, fields[1:])),
                related_section=section.lower() if section is not None else None,
                period_kind="related_term",
                source_keyword=source_keyword or csv_source_keyword,
                data_type_hint=data_type_hint,
            )
        )

    if (
        source_keyword is not None
        and csv_source_keyword is not None
        and source_keyword.casefold() != csv_source_keyword.casefold()
    ):
        raise ParseError(
            source_id,
            raw_collection_id,
            "source_keyword",
            ParseErrorKind.WRONG_FORMAT,
            "related CSV keyword does not match collection metadata",
        )

    return ParsedTrendsPayload(
        provenance=provenance,
        keywords=(keyword,),
        rows=tuple(rows),
        row_count=len(rows),
        data_type_hint=data_type_hint,
        dimension_column="query" if "quer" in data_type_hint.lower() else "topic",
        source_keyword=source_keyword or csv_source_keyword,
    )
