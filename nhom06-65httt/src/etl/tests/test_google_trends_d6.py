"""Unit tests for D6 using synthetic Google Trends-shaped CSV fixtures only.

These fixtures are not real collected Google Trends data.

Phạm vi test:
- Import CSV fixtures (Interest Over Time, by Region, Related Queries, Related Topics).
- Giá trị Breakout trong Related Queries/Topics – phải giữ nguyên là chuỗi.
- Giá trị 0 không bị bỏ hoặc thay thế.
- Chống thu thập trùng lặp theo SHA-256.
- Encoding UTF-8-BOM (phổ biến khi dùng Excel).
- Header không có period column → fallback.
- Nhiều section trong 1 file (Related Queries: Top + Rising).
- RawStorage payload + manifest kiểm tra đầy đủ.
- GoogleTrendsCsvImporter: skip bad filename, skip empty, skip duplicate.
"""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from etl.google_trends_collector import (
    GoogleTrendsExportAdapter,
    GoogleTrendsRequest,
    TrendsDataType,
)
from etl.google_trends_csv_importer import (
    G1_GEOS,
    G1_KEYWORDS,
    GoogleTrendsCsvImporter,
    _parse_filename,
    _build_request,
    _infer_cadence,
    _infer_period,
    _sha256_hex,
)
from etl.normalizer import NormalizationStatus, normalize_trends_row
from etl.raw_storage import CollectionStatus, RawStorage
from etl.source_registry import create_project_source_registry
from etl.trends_parser import GoogleTrendsParser

FIXTURES = Path(__file__).parent / "fixtures"
IOT_FIXTURE = FIXTURES / "gt_interest_over_time_fixture.csv"
IBR_FIXTURE = FIXTURES / "gt_interest_by_region_fixture.csv"
RQ_FIXTURE = FIXTURES / "gt_related_queries_fixture.csv"
RT_FIXTURE = FIXTURES / "gt_related_topics_fixture.csv"

CID = "d6test" + "0" * 26


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_and_storage(raw_dir: Path):
    reg = create_project_source_registry()
    storage = RawStorage(raw_dir, reg)
    return reg, storage


def _make_iot_request(geo: str = "VN") -> GoogleTrendsRequest:
    return GoogleTrendsRequest(
        keywords=("ceramic tableware", "porcelain tableware", "stoneware"),
        period_start=date(2021, 1, 1),
        period_end=date(2026, 11, 20),
        geo=geo,
        data_type=TrendsDataType.INTEREST_OVER_TIME,
        search_type="web",
        interval="weekly",
    )


def _make_rq_request(geo: str = "VN") -> GoogleTrendsRequest:
    return GoogleTrendsRequest(
        keywords=("ceramic tableware",),
        period_start=date(2021, 1, 1),
        period_end=date(2026, 11, 20),
        geo=geo,
        data_type=TrendsDataType.RELATED_QUERIES,
        search_type="web",
    )


# ---------------------------------------------------------------------------
# Bộ 1 – Parser: Interest Over Time fixture thực tế hơn
# ---------------------------------------------------------------------------


class InterestOverTimeParserTests(unittest.TestCase):
    """Parser nhận diện đúng Interest Over Time với metadata header."""

    def setUp(self):
        self.parser = GoogleTrendsParser()

    def test_parses_iot_fixture_row_count(self):
        payload = IOT_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 10)

    def test_iot_data_type_hint(self):
        payload = IOT_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)
        self.assertIsNotNone(result.data_type_hint)
        self.assertIn("Interest over time", result.data_type_hint)

    def test_iot_keywords_extracted(self):
        result = self.parser.parse(IOT_FIXTURE.read_bytes(), CID)
        self.assertIn("ceramic tableware", result.keywords)
        self.assertIn("porcelain tableware", result.keywords)
        self.assertIn("stoneware", result.keywords)

    def test_iot_values_are_strings_not_ints(self):
        result = self.parser.parse(IOT_FIXTURE.read_bytes(), CID)
        for row in result.rows:
            for _kw, val in row.keyword_values:
                self.assertIsInstance(val, str, f"Value should be str, got {type(val)}: {val!r}")

    def test_iot_value_100_preserved_as_string(self):
        result = self.parser.parse(IOT_FIXTURE.read_bytes(), CID)
        # Row với period_label "2022-01-02" có ceramic tableware=100
        rows_by_period = {r.period_label: r for r in result.rows}
        row = rows_by_period["2022-01-02"]
        kv = dict(row.keyword_values)
        self.assertEqual(kv["ceramic tableware"], "100")

    def test_iot_value_0_not_dropped(self):
        """Giá trị 0 không có nghĩa là không có dữ liệu – phải giữ nguyên."""
        csv_bytes = b"Interest over time\nWeek,ceramic vase\n2025-01-05,0\n2025-01-12,5\n"
        result = self.parser.parse(csv_bytes, CID)
        self.assertEqual(result.row_count, 2)
        kv0 = dict(result.rows[0].keyword_values)
        self.assertEqual(kv0["ceramic vase"], "0")

    def test_header_only_compare_infers_interest_over_time(self):
        payload = b"Time,ceramic,ceramics,pottery,porcelain,stoneware\n2021-11-28,1,2,3,4,5\n"
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.data_type_hint, "Interest over time")


