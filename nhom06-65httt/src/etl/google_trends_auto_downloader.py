"""Automated downloader for Google Trends G1 CSV files and RawStorage ingestion.

Fetches real Google Trends data for the 6 configured G1 markets (VN, US, JP, DE, FR, IN)
and 5 G1 keywords (ceramic, ceramics, pottery, porcelain, stoneware) via Google Trends'
explore and widgetdata endpoints, formats them according to the G1 CSV contract,
writes them to ``data/incoming/google_trends/``, and imports them into
``data/raw/google_trends/`` using ``GoogleTrendsCsvImporter``.
"""

from __future__ import annotations

import argparse
import csv
import http.cookiejar
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from etl.google_trends_csv_importer import (  # noqa: E402
    G1_GEOS,
    G1_KEYWORDS,
    GoogleTrendsCsvImporter,
    _infer_period,
)

_TRENDS_BASE_URL = "https://trends.google.com"
_EXPLORE_URL = f"{_TRENDS_BASE_URL}/trends/api/explore"
_MULTILINE_URL = f"{_TRENDS_BASE_URL}/trends/api/widgetdata/multiline"
_COMPAREDGEO_URL = f"{_TRENDS_BASE_URL}/trends/api/widgetdata/comparedgeo"
_RELATED_URL = f"{_TRENDS_BASE_URL}/trends/api/widgetdata/relatedsearches"
_JSON_PREFIX = ")]}',\n"


def _strip_xssi_prefix(raw_text: str) -> str:
    text = raw_text.lstrip()
    if text.startswith(")]}'"):
        newline_idx = text.find("\n")
        if newline_idx != -1:
            return text[newline_idx + 1 :]
    return text


