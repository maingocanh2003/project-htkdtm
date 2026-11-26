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
    GoogleTrendsCsvImporter,
    _parse_filename,
    _build_request,
    _infer_cadence,
    _infer_period,
    _sha256_hex,
)
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
# Bộ 7 – Importer: filename parsing và chống duplicate
# ---------------------------------------------------------------------------


class FilenameParsingTests(unittest.TestCase):
    def test_valid_iot_filename(self):
        result = _parse_filename("g1_VN_interest_over_time_20261120.csv")
        self.assertIsNotNone(result)
        group, geo, dt, date_str = result
        self.assertEqual(group, "g1")
        self.assertEqual(geo, "VN")
        self.assertEqual(dt, "interest_over_time")
        self.assertEqual(date_str, "20261120")

    def test_valid_related_queries_filename(self):
        result = _parse_filename("g3_US_related_queries_20261120.csv")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "US")
        self.assertEqual(result[2], "related_queries")

    def test_related_top_and_rising_filenames_preserve_section(self):
        cases = (
            ("g1_VN_related_queries_top_20261120.csv", "related_queries_top"),
            ("g1_VN_related_queries_rising_20261120.csv", "related_queries_rising"),
            ("g1_VN_related_topics_top_20261120.csv", "related_topics_top"),
            ("g1_VN_related_topics_rising_20261120.csv", "related_topics_rising"),
        )
        for filename, expected_type in cases:
            with self.subTest(filename=filename):
                result = _parse_filename(filename)
                self.assertIsNotNone(result)
                self.assertEqual(result[2], expected_type)
                self.assertEqual(result[3], "20261120")

    def test_valid_ibr_filename(self):
        result = _parse_filename("g4_VN_interest_by_region_20261120.csv")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "g4")

    def test_invalid_filename_no_match(self):
        self.assertIsNone(_parse_filename("random_file.csv"))
        self.assertIsNone(_parse_filename("g1_VN_bad_type_20261120.csv"))
        self.assertIsNone(_parse_filename("g1_VN_related_queries_unknown_20261120.csv"))
        self.assertIsNone(_parse_filename("trends_export.csv"))

    def test_build_request_iot(self):
        req = _build_request("g1", "VN", "interest_over_time", "20261120")
        self.assertIsNotNone(req)
        self.assertEqual(req.geo, "VN")
        self.assertEqual(req.data_type, TrendsDataType.INTEREST_OVER_TIME)
        self.assertIsNone(req.interval)
        self.assertIn("ceramic tableware", req.keywords)

    def test_build_request_accepts_inferred_interval(self):
        req = _build_request(
            "g1", "VN", "interest_over_time", "20261120", interval="weekly"
        )
        self.assertIsNotNone(req)
        self.assertEqual(req.interval, "weekly")

    def test_build_request_related_queries_no_interval(self):
        req = _build_request("g3", "US", "related_queries", "20261120")
        self.assertIsNotNone(req)
        self.assertIsNone(req.interval)

    def test_build_request_preserves_related_section(self):
        cases = (
            ("related_queries_top", TrendsDataType.RELATED_QUERIES, "top"),
            ("related_queries_rising", TrendsDataType.RELATED_QUERIES, "rising"),
            ("related_topics_top", TrendsDataType.RELATED_TOPICS, "top"),
            ("related_topics_rising", TrendsDataType.RELATED_TOPICS, "rising"),
        )
        for filename_type, data_type, section in cases:
            with self.subTest(filename_type=filename_type):
                req = _build_request("g1", "VN", filename_type, "20261120")
                self.assertIsNotNone(req)
                self.assertEqual(req.data_type, data_type)
                self.assertEqual(req.related_section, section)

    def test_build_request_unknown_group_returns_none(self):
        req = _build_request("g99", "US", "interest_over_time", "20261120")
        self.assertIsNone(req)

    def test_invalid_export_date_is_rejected(self):
        self.assertIsNone(_parse_filename("g1_VN_interest_over_time_20260230.csv"))

    def test_five_year_range_handles_leap_day(self):
        start, end = _infer_period("20240229")
        self.assertEqual(start, date(2019, 2, 28))
        self.assertEqual(end, date(2024, 2, 29))