# ---------------------------------------------------------------------------
# Bộ 2 – Parser: Interest by Region
# ---------------------------------------------------------------------------


class InterestByRegionParserTests(unittest.TestCase):
    """Parser nhận diện Interest by Region CSV (không có cột Week/Day/Month)."""

    def setUp(self):
        self.parser = GoogleTrendsParser()

    def test_ibr_fallback_to_first_column_as_period(self):
        """Interest by Region uses Region as its row dimension."""
        payload = IBR_FIXTURE.read_bytes()
        result = self.parser.parse(payload, CID)
        # Data_type_hint là "Interest by region"
        self.assertIn("region", (result.data_type_hint or "").lower())
        # 6 vùng/quốc gia
        self.assertEqual(result.row_count, 6)

    def test_ibr_region_names_as_period_labels(self):
        result = self.parser.parse(IBR_FIXTURE.read_bytes(), CID)
        periods = [r.period_label for r in result.rows]
        self.assertIn("Vietnam", periods)
        self.assertIn("Japan", periods)

    def test_ibr_values_preserved_as_strings(self):
        result = self.parser.parse(IBR_FIXTURE.read_bytes(), CID)
        for row in result.rows:
            for _kw, val in row.keyword_values:
                self.assertIsInstance(val, str)

    def test_ibr_vietnam_has_value_100(self):
        result = self.parser.parse(IBR_FIXTURE.read_bytes(), CID)
        vn_rows = [r for r in result.rows if r.period_label == "Vietnam"]
        self.assertEqual(len(vn_rows), 1)
        kv = dict(vn_rows[0].keyword_values)
        self.assertEqual(kv["ceramic tableware"], "100")


# ---------------------------------------------------------------------------
# Bộ 3 – Parser: Related Queries với Breakout
# ---------------------------------------------------------------------------


