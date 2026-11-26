"""D6 – Google Trends CSV Importer.

Script tiện ích để import từng file CSV từ thư mục incoming vào RawStorage.

Quy ước tên file:
    {nhom}_{geo}_{data_type}_{date}.csv

Ví dụ:
    g1_VN_interest_over_time_20261120.csv
    g3_US_related_queries_20261120.csv
    g4_VN_interest_by_region_20261120.csv

Chống trùng lặp: so sánh SHA-256 của payload trước khi lưu.
Nếu SHA-256 đã tồn tại trong index, bỏ qua và báo cáo.

Sử dụng:
    python google_trends_csv_importer.py \\
        --incoming nhom06-65httt/data/incoming/google_trends \\
        --raw nhom06-65httt/data/raw \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Thêm src vào sys.path để import được ETL modules
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent  # nhom06-65httt/src
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


# ---------------------------------------------------------------------------
# Cấu hình nhóm từ khóa
# ---------------------------------------------------------------------------

_KEYWORD_GROUPS: Dict[str, Tuple[str, ...]] = {
    "g1": (
        "ceramic tableware",
        "porcelain tableware",
        "ceramic dinnerware",
        "porcelain dinnerware",
        "stoneware",
    ),
    "g1b": (
        "ceramic plates",
        "ceramic bowls",
        "ceramic mugs",
    ),
    "g2": (
        "dinnerware sets",
        "porcelain dinnerware sets",
        "ceramic kitchenware",
        "ceramic tea sets",
        "porcelain tea sets",
    ),
    "g3": (
        "ceramic vase",
        "pottery",
        "ceramic decoration",
        "handmade pottery",
    ),
    "g4": (
        "bộ đồ ăn gốm sứ",
        "bát đĩa gốm sứ",
        "gốm sứ Bát Tràng",
        "đồ gốm trang trí",
        "bình hoa gốm sứ",
    ),
}

_DATA_TYPE_MAP: Dict[str, TrendsDataType] = {
    "interest_over_time": TrendsDataType.INTEREST_OVER_TIME,
    "interest_by_region": TrendsDataType.INTEREST_BY_REGION,
    "related_queries": TrendsDataType.RELATED_QUERIES,
    "related_queries_top": TrendsDataType.RELATED_QUERIES,
    "related_queries_rising": TrendsDataType.RELATED_QUERIES,
    "related_topics": TrendsDataType.RELATED_TOPICS,
    "related_topics_top": TrendsDataType.RELATED_TOPICS,
    "related_topics_rising": TrendsDataType.RELATED_TOPICS,
}

# Pattern: {group}_{geo}_{data_type}_{date}.csv
# Ví dụ: g1_VN_interest_over_time_20261120.csv
_FILENAME_RE = re.compile(
    r"^(?P<group>g\w+)_(?P<geo>[A-Z]{2,3})_"
    r"(?P<data_type>interest_over_time|interest_by_region|related_queries|related_topics)"
    r"(?:_(?P<related_section>top|rising))?"
    r"_(?P<date>\d{8})\.csv$",
    re.IGNORECASE,
)

# SHA-256 index để chống trùng lặp – lưu trong incoming/ để bền vững
_SHA256_INDEX_FILENAME = ".imported_sha256_index.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _import_fingerprint(sha256: str, request: GoogleTrendsRequest) -> str:
    identity = {
        "sha256": sha256,
        "keywords": request.keywords,
        "period_start": request.period_start.isoformat(),
        "period_end": request.period_end.isoformat(),
        "geo": request.geo,
        "data_type": request.data_type.value,
        "search_type": request.search_type,
        "interval": request.interval,
        "category": request.category,
    }
    if request.related_section is not None:
        identity["related_section"] = request.related_section
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return _sha256_hex(encoded)


def _load_sha256_index(incoming_dir: Path) -> Dict[str, str]:
    """Load import-fingerprint → collection_id index from JSON."""
    path = incoming_dir / _SHA256_INDEX_FILENAME
    if path.exists():
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
    return {}


def _save_sha256_index(incoming_dir: Path, index: Dict[str, str]) -> None:
    path = incoming_dir / _SHA256_INDEX_FILENAME
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_filename(filename: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse tên file → (group, geo, data_type, date_str) hoặc None."""
    m = _FILENAME_RE.match(filename)
    if not m:
        return None
    date_str = m.group("date")
    try:
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return None
    data_type = m.group("data_type").lower()
    related_section = m.group("related_section")
    if related_section:
        data_type = f"{data_type}_{related_section.lower()}"
    return (m.group("group").lower(), m.group("geo").upper(), data_type, date_str)