def _format_csv_lines(rows: Sequence[Sequence[Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


class GoogleTrendsAutoDownloader:
    """Download real Google Trends G1 datasets and write G1-compliant CSV files."""

    def __init__(
        self,
        incoming_dir: Path,
        export_date: Optional[date] = None,
        hl: str = "en-US",
        tz_offset_minutes: int = -420,
        request_delay_seconds: float = 1.2,
        max_retries: int = 4,
    ) -> None:
        self.incoming_dir = Path(incoming_dir)
        self.export_date = export_date or datetime.now(timezone.utc).date()
        self.date_str = self.export_date.strftime("%Y%m%d")
        self.hl = hl
        self.tz = tz_offset_minutes
        self.delay = request_delay_seconds
        self.max_retries = max_retries
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie_jar)
        )
        self._opener.addheaders = [
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36",
            ),
            ("Accept", "application/json, text/plain, */*"),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Referer", "https://trends.google.com/trends/explore"),
        ]

    def _warm_cookies(self, geo: str = "US") -> None:
        url = f"{_TRENDS_BASE_URL}/trends/?geo={urllib.parse.quote(geo)}"
        try:
            with self._opener.open(url, timeout=20) as resp:
                resp.read()
        except Exception:
            pass

    def _get_json(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = urllib.parse.urlencode(params)
        full_url = f"{url}?{query}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                with self._opener.open(full_url, timeout=25) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(_strip_xssi_prefix(raw))
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 429:
                    wait_s = self.delay * (2 ** attempt)
                    print(f"  [RETRY] HTTP 429 rate limit, sleeping {wait_s:.1f}s...")
                    self._warm_cookies()
                    time.sleep(wait_s)
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                wait_s = self.delay * attempt
                time.sleep(wait_s)

        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_exc}")

    def download_all(
        self,
        geos: Sequence[str] = G1_GEOS,
        keywords: Sequence[str] = G1_KEYWORDS,
    ) -> List[Path]:
        """Download G1 CSVs for all selected geos and return written file paths."""
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self._warm_cookies()
        written_files: List[Path] = []

        for geo in geos:
            print(f"\n=== Downloading Google Trends G1 for market: {geo} ===")
            geo_files = self.download_market(geo, tuple(keywords))
            written_files.extend(geo_files)
            time.sleep(self.delay)

        return written_files

    def download_market(
        self,
        geo: str,
        keywords: Tuple[str, ...] = G1_KEYWORDS,
    ) -> List[Path]:
        """Fetch 5-keyword compare and per-keyword related widgets for one market."""
        written: List[Path] = []
        explore_req = {
            "comparisonItem": [
                {"keyword": kw, "geo": geo, "time": "today 5-y"}
                for kw in keywords
            ],
            "category": 0,
            "property": "",
        }
        explore_data = self._get_json(
            _EXPLORE_URL,
            {
                "hl": self.hl,
                "tz": str(self.tz),
                "req": json.dumps(explore_req, separators=(",", ":")),
            },
        )
        widgets = explore_data.get("widgets", [])
        time.sleep(self.delay)

        for widget in widgets:
            wid = str(widget.get("id") or "")
            token = widget.get("token")
            wreq = widget.get("request")
            if not token or not isinstance(wreq, dict):
                continue

            if wid == "TIMESERIES":
                path = self._fetch_and_write_interest_over_time(
                    geo, keywords, token, wreq
                )
                if path is not None:
                    written.append(path)
                time.sleep(self.delay)

            elif wid == "GEO_MAP":
                path = self._fetch_and_write_interest_by_region(
                    geo, keywords, token, wreq
                )
                if path is not None:
                    written.append(path)
                time.sleep(self.delay)

            elif wid.startswith("RELATED_QUERIES"):
                idx = self._extract_widget_index(wid)
                if idx is not None and 0 <= idx < len(keywords):
                    kw = keywords[idx]
                    paths = self._fetch_and_write_related(
                        geo, kw, "queries", token, wreq
                    )
                    written.extend(paths)
                    time.sleep(self.delay)

            elif wid.startswith("RELATED_TOPICS"):
                idx = self._extract_widget_index(wid)
                if idx is not None and 0 <= idx < len(keywords):
                    kw = keywords[idx]
                    paths = self._fetch_and_write_related(
                        geo, kw, "topics", token, wreq
                    )
                    written.extend(paths)
                    time.sleep(self.delay)

        return written

    @staticmethod
    def _extract_widget_index(widget_id: str) -> Optional[int]:
        parts = widget_id.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return int(parts[1])
        return 0

    def _fetch_and_write_interest_over_time(
        self,
        geo: str,
        keywords: Tuple[str, ...],
        token: str,
        wreq: Dict[str, Any],
    ) -> Optional[Path]:
        data = self._get_json(
            _MULTILINE_URL,
            {
                "hl": self.hl,
                "tz": str(self.tz),
                "req": json.dumps(wreq, separators=(",", ":")),
                "token": token,
            },
        )
        timeline = data.get("default", {}).get("timelineData", [])
        if not timeline:
            print(f"  [WARN] No timelineData for {geo}")
            return None

        period_start, period_end = _infer_period(self.date_str)
        min_allowed_date = period_start - timedelta(days=7)

        rows: List[List[Any]] = [
            ["Interest over time"],
            ["Week", *keywords],
        ]
        data_row_count = 0
        for point in timeline:
            ts = point.get("time")
            values = point.get("value")
            if ts is None or not isinstance(values, list) or len(values) != len(keywords):
                continue
            dt = datetime.fromtimestamp(int(ts), timezone.utc).date()
            if dt < min_allowed_date or dt > period_end:
                continue
            rows.append([dt.isoformat(), *(str(int(v)) for v in values)])
            data_row_count += 1

        if data_row_count == 0:
            return None

        filename = f"g1_{geo}_compare5_interest_over_time_{self.date_str}.csv"
        path = self.incoming_dir / filename
        path.write_bytes(_format_csv_lines(rows))
        print(f"  [SAVED] {filename} ({data_row_count} weekly rows)")
        return path

    def _fetch_and_write_interest_by_region(
        self,
        geo: str,
        keywords: Tuple[str, ...],
        token: str,
        wreq: Dict[str, Any],
    ) -> Optional[Path]:
        data = self._get_json(
            _COMPAREDGEO_URL,
            {
                "hl": self.hl,
                "tz": str(self.tz),
                "req": json.dumps(wreq, separators=(",", ":")),
                "token": token,
            },
        )
        geo_map = data.get("default", {}).get("geoMapData", [])
        if not geo_map:
            print(f"  [WARN] No geoMapData for {geo}")
            return None

        rows: List[List[Any]] = [
            ["Interest by region"],
            ["Region", *keywords],
        ]
        data_row_count = 0
        for entry in geo_map:
            region_name = str(entry.get("geoName") or "").strip()
            values = entry.get("value")
            if not region_name or not isinstance(values, list) or len(values) != len(keywords):
                continue
            rows.append([region_name, *(str(int(v)) for v in values)])
            data_row_count += 1

        if data_row_count == 0:
            return None

        filename = f"g1_{geo}_compare5_interest_by_region_{self.date_str}.csv"
        path = self.incoming_dir / filename
        path.write_bytes(_format_csv_lines(rows))
        print(f"  [SAVED] {filename} ({data_row_count} regions)")
        return path

    def _fetch_and_write_related(
        self,
        geo: str,
        keyword: str,
        kind: str,
        token: str,
        wreq: Dict[str, Any],
    ) -> List[Path]:
        data = self._get_json(
            _RELATED_URL,
            {
                "hl": self.hl,
                "tz": str(self.tz),
                "req": json.dumps(wreq, separators=(",", ":")),
                "token": token,
            },
        )
        ranked_lists = data.get("default", {}).get("rankedList", [])
        if not isinstance(ranked_lists, list) or not ranked_lists:
            return []

        section_map = [
            ("top", ranked_lists[0] if len(ranked_lists) > 0 else {}),
            ("rising", ranked_lists[1] if len(ranked_lists) > 1 else {}),
        ]
        written: List[Path] = []

        for section, container in section_map:
            items = container.get("rankedKeyword", []) if isinstance(container, dict) else []
            if not isinstance(items, list) or not items:
                continue

            rows: List[List[Any]] = [
                [f"Related {kind}"],
                [section.title(), keyword],
            ]
            item_count = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                if kind == "queries":
                    label = str(item.get("query") or "").strip()
                else:
                    topic_obj = item.get("topic")
                    label = (
                        str(topic_obj.get("title") or "").strip()
                        if isinstance(topic_obj, dict)
                        else str(item.get("title") or "").strip()
                    )
                if not label:
                    continue

                formatted_val = str(item.get("formattedValue") or "").strip()
                raw_val = item.get("value")
                if formatted_val.casefold() == "breakout":
                    val_str = "Breakout"
                elif raw_val is not None:
                    val_str = str(raw_val)
                elif formatted_val:
                    val_str = formatted_val
                else:
                    continue

                rows.append([label, val_str])
                item_count += 1

            if item_count == 0:
                continue

            filename = f"g1_{geo}_{keyword}_related_{kind}_{section}_{self.date_str}.csv"
            path = self.incoming_dir / filename
            path.write_bytes(_format_csv_lines(rows))
            print(f"  [SAVED] {filename} ({item_count} {section} {kind})")
            written.append(path)

        return written


