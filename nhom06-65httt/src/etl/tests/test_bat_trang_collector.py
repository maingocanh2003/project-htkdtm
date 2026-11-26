"""Unit tests for D9 â€” BatTrangWooCommerceCollector (mocked HTTP, no live network)."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from etl.bat_trang_collector import BatTrangWooCommerceCollector
from etl.deduplicator import DeduplicationIndex
from etl.http_client import HttpResponse
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
        "prices": {"price": "0", "currency_code": "VND", "currency_minor_unit": 0},
        "price_html": "",  # unpriced -> price_vnd must remain None
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
        self.assertEqual(result.raw_product_count, 2)  # 1001 + 1002 (duplicate skipped)
        self.assertEqual(result.parsed_count, 2)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.valid_count, 1)       # BT-AC-01 has valid price + category
        self.assertEqual(result.quarantined_count, 1) # GBT-1002 quarantined (missing price_vnd)

        # Verify RawStorage payload & SHA-256 checksum & manifest provenance
        payload = self.raw_storage.read_payload("bat_trang", result.collection_id)
        manifest = self.raw_storage.read_manifest("bat_trang", result.collection_id)
        self.assertEqual(manifest["metadata"]["source_id"], "bat_trang")
        self.assertEqual(manifest["metadata"]["checksum"]["algorithm"], "sha256")
        self.assertIn("products", json.loads(payload.decode("utf-8")))

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

