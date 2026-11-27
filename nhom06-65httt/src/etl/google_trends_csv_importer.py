"""Validate and import the five-keyword Google Trends G1 UI exports."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent
sys.path.insert(0, str(_SRC))

from etl.google_trends_collector import (  # noqa: E402
    GoogleTrendsExportAdapter,
    GoogleTrendsRequest,
    TrendsDataType,
)
from etl.parsed_record import ParseError  # noqa: E402
from etl.raw_storage import RawStorage  # noqa: E402
from etl.source_registry import create_project_source_registry  # noqa: E402
from etl.trends_parser import GoogleTrendsParser  # noqa: E402


G1_KEYWORDS: Tuple[str, ...] = (
    "ceramic",
    "ceramics",
    "pottery",
    "porcelain",
    "stoneware",
)
G1_GEOS: Tuple[str, ...] = ("VN", "US", "JP", "DE", "FR", "IN")

_FILENAME_RE = re.compile(
    r"^g1_(?P<geo>VN|US|JP|DE|FR|IN)_(?:"
    r"compare5_(?P<chart>interest_over_time|interest_by_region)"
    r"|(?P<keyword>ceramic|ceramics|pottery|porcelain|stoneware)_"
    r"(?P<related>related_queries|related_topics)_(?P<section>top|rising)"
    r")_(?P<date>\d{8})\.csv$"
)
_SHA256_INDEX_FILENAME = ".imported_sha256_index.json"
_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_sha256_index(incoming_dir: Path) -> Dict[str, str]:
    path = incoming_dir / _SHA256_INDEX_FILENAME
    if not path.exists():
        return {}
    index = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or any(
        not isinstance(digest, str)
        or not re.fullmatch(r"[a-f0-9]{64}", digest)
        or not isinstance(collection_id, str)
        or not re.fullmatch(r"[a-f0-9]{32}", collection_id)
        for digest, collection_id in index.items()
    ):
        raise ValueError(f"Invalid SHA-256 import index: {path}")
    return index


def _save_sha256_index(incoming_dir: Path, index: Dict[str, str]) -> None:
    path = incoming_dir / _SHA256_INDEX_FILENAME
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        temporary_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(path)
    except OSError:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def _parse_filename(filename: str) -> Optional[Tuple[str, str, str, str]]:
    """Return group, geo, data type, and export date for a permitted G1 name."""
    match = _FILENAME_RE.fullmatch(filename)
    if match is None:
        return None
    geo = match.group("geo")
    if geo is None:
        return None
    date_str = match.group("date")
    try:
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return None
    data_type = match.group("chart")
    if data_type is None:
        data_type = f"{match.group('related')}_{match.group('section')}"
    return "g1", geo, data_type, date_str


def _filename_keyword(filename: str) -> Optional[str]:
    match = _FILENAME_RE.fullmatch(filename)
    return match.group("keyword") if match is not None else None


def _infer_period(date_str: str) -> Tuple[date, date]:
    """Infer the selected five-year date window from the actual export date."""
    export_date = datetime.strptime(date_str, "%Y%m%d").date()
    start_year = export_date.year - 5
    start_day = min(
        export_date.day, calendar.monthrange(start_year, export_date.month)[1]
    )
    return date(start_year, export_date.month, start_day), export_date


def _infer_cadence(period_labels: Tuple[str, ...]) -> Optional[str]:
    if len(period_labels) < 2:
        return None
    periods: List[date] = []
    for label in period_labels:
        parsed_date: Optional[date] = None
        for date_format in _DATE_FORMATS:
            try:
                parsed_date = datetime.strptime(label.strip(), date_format).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            return None
        periods.append(parsed_date)

    gaps = tuple(current - previous for previous, current in zip(periods, periods[1:]))
    if not gaps or any(gap.days <= 0 for gap in gaps):
        return None
    if all(gap == timedelta(days=7) for gap in gaps):
        return "weekly"
    if all(
        previous.day == current.day == 1
        and (current.year - previous.year) * 12 + current.month - previous.month == 1
        for previous, current in zip(periods, periods[1:])
    ):
        return "monthly"
    if all(gap == timedelta(days=1) for gap in gaps):
        return "daily"
    return None


def _canonical_keyword_header(header: str) -> str:
    """Remove Google Trends' optional geo suffix while preserving keyword text."""
    normalized = header.strip()
    for keyword in G1_KEYWORDS:
        folded = normalized.casefold()
        canonical = keyword.casefold()
        if folded == canonical or folded.startswith(canonical + ":") or folded.startswith(
            canonical + " ("
        ):
            return keyword
    return normalized