def _infer_period(date_str: str) -> Tuple[date, date]:
    """Từ date_str (YYYYMMDD) → (period_start, period_end).
    Mặc định: 5 năm trước ngày xuất đến ngày xuất.
    """
    export_date = datetime.strptime(date_str, "%Y%m%d").date()
    start_year = export_date.year - 5
    start_day = min(export_date.day, calendar.monthrange(start_year, export_date.month)[1])
    period_start = date(start_year, export_date.month, start_day)
    period_end = export_date
    return period_start, period_end


def _infer_cadence(period_labels: Tuple[str, ...]) -> Optional[str]:
    """Infer a regular cadence from parsed date labels, or leave it unknown."""
    if len(period_labels) < 2:
        return None

    periods: List[date] = []
    for label in period_labels:
        parsed_date: Optional[date] = None
        for date_format in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"):
            try:
                parsed_date = datetime.strptime(label.strip(), date_format).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            return None
        periods.append(parsed_date)

    if any(current <= previous for previous, current in zip(periods, periods[1:])):
        return None

    if all(current - previous == timedelta(days=7) for previous, current in zip(periods, periods[1:])):
        return "weekly"
    if all(
        previous.day == current.day == 1
        and (current.year - previous.year) * 12 + current.month - previous.month == 1
        for previous, current in zip(periods, periods[1:])
    ):
        return "monthly"
    if all(current - previous == timedelta(days=1) for previous, current in zip(periods, periods[1:])):
        return "daily"
    return None


def _keyword_headers_match(
    requested_keywords: Tuple[str, ...],
    exported_keywords: Tuple[str, ...],
) -> bool:
    requested = tuple(keyword.strip().casefold() for keyword in requested_keywords)
    exported = tuple(keyword.strip().casefold() for keyword in exported_keywords)
    return requested == exported


def _build_request(
    group: str,
    geo: str,
    data_type_str: str,
    date_str: str,
    original_filename: Optional[str] = None,
    interval: Optional[str] = None,
    exported_keywords: Optional[Tuple[str, ...]] = None,
    keyword_header_matches_request: Optional[bool] = None,
) -> Optional[GoogleTrendsRequest]:
    """Tạo GoogleTrendsRequest từ thông tin tên file."""
    keywords = _KEYWORD_GROUPS.get(group)
    if not keywords:
        print(f"  [WARN] Unknown keyword group: '{group}' - skipped")
        return None

    data_type = _DATA_TYPE_MAP.get(data_type_str)
    if data_type is None:
        print(f"  [WARN] Unknown data type: '{data_type_str}' - skipped")
        return None

    related_section = (
        data_type_str.rsplit("_", 1)[1]
        if data_type_str.endswith(("_top", "_rising"))
        else None
    )
    period_start, period_end = _infer_period(date_str)

    return GoogleTrendsRequest(
        keywords=keywords,
        period_start=period_start,
        period_end=period_end,
        geo=geo,
        data_type=data_type,
        search_type="web",
        interval=interval,
        original_filename=original_filename,
        export_date=datetime.strptime(date_str, "%Y%m%d").date(),
        related_section=related_section,
        exported_keywords=exported_keywords,
        keyword_header_matches_request=keyword_header_matches_request,
    )


# ---------------------------------------------------------------------------
# Importer chính
# ---------------------------------------------------------------------------