class RelatedQueriesParserTests(unittest.TestCase):
    """Related Queries có thể có Top/Rising sections và giá trị Breakout."""

    def setUp(self):
        self.parser = GoogleTrendsParser()

    def test_related_queries_fixture_parsed(self):
        result = self.parser.parse(RQ_FIXTURE.read_bytes(), CID)
        # 10 rows (5 Top + 5 Rising)
        self.assertGreater(result.row_count, 0)

    def test_breakout_value_kept_as_string(self):
        """'Breakout' phải được giữ nguyên là chuỗi, không chuyển thành số."""
        csv_bytes = (
            b"Related queries\n"
            b"Top,ceramic tableware\n"
            b"ceramic bowl set,100\n"
            b"Rising,ceramic tableware\n"
            b"ceramic tableware aesthetic,Breakout\n"
            b"ceramic tableware green,350\n"
        )
        result = self.parser.parse(csv_bytes, CID)
        # Tìm row có "Breakout"
        breakout_rows = [
            r for r in result.rows
            if any(v == "Breakout" for _, v in r.keyword_values)
        ]
        self.assertEqual(len(breakout_rows), 1)
        kv = dict(breakout_rows[0].keyword_values)
        self.assertEqual(kv["ceramic tableware"], "Breakout")
        self.assertEqual(breakout_rows[0].raw_row["section"], "Rising")
        self.assertEqual(breakout_rows[0].related_section, "rising")
        self.assertEqual(breakout_rows[0].source_keyword, "ceramic tableware")

    def test_rising_numeric_value_kept_as_string(self):
        """Rising value như 350 phải là str, không phải int."""
        csv_bytes = (
            b"Related queries\n"
            b"Top,kw\nterm_a,100\n"
            b"Rising,kw\nterm_b,350\n"
        )
        result = self.parser.parse(csv_bytes, CID)
        rising_rows = [r for r in result.rows if r.period_label == "term_b"]
        if rising_rows:
            kv = dict(rising_rows[0].keyword_values)
            self.assertIsInstance(kv["kw"], str)
            self.assertEqual(kv["kw"], "350")

    def test_native_related_queries_header_keeps_zero_and_breakout(self):
        payload = (
            b"Related queries\n"
            b"Top\n"
            b"query,value\n"
            b"ceramic bowl set,0\n"
            b"Rising\n"
            b"query,value\n"
            b"handmade ceramic,Breakout\n"
        )
        result = self.parser.parse(payload, CID)
        values = {row.period_label: dict(row.keyword_values)["value"] for row in result.rows}
        self.assertEqual(values["ceramic bowl set"], "0")
        self.assertEqual(values["handmade ceramic"], "Breakout")
        self.assertEqual(result.rows[0].raw_row["section"], "Top")
        self.assertEqual(result.rows[0].related_section, "top")
        self.assertEqual(result.rows[1].related_section, "rising")

    def test_sectioned_related_table_preserves_all_percentage_columns(self):
        payload = (
            b"Related queries\n"
            b"Top,ceramic\n"
            b"query,search interest,increase percent\n"
            b"ceramic bowl,100,0%\n"
        )
        result = self.parser.parse(payload, CID)
        self.assertEqual(
            result.rows[0].keyword_values,
            (("search interest", "100"), ("increase percent", "0%")),
        )
        self.assertEqual(result.rows[0].raw_row["increase percent"], "0%")

    def test_related_queries_data_type_hint(self):
        result = self.parser.parse(RQ_FIXTURE.read_bytes(), CID)
        self.assertIn("Related queries", result.data_type_hint or "")

    def test_flat_related_queries_export_keeps_all_columns(self):
        payload = (
            b"query,search interest,increase percent\n"
            b"ceramic bowl set,100,0\n"
            b"handmade ceramic,Breakout,250\n"
        )
        result = self.parser.parse(payload, CID)

        self.assertEqual(result.data_type_hint, "Related queries")
        self.assertEqual(result.row_count, 2)
        row = result.rows[1]
        self.assertEqual(row.period_label, "handmade ceramic")
        self.assertEqual(
            row.keyword_values,
            (("search interest", "Breakout"), ("increase percent", "250")),
        )
        self.assertEqual(row.raw_row["query"], "handmade ceramic")


# ---------------------------------------------------------------------------
# Bộ 4 – Parser: Related Topics
# ---------------------------------------------------------------------------


class RelatedTopicsParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = GoogleTrendsParser()

    def test_related_topics_fixture_parsed(self):
        result = self.parser.parse(RT_FIXTURE.read_bytes(), CID)
        self.assertGreater(result.row_count, 0)

    def test_topics_breakout_preserved(self):
        result = self.parser.parse(RT_FIXTURE.read_bytes(), CID)
        breakout_rows = [
            r for r in result.rows
            if any(v == "Breakout" for _, v in r.keyword_values)
        ]
        self.assertGreater(len(breakout_rows), 0)

    def test_related_topics_data_type_hint(self):
        result = self.parser.parse(RT_FIXTURE.read_bytes(), CID)
        self.assertIn("Related topics", result.data_type_hint or "")

    def test_flat_related_topics_export_keeps_all_columns(self):
        payload = (
            b"topic,search interest,increase percent\n"
            b"home decor,100,0\n"
            b"ceramic art,Breakout,300\n"
        )
        result = self.parser.parse(payload, CID)

        self.assertEqual(result.data_type_hint, "Related topics")
        self.assertEqual(result.row_count, 2)
        row = result.rows[1]
        self.assertEqual(row.period_label, "ceramic art")
        self.assertEqual(
            row.keyword_values,
            (("search interest", "Breakout"), ("increase percent", "300")),
        )
        self.assertEqual(row.raw_row["topic"], "ceramic art")