def _recognized_chart_hint(hint: str) -> Optional[str]:
    for chart_type in (
        "interest over time",
        "interest by region",
        "related queries",
        "related topics",
    ):
        if chart_type in hint:
            return chart_type
    return None


def _build_request(
    group: str,
    geo: str,
    data_type_str: str,
    date_str: str,
    original_filename: Optional[str] = None,
    interval: Optional[str] = None,
    exported_keywords: Optional[Tuple[str, ...]] = None,
    keyword_header_matches_request: Optional[bool] = None,
    keyword: Optional[str] = None,
) -> Optional[GoogleTrendsRequest]:
    if group != "g1" or geo not in G1_GEOS:
        return None

    if data_type_str == "interest_over_time":
        data_type = TrendsDataType.INTEREST_OVER_TIME
    elif data_type_str == "interest_by_region":
        data_type = TrendsDataType.INTEREST_BY_REGION
    elif data_type_str.startswith("related_queries_"):
        data_type = TrendsDataType.RELATED_QUERIES
    elif data_type_str.startswith("related_topics_"):
        data_type = TrendsDataType.RELATED_TOPICS
    else:
        return None

    related_section = (
        data_type_str.rsplit("_", 1)[1]
        if data_type_str.endswith(("_top", "_rising"))
        else None
    )
    if related_section and keyword not in G1_KEYWORDS:
        return None

    period_start, period_end = _infer_period(date_str)
    keywords = (keyword,) if related_section and keyword else G1_KEYWORDS
    return GoogleTrendsRequest(
        keywords=keywords,
        period_start=period_start,
        period_end=period_end,
        geo=geo,
        data_type=data_type,
        search_type="web",
        interval=interval,
        category="All categories",
        original_filename=original_filename,
        export_date=datetime.strptime(date_str, "%Y%m%d").date(),
        related_section=related_section,
        exported_keywords=exported_keywords,
        keyword_header_matches_request=keyword_header_matches_request,
        group_id=group,
    )


