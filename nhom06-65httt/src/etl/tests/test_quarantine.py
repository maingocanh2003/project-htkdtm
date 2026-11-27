"""Unit tests for D13 — Quarantine and Recovery storage."""

import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from etl.deduplicator import DeduplicationIndex
from etl.normalizer import (
    NormalizationStatus,
    NormalizedField,
    NormalizedTradeRecord,
    normalize_domestic_product,
    normalize_product_record,
    normalize_review_record,
    normalize_trade_record,
    normalize_trends_row,
)
from etl.parsed_record import (
    ParsedCommercialInfo,
    ParsedDomesticProductRecord,
    ParsedPriceInfo,
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedTradeRecord,
    ParsedTrendsRow,
    RecordProvenance,
)
from etl.quality_validator import DataQualityValidator, TradeQualityValidator
from etl.quarantine import (
    QuarantineReasonType,
    QuarantineRecoveryError,
    QuarantineStatus,
    QuarantineStorageError,
    QuarantineStore,
    _json_safe,
    rehydrate_record,
)
from etl.raw_storage import CollectionStatus, RawStorage
from etl.source_registry import (
    CollectionMetadata,
    Source,
    SourceGroup,
    SourceRegistry,
    SourceStatus,
    SourceType,
)


class QuarantineAndRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        self.registry = SourceRegistry()
        self.registry.register(
            Source(
                source_id="un_comtrade",
                source_name="UN Comtrade",
                source_type=SourceType.API,
                base_url="https://comtradeapi.un.org",
                status=SourceStatus.ACTIVE,
                description="UN Comtrade trade data",
                source_group=SourceGroup.UN_COMTRADE,
            )
        )
        self.raw_storage = RawStorage(self.root / "raw", self.registry)
        self.raw_bytes = b'{"count": 1, "data": [{"cmdCode": "6911", "primaryValue": -50}]}'
        self.collection_id = self.raw_storage.save(
            payload=self.raw_bytes,
            metadata=CollectionMetadata(
                collected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                source_id="un_comtrade",
                data_format="json",
            ),
            request_parameters={"cmdCode": "6911"},
            status=CollectionStatus.SUCCESS,
        )
        self.provenance = RecordProvenance(
            source_id="un_comtrade",
            raw_collection_id=self.collection_id,
            collected_at_iso="2026-01-01T00:00:00+00:00",
            source_url="https://comtradeapi.un.org/preview",
        )
        self.store = QuarantineStore(self.root / "quarantine")

    def tearDown(self):
        self.tmp.cleanup()

    def _make_invalid_trade(self) -> NormalizedTradeRecord:
        return NormalizedTradeRecord(
            provenance=self.provenance,
            raw_record={"cmdCode": "6911", "primaryValue": -50},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(-50.0, -50.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )

    def test_quarantine_invalid_record_preserves_provenance_and_raw_storage(self):
        rec = self._make_invalid_trade()
        val_res = DataQualityValidator.validate_trade_record(rec, record_id="TR_BAD")
        self.assertFalse(val_res.is_valid)

        entry = self.store.quarantine_from_validation(val_res, rec)
        self.assertEqual(entry.reason_type, QuarantineReasonType.VALIDATION_ERROR)
        self.assertEqual(entry.status, QuarantineStatus.QUARANTINED)
        self.assertEqual(entry.source_id, "un_comtrade")
        self.assertEqual(entry.raw_collection_id, self.collection_id)
        self.assertGreater(len(entry.error_codes), 0)
        self.assertGreater(len(entry.error_reasons), 0)

        # D3 RawStorage payload must remain completely untouched
        self.assertEqual(
            self.raw_storage.read_payload("un_comtrade", self.collection_id),
            self.raw_bytes,
        )

    def test_separates_validation_errors_from_duplicate_suspects_and_queries(self):
        # 1. Validation error entry
        val_res = DataQualityValidator.validate_trade_record(self._make_invalid_trade())
        q_val = self.store.quarantine_from_validation(val_res, {"cmdCode": "6911"})

        # 2. Duplicate suspect entry
        idx = DeduplicationIndex()
        prov_etsy = RecordProvenance("etsy", self.collection_id, "2026-01-01T00:00:00+00:00", None)
        p1 = ParsedProductRecord(prov_etsy, {}, "101", None, "Bowl", "DINNERWARE", None, (ParsedPriceInfo("10", "USD", "offer"),))
        p2 = ParsedProductRecord(prov_etsy, {}, "202", None, "Bowl", "DINNERWARE", None, (ParsedPriceInfo("10", "USD", "offer"),))
        idx.check_and_register(p1)
        dup_res = idx.check_and_register(p2)
        q_dup = self.store.quarantine_duplicate(dup_res, p2)

        # Query by ID, source_id, status, reason_type
        self.assertEqual(self.store.get(q_val.quarantine_id).quarantine_id, q_val.quarantine_id)
        self.assertEqual(len(self.store.query(source_id="un_comtrade")), 1)
        self.assertEqual(len(self.store.query(source_id="etsy")), 1)
        self.assertEqual(len(self.store.query(reason_type=QuarantineReasonType.VALIDATION_ERROR)), 1)
        self.assertEqual(len(self.store.query(reason_type=QuarantineReasonType.POTENTIAL_DUPLICATE)), 1)
        self.assertEqual(len(self.store.query(status=QuarantineStatus.QUARANTINED)), 2)

        with self.assertRaises(KeyError):
            self.store.get("ff" * 16)

    def test_recovery_succeeds_after_rule_fix_and_preserves_history(self):
        # Quarantine a dict record that initially fails due to missing trade_value_usd
        raw_dict = {
            "reporter_code": "842",
            "partner_code": "704",
            "year": "2022",
            "trade_flow": "Export",
            "hs_code": "6911",
            "trade_value_usd": -100,
        }
        val_res = TradeQualityValidator.validate(raw_dict, record_id="DICT_1")
        entry = self.store.quarantine_from_validation(val_res, raw_dict, provenance=self.provenance)

        # Attempt 1: still fails validation -> RECOVERY_FAILED
        res1 = self.store.recover(
            entry.quarantine_id,
            validator_fn=lambda d: TradeQualityValidator.validate(d),
        )
        self.assertFalse(res1.recovered)
        self.assertEqual(res1.new_status, QuarantineStatus.RECOVERY_FAILED)
        self.assertEqual(len(res1.entry.history), 1)
        self.assertEqual(res1.entry.history[0].attempt_number, 1)
        self.assertEqual(res1.entry.history[0].raw_collection_id, self.collection_id)

        # Attempt 2: updated normalizer fixes the negative/reversed sign rule -> RECOVERED
        def fixed_normalizer(snapshot: dict) -> dict:
            fixed = dict(snapshot)
            fixed["trade_value_usd"] = abs(float(fixed["trade_value_usd"]))
            return fixed

        res2 = self.store.recover(
            entry.quarantine_id,
            normalizer_fn=fixed_normalizer,
            validator_fn=lambda d: TradeQualityValidator.validate(d),
        )
        self.assertTrue(res2.recovered)
        self.assertEqual(res2.new_status, QuarantineStatus.RECOVERED)
        # History preserves BOTH attempt 1 and attempt 2, plus original raw_collection_id
        reloaded = self.store.get(entry.quarantine_id)
        self.assertEqual(reloaded.raw_collection_id, self.collection_id)
        self.assertEqual(len(reloaded.history), 2)
        self.assertEqual(reloaded.history[0].new_status, QuarantineStatus.RECOVERY_FAILED)
        self.assertEqual(reloaded.history[1].new_status, QuarantineStatus.RECOVERED)

        # D3 RawStorage still untouched
        self.assertEqual(
            self.raw_storage.read_payload("un_comtrade", self.collection_id),
            self.raw_bytes,
        )

    def test_quarantine_guards_reject_valid_or_unprovenanced_records(self):
        valid_dict = {
            "reporter_code": "842",
            "partner_code": "704",
            "year": "2022",
            "trade_flow": "Export",
            "hs_code": "6911",
            "trade_value_usd": "500",
        }
        val_ok = TradeQualityValidator.validate(valid_dict)
        with self.assertRaises(ValueError):
            self.store.quarantine_from_validation(val_ok, valid_dict, provenance=self.provenance)

        val_bad = TradeQualityValidator.validate({"year": "1990"})
        with self.assertRaises(ValueError):
            self.store.quarantine_from_validation(val_bad, {"year": "1990"})

    def test_trends_context_survives_quarantine_record_round_trip(self):
        parsed = ParsedTrendsRow(
            provenance=self.provenance,
            raw_row={"query": "ceramic mug", "value": "Breakout"},
            period_label="ceramic mug",
            keyword_values=(("search interest", "Breakout"),),
            related_section="rising",
            period_kind="related_term",
            source_keyword="ceramic",
            data_type_hint="Related queries",
        )
        restored = rehydrate_record("ParsedTrendsRow", _json_safe(parsed))
        self.assertEqual(restored.period_kind, "related_term")
        self.assertEqual(restored.related_section, "rising")
        self.assertEqual(restored.source_keyword, "ceramic")
        self.assertEqual(restored.data_type_hint, "Related queries")

    def test_recovery_from_parsed_and_normalized_trade_records(self):
        # 1. Quarantine a ParsedTradeRecord that initially fails (period="1995")
        parsed_trade = ParsedTradeRecord(
            provenance=self.provenance,
            raw_record={"cmdCode": "6911", "period": "1995"},
            reporter_code="842",
            partner_code="704",
            hs_code="6911",
            period="1995",
            flow_code="M",
            net_weight_kg=10.0,
            trade_value_usd=100.0,
            reporter_name=None,
            partner_name=None,
            product_description="Ceramic tableware",
        )
        val_parsed = DataQualityValidator.validate_trade_record(parsed_trade)
        self.assertFalse(val_parsed.is_valid)
        entry_p = self.store.quarantine_from_validation(val_parsed, parsed_trade)
        self.assertEqual(entry_p.record_type, "ParsedTradeRecord")

        # Recover: fix period before D11 normalizer, then run D11 normalizer -> D12 validator
        def fix_and_normalize_trade(rec: ParsedTradeRecord) -> NormalizedTradeRecord:
            self.assertIsInstance(rec, ParsedTradeRecord)
            fixed = ParsedTradeRecord(
                provenance=rec.provenance,
                raw_record=rec.raw_record,
                reporter_code=rec.reporter_code,
                partner_code=rec.partner_code,
                hs_code=rec.hs_code,
                period="2022",
                flow_code=rec.flow_code,
                net_weight_kg=rec.net_weight_kg,
                trade_value_usd=rec.trade_value_usd,
                reporter_name=rec.reporter_name,
                partner_name=rec.partner_name,
                product_description=rec.product_description,
            )
            return normalize_trade_record(fixed)

        res_p = self.store.recover(
            entry_p.quarantine_id,
            normalizer_fn=fix_and_normalize_trade,
            validator_fn=DataQualityValidator.validate_trade_record,
        )
        self.assertTrue(res_p.recovered)
        self.assertEqual(res_p.new_status, QuarantineStatus.RECOVERED)
        self.assertIsInstance(res_p.normalized_record, NormalizedTradeRecord)
        self.assertEqual(res_p.normalized_record.provenance.raw_collection_id, self.collection_id)

        # 2. Quarantine a NormalizedTradeRecord and recover directly via D12 validator
        norm_bad = self._make_invalid_trade()
        val_norm = DataQualityValidator.validate_trade_record(norm_bad)
        entry_n = self.store.quarantine_from_validation(val_norm, norm_bad)
        self.assertEqual(entry_n.record_type, "NormalizedTradeRecord")

        def fix_norm_trade(rec: NormalizedTradeRecord) -> NormalizedTradeRecord:
            self.assertIsInstance(rec, NormalizedTradeRecord)
            return NormalizedTradeRecord(
                provenance=rec.provenance,
                raw_record=rec.raw_record,
                reporter_country=rec.reporter_country,
                partner_country=rec.partner_country,
                hs_code=rec.hs_code,
                period=rec.period,
                flow_code=rec.flow_code,
                net_weight_kg=rec.net_weight_kg,
                trade_value_usd=NormalizedField(50.0, 50.0, NormalizationStatus.CONFIRMED),
                product_description=rec.product_description,
            )

        res_n = self.store.recover(
            entry_n.quarantine_id,
            normalizer_fn=fix_norm_trade,
            validator_fn=DataQualityValidator.validate_trade_record,
        )
        self.assertTrue(res_n.recovered)
        self.assertEqual(res_n.entry.raw_collection_id, self.collection_id)

    def test_recovery_supports_all_other_d10_d12_record_types(self):
        # ParsedProductRecord -> normalize_product_record -> validate_product_record
        p_prod = ParsedProductRecord(
            self.provenance, {}, "P1", None, "  ", "DINNERWARE", None,
            (ParsedPriceInfo("24.99", "USD", "offer"),),
        )
        q_prod = self.store.quarantine_from_validation(
            DataQualityValidator.validate_product_record(p_prod), p_prod
        )
        res_prod = self.store.recover(
            q_prod.quarantine_id,
            normalizer_fn=lambda r: normalize_product_record(
                ParsedProductRecord(r.provenance, r.raw_record, r.source_product_id, r.product_url, "Bowl", r.category, r.category_id, r.prices)
            ),
            validator_fn=DataQualityValidator.validate_product_record,
        )
        self.assertTrue(res_prod.recovered)

        # ParsedReviewRecord -> normalize_review_record -> validate_review_record
        p_rev = ParsedReviewRecord(self.provenance, {}, "P1", 0, "Nice", None, "en")
        q_rev = self.store.quarantine_from_validation(
            DataQualityValidator.validate_review_record(p_rev), p_rev
        )
        res_rev = self.store.recover(
            q_rev.quarantine_id,
            normalizer_fn=lambda r: normalize_review_record(
                ParsedReviewRecord(r.provenance, r.raw_record, r.product_reference, 5, r.review_text, r.reviewed_at_iso, r.language)
            ),
            validator_fn=DataQualityValidator.validate_review_record,
        )
        self.assertTrue(res_rev.recovered)

        # ParsedTrendsRow -> normalize_trends_row -> validate_trends_row
        p_trend = ParsedTrendsRow(self.provenance, {}, "", (("mug", "80"),))
        q_trend = self.store.quarantine_from_validation(
            DataQualityValidator.validate_trends_row(p_trend), p_trend
        )
        res_trend = self.store.recover(
            q_trend.quarantine_id,
            normalizer_fn=lambda r: normalize_trends_row(
                ParsedTrendsRow(r.provenance, r.raw_row, "2025-01-05", r.keyword_values)
            ),
            validator_fn=DataQualityValidator.validate_trends_row,
        )
        self.assertTrue(res_trend.recovered)

        # ParsedDomesticProductRecord -> normalize_domestic_product -> validate_domestic_product
        p_dom = ParsedDomesticProductRecord(
            self.provenance, {}, "D1", None, "Bình hoa", None, "VASE_DECOR", None, None,
            ParsedCommercialInfo(None, "VND", 10, 7, True),
        )
        q_dom = self.store.quarantine_from_validation(
            DataQualityValidator.validate_domestic_product(p_dom), p_dom
        )
        res_dom = self.store.recover(
            q_dom.quarantine_id,
            normalizer_fn=lambda r: normalize_domestic_product(
                ParsedDomesticProductRecord(
                    r.provenance, r.raw_record, r.source_product_id, r.product_url,
                    r.name, r.description, r.category, r.material, r.origin_region,
                    ParsedCommercialInfo("120000", "VND", 10, 7, True),
                )
            ),
            validator_fn=DataQualityValidator.validate_domestic_product,
        )
        self.assertTrue(res_dom.recovered)
        self.assertEqual(res_dom.normalized_record.price_vnd.value, Decimal("120000"))

    def test_quarantine_json_io_errors_and_invalid_id(self):
        # Invalid quarantine_id
        with self.assertRaises(ValueError):
            self.store.get("../escape")
        with self.assertRaises(ValueError):
            self.store.get("not-a-uuid")

        # Valid entry + corrupted JSON + missing-field JSON in entries dir
        val_bad = TradeQualityValidator.validate(self._make_invalid_trade())
        valid_entry = self.store.quarantine_from_validation(val_bad, self._make_invalid_trade())

        corrupt_id = "00" * 16
        corrupt_path = self.root / "quarantine" / "entries" / f"{corrupt_id}.json"
        corrupt_path.write_text("{bad json", encoding="utf-8")

        missing_id = "11" * 16
        missing_path = self.root / "quarantine" / "entries" / f"{missing_id}.json"
        missing_path.write_text('{"quarantine_id": "11"}', encoding="utf-8")

        # get() raises QuarantineStorageError and does not delete bad files
        with self.assertRaises(QuarantineStorageError):
            self.store.get(corrupt_id)
        with self.assertRaises(QuarantineStorageError):
            self.store.get(missing_id)
        self.assertTrue(corrupt_path.exists())
        self.assertTrue(missing_path.exists())
        self.assertTrue(missing_path.exists())

        # query() skips corrupted files without crashing; query_with_errors() reports them
        entries = self.store.query()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].quarantine_id, valid_entry.quarantine_id)

        qres = self.store.query_with_errors()
        self.assertEqual(len(qres.entries), 1)
        self.assertEqual(len(qres.errors), 2)
        self.assertEqual(
            {path.name for path, _ in qres.errors},
            {f"{corrupt_id}.json", f"{missing_id}.json"},
        )

        # Unknown record_type during recovery raises QuarantineRecoveryError
        bad_type_id = "22" * 16
        bad_type_path = self.root / "quarantine" / "entries" / f"{bad_type_id}.json"
        bad_type_path.write_text(
            corrupt_path.read_text(encoding="utf-8").replace("{bad json", "")
            or f'{{"quarantine_id":"{bad_type_id}","entity_type":"trade_statistics","record_type":"UnknownType","reason_type":"validation_error","source_id":"un_comtrade","raw_collection_id":"{self.collection_id}","collected_at_iso":"2026-01-01T00:00:00+00:00","record_snapshot":{{}},"error_codes":[],"error_reasons":[],"quarantined_at_iso":"2026-01-01T00:00:00+00:00","status":"quarantined","history":[]}}',
            encoding="utf-8",
        )
        with self.assertRaises(QuarantineRecoveryError):
            self.store.recover(bad_type_id, validator_fn=DataQualityValidator.validate_trade_record)

        # Read OSError & Write OSError
        with patch.object(Path, "read_text", side_effect=OSError("read error")):
            with self.assertRaises(QuarantineStorageError):
                self.store.get(valid_entry.quarantine_id)

        with patch.object(Path, "write_text", side_effect=OSError("write error")):
            with self.assertRaises(QuarantineStorageError):
                self.store.quarantine_from_validation(val_bad, self._make_invalid_trade())


if __name__ == "__main__":
    unittest.main()