class RelatedSectionMetadataTests(unittest.TestCase):
    def test_metadata_section_is_attached_without_mutating_raw_row(self):
        cases = (
            (b"query,search interest,increase percent\nterm,10,20\n", "top"),
            (b"query,search interest,increase percent\nterm,10,Breakout\n", "rising"),
            (b"topic,search interest,increase percent\nterm,10,20\n", "top"),
            (b"topic,search interest,increase percent\nterm,10,Breakout\n", "rising"),
        )
        parser = GoogleTrendsParser()

        for payload, section in cases:
            with self.subTest(section=section, header=payload.split(b",", 1)[0]):
                result = parser.parse(payload, CID, related_section=section)
                self.assertEqual(result.row_count, 1)
                self.assertEqual(result.rows[0].related_section, section)
                self.assertNotIn("section", result.rows[0].raw_row)

    def test_legacy_parser_call_keeps_related_section_optional(self):
        payload = b"query,search interest,increase percent\nterm,10,20\n"
        result = GoogleTrendsParser().parse(payload, CID)
        self.assertIsNone(result.rows[0].related_section)


class CadenceInferenceTests(unittest.TestCase):
    def test_monthly_dates_are_recognized(self):
        self.assertEqual(
            _infer_cadence(("2021-11-01", "2021-12-01", "2022-01-01")),
            "monthly",
        )

    def test_weekly_dates_are_recognized(self):
        self.assertEqual(
            _infer_cadence(("2026-10-25", "2026-11-01", "2026-11-08")),
            "weekly",
        )

    def test_irregular_dates_remain_unknown(self):
        self.assertIsNone(
            _infer_cadence(("2026-10-25", "2026-11-01", "2026-11-15"))
        )


# ---------------------------------------------------------------------------
# Bộ 5 – Parser: Encoding và header bất thường
# ---------------------------------------------------------------------------


class EncodingAndHeaderTests(unittest.TestCase):
    def setUp(self):
        self.parser = GoogleTrendsParser()

    def test_utf8_bom_decoded_correctly(self):
        """Google Trends có thể xuất UTF-8-BOM (EF BB BF) – phải đọc được."""
        bom = b"\xef\xbb\xbf"
        payload = bom + b"Week,ceramic vase\n2025-01-05,55\n"
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 1)
        self.assertIn("ceramic vase", result.keywords)
        self.assertEqual(result.rows[0].period_label, "2025-01-05")

    def test_windows_crlf_line_endings(self):
        """CSV với CRLF (\\r\\n) phải parse được."""
        payload = b"Week,pottery\r\n2025-01-05,70\r\n2025-01-12,80\r\n"
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 2)

    def test_mixed_case_period_column(self):
        """Cột 'week' (lowercase) phải nhận diện được."""
        payload = b"week,kw_a\n2025-01-05,55\n"
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.rows[0].period_label, "2025-01-05")

    def test_extra_blank_lines_before_header(self):
        """Dòng trắng trước header phải bị bỏ qua."""
        payload = b"\n\nInterest over time\n\nWeek,pottery\n2025-01-05,65\n"
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 1)

    def test_vietnamese_keyword_in_header(self):
        """Từ khóa tiếng Việt trong cột header phải được đọc đúng."""
        payload = "Week,gốm sứ Bát Tràng,bình hoa gốm sứ\n2025-01-05,80,60\n".encode("utf-8")
        result = self.parser.parse(payload, CID)
        self.assertEqual(result.row_count, 1)
        self.assertIn("gốm sứ Bát Tràng", result.keywords)


# ---------------------------------------------------------------------------
# Bộ 6 – Adapter: RawStorage + SHA-256 + manifest
# ---------------------------------------------------------------------------


class AdapterRawStorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.reg, self.storage = _make_registry_and_storage(self.root / "raw")
        self.adapter = GoogleTrendsExportAdapter(self.storage, self.reg)

    def tearDown(self):
        self._tmp.cleanup()

    def test_iot_csv_stored_with_sha256_and_manifest(self):
        payload = IOT_FIXTURE.read_bytes()
        request = _make_iot_request("US")
        collection_id = self.adapter.ingest(payload, request)

        stored = self.storage.read_payload("google_trends", collection_id)
        self.assertEqual(stored, payload)

        manifest = self.storage.read_manifest("google_trends", collection_id)
        meta = manifest["metadata"]
        self.assertEqual(meta["source_id"], "google_trends")
        self.assertEqual(meta["data_format"], "csv")
        self.assertEqual(meta["status"], "success")
        self.assertEqual(meta["checksum"]["algorithm"], "sha256")
        # SHA-256 khớp
        import hashlib
        expected_sha = hashlib.sha256(payload).hexdigest()
        self.assertEqual(meta["checksum"]["value"], expected_sha)

    def test_related_queries_manifest_scale_not_assumed(self):
        payload = RQ_FIXTURE.read_bytes()
        request = _make_rq_request("VN")
        collection_id = self.adapter.ingest(payload, request)
        manifest = self.storage.read_manifest("google_trends", collection_id)
        semantics = manifest["metadata"]["request_parameters"]["value_semantics"]
        self.assertEqual(semantics["scale"], "not_assumed")

    def test_iot_manifest_scale_0_to_100(self):
        payload = IOT_FIXTURE.read_bytes()
        request = _make_iot_request("JP")
        collection_id = self.adapter.ingest(payload, request)
        manifest = self.storage.read_manifest("google_trends", collection_id)
        semantics = manifest["metadata"]["request_parameters"]["value_semantics"]
        self.assertIn("0-100", semantics["scale"])

    def test_different_geo_produces_different_collection_ids(self):
        payload = IOT_FIXTURE.read_bytes()
        cid_vn = self.adapter.ingest(payload, _make_iot_request("VN"))
        cid_us = self.adapter.ingest(payload, _make_iot_request("US"))
        # Mỗi lần ingest tạo collection mới (kể cả cùng payload)
        self.assertNotEqual(cid_vn, cid_us)

    def test_attribution_text_in_manifest(self):
        payload = IOT_FIXTURE.read_bytes()
        cid = self.adapter.ingest(payload, _make_iot_request("DE"))
        manifest = self.storage.read_manifest("google_trends", cid)
        self.assertIn("Google Trends", manifest["metadata"]["request_parameters"]["attribution_text"])


# ---------------------------------------------------------------------------
# G1 importer: strict filenames, five-keyword compare exports, provenance.
# ---------------------------------------------------------------------------


def _compare_payload(dimension="Week", values=("100", "0", "50", "25", "10")):
    title = "Interest by region" if dimension == "Region" else "Interest over time"
    first = (
        "Vietnam"
        if dimension == "Region"
        else "2021-11-28"
    )
    second = "Japan" if dimension == "Region" else "2021-12-05"
    headers = ",".join(G1_KEYWORDS)
    return (
        f"{title}\n{dimension},{headers}\n"
        f"{first},{','.join(values)}\n{second},{','.join(values)}\n"
    ).encode("utf-8")


def _related_payload(kind, section, keyword):
    label = f"{keyword} {'ceramic bowls' if kind == 'queries' else 'ceramic art'}"
    value = "Breakout" if section == "rising" else "0"
    return (
        f"Related {kind}\n{section.title()},{keyword}\n"
        f"{label},{value}\n"
    ).encode("utf-8")


class FilenameParsingTests(unittest.TestCase):
    def test_exact_g1_conventions_are_accepted_for_six_markets(self):
        for geo in G1_GEOS:
            examples = (
                (f"g1_{geo}_compare5_interest_over_time_20261127.csv", "interest_over_time"),
                (f"g1_{geo}_compare5_interest_by_region_20261127.csv", "interest_by_region"),
                (f"g1_{geo}_ceramic_related_queries_top_20261127.csv", "related_queries_top"),
                (f"g1_{geo}_stoneware_related_topics_rising_20261127.csv", "related_topics_rising"),
            )
            for filename, expected_type in examples:
                with self.subTest(filename=filename):
                    result = _parse_filename(filename)
                    self.assertEqual(result, ("g1", geo, expected_type, "20261127"))

    def test_non_g1_country_keyword_or_invalid_date_is_rejected(self):
        for filename in (
            "g2_VN_compare5_interest_over_time_20261127.csv",
            "g1_BR_compare5_interest_over_time_20261127.csv",
            "g1_VN_ceramicware_related_topics_top_20261127.csv",
            "g1_VN_compare5_interest_over_time_20260230.csv",
            "g1_VN_interest_over_time_20261127.csv",
        ):
            with self.subTest(filename=filename):
                self.assertIsNone(_parse_filename(filename))

    def test_build_request_uses_exact_five_keyword_configuration(self):
        for geo in G1_GEOS:
            request = _build_request("g1", geo, "interest_over_time", "20261127")
            self.assertEqual(request.keywords, G1_KEYWORDS)
            self.assertEqual(request.geo, geo)
            self.assertEqual(request.search_type, "web")
            self.assertEqual(request.category, "All categories")
            self.assertEqual(request.group_id, "g1")
            self.assertIsNone(request.interval)
        self.assertIsNone(_build_request("g1", "BR", "interest_over_time", "20261127"))

    def test_five_year_range_handles_leap_day(self):
        start, end = _infer_period("20240229")
        self.assertEqual(start, date(2019, 2, 28))
        self.assertEqual(end, date(2024, 2, 29))