def _validate_payload(
    payload: bytes,
    data_type_str: str,
    requested_keywords: Tuple[str, ...],
    export_date: date,
) -> Tuple[Tuple[str, ...], Optional[str]]:
    section = (
        data_type_str.rsplit("_", 1)[1]
        if data_type_str.endswith(("_top", "_rising"))
        else None
    )
    parsed = GoogleTrendsParser().parse(
        payload,
        raw_collection_id="import-validation",
        related_section=section,
        source_keyword=requested_keywords[0] if section else None,
    )
    hint = (parsed.data_type_hint or "").strip().casefold()
    recognized_hint = _recognized_chart_hint(hint)

    if data_type_str == "interest_over_time":
        if parsed.dimension_column is None or parsed.dimension_column.strip().casefold() not in {
            "week",
            "month",
            "day",
            "time",
        }:
            raise ValueError("Interest Over Time CSV must have a Week/Month/Day/Time header")
        if recognized_hint and recognized_hint != "interest over time":
            raise ValueError("CSV chart title does not match Interest Over Time")
        exported = tuple(_canonical_keyword_header(name) for name in parsed.keywords)
        if exported != requested_keywords:
            raise ValueError(
                "Interest Over Time CSV must contain the five G1 keyword columns "
                "in the configured order"
            )
        if not parsed.rows:
            raise ValueError("Interest Over Time CSV contains no data rows")
        if not _rows_match_window(parsed, export_date):
            raise ValueError("CSV period labels fall outside the selected five-year window")
        return exported, _infer_cadence(tuple(row.period_label for row in parsed.rows))

    if data_type_str == "interest_by_region":
        if (
            parsed.dimension_column is None
            or parsed.dimension_column.strip().casefold() != "region"
        ):
            raise ValueError("Interest by Region CSV must have a Region header")
        if recognized_hint and recognized_hint != "interest by region":
            raise ValueError("CSV chart title does not match Interest by Region")
        exported = tuple(_canonical_keyword_header(name) for name in parsed.keywords)
        if exported != requested_keywords:
            raise ValueError(
                "Interest by Region CSV must contain the five G1 keyword columns "
                "in the configured order"
            )
        if not parsed.rows:
            raise ValueError("Interest by Region CSV contains no data rows")
        return exported, None

    expected_hint = (
        "related queries" if data_type_str.startswith("related_queries_")
        else "related topics"
    )
    if recognized_hint and recognized_hint != expected_hint:
        raise ValueError(f"CSV chart title/header does not match {expected_hint.title()}")
    if recognized_hint is None and parsed.dimension_column is None:
        raise ValueError(f"CSV header does not identify {expected_hint.title()} data")
    if not parsed.rows:
        raise ValueError(f"{expected_hint.title()} CSV contains no data rows")
    if any(row.related_section != section for row in parsed.rows):
        raise ValueError(f"CSV related section does not match filename section '{section}'")
    if parsed.source_keyword != requested_keywords[0]:
        raise ValueError("Related CSV keyword does not match the filename keyword")
    return requested_keywords, None


def _rows_match_window(parsed, export_date: date) -> bool:
    period_start, period_end = _infer_period(export_date.strftime("%Y%m%d"))
    for row in parsed.rows:
        parsed_label: Optional[date] = None
        for date_format in _DATE_FORMATS:
            try:
                parsed_label = datetime.strptime(row.period_label.strip(), date_format).date()
                break
            except ValueError:
                continue
        if parsed_label is None:
            return False
        if parsed_label > period_end:
            return False
        if parsed_label < period_start:
            month_bucket = (
                (len(row.period_label.strip()) == 7 or row.period_label.strip().endswith("-01"))
                and parsed_label.year == period_start.year
                and parsed_label.month == period_start.month
            )
            weekly_bucket = parsed_label >= period_start - timedelta(days=7)
            if not (month_bucket or weekly_bucket):
                return False
    return True