class GoogleTrendsCsvImporter:
    """Import tất cả file CSV trong incoming_dir vào RawStorage."""

    def __init__(
        self,
        incoming_dir: Path,
        raw_dir: Path,
        dry_run: bool = False,
    ) -> None:
        self._incoming_dir = incoming_dir
        self._dry_run = dry_run
        reg = create_project_source_registry()
        self._adapter = GoogleTrendsExportAdapter(RawStorage(raw_dir, reg), reg)
        self._sha256_index = _load_sha256_index(incoming_dir)
        self._incoming_dir_ref = incoming_dir  # cho save index

    def run(self) -> List[Dict]:
        """Chạy import tất cả file CSV hợp lệ. Trả về danh sách kết quả."""
        csv_files = sorted(
            f for f in self._incoming_dir.iterdir()
            if f.suffix.lower() == ".csv"
        )

        if not csv_files:
            print(f"[INFO] No CSV files found in: {self._incoming_dir}")
            print("[INFO] Add official Google Trends UI exports and run again.")
            return []

        results = []
        for csv_file in csv_files:
            result = self._process_file(csv_file)
            results.append(result)

        if not self._dry_run:
            _save_sha256_index(self._incoming_dir_ref, self._sha256_index)

        self._print_summary(results)
        return results

    def _process_file(self, csv_file: Path) -> Dict:
        filename = csv_file.name
        print(f"\n[FILE] {filename}")

        parsed = _parse_filename(filename)
        if parsed is None:
            print(f"  [SKIP] Invalid filename or date: {filename}")
            return {"file": filename, "status": "skipped_bad_name"}

        group, geo, data_type_str, date_str = parsed
        print(f"  Group: {group}, country: {geo}, type: {data_type_str}, export date: {date_str}")

        payload = csv_file.read_bytes()
        if not payload:
            print("  [SKIP] Empty file")
            return {"file": filename, "status": "skipped_empty"}

        sha256 = _sha256_hex(payload)
        requested_keywords = _KEYWORD_GROUPS.get(group)
        interval: Optional[str] = None
        exported_keywords: Optional[Tuple[str, ...]] = None
        keyword_header_matches_request: Optional[bool] = None
        if (
            requested_keywords is not None
            and data_type_str in {"interest_over_time", "interest_by_region"}
        ):
            try:
                preview = GoogleTrendsParser().parse(
                    payload, raw_collection_id="import-metadata-preview"
                )
            except ParseError as exc:
                print(
                    "  [WARN] Could not inspect CSV metadata "
                    f"({exc.kind.value}); cadence and exported keywords remain unknown"
                )
            else:
                exported_keywords = preview.keywords
                keyword_header_matches_request = _keyword_headers_match(
                    requested_keywords, exported_keywords
                )
                if not keyword_header_matches_request:
                    print(
                        "  [WARN] Requested keywords differ from CSV keyword columns; "
                        "both will be recorded"
                    )
                if data_type_str == "interest_over_time":
                    interval = _infer_cadence(
                        tuple(row.period_label for row in preview.rows)
                    )
                    if interval is None:
                        print(
                            "  [WARN] Could not infer Interest Over Time cadence "
                            "from CSV dates; interval remains unknown"
                        )

        request = _build_request(
            group,
            geo,
            data_type_str,
            date_str,
            original_filename=filename,
            interval=interval,
            exported_keywords=exported_keywords,
            keyword_header_matches_request=keyword_header_matches_request,
        )
        if request is None:
            return {"file": filename, "status": "skipped_bad_request"}

        fingerprint = _import_fingerprint(sha256, request)
        if fingerprint in self._sha256_index:
            existing_cid = self._sha256_index[fingerprint]
            print(f"  [SKIP] Already imported (matching file and query): collection_id={existing_cid}")
            return {
                "file": filename,
                "status": "skipped_duplicate",
                "sha256": sha256,
                "existing_collection_id": existing_cid,
            }

        if self._dry_run:
            print(f"  [DRY-RUN] Would import: SHA-256={sha256[:16]}...")
            return {"file": filename, "status": "dry_run", "sha256": sha256}

        try:
            collection_id = self._adapter.ingest(payload, request)
            self._sha256_index[fingerprint] = collection_id
            print(f"  [OK] collection_id={collection_id}")
            print(f"       SHA-256={sha256}")
            return {
                "file": filename,
                "status": "imported",
                "collection_id": collection_id,
                "sha256": sha256,
                "group": group,
                "geo": geo,
                "data_type": data_type_str,
                "size_bytes": len(payload),
            }
        except (OSError, TypeError, ValueError) as exc:
            print(f"  [ERROR] Could not store CSV: {exc}")
            return {"file": filename, "status": "error", "error": str(exc)}

    @staticmethod
    def _print_summary(results: List[Dict]) -> None:
        print("\n" + "=" * 60)
        print("IMPORT SUMMARY")
        print("=" * 60)
        counts: Dict[str, int] = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        for status, count in sorted(counts.items()):
            print(f"  {status:30s}: {count}")
        total = len(results)
        imported = counts.get("imported", 0)
        print(f"\nFiles: {total}  |  Imported: {imported}  |  Skipped: {total - imported}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Google Trends CSV exports vào RawStorage (D6).",
    )
    parser.add_argument(
        "--incoming",
        type=Path,
        default=Path("nhom06-65httt/data/incoming/google_trends"),
        help="Thư mục chứa file CSV xuất từ Google Trends",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("nhom06-65httt/data/raw"),
        help="Thư mục RawStorage đích",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ kiểm tra file, không lưu vào RawStorage",
    )
    args = parser.parse_args()

    if not args.incoming.exists():
        print(f"[ERROR] Thư mục không tồn tại: {args.incoming}")
        sys.exit(1)

    importer = GoogleTrendsCsvImporter(
        incoming_dir=args.incoming,
        raw_dir=args.raw,
        dry_run=args.dry_run,
    )
    results = importer.run()

    # Exit code non-zero nếu có error
    if any(r["status"] == "error" for r in results):
        sys.exit(2)


if __name__ == "__main__":
    main()