class G1ImporterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.incoming = self.root / "incoming"
        self.incoming.mkdir()
        self.raw = self.root / "raw"

    def _place(self, filename, payload):
        path = self.incoming / filename
        path.write_bytes(payload)
        return path

    def _importer(self, dry_run=False):
        return GoogleTrendsCsvImporter(self.incoming, self.raw, dry_run=dry_run)

    def _request_for(self, result):
        storage = RawStorage(self.raw, create_project_source_registry())
        manifest = storage.read_manifest("google_trends", result["collection_id"])
        return storage, manifest, manifest["metadata"]["request_parameters"]

    def test_compare_files_preserve_all_five_independent_keyword_values_and_metadata(self):
        filename = "g1_VN_compare5_interest_over_time_20261127.csv"
        payload = _compare_payload()
        self._place(filename, payload)

        result = self._importer().run()[0]

        self.assertEqual(result["status"], "imported")
        storage, manifest, request = self._request_for(result)
        self.assertEqual(storage.read_payload("google_trends", result["collection_id"]), payload)
        self.assertEqual(request["group_id"], "g1")
        self.assertEqual(request["keywords"], list(G1_KEYWORDS))
        self.assertEqual(request["geo"], "VN")
        self.assertEqual(request["period_start"], "2021-11-27")
        self.assertEqual(request["period_end"], "2026-11-27")
        self.assertEqual(request["data_type"], "interest_over_time")
        self.assertEqual(request["interval"], "weekly")
        self.assertEqual(request["category"], "All categories")
        self.assertEqual(request["search_type_label"], "Web Search")
        self.assertEqual(request["original_filename"], filename)
        self.assertEqual(request["filename"], filename)
        self.assertEqual(request["source"], "Google Trends")
        self.assertEqual(request["source_type"], "manual")
        self.assertEqual(
            request["time_range"],
            {"start": "2021-11-27", "end": "2026-11-27", "label": "Past 5 years"},
        )
        self.assertEqual(request["sha256"], _sha256_hex(payload))
        self.assertEqual(manifest["metadata"]["checksum"]["value"], _sha256_hex(payload))
        parsed = GoogleTrendsParser().parse(payload, result["collection_id"])
        self.assertEqual(dict(parsed.rows[0].keyword_values), dict(zip(G1_KEYWORDS, ("100", "0", "50", "25", "10"))))

    def test_importer_stores_non_vietnam_market_metadata(self):
        filename = "g1_US_compare5_interest_over_time_20261127.csv"
        self._place(filename, _compare_payload())

        result = self._importer().run()[0]

        self.assertEqual(result["status"], "imported")
        _, _, request = self._request_for(result)
        self.assertEqual(request["geo"], "US")
        self.assertEqual(request["geo_name"], "United States")
        self.assertEqual(request["keywords"], list(G1_KEYWORDS))

    def test_region_compare_has_region_dimension_not_a_date(self):
        payload = _compare_payload("Region")
        filename = "g1_VN_compare5_interest_by_region_20261127.csv"
        self._place(filename, payload)
        result = self._importer().run()[0]
        self.assertEqual(result["status"], "imported")

        parsed = GoogleTrendsParser().parse(payload, result["collection_id"])
        row = parsed.rows[0]
        self.assertEqual(row.period_label, "Vietnam")
        self.assertEqual(row.period_kind, "region")
        normalized = normalize_trends_row(row)
        self.assertEqual(normalized.period_label.value, "Vietnam")
        self.assertEqual(normalized.period_label.status, NormalizationStatus.CONFIRMED)

    def test_monthly_cadence_and_google_geo_suffixes_are_supported(self):
        columns = ", ".join(f"{word}: (Vietnam)" for word in G1_KEYWORDS)
        payload = (
            f"Interest over time\nMonth,{columns}\n"
            "2021-11-01,0,1,2,3,4\n"
            "2021-12-01,5,6,7,8,9\n"
            "2022-01-01,10,11,12,13,14\n"
        ).encode()
        self._place("g1_VN_compare5_interest_over_time_20261127.csv", payload)
        result = self._importer().run()[0]
        _, _, request = self._request_for(result)
        self.assertEqual(request["interval"], "monthly")
        self.assertEqual(request["keywords"], list(G1_KEYWORDS))

    def test_google_metadata_preamble_and_related_percentage_columns_are_supported(self):
        iot = (
            "Category: All categories\n"
            "All categories\n"
            "Interest over time\n"
            f"Week,{','.join(G1_KEYWORDS)}\n"
            "2021-11-28,1,2,3,4,5\n"
        ).encode()
        self._place("g1_VN_compare5_interest_over_time_20261127.csv", iot)
        iot_result = self._importer(dry_run=True).run()[0]
        self.assertEqual(iot_result["status"], "would_import")

        related = (
            b"Category: All categories\n"
            b"Related queries\n"
            b"query,search interest,increase percent\n"
            b"ceramic bowl,Breakout,250%\n"
        )
        parsed = GoogleTrendsParser().parse(
            related, CID, related_section="rising"
        )
        self.assertEqual(
            parsed.rows[0].keyword_values,
            (("search interest", "Breakout"), ("increase percent", "250%")),
        )
        self.assertEqual(parsed.data_type_hint, "Related queries")

    def test_all_related_kinds_and_sections_keep_keyword_breakout_and_zero(self):
        files = []
        for keyword in G1_KEYWORDS:
            for kind in ("queries", "topics"):
                for section in ("top", "rising"):
                    filename = (
                        f"g1_VN_{keyword}_related_{kind}_{section}_20261127.csv"
                    )
                    payload = _related_payload(kind, section, keyword)
                    files.append((filename, payload, keyword, kind, section))
                    self._place(filename, payload)

        results = self._importer().run()
        self.assertEqual(len(results), 20)
        self.assertTrue(all(result["status"] == "imported" for result in results))
        storage = RawStorage(self.raw, create_project_source_registry())
        for result in results:
            manifest = storage.read_manifest("google_trends", result["collection_id"])
            request = manifest["metadata"]["request_parameters"]
            _, _, keyword, kind, section = next(
                item for item in files if item[0] == result["file"]
            )
            self.assertEqual(request["keywords"], [keyword])
            self.assertEqual(request["keyword"], keyword)
            self.assertEqual(request["data_type"], f"related_{kind}")
            self.assertEqual(request["related_section"], section)
            parsed = GoogleTrendsParser().parse(
                storage.read_payload("google_trends", result["collection_id"]),
                result["collection_id"],
                related_section=section,
            )
            self.assertEqual(parsed.rows[0].related_section, section)
            self.assertEqual(parsed.rows[0].source_keyword, keyword)
            normalized = normalize_trends_row(parsed.rows[0])
            self.assertEqual(normalized.related_section, section)
            self.assertEqual(normalized.source_keyword, keyword)
            self.assertEqual(normalized.data_type_hint, f"Related {kind}")
            self.assertEqual(parsed.rows[0].keyword_values[0][1], "Breakout" if section == "rising" else "0")

    def test_exact_expected_filename_set_has_132_files(self):
        export_date = "20261127"
        names = set()
        for geo in G1_GEOS:
            names.update(
                f"g1_{geo}_compare5_interest_{chart}_{export_date}.csv"
                for chart in ("over_time", "by_region")
            )
            names.update(
                f"g1_{geo}_{keyword}_related_{kind}_{section}_{export_date}.csv"
                for keyword in G1_KEYWORDS
                for kind in ("queries", "topics")
                for section in ("top", "rising")
            )
        self.assertEqual(len(names), 132)

    def test_missing_keyword_column_wrong_header_and_mismatched_title_are_rejected(self):
        valid_header = ",".join(G1_KEYWORDS)
        cases = (
            (
                "g1_VN_compare5_interest_over_time_20261127.csv",
                f"Interest over time\nWeek,{','.join(G1_KEYWORDS[:-1])}\n2021-11-28,1,2,3,4\n".encode(),
            ),
            (
                "g1_VN_compare5_interest_over_time_20261127.csv",
                f"Interest over time\nDate,{valid_header}\n2021-11-28,1,2,3,4,5\n".encode(),
            ),
            (
                "g1_VN_compare5_interest_by_region_20261127.csv",
                f"Interest over time\nRegion,{valid_header}\nVietnam,1,2,3,4,5\n".encode(),
            ),
        )
        for filename, payload in cases:
            with self.subTest(filename=filename, payload=payload):
                self._place(filename, payload)
                result = self._importer(dry_run=True).run()[0]
                self.assertEqual(result["status"], "rejected")
                for existing in self.incoming.glob("*.csv"):
                    existing.unlink()

    def test_related_metadata_section_must_match_csv_content(self):
        payload = (
            b"Related queries\nTop,ceramic\nceramic bowl,100\n"
        )
        filename = "g1_VN_ceramic_related_queries_rising_20261127.csv"
        self._place(filename, payload)
        result = self._importer(dry_run=True).run()[0]
        self.assertEqual(result["status"], "rejected")

    def test_related_keyword_in_csv_must_match_filename(self):
        payload = b"Related topics\nTop,porcelain\nCeramic,100\n"
        filename = "g1_VN_stoneware_related_topics_top_20261127.csv"
        self._place(filename, payload)
        result = self._importer(dry_run=True).run()[0]
        self.assertEqual(result["status"], "rejected")

    def test_duplicate_sha256_is_skipped_even_when_filename_date_differs(self):
        payload = _compare_payload()
        self._place("g1_VN_compare5_interest_over_time_20261127.csv", payload)
        self._place("g1_VN_compare5_interest_over_time_20261128.csv", payload)
        results = self._importer().run()
        self.assertEqual([result["status"] for result in results], ["imported", "skipped_duplicate"])
        index = json.loads((self.incoming / ".imported_sha256_index.json").read_text())
        self.assertEqual(index, { _sha256_hex(payload): results[0]["collection_id"] })

    def test_dry_run_has_no_raw_or_index_side_effects(self):
        self._place(
            "g1_VN_compare5_interest_over_time_20261127.csv",
            _compare_payload(),
        )
        result = self._importer(dry_run=True).run()[0]
        self.assertEqual(result["status"], "would_import")
        self.assertFalse(self.raw.exists())
        self.assertFalse((self.incoming / ".imported_sha256_index.json").exists())

    def test_invalid_filename_and_empty_csv_are_rejected(self):
        self._place("not-a-g1-file.csv", b"Week,ceramic\n2021-11-28,1\n")
        self._place("g1_VN_compare5_interest_over_time_20261127.csv", b"")
        results = self._importer(dry_run=True).run()
        self.assertEqual([result["status"] for result in results], ["rejected", "rejected"])


