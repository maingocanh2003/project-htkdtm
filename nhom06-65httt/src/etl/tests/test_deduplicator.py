"""Unit tests for D13 — Deduplication engine."""

import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from etl.deduplicator import (
    DeduplicationIndex,
    DeduplicationStorageError,
    DuplicateStatus,
)
from etl.normalizer import (
    NormalizationStatus,
    NormalizedCurrency,
    NormalizedField,
    NormalizedProductRecord,
    NormalizedTradeRecord,
)
from etl.parsed_record import (
    ParsedCommercialInfo,
    ParsedDomesticProductRecord,
    ParsedPriceInfo,
    ParsedProductRecord,
    ParsedReviewRecord,
    ParsedSupplierInfo,
    ParsedTrendsRow,
    RecordProvenance,
)


class DeduplicationIndexTests(unittest.TestCase):
    def setUp(self):
        self.prov_etsy = RecordProvenance(
            source_id="etsy",
            raw_collection_id="aa" * 16,
            collected_at_iso="2026-01-01T00:00:00+00:00",
            source_url="https://example.invalid/etsy",
        )
        self.prov_etsy_2 = RecordProvenance(
            source_id="etsy",
            raw_collection_id="bb" * 16,
            collected_at_iso="2026-01-02T00:00:00+00:00",
            source_url="https://example.invalid/etsy",
        )
        self.prov_trade = RecordProvenance(
            source_id="un_comtrade",
            raw_collection_id="cc" * 16,
            collected_at_iso="2026-01-01T00:00:00+00:00",
            source_url="https://example.invalid/comtrade",
        )

    def test_exact_duplicate_by_source_id_and_product_id(self):
        idx = DeduplicationIndex()
        rec1 = ParsedProductRecord(
            provenance=self.prov_etsy,
            raw_record={"listing_id": 1001, "title": "Ceramic Bowl"},
            source_product_id="1001",
            product_url=None,
            name="Ceramic Bowl",
            category="DINNERWARE",
            category_id=None,
            prices=(ParsedPriceInfo("24.99", "USD", "minimum_listing_price"),),
        )
        rec2 = ParsedProductRecord(
            provenance=self.prov_etsy_2,
            raw_record={"listing_id": 1001, "title": "Ceramic Bowl Updated"},
            source_product_id="1001",
            product_url=None,
            name="Ceramic Bowl Updated",
            category="DINNERWARE",
            category_id=None,
            prices=(ParsedPriceInfo("25.99", "USD", "minimum_listing_price"),),
        )

        r1 = idx.check_and_register(rec1, record_id="ETSY_1001_A")
        self.assertEqual(r1.status, DuplicateStatus.UNIQUE)
        self.assertFalse(r1.is_duplicate)
        self.assertTrue(r1.key_confirmed)

        r2 = idx.check_and_register(rec2, record_id="ETSY_1001_B")
        self.assertEqual(r2.status, DuplicateStatus.EXACT_DUPLICATE)
        self.assertTrue(r2.is_duplicate)
        self.assertTrue(r2.key_confirmed)
        self.assertFalse(r2.needs_confirmation)
        self.assertEqual(r2.matched_record_id, "ETSY_1001_A")
        self.assertEqual(r2.matched_collection_id, "aa" * 16)

    def test_exact_duplicate_by_confirmed_business_key(self):
        idx = DeduplicationIndex()
        sup1 = {"supplier_code": "ML01", "supplier_name": "Minh Long 1"}
        sup2 = {"supplier_code": "ML01", "supplier_name": "Minh Long I"}

        r1 = idx.check_and_register(sup1, entity_type="suppliers", record_id="SUP_1")
        r2 = idx.check_and_register(sup2, entity_type="suppliers", record_id="SUP_2")
        self.assertEqual(r1.status, DuplicateStatus.UNIQUE)
        self.assertEqual(r2.status, DuplicateStatus.EXACT_DUPLICATE)
        self.assertEqual(r2.key_used, "supplier_code")

        # Country & Category confirmed codes
        c1 = {"country_code": "VNM", "country_name": "Viet Nam"}
        c2 = {"country_code": "VNM", "country_name": "Vietnam"}
        self.assertEqual(idx.check_and_register(c1, entity_type="countries").status, DuplicateStatus.UNIQUE)
        self.assertEqual(idx.check_and_register(c2, entity_type="countries").status, DuplicateStatus.EXACT_DUPLICATE)

    def test_do_not_conclude_exact_duplicate_on_product_name_alone(self):
        idx = DeduplicationIndex()
        rec1 = NormalizedProductRecord(
            provenance=self.prov_etsy,
            raw_record={},
            source_product_id=NormalizedField("1001", "1001", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField("Bình hoa gốm", "Bình hoa gốm", NormalizationStatus.CONFIRMED),
            product_url=NormalizedField(None, None, NormalizationStatus.MISSING),
            category=NormalizedField("VASE_DECOR", "VASE_DECOR", NormalizationStatus.CONFIRMED),
            price=NormalizedCurrency(
                "30", "USD", Decimal("30"), "USD", NormalizationStatus.CONFIRMED,
                Decimal("30"), "USD", NormalizationStatus.CONFIRMED,
            ),
        )
        # Different source_product_id, identical product_name -> POTENTIAL_DUPLICATE only
        rec2 = NormalizedProductRecord(
            provenance=self.prov_etsy_2,
            raw_record={},
            source_product_id=NormalizedField("2002", "2002", NormalizationStatus.CONFIRMED),
            product_name=NormalizedField("  Bình hoa gốm  ", "Bình hoa gốm", NormalizationStatus.CONFIRMED),
            product_url=NormalizedField(None, None, NormalizationStatus.MISSING),
            category=NormalizedField("VASE_DECOR", "VASE_DECOR", NormalizationStatus.CONFIRMED),
            price=NormalizedCurrency(
                "30", "USD", Decimal("30"), "USD", NormalizationStatus.CONFIRMED,
                Decimal("30"), "USD", NormalizationStatus.CONFIRMED,
            ),
        )

        idx.check_and_register(rec1, record_id="P_1001")
        r2 = idx.check_and_register(rec2, record_id="P_2002")
        self.assertEqual(r2.status, DuplicateStatus.POTENTIAL_DUPLICATE)
        self.assertNotEqual(r2.status, DuplicateStatus.EXACT_DUPLICATE)
        self.assertTrue(r2.needs_confirmation)
        self.assertFalse(r2.key_confirmed)
        self.assertEqual(r2.matched_record_id, "P_1001")

    def test_missing_identifier_key_gives_pending_confirmation(self):
        idx = DeduplicationIndex()
        missing_id_prod = {
            "source_id": "etsy",
            "source_product_id": "   ",
            "product_name": "Unique Unnamed Vase",
        }
        res = idx.check_and_register(missing_id_prod, entity_type="market_products")
        self.assertEqual(res.status, DuplicateStatus.PENDING_KEY_CONFIRMATION)
        self.assertFalse(res.is_duplicate)
        self.assertFalse(res.key_confirmed)
        self.assertTrue(res.needs_confirmation)

        # Second record also missing ID but same name -> POTENTIAL_DUPLICATE (not exact)
        res2 = idx.check_and_register(missing_id_prod, entity_type="market_products")
        self.assertEqual(res2.status, DuplicateStatus.POTENTIAL_DUPLICATE)
        self.assertTrue(res2.needs_confirmation)

    def test_unconfirmed_schema_entities_yield_pending_then_potential_duplicate(self):
        idx = DeduplicationIndex()
        trade1 = NormalizedTradeRecord(
            provenance=self.prov_trade,
            raw_record={"cmdCode": "6911"},
            reporter_country=NormalizedField("842", "USA", NormalizationStatus.CONFIRMED),
            partner_country=NormalizedField("704", "VNM", NormalizationStatus.CONFIRMED),
            hs_code=NormalizedField("6911", "6911", NormalizationStatus.CONFIRMED),
            period=NormalizedField("2022", "2022", NormalizationStatus.CONFIRMED),
            flow_code=NormalizedField("M", "Import", NormalizationStatus.CONFIRMED),
            net_weight_kg=NormalizedField(10.0, 10.0, NormalizationStatus.CONFIRMED),
            trade_value_usd=NormalizedField(100.0, 100.0, NormalizationStatus.CONFIRMED),
            product_description=NormalizedField(None, None, NormalizationStatus.MISSING),
        )
        r1 = idx.check_and_register(trade1, record_id="TR_1")
        self.assertEqual(r1.status, DuplicateStatus.PENDING_KEY_CONFIRMATION)
        self.assertFalse(r1.is_duplicate)
        self.assertTrue(r1.needs_confirmation)

        r2 = idx.check_and_register(trade1, record_id="TR_2")
        self.assertEqual(r2.status, DuplicateStatus.POTENTIAL_DUPLICATE)
        self.assertTrue(r2.is_duplicate)
        self.assertTrue(r2.needs_confirmation)
        self.assertFalse(r2.key_confirmed)

        # Reviews, Trends, and ParsedSupplierInfo also await composite key confirmation
        rev = ParsedReviewRecord(self.prov_etsy, {}, "1001", 5, "Great!", "2026-01-01T00:00:00+00:00", "en")
        self.assertEqual(idx.check_and_register(rev).status, DuplicateStatus.PENDING_KEY_CONFIRMATION)
        self.assertEqual(idx.check_and_register(rev).status, DuplicateStatus.POTENTIAL_DUPLICATE)

        trend = ParsedTrendsRow(self.prov_trade, {}, "2025-01-05", (("mug", "80"),))
        self.assertEqual(idx.check_and_register(trend).status, DuplicateStatus.PENDING_KEY_CONFIRMATION)
        self.assertEqual(idx.check_and_register(trend).status, DuplicateStatus.POTENTIAL_DUPLICATE)

        sup = ParsedSupplierInfo("Gốm Việt", "0314567890", None, None, None, None, None, None)
        self.assertEqual(idx.check_and_register(sup).status, DuplicateStatus.PENDING_KEY_CONFIRMATION)
        self.assertEqual(idx.check_and_register(sup).status, DuplicateStatus.POTENTIAL_DUPLICATE)

    def test_domestic_product_exact_duplicate_and_json_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "dedup_index.json"
            idx1 = DeduplicationIndex(index_file=index_path)

            dom = ParsedDomesticProductRecord(
                provenance=RecordProvenance("minh_long_1", "dd" * 16, "2026-01-01T00:00:00+00:00", None),
                raw_record={"source_product_id": "ML-001"},
                source_product_id="ML-001",
                product_url=None,
                name="Ấm chén Hoàng Liên",
                description=None,
                category="TEA_SET",
                material=None,
                origin_region=None,
                commercial=ParsedCommercialInfo("450000", "VND", 10, 7, True),
            )
            r1 = idx1.check_and_register(dom, record_id="DOM_1")
            self.assertEqual(r1.status, DuplicateStatus.UNIQUE)
            self.assertTrue(index_path.exists())

            # Reload from disk and verify exact duplicate is still detected
            idx2 = DeduplicationIndex(index_file=index_path)
            r2 = idx2.check_and_register(dom, record_id="DOM_2")
            self.assertEqual(r2.status, DuplicateStatus.EXACT_DUPLICATE)
            self.assertEqual(r2.matched_record_id, "DOM_1")

    def test_unsupported_record_type_raises_type_error(self):
        idx = DeduplicationIndex()
        with self.assertRaises(TypeError):
            idx.check_and_register("not-a-record")  # type: ignore[arg-type]

    def test_country_category_normalization_and_market_regions_unique_key(self):
        idx = DeduplicationIndex()
        # Case, whitespace, and numeric M49 normalization for countries
        r1 = idx.check_and_register({"country_code": " vnm "}, entity_type="countries")
        r2 = idx.check_and_register({"country_code": "VNM"}, entity_type="countries")
        r3 = idx.check_and_register({"country_code": "704"}, entity_type="countries")
        self.assertEqual(r1.status, DuplicateStatus.UNIQUE)
        self.assertEqual(r2.status, DuplicateStatus.EXACT_DUPLICATE)
        self.assertEqual(r3.status, DuplicateStatus.EXACT_DUPLICATE)

        # product_categories normalization
        c1 = idx.check_and_register({"category_code": "tea set"}, entity_type="product_categories")
        c2 = idx.check_and_register({"category_code": "TEA_SET"}, entity_type="product_categories")
        self.assertEqual(c1.status, DuplicateStatus.UNIQUE)
        self.assertEqual(c2.status, DuplicateStatus.EXACT_DUPLICATE)

        # market_regions: uq_country_region_code UNIQUE (country_id, region_code)
        m1 = idx.check_and_register({"country_id": 1, "region_code": "us-ca"}, entity_type="market_regions")
        m2 = idx.check_and_register({"country_id": 1, "region_code": "US-CA"}, entity_type="market_regions")
        m_missing = idx.check_and_register({"country_id": 1}, entity_type="market_regions")
        self.assertEqual(m1.status, DuplicateStatus.UNIQUE)
        self.assertTrue(m1.key_confirmed)
        self.assertEqual(m2.status, DuplicateStatus.EXACT_DUPLICATE)
        self.assertEqual(m_missing.status, DuplicateStatus.PENDING_KEY_CONFIRMATION)

    def test_corrupted_index_and_write_error_raise_storage_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "dedup_index.json"
            index_path.write_text("{corrupt-json", encoding="utf-8")

            with self.assertRaises(DeduplicationStorageError):
                DeduplicationIndex(index_file=index_path)
            # Corrupted file must not be deleted or overwritten
            self.assertEqual(index_path.read_text(encoding="utf-8"), "{corrupt-json")

            valid_path = Path(tmpdir) / "valid_index.json"
            idx = DeduplicationIndex(index_file=valid_path)
            with patch.object(Path, "write_text", side_effect=OSError("disk full")):
                with self.assertRaises(DeduplicationStorageError):
                    idx.check_and_register({"country_code": "VNM"}, entity_type="countries")
            # No leftover .tmp files
            self.assertEqual(list(Path(tmpdir).glob("*.tmp")), [])

    def test_concurrent_updates_preserve_all_registered_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "shared_index.json"
            errors = []

            def worker(worker_id: int) -> None:
                try:
                    local_idx = DeduplicationIndex(index_file=index_path)
                    for j in range(10):
                        res = local_idx.check_and_register(
                            {
                                "source_id": "etsy",
                                "source_product_id": f"W{worker_id}-{j}",
                                "product_name": f"Product {worker_id}-{j}",
                            },
                            entity_type="market_products",
                        )
                        if res.status != DuplicateStatus.UNIQUE:
                            raise AssertionError(f"Expected UNIQUE, got {res.status}")
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            reloaded = DeduplicationIndex(index_file=index_path)
            for i in range(4):
                for j in range(10):
                    dup = reloaded.check_and_register(
                        {
                            "source_id": "etsy",
                            "source_product_id": f"W{i}-{j}",
                            "product_name": f"Product {i}-{j}",
                        },
                        entity_type="market_products",
                    )
                    self.assertEqual(dup.status, DuplicateStatus.EXACT_DUPLICATE)


if __name__ == "__main__":
    unittest.main()
