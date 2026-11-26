import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from etl.product_response import (
    AmazonCreatorsResponseAdapter,
    EtsyListingResponseAdapter,
    ProductResponseError,
)
from etl.raw_storage import RawStorage
from etl.source_registry import create_project_source_registry


FIXTURES = Path(__file__).parent / "fixtures"
COLLECTED_AT = datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)


class ProductResponseAdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry = create_project_source_registry()
        self.etsy_adapter = EtsyListingResponseAdapter()
        self.amazon_adapter = AmazonCreatorsResponseAdapter()

    def test_etsy_fixture_extracts_actual_fields_and_keeps_raw_payload(self):
        payload = (FIXTURES / "etsy_active_listings_response.json").read_bytes()

        response = self.etsy_adapter.parse(payload, COLLECTED_AT)
        product = response.records[0]

        self.assertEqual(response.metadata.source_id, "etsy")
        self.assertEqual(
            response.metadata.endpoint,
            "/v3/application/listings/active",
        )
        self.assertEqual(product.source_product_id, "123456789")
        self.assertEqual(
            product.product_url,
            "https://example.invalid/fixture/etsy-listing-1",
        )
        self.assertEqual(product.name, "Synthetic Ceramic Serving Bowl")
        self.assertIsNone(product.category)
        self.assertEqual(product.category_id, "4321")
        self.assertEqual(product.prices[0].amount, Decimal("24.99"))
        self.assertEqual(product.prices[0].currency_code, "USD")
        self.assertEqual(product.prices[0].basis, "minimum_listing_price")
        self.assertEqual(response.raw_payload, payload)

    def test_amazon_fixture_extracts_only_returned_fields_and_all_offers(self):
        payload = (
            FIXTURES / "amazon_creators_search_items_response.json"
        ).read_bytes()

        response = self.amazon_adapter.parse(payload, COLLECTED_AT)
        product = response.records[0]

        self.assertEqual(response.metadata.source_id, "amazon")
        self.assertEqual(
            response.metadata.endpoint,
            "/catalog/v1/searchItems",
        )
        self.assertEqual(product.source_product_id, "FIXTURE-ASIN-001")
        self.assertEqual(
            product.product_url,
            "https://example.invalid/fixture/amazon-item-1",
        )
        self.assertEqual(product.name, "Synthetic Porcelain Dinner Set")
        self.assertEqual(product.category, "Synthetic tableware")
        self.assertIsNone(product.category_id)
        self.assertEqual(
            [price.amount for price in product.prices],
            [Decimal("39.95"), Decimal("35")],
        )
        self.assertEqual(
            [price.currency_code for price in product.prices],
            ["USD", "USD"],
        )
        self.assertTrue(
            all(price.basis == "marketplace_offer" for price in product.prices)
        )
        self.assertEqual(response.raw_payload, payload)

    def test_absent_optional_fields_are_not_fabricated(self):
        payload = json.dumps(
            {
                "itemsResult": {
                    "items": [
                        {
                            "asin": "FIXTURE-ASIN-002",
                            "itemInfo": {},
                        }
                    ]
                }
            }
        ).encode("utf-8")

        product = self.amazon_adapter.parse(payload, COLLECTED_AT).records[0]

        self.assertIsNone(product.product_url)
        self.assertIsNone(product.name)
        self.assertIsNone(product.category)
        self.assertIsNone(product.category_id)
        self.assertEqual(product.prices, ())

    def test_missing_source_product_id_is_rejected(self):
        etsy_payload = b'{"count": 1, "results": [{"title": "No ID"}]}'
        amazon_payload = b'{"itemsResult": {"items": [{"itemInfo": {}}]}}'

        with self.assertRaisesRegex(ProductResponseError, "listing_id"):
            self.etsy_adapter.parse(etsy_payload, COLLECTED_AT)
        with self.assertRaisesRegex(ProductResponseError, "asin"):
            self.amazon_adapter.parse(amazon_payload, COLLECTED_AT)

    def test_invalid_json_and_response_envelopes_are_reported(self):
        with self.assertRaisesRegex(ProductResponseError, "valid JSON"):
            self.etsy_adapter.parse(b"\xff", COLLECTED_AT)
        with self.assertRaisesRegex(ProductResponseError, "itemsResult.items"):
            self.amazon_adapter.parse(b'{"itemsResult": {}}', COLLECTED_AT)

    def test_synthetic_fixture_bytes_can_use_d3_storage_contract(self):
        responses = (
            self.etsy_adapter.parse(
                (FIXTURES / "etsy_active_listings_response.json").read_bytes(),
                COLLECTED_AT,
            ),
            self.amazon_adapter.parse(
                (
                    FIXTURES
                    / "amazon_creators_search_items_response.json"
                ).read_bytes(),
                COLLECTED_AT,
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            storage = RawStorage(Path(temp_dir), self.registry)
            for response in responses:
                collection_id = storage.save(
                    response.raw_payload,
                    response.metadata,
                    {"fixture": True},
                )
                source_id = response.metadata.source_id

                self.assertEqual(
                    storage.read_payload(source_id, collection_id),
                    response.raw_payload,
                )
                manifest = storage.read_manifest(source_id, collection_id)
                self.assertEqual(
                    manifest["metadata"]["source_id"],
                    source_id,
                )
                self.assertEqual(manifest["metadata"]["status"], "success")
                self.assertEqual(
                    manifest["metadata"]["request_parameters"],
                    {"fixture": True},
                )

    def test_etsy_malformed_price_and_taxonomy_errors(self):
        # Etsy price divisor <= 0
        payload_div_zero = json.dumps({
            "count": 1,
            "results": [{"listing_id": 1, "price": {"amount": 100, "divisor": 0, "currency_code": "USD"}}],
        }).encode()
        with self.assertRaisesRegex(ProductResponseError, "amount, divisor, currency"):
            self.etsy_adapter.parse(payload_div_zero, COLLECTED_AT)

        # Etsy price missing currency
        payload_no_curr = json.dumps({
            "count": 1,
            "results": [{"listing_id": 1, "price": {"amount": 100, "divisor": 100, "currency_code": " "}}],
        }).encode()
        with self.assertRaisesRegex(ProductResponseError, "amount, divisor, currency"):
            self.etsy_adapter.parse(payload_no_curr, COLLECTED_AT)

        # Etsy taxonomy_id not integer or < 1
        payload_bad_tax = json.dumps({
            "count": 1,
            "results": [{"listing_id": 1, "taxonomy_id": "not_an_int"}],
        }).encode()
        with self.assertRaisesRegex(ProductResponseError, "positive integer"):
            self.etsy_adapter.parse(payload_bad_tax, COLLECTED_AT)

        payload_neg_tax = json.dumps({
            "count": 1,
            "results": [{"listing_id": 1, "taxonomy_id": -5}],
        }).encode()
        with self.assertRaisesRegex(ProductResponseError, "positive integer"):
            self.etsy_adapter.parse(payload_neg_tax, COLLECTED_AT)

    def test_amazon_malformed_title_and_asin_errors(self):
        # Non-string displayValue
        payload_bad_title = json.dumps({
            "itemsResult": {"items": [{"asin": "B001", "itemInfo": {"title": {"displayValue": 12345}}}]}
        }).encode()
        with self.assertRaisesRegex(ProductResponseError, "Amazon item title must be a string"):
            self.amazon_adapter.parse(payload_bad_title, COLLECTED_AT)

        # Non-dict item
        payload_bad_item = json.dumps({
            "itemsResult": {"items": ["not_a_dict"]}
        }).encode()
        with self.assertRaisesRegex(ProductResponseError, "Amazon items must contain item objects"):
            self.amazon_adapter.parse(payload_bad_item, COLLECTED_AT)


if __name__ == "__main__":
    unittest.main()