# ---------------------------------------------------------------------------
# Bộ 8 – End-to-end: Ingest → Parse
# ---------------------------------------------------------------------------


class EndToEndIngestAndParseTests(unittest.TestCase):
    """Import 1 file thực tế vào RawStorage rồi parse lại từ payload."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.reg, self.storage = _make_registry_and_storage(self.root / "raw")
        self.adapter = GoogleTrendsExportAdapter(self.storage, self.reg)
        self.parser = GoogleTrendsParser()

    def tearDown(self):
        self._tmp.cleanup()

    def test_iot_round_trip_payload_matches(self):
        raw = IOT_FIXTURE.read_bytes()
        cid = self.adapter.ingest(raw, _make_iot_request("VN"))
        retrieved = self.storage.read_payload("google_trends", cid)
        self.assertEqual(retrieved, raw)

    def test_iot_round_trip_parse_gives_10_rows(self):
        raw = IOT_FIXTURE.read_bytes()
        cid = self.adapter.ingest(raw, _make_iot_request("VN"))
        retrieved = self.storage.read_payload("google_trends", cid)
        result = self.parser.parse(retrieved, cid, collected_at_iso="2026-11-20T00:00:00+00:00")
        self.assertEqual(result.row_count, 10)
        self.assertEqual(result.provenance.raw_collection_id, cid)

    def test_related_queries_round_trip_breakout_preserved(self):
        raw = RQ_FIXTURE.read_bytes()
        cid = self.adapter.ingest(raw, _make_rq_request("US"))
        retrieved = self.storage.read_payload("google_trends", cid)
        result = self.parser.parse(retrieved, cid)
        breakout_rows = [
            r for r in result.rows
            if any(v == "Breakout" for _, v in r.keyword_values)
        ]
        self.assertGreater(len(breakout_rows), 0)

    def test_ibr_round_trip_region_values_preserved(self):
        raw = IBR_FIXTURE.read_bytes()
        cid = self.adapter.ingest(raw, GoogleTrendsRequest(
            keywords=("ceramic tableware", "porcelain tableware"),
            period_start=date(2021, 1, 1),
            period_end=date(2026, 11, 20),
            geo="WORLD",
            data_type=TrendsDataType.INTEREST_BY_REGION,
            search_type="web",
        ))
        retrieved = self.storage.read_payload("google_trends", cid)
        result = self.parser.parse(retrieved, cid)
        self.assertEqual(result.row_count, 6)


if __name__ == "__main__":
    unittest.main()