def main() -> int:
    default_data_root = Path(__file__).resolve().parents[2] / "data"
    parser = argparse.ArgumentParser(
        description="Automatically download Google Trends G1 CSVs and import into data/raw/google_trends."
    )
    parser.add_argument(
        "--incoming",
        type=Path,
        default=default_data_root / "incoming" / "google_trends",
        help="Target directory for downloaded G1 CSV files",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=default_data_root / "raw",
        help="RawStorage root directory",
    )
    parser.add_argument(
        "--geo",
        action="append",
        dest="geos",
        choices=G1_GEOS,
        help="Market code(s) to download (defaults to all 6: VN, US, JP, DE, FR, IN)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Export date in YYYYMMDD format (defaults to today UTC)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between Google Trends API requests",
    )
    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Only download CSVs into incoming directory without importing into data/raw",
    )
    parser.add_argument(
        "--dry-run-import",
        action="store_true",
        help="Run GoogleTrendsCsvImporter in --dry-run mode after downloading",
    )
    args = parser.parse_args()

    export_date = (
        datetime.strptime(args.date, "%Y%m%d").date()
        if args.date
        else datetime.now(timezone.utc).date()
    )
    selected_geos = tuple(args.geos) if args.geos else G1_GEOS

    downloader = GoogleTrendsAutoDownloader(
        incoming_dir=args.incoming,
        export_date=export_date,
        request_delay_seconds=args.delay,
    )
    files = downloader.download_all(geos=selected_geos)
    print(f"\nDownloaded {len(files)} Google Trends G1 CSV files to {args.incoming}")

    if args.no_import:
        return 0

    importer = GoogleTrendsCsvImporter(
        incoming_dir=args.incoming,
        raw_dir=args.raw,
        dry_run=args.dry_run_import,
    )
    results = importer.run()
    if any(r["status"] == "rejected" for r in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