class GoogleTrendsCsvImporter:
    """Validate G1 exports and store immutable raw payloads with provenance."""

    def __init__(
        self,
        incoming_dir: Path,
        raw_dir: Path,
        dry_run: bool = False,
    ) -> None:
        self._incoming_dir = Path(incoming_dir)
        self._raw_dir = Path(raw_dir)
        self._dry_run = dry_run
        registry = create_project_source_registry()
        self._storage = RawStorage(self._raw_dir, registry)
        self._adapter = GoogleTrendsExportAdapter(self._storage, registry)
        self._sha256_index = _load_sha256_index(self._incoming_dir)
        self._seen_sha256 = set()

    def run(self) -> List[Dict[str, str]]:
        if not self._incoming_dir.is_dir():
            raise FileNotFoundError(f"Incoming directory does not exist: {self._incoming_dir}")

        csv_files = sorted(
            path for path in self._incoming_dir.iterdir()
            if path.is_file() and path.suffix.casefold() == ".csv"
        )
        results = [self._process_file(path) for path in csv_files]
        if not self._dry_run and any(result["status"] == "imported" for result in results):
            _save_sha256_index(self._incoming_dir, self._sha256_index)
        self._print_summary(results)
        return results

    def _process_file(self, csv_file: Path) -> Dict[str, str]:
        filename = csv_file.name
        print(f"\n[FILE] {filename}")
        parsed_name = _parse_filename(filename)
        if parsed_name is None:
            return self._rejected(filename, "Filename is not a permitted G1 CSV name/date")
        group, geo, data_type_str, date_str = parsed_name
        export_date = datetime.strptime(date_str, "%Y%m%d").date()
        requested_keywords = (
            (_filename_keyword(filename),)
            if data_type_str.startswith(("related_queries_", "related_topics_"))
            else G1_KEYWORDS
        )
        if not all(requested_keywords):
            return self._rejected(filename, "Filename does not identify a G1 keyword")

        try:
            payload = csv_file.read_bytes()
        except OSError as exc:
            return self._rejected(filename, f"Could not read CSV: {exc}")
        if not payload:
            return self._rejected(filename, "CSV file is empty")

        sha256 = _sha256_hex(payload)
        if sha256 in self._sha256_index or sha256 in self._seen_sha256:
            print(f"  [SKIPPED] Duplicate SHA-256: {sha256}")
            self._seen_sha256.add(sha256)
            return {
                "file": filename,
                "status": "skipped_duplicate",
                "sha256": sha256,
            }

        try:
            exported_keywords, interval = _validate_payload(
                payload, data_type_str, requested_keywords, export_date
            )
        except (ParseError, ValueError) as exc:
            return self._rejected(filename, str(exc), sha256)

        request = _build_request(
            group,
            geo,
            data_type_str,
            date_str,
            original_filename=filename,
            interval=interval,
            exported_keywords=exported_keywords,
            keyword_header_matches_request=True,
            keyword=requested_keywords[0] if len(requested_keywords) == 1 else None,
        )
        if request is None:
            return self._rejected(filename, "Could not construct G1 collection metadata", sha256)

        self._seen_sha256.add(sha256)
        if self._dry_run:
            print(f"  [WOULD IMPORT] Validated SHA-256={sha256}")
            return {
                "file": filename,
                "status": "would_import",
                "sha256": sha256,
            }

        try:
            collection_id = self._adapter.ingest(payload, request)
        except (OSError, TypeError, ValueError) as exc:
            return self._rejected(filename, f"Could not store CSV: {exc}", sha256)
        self._sha256_index[sha256] = collection_id
        print(f"  [IMPORTED] collection_id={collection_id} SHA-256={sha256}")
        return {
            "file": filename,
            "status": "imported",
            "sha256": sha256,
            "collection_id": collection_id,
        }

    @staticmethod
    def _rejected(filename: str, reason: str, sha256: Optional[str] = None) -> Dict[str, str]:
        print(f"  [REJECTED] {reason}")
        result = {"file": filename, "status": "rejected", "reason": reason}
        if sha256:
            result["sha256"] = sha256
        return result

    @staticmethod
    def _print_summary(results: List[Dict[str, str]]) -> None:
        counts: Dict[str, int] = {}
        for result in results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        print("\nIMPORT SUMMARY")
        print(f"  Imported: {counts.get('imported', 0)}")
        print(f"  Would import (dry-run): {counts.get('would_import', 0)}")
        print(f"  Skipped: {counts.get('skipped_duplicate', 0)}")
        print(f"  Rejected: {counts.get('rejected', 0)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate/import Google Trends G1 UI exports."
    )
    parser.add_argument(
        "--incoming",
        type=Path,
        default=Path("nhom06-65httt/data/incoming/google_trends"),
        help="Directory containing G1 CSV exports for the six configured markets",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("nhom06-65httt/data/raw"),
        help="RawStorage root directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate files without writing collections or the import index",
    )
    args = parser.parse_args()

    try:
        importer = GoogleTrendsCsvImporter(
            incoming_dir=args.incoming,
            raw_dir=args.raw,
            dry_run=args.dry_run,
        )
        results = importer.run()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    if any(result["status"] == "rejected" for result in results):
        sys.exit(2)


if __name__ == "__main__":
    main()
