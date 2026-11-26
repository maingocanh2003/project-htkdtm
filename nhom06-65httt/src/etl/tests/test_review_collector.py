import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from etl.http_client import HttpResponse
from etl.raw_storage import CollectionStatus, RawStorage
from etl.review_collector import (
    EtsyReviewCollector,
    ReviewCollectionError,
)
from etl.source_registry import (
    SourceRegistry,
    SourceStatus,
    create_project_source_registry,
)


FIXTURES = Path(__file__).parent / "fixtures"
LISTING_ID = 987654321
API_KEY = "fixture-key:fixture-secret"


def create_active_etsy_registry():
    registry = SourceRegistry()
    for source in create_project_source_registry().list_sources():
        if source.source_id == "etsy":
            source = replace(source, status=SourceStatus.ACTIVE)
        registry.register(source)
    return registry


class EtsyReviewCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.registry = create_active_etsy_registry()
        self.storage = RawStorage(Path(self.temp_dir.name), self.registry)
        self.http_client = Mock()
        self.collector = EtsyReviewCollector(
            self.http_client,
            self.storage,
            self.registry,
            API_KEY,
            page_size=1,
        )

    def test_collects_pages_and_preserves_review_text_and_raw_provenance(self):
        first_payload = (
            FIXTURES / "etsy_listing_reviews_page_0.json"
        ).read_bytes()
        second_payload = (
            FIXTURES / "etsy_listing_reviews_page_1.json"
        ).read_bytes()
        self.http_client.get.side_effect = [
            HttpResponse(200, {}, first_payload, "https://openapi.etsy.com/reviews"),
            HttpResponse(200, {}, second_payload, "https://openapi.etsy.com/reviews"),
        ]

        result = self.collector.collect_listing(LISTING_ID)

        self.assertEqual(result.status, CollectionStatus.SUCCESS)
        self.assertEqual(result.reported_count, 2)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(len(result.raw_collection_ids), 2)
        self.assertEqual(result.records[0].source_id, "etsy")
        self.assertIsNone(result.records[0].source_review_id)
        self.assertEqual(result.records[0].product_reference, str(LISTING_ID))
        self.assertEqual(
            result.records[0].review_text,
            "  Raw\nreview — synthetic fixture. ",
        )
        self.assertEqual(result.records[0].rating, 5)
        self.assertEqual(
            result.records[0].reviewed_at,
            datetime.fromtimestamp(1760000000, timezone.utc),
        )
        self.assertIsNone(result.records[0].review_url)
        self.assertIsNone(result.records[1].review_text)

        endpoint = (
            "https://openapi.etsy.com"
            f"/v3/application/listings/{LISTING_ID}/reviews"
        )
        self.assertEqual(
            [call.args[0] for call in self.http_client.get.call_args_list],
            [endpoint, endpoint],
        )
        self.assertEqual(
            [
                call.kwargs["params"]
                for call in self.http_client.get.call_args_list
            ],
            [
                {"limit": 1, "offset": 0},
                {"limit": 1, "offset": 1},
            ],
        )
        self.assertTrue(
            all(
                call.kwargs["headers"] == {"x-api-key": API_KEY}
                for call in self.http_client.get.call_args_list
            )
        )

        for collection_id, payload, expected_offset in zip(
            result.raw_collection_ids,
            (first_payload, second_payload),
            (0, 1),
        ):
            self.assertEqual(
                self.storage.read_payload("etsy", collection_id),
                payload,
            )
            manifest = self.storage.read_manifest("etsy", collection_id)
            self.assertEqual(manifest["metadata"]["source_id"], "etsy")
            self.assertEqual(manifest["metadata"]["status"], "success")
            self.assertEqual(
                manifest["metadata"]["endpoint"],
                f"/v3/application/listings/{LISTING_ID}/reviews",
            )
            self.assertEqual(
                manifest["metadata"]["request_parameters"],
                {
                    "listing_id": LISTING_ID,
                    "limit": 1,
                    "offset": expected_offset,
                },
            )

    def test_planned_source_cannot_make_live_requests(self):
        planned_registry = create_project_source_registry()
        storage = RawStorage(Path(self.temp_dir.name), planned_registry)

        with self.assertRaisesRegex(ValueError, "must be active"):
            EtsyReviewCollector(
                self.http_client,
                storage,
                planned_registry,
                API_KEY,
            )

        self.http_client.get.assert_not_called()

    def test_api_key_can_be_loaded_from_environment_without_a_default(self):
        with self.assertRaisesRegex(ValueError, "ETSY_API_KEY"):
            EtsyReviewCollector.from_env(
                self.http_client,
                self.storage,
                self.registry,
                environ={},
            )

        collector = EtsyReviewCollector.from_env(
            self.http_client,
            self.storage,
            self.registry,
            environ={"ETSY_API_KEY": API_KEY},
        )
        self.assertIsInstance(collector, EtsyReviewCollector)

    def test_invalid_listing_id_does_not_issue_a_request(self):
        for listing_id in (0, -1, True, "987654321"):
            with self.subTest(listing_id=listing_id):
                with self.assertRaisesRegex(ValueError, "listing_id"):
                    self.collector.collect_listing(listing_id)

        self.http_client.get.assert_not_called()

    def test_malformed_page_is_preserved_as_failed_raw_data(self):
        payload = b'{"count": 1, "results": [{"listing_id": 987654321}]}'
        self.http_client.get.return_value = HttpResponse(
            200,
            {},
            payload,
            "https://openapi.etsy.com/reviews",
        )

        with self.assertRaisesRegex(
            ReviewCollectionError,
            "rating",
        ) as raised:
            self.collector.collect_listing(LISTING_ID)

        self.assertEqual(
            self.storage.read_payload("etsy", raised.exception.collection_id),
            payload,
        )
        manifest = self.storage.read_manifest(
            "etsy",
            raised.exception.collection_id,
        )
        self.assertEqual(manifest["metadata"]["status"], "failed")

    def test_response_for_a_different_product_is_rejected(self):
        payload = (
            b'{"count": 1, "results": [{"listing_id": 123, "rating": 5,'
            b' "review": "synthetic"}]}'
        )
        self.http_client.get.return_value = HttpResponse(
            200,
            {},
            payload,
            "https://openapi.etsy.com/reviews",
        )

        with self.assertRaisesRegex(
            ReviewCollectionError,
            "does not match",
        ):
            self.collector.collect_listing(LISTING_ID)

    def test_page_size_and_api_key_validation(self):
        with self.assertRaisesRegex(ValueError, "page_size must be an integer between 1 and 100"):
            EtsyReviewCollector(self.http_client, self.storage, self.registry, API_KEY, page_size=0)
        with self.assertRaisesRegex(ValueError, "page_size must be an integer between 1 and 100"):
            EtsyReviewCollector(self.http_client, self.storage, self.registry, API_KEY, page_size=101)
        with self.assertRaisesRegex(ValueError, "page_size must be an integer between 1 and 100"):
            EtsyReviewCollector(self.http_client, self.storage, self.registry, API_KEY, page_size="10")  # type: ignore
        with self.assertRaisesRegex(ValueError, "api_key must not be empty"):
            EtsyReviewCollector(self.http_client, self.storage, self.registry, "   ")

    def test_malformed_page_envelope_errors(self):
        # Non-dict body
        self.http_client.get.return_value = HttpResponse(200, {}, b'["not_dict"]', "https://openapi.etsy.com/reviews")
        with self.assertRaisesRegex(ReviewCollectionError, "must be a JSON object"):
            self.collector.collect_listing(LISTING_ID)

        # Negative count
        self.http_client.get.return_value = HttpResponse(200, {}, b'{"count": -1, "results": []}', "https://openapi.etsy.com/reviews")
        with self.assertRaisesRegex(ReviewCollectionError, "valid count and results list"):
            self.collector.collect_listing(LISTING_ID)

        # Results is not a list
        self.http_client.get.return_value = HttpResponse(200, {}, b'{"count": 0, "results": "not_list"}', "https://openapi.etsy.com/reviews")
        with self.assertRaisesRegex(ReviewCollectionError, "valid count and results list"):
            self.collector.collect_listing(LISTING_ID)


if __name__ == "__main__":
    unittest.main()
