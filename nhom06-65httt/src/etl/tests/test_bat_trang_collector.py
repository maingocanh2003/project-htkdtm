"""Unit tests for D9 â€” BatTrangWooCommerceCollector (mocked HTTP, no live network)."""

import base64
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from etl.bat_trang_collector import (
    BatTrangWooCommerceCollector,
    _map_wc_product_to_d9,
    wc_store_raw_payload_to_d9,
)
from etl.deduplicator import DeduplicationIndex
from etl.http_client import HttpResponse
from etl.pipeline import EtlPipeline
from etl.quarantine import QuarantineReasonType, QuarantineStore
from etl.raw_storage import CollectionStatus, RawStorage
from etl.source_registry import create_project_source_registry


_FIXTURE_PAGE_1 = [
    {
        "id": 1001,
        "name": "Bá»™ áº¤m ChÃ©n Men Lam BÃ¡t TrÃ ng",
        "permalink": "https://gombattrang.vn/san-pham/bo-am-chen-men-lam/",
        "sku": "BT-AC-01",
        "description": "<p>Bá»™ áº¥m chÃ©n thá»§ cÃ´ng BÃ¡t TrÃ ng.</p>",
        "short_description": "",
        "prices": {"price": "450000", "currency_code": "VND", "currency_minor_unit": 0},
        "price_html": "<span>450.000Ä‘</span>",
        "categories": [{"id": 10, "name": "Bá»™ áº¥m chÃ©n"}],
        "images": [{"src": "https://gombattrang.vn/img/1001.jpg"}],
        "attributes": [
            {"name": "Cháº¥t liá»‡u", "terms": [{"name": "Gá»‘m sá»© BÃ¡t TrÃ ng"}]},
            {"name": "MÃ u sáº¯c", "terms": [{"name": "Xanh lam"}]},
        ],
    },
    {
        "id": 1002,
        "name": "BÃ¬nh HÃºt Lá»™c Tá»© Cáº£nh",
        "permalink": "https://gombattrang.vn/san-pham/binh-hut-loc/",
        "sku": "",  # missing SKU -> fallback GBT-1002
        "description": "",
        "short_description": "",
        "prices": {"currency_code": "VND", "currency_minor_unit": 0},
        "price_html": "",
        "categories": [{"id": 11, "name": "Lá» hoa"}],
        "images": [],
        "attributes": [],
    },
]

_FIXTURE_PAGE_2 = [
    # Duplicate of BT-AC-01 across pages -> must be deduplicated
    {
        "id": 1001,
        "name": "Bá»™ áº¤m ChÃ©n Men Lam BÃ¡t TrÃ ng",
        "permalink": "https://gombattrang.vn/san-pham/bo-am-chen-men-lam/",
        "sku": "BT-AC-01",
        "description": "<p>Bá»™ áº¥m chÃ©n thá»§ cÃ´ng BÃ¡t TrÃ ng.</p>",
        "prices": {"price": "450000", "currency_code": "VND", "currency_minor_unit": 0},
        "price_html": "<span>450.000Ä‘</span>",
        "categories": [{"id": 10, "name": "Bá»™ áº¥m chÃ©n"}],
        "images": [],
        "attributes": [],
    },
]


class _FakeHttpClient:
    def __init__(self, responses: Dict[int, Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, Optional[Mapping[str, Any]]]] = []

    def get(
        self,
        url: str,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> HttpResponse:
        self.calls.append((url, params))
        page = int((params or {}).get("page", 1))
        outcome = self._responses.get(page, [])
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, int):
            return HttpResponse(status_code=outcome, headers={}, body=b"{}", url=url)
        body = json.dumps(outcome, ensure_ascii=False).encode("utf-8")
        return HttpResponse(status_code=200, headers={}, body=body, url=url)


class BatTrangCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.registry = create_project_source_registry()
        self.raw_storage = RawStorage(self.root / "raw", self.registry)
        self.quarantine = QuarantineStore(self.root / "quarantine")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_legacy_d9_raw_payload_remains_replayable(self):
        legacy_payload = json.dumps(
            {
                "supplier": {"supplier_name": "Legacy supplier"},
                "products": [],
            }
        ).encode("utf-8")

        self.assertEqual(wc_store_raw_payload_to_d9(legacy_payload), legacy_payload)

    def test_maps_vnd_price_from_minor_units_and_preserves_source_fields(self) -> None:
        source_prices = {
            "price": "450000",
            "currency_code": "VND",
            "currency_minor_unit": 0,
        }
        mapped = _map_wc_product_to_d9(
            {
                "id": 9001,
                "sku": "BT-9001",
                "prices": source_prices,
                "price_html": "<span>450.000 đ</span>",
            }
        )

        self.assertIsNotNone(mapped)
        self.assertEqual(mapped["wc_id"], 9001)
        self.assertEqual(mapped["sku"], "BT-9001")
        self.assertEqual(mapped["source_product_id"], "BT-9001")
        self.assertEqual(mapped["price_vnd"], 450000.0)
        self.assertEqual(mapped["currency"], "VND")
        self.assertEqual(mapped["store_api_prices"], source_prices)

    def test_maps_zero_price_as_a_present_price(self) -> None:
        source_prices = {
            "price": "0",
            "currency_code": "VND",
            "currency_minor_unit": 0,
        }
        mapped = _map_wc_product_to_d9(
            {"id": 9002, "sku": "", "prices": source_prices, "price_html": ""}
        )

        self.assertIsNotNone(mapped)
        self.assertEqual(mapped["source_product_id"], "GBT-9002")
        self.assertEqual(mapped["price_vnd"], 0.0)
        self.assertEqual(mapped["store_api_prices"], source_prices)

        collector = BatTrangWooCommerceCollector(
            _FakeHttpClient(
                {
                    1: [
                        {
                            "id": 9002,
                            "sku": "",
                            "name": "Product with zero price",
                            "prices": source_prices,
                            "categories": [{"name": "Gia dụng"}],
                        }
                    ]
                }
            ),
            self.raw_storage,
            self.registry,
        )
        result = collector.collect(per_page=1, max_pages=2)

        self.assertEqual(result.valid_count, 1)
        self.assertEqual(result.quarantined_count, 0)
        self.assertEqual(result.parsed_payload.products[0].commercial.price_vnd_str, "0.0")

    def test_missing_price_stays_missing_even_when_price_html_contains_text(self) -> None:
        source_prices = {"currency_code": "VND", "currency_minor_unit": 0}
        mapped = _map_wc_product_to_d9(
            {
                "id": 9003,
                "sku": "BT-9003",
                "prices": source_prices,
                "price_html": "<span>450.000 đ</span>",
            }
        )

        self.assertIsNotNone(mapped)
        self.assertIsNone(mapped["price_vnd"])
        self.assertEqual(mapped["store_api_prices"], source_prices)

    def test_missing_currency_does_not_assume_price_is_vnd(self) -> None:
        source_prices = {"price": "450000", "currency_minor_unit": 0}
        mapped = _map_wc_product_to_d9(
            {"id": 9004, "sku": "BT-9004", "prices": source_prices}
        )

        self.assertIsNotNone(mapped)
        self.assertIsNone(mapped["currency"])
        self.assertIsNone(mapped["price_vnd"])
        self.assertEqual(mapped["store_api_prices"], source_prices)

    def test_missing_minor_unit_does_not_assume_zero_decimals(self) -> None:
        source_prices = {"price": "450000", "currency_code": "VND"}
        mapped = _map_wc_product_to_d9(
            {"id": 9007, "sku": "BT-9007", "prices": source_prices}
        )

        self.assertIsNotNone(mapped)
        self.assertIsNone(mapped["price_vnd"])
        self.assertEqual(mapped["store_api_prices"], source_prices)

    def test_applies_currency_minor_unit(self) -> None:
        source_prices = {
            "price": "12345",
            "currency_code": "VND",
            "currency_minor_unit": 2,
        }
        mapped = _map_wc_product_to_d9(
            {"id": 9005, "sku": "BT-9005", "prices": source_prices}
        )

        self.assertIsNotNone(mapped)
        self.assertEqual(mapped["price_vnd"], 123.45)

    def test_invalid_price_or_minor_unit_stays_unmapped(self) -> None:
        for price, minor_unit in (
            ("invalid", 0),
            ("12.5", 0),
            ("-1", 0),
            ("450000", -1),
            ("450000", "unknown"),
        ):
            with self.subTest(price=price, minor_unit=minor_unit):
                mapped = _map_wc_product_to_d9(
                    {
                        "id": 9006,
                        "sku": "BT-9006",
                        "prices": {
                            "price": price,
                            "currency_code": "VND",
                            "currency_minor_unit": minor_unit,
                        },
                    }
                )
                self.assertIsNotNone(mapped)
                self.assertIsNone(mapped["price_vnd"])

    def test_pagination_dedup_raw_storage_sha256_and_quarantine(self) -> None:
        client = _FakeHttpClient({1: _FIXTURE_PAGE_1, 2: _FIXTURE_PAGE_2})
        collector = BatTrangWooCommerceCollector(client, self.raw_storage, self.registry)
        dedup = DeduplicationIndex()

        result = collector.collect(
            per_page=2,
            max_pages=5,
            dedup_index=dedup,
            quarantine_store=self.quarantine,
        )

        self.assertEqual(result.status, CollectionStatus.SUCCESS)
        self.assertEqual(result.pages_requested, 2)
        self.assertEqual(result.pages_succeeded, 2)
        self.assertEqual(result.raw_product_count, 3)  # Includes the duplicate API item.
        self.assertEqual(result.parsed_count, 2)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.valid_count, 1)       # BT-AC-01 has valid price + category
        self.assertEqual(result.quarantined_count, 1) # GBT-1002 quarantined (missing price_vnd)

        # Verify RawStorage payload & SHA-256 checksum & manifest provenance
        payload = self.raw_storage.read_payload("bat_trang", result.collection_id)
        manifest = self.raw_storage.read_manifest("bat_trang", result.collection_id)
        self.assertEqual(manifest["metadata"]["source_id"], "bat_trang")
        self.assertEqual(manifest["metadata"]["checksum"]["algorithm"], "sha256")
        raw_envelope = json.loads(payload.decode("utf-8"))
        self.assertEqual(raw_envelope["format"], "woocommerce_store_api_raw_v1")
        raw_page = next(
            item for item in raw_envelope["responses"] if item["page"] == 1
        )
        stored_source_items = json.loads(
            base64.b64decode(raw_page["body_base64"], validate=True).decode("utf-8")
        )
        self.assertEqual(stored_source_items, _FIXTURE_PAGE_1)
        self.assertEqual(
            result.parsed_payload.products[0].raw_record["store_api_prices"],
            _FIXTURE_PAGE_1[0]["prices"],
        )

        # Verify missing fields remain None (never invented)
        p2 = result.parsed_payload.products[1]
        self.assertEqual(p2.source_product_id, "GBT-1002")
        self.assertIsNone(p2.commercial.price_vnd_str)
        self.assertIsNone(p2.commercial.moq)
        self.assertIsNone(p2.material)

        # Verify quarantine entry has validation_error and provenance
        q_entries = self.quarantine.query(
            source_id="bat_trang",
            reason_type=QuarantineReasonType.VALIDATION_ERROR,
        )
        self.assertEqual(len(q_entries), 1)
        self.assertEqual(q_entries[0].raw_collection_id, result.collection_id)

    def test_raw_keeps_duplicate_and_incomplete_api_items_for_pipeline_replay(self):
        complete_product = {
            "id": 1201,
            "sku": "BT-1201",
            "name": "Product retained after processing",
            "prices": {
                "price": "250000",
                "currency_code": "VND",
                "currency_minor_unit": 0,
            },
            "categories": [{"name": "Gia dung"}],
        }
        duplicate_product = dict(complete_product, id=1202)
        incomplete_product = {"name": "API item without an ID"}
        api_items = [complete_product, duplicate_product, incomplete_product]
        collector = BatTrangWooCommerceCollector(
            _FakeHttpClient({1: api_items, 2: []}),
            self.raw_storage,
            self.registry,
        )

        collected = collector.collect(per_page=3, max_pages=3)

        self.assertEqual(collected.raw_product_count, 3)
        self.assertEqual(collected.parsed_count, 1)
        self.assertEqual(collected.duplicate_count, 1)
        self.assertEqual(collected.valid_count, 1)

        raw_before_replay = self.raw_storage.read_payload(
            "bat_trang", collected.collection_id
        )
        raw_envelope = json.loads(raw_before_replay.decode("utf-8"))
        first_response = raw_envelope["responses"][0]
        stored_response_body = base64.b64decode(
            first_response["body_base64"], validate=True
        )
        self.assertEqual(
            stored_response_body,
            json.dumps(api_items, ensure_ascii=False).encode("utf-8"),
        )
        self.assertEqual(
            json.loads(stored_response_body.decode("utf-8")),
            api_items,
        )

        pipeline = EtlPipeline(
            self.root / "raw",
            self.root / "processed",
            self.root / "quarantine",
        )
        replayed = pipeline.run(["bat_trang"])[0]

        self.assertEqual(replayed.parser_errors, 0)
        self.assertEqual(replayed.parsed_records, 2)
        self.assertEqual(replayed.duplicate_candidates, 1)
        self.assertEqual(replayed.processed_records, 1)
        self.assertEqual(
            self.raw_storage.read_payload("bat_trang", collected.collection_id),
            raw_before_replay,
        )

    def test_continues_when_one_page_fails_and_marks_partial(self) -> None:
        client = _FakeHttpClient({1: RuntimeError("timeout"), 2: _FIXTURE_PAGE_1, 3: []})
        collector = BatTrangWooCommerceCollector(client, self.raw_storage, self.registry)

        result = collector.collect(per_page=2, max_pages=3)

        self.assertEqual(result.status, CollectionStatus.PARTIAL)
        self.assertEqual(result.pages_requested, 3)
        self.assertEqual(result.pages_succeeded, 2)
        self.assertEqual(len(result.failed_pages), 1)
        self.assertEqual(result.failed_pages[0][0], 1)
        self.assertEqual(result.parsed_count, 2)


if __name__ == "__main__":
    unittest.main()