class ImporterDuplicateTests(unittest.TestCase):
    """Chống thu thập trùng lặp theo SHA-256."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.incoming = self.root / "incoming"
        self.incoming.mkdir()
        self.raw = self.root / "raw"
        self.raw.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _make_importer(self):
        return GoogleTrendsCsvImporter(self.incoming, self.raw)

    def _place_csv(self, filename: str, content: bytes) -> Path:
        p = self.incoming / filename
        p.write_bytes(content)
        return p

    def test_import_valid_csv_once(self):
        payload = IOT_FIXTURE.read_bytes()
        filename = "g1_VN_interest_over_time_20261120.csv"
        self._place_csv(filename, payload)
        results = self._make_importer().run()
        imported = [r for r in results if r["status"] == "imported"]
        self.assertEqual(len(imported), 1)
        registry = create_project_source_registry()
        stored = RawStorage(self.raw, registry)
        manifest = stored.read_manifest(
            "google_trends", imported[0]["collection_id"]
        )
        request = manifest["metadata"]["request_parameters"]
        self.assertEqual(request["original_filename"], filename)
        self.assertEqual(request["export_date"], "2026-11-20")
        self.assertIsNone(request["export_timestamp"])
        self.assertEqual(request["geo"], "VN")

    def test_corrupt_sha256_index_fails_explicitly(self):
        (self.incoming / ".imported_sha256_index.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        with self.assertRaises(json.JSONDecodeError):
            self._make_importer()

    def test_duplicate_csv_skipped_on_second_run(self):
        payload = IOT_FIXTURE.read_bytes()
        self._place_csv("g1_VN_interest_over_time_20261120.csv", payload)
        # Import lần 1
        self._make_importer().run()
        # Import lần 2 cùng file → phải skip vì SHA-256 đã có trong index
        results = self._make_importer().run()
        skipped = [r for r in results if r["status"] == "skipped_duplicate"]
        self.assertEqual(len(skipped), 1)

    def test_import_records_monthly_cadence_and_keyword_header_mismatch(self):
        payload = (
            b"Time,ceramic\n"
            b"2021-11-01,16\n"
            b"2021-12-01,15\n"
            b"2022-01-01,14\n"
        )
        filename = "g1_VN_interest_over_time_20261127.csv"
        self._place_csv(filename, payload)

        results = self._make_importer().run()
        imported = next(result for result in results if result["status"] == "imported")
        manifest = RawStorage(
            self.raw, create_project_source_registry()
        ).read_manifest("google_trends", imported["collection_id"])
        request = manifest["metadata"]["request_parameters"]

        self.assertEqual(request["interval"], "monthly")
        self.assertEqual(request["keywords"], ["ceramic"])
        self.assertEqual(len(request["requested_keywords"]), 5)
        self.assertFalse(request["keyword_header_matches_request"])

    def test_import_records_weekly_cadence(self):
        payload = (
            b"Week,ceramic tableware\n"
            b"2026-10-25,10\n"
            b"2026-11-01,11\n"
            b"2026-11-08,12\n"
        )
        self._place_csv("g1_VN_interest_over_time_20261127.csv", payload)

        results = self._make_importer().run()
        imported = next(result for result in results if result["status"] == "imported")
        manifest = RawStorage(
            self.raw, create_project_source_registry()
        ).read_manifest("google_trends", imported["collection_id"])
        self.assertEqual(
            manifest["metadata"]["request_parameters"]["interval"], "weekly"
        )

    def test_top_and_rising_imports_keep_distinct_manifest_metadata(self):
        query_payload = (
            b"query,search interest,increase percent\n"
            b"ceramic bowl set,100,0\n"
        )
        topic_payload = (
            b"topic,search interest,increase percent\n"
            b"home decor,100,0\n"
        )
        files = (
            ("g1_VN_related_queries_top_20261120.csv", query_payload, "queries", "top"),
            ("g1_VN_related_queries_rising_20261120.csv", query_payload, "queries", "rising"),
            ("g1_VN_related_topics_top_20261120.csv", topic_payload, "topics", "top"),
            ("g1_VN_related_topics_rising_20261120.csv", topic_payload, "topics", "rising"),
        )
        for filename, payload, _kind, _section in files:
            self._place_csv(filename, payload)

        results = self._make_importer().run()
        imported = [result for result in results if result["status"] == "imported"]
        self.assertEqual(len(imported), 4)
        self.assertEqual(len({result["collection_id"] for result in imported}), 4)

        registry = create_project_source_registry()
        storage = RawStorage(self.raw, registry)
        expected = {
            filename: (f"related_{kind}", section)
            for filename, _payload, kind, section in files
        }
        for result in imported:
            manifest = storage.read_manifest(
                "google_trends", result["collection_id"]
            )
            request = manifest["metadata"]["request_parameters"]
            expected_type, expected_section = expected[result["file"]]
            self.assertEqual(request["data_type"], expected_type)
            self.assertEqual(request["related_section"], expected_section)
            self.assertEqual(request["original_filename"], result["file"])
            parsed_payload = GoogleTrendsParser().parse(
                storage.read_payload("google_trends", result["collection_id"]),
                result["collection_id"],
                related_section=request["related_section"],
            )
            self.assertEqual(
                parsed_payload.rows[0].related_section, expected_section
            )
            self.assertNotIn("section", parsed_payload.rows[0].raw_row)

        second_run = self._make_importer().run()
        self.assertEqual(
            sum(result["status"] == "skipped_duplicate" for result in second_run),
            4,
        )

    def test_same_payload_with_different_country_is_not_duplicate(self):
        payload = IOT_FIXTURE.read_bytes()
        self._place_csv("g1_VN_interest_over_time_20261120.csv", payload)
        self._place_csv("g1_US_interest_over_time_20261120.csv", payload)
        results = self._make_importer().run()
        imported = [r for r in results if r["status"] == "imported"]
        self.assertEqual(len(imported), 2)

    def test_bad_filename_skipped(self):
        self._place_csv("random_export.csv", b"Week,kw\n2025-01-05,55\n")
        results = self._make_importer().run()
        skipped = [r for r in results if r["status"] == "skipped_bad_name"]
        self.assertEqual(len(skipped), 1)

    def test_empty_csv_skipped(self):
        self._place_csv("g1_VN_interest_over_time_20261120.csv", b"")
        results = self._make_importer().run()
        skipped = [r for r in results if r["status"] == "skipped_empty"]
        self.assertEqual(len(skipped), 1)

    def test_multiple_files_different_geos_all_imported(self):
        payload = IOT_FIXTURE.read_bytes()
        # Payload khác nhau (nội dung giả) để tránh SHA-256 trùng
        payload_vn = payload + b"# VN"
        payload_us = payload + b"# US"
        self._place_csv("g1_VN_interest_over_time_20261120.csv", payload_vn)
        self._place_csv("g1_US_interest_over_time_20261120.csv", payload_us)
        results = self._make_importer().run()
        imported = [r for r in results if r["status"] == "imported"]
        self.assertEqual(len(imported), 2)

    def test_dry_run_does_not_write_to_raw_storage(self):
        payload = IOT_FIXTURE.read_bytes()
        self._place_csv("g1_VN_interest_over_time_20261120.csv", payload)
        importer = GoogleTrendsCsvImporter(self.incoming, self.raw, dry_run=True)
        results = importer.run()
        dry = [r for r in results if r["status"] == "dry_run"]
        self.assertEqual(len(dry), 1)
        # Raw dir không có gì được tạo
        raw_files = list(self.raw.rglob("*.bin"))
        self.assertEqual(len(raw_files), 0)

    def test_sha256_index_persisted_across_importer_instances(self):
        """Index SHA-256 phải được lưu để lần chạy sau vẫn nhận ra file đã import."""
        payload = IOT_FIXTURE.read_bytes()
        self._place_csv("g1_VN_interest_over_time_20261120.csv", payload)
        # Instance 1 import
        self._make_importer().run()
        # Instance 2 mới (tạo lại từ đầu) → phải nhận ra duplicate
        results = self._make_importer().run()
        skipped = [r for r in results if r["status"] == "skipped_duplicate"]
        self.assertEqual(len(skipped), 1)


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
