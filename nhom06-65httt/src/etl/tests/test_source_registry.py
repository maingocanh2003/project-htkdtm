import unittest
from datetime import datetime, timezone
from dataclasses import fields

from etl.source_registry import (
    CollectionMetadata,
    Source,
    SourceGroup,
    SourceRegistry,
    SourceStatus,
    SourceType,
    create_project_source_registry,
)


def make_source(source_id="sample_api", source_type=SourceType.API):
    return Source(
        source_id=source_id,
        source_name="Sample source",
        source_type=source_type,
        base_url="https://example.test",
        status=SourceStatus.PLANNED,
        description="A test source.",
        source_group=SourceGroup.UN_COMTRADE,
    )


class SourceRegistryTests(unittest.TestCase):
    def test_register_and_retrieve_source(self):
        registry = SourceRegistry()
        source = make_source()

        registry.register(source)

        self.assertIs(registry.get("sample_api"), source)
        self.assertEqual(registry.list_sources(), (source,))

    def test_duplicate_source_id_is_rejected(self):
        registry = SourceRegistry()
        registry.register(make_source())

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(make_source())

    def test_unknown_source_lookup_raises_key_error(self):
        with self.assertRaises(KeyError):
            SourceRegistry().get("missing")

    def test_invalid_source_fields_and_credential_url_are_rejected(self):
        invalid_values = (
            {"source_id": "Bad Id"},
            {"source_name": " "},
            {"description": ""},
            {"base_url": "https://user:password@example.test"},
            {"base_url": "https://example.test/?api_key=secret"},
        )
        for overrides in invalid_values:
            with self.subTest(overrides=overrides):
                values = {
                    "source_id": "valid_id",
                    "source_name": "Valid source",
                    "source_type": SourceType.API,
                    "base_url": "https://example.test",
                    "status": SourceStatus.PLANNED,
                    "description": "Valid description.",
                    "source_group": SourceGroup.UN_COMTRADE,
                }
                values.update(overrides)
                with self.assertRaises(ValueError):
                    Source(**values)

    def test_source_has_no_credential_fields(self):
        field_names = {field.name for field in fields(Source)}

        self.assertNotIn("api_key", field_names)
        self.assertNotIn("password", field_names)

    def test_project_catalog_declares_groups_and_all_source_types(self):
        registry = create_project_source_registry()
        sources = registry.list_sources()

        self.assertEqual(len(sources), 9)  # updated for D9: +thegioigom, +goc_gom_viet
        self.assertEqual(
            {source.source_group for source in sources},
            set(SourceGroup),
        )
        self.assertEqual(
            {source.source_type for source in sources},
            set(SourceType),
        )
        expected = {
            "un_comtrade": (
                SourceGroup.UN_COMTRADE,
                SourceType.API,
                SourceStatus.ACTIVE,
                "https://comtradeapi.un.org",
            ),
            "itc_trade_map": (
                SourceGroup.ITC_TRADE_MAP,
                SourceType.FILE_DATASET,
                SourceStatus.PLANNED,
                "https://www.trademap.org",
            ),
            "google_trends": (
                SourceGroup.GOOGLE_TRENDS,
                SourceType.MANUAL,
                SourceStatus.ACTIVE,
                "https://trends.google.com",
            ),
            "etsy": (
                SourceGroup.MARKETPLACE_PRODUCTS,
                SourceType.API,
                SourceStatus.PLANNED,
                "https://openapi.etsy.com",
            ),
            "amazon": (
                SourceGroup.MARKETPLACE_PRODUCTS,
                SourceType.API,
                SourceStatus.PLANNED,
                "https://creatorsapi.amazon",
            ),
            "minh_long_1": (
                SourceGroup.DOMESTIC_SUPPLIER_CATALOGS,
                SourceType.FILE_DATASET,
                SourceStatus.ACTIVE,
                None,
            ),
            "bat_trang": (
                SourceGroup.DOMESTIC_SUPPLIER_CATALOGS,
                SourceType.FILE_DATASET,
                SourceStatus.ACTIVE,
                None,
            ),
            "thegioigom": (
                SourceGroup.DOMESTIC_SUPPLIER_CATALOGS,
                SourceType.API,
                SourceStatus.ACTIVE,
                "https://thegioigom.com",
            ),
            "goc_gom_viet": (
                SourceGroup.DOMESTIC_SUPPLIER_CATALOGS,
                SourceType.API,
                SourceStatus.PLANNED,
                "https://gocgomviet.com",
            ),
        }
        self.assertEqual(
            {
                source.source_id: (
                    source.source_group,
                    source.source_type,
                    source.status,
                    source.base_url,
                )
                for source in sources
            },
            expected,
        )
        self.assertTrue(
            all(
                source.source_name.strip() and source.description.strip()
                for source in sources
            )
        )

    def test_metadata_requires_known_source_and_api_endpoint(self):
        registry = create_project_source_registry()
        metadata = CollectionMetadata(
            collected_at=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
            source_id="un_comtrade",
            data_format="json",
            version="v1",
            endpoint="/public/v1/preview/C/A/HS",
        )

        registry.validate_metadata(metadata)

        unknown_source = CollectionMetadata(
            collected_at=metadata.collected_at,
            source_id="unknown",
            data_format="csv",
        )
        with self.assertRaises(KeyError):
            registry.validate_metadata(unknown_source)

        manual_source_metadata = CollectionMetadata(
            collected_at=metadata.collected_at,
            source_id="google_trends",
            data_format="csv",
            endpoint="/explore",
        )
        with self.assertRaisesRegex(ValueError, "only valid for API"):
            registry.validate_metadata(manual_source_metadata)

    def test_metadata_rejects_missing_timezone_or_format(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            CollectionMetadata(
                collected_at=datetime(2026, 1, 2),
                source_id="un_comtrade",
                data_format="json",
            )
        with self.assertRaisesRegex(ValueError, "data_format"):
            CollectionMetadata(
                collected_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                source_id="un_comtrade",
                data_format=" ",
            )

    def test_metadata_rejects_endpoint_with_embedded_credentials(self):
        with self.assertRaisesRegex(ValueError, "credentials"):
            CollectionMetadata(
                collected_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                source_id="un_comtrade",
                data_format="json",
                endpoint="https://user:password@example.test/api",
            )

    def test_register_and_validate_type_checks(self):
        registry = SourceRegistry()
        with self.assertRaisesRegex(TypeError, "source must be a Source"):
            registry.register("not_a_source")  # type: ignore

        with self.assertRaisesRegex(TypeError, "metadata must be CollectionMetadata"):
            registry.validate_metadata("not_metadata")  # type: ignore

    def test_invalid_source_enums_and_urls_are_rejected(self):
        base_kwargs = {
            "source_id": "valid_id",
            "source_name": "Valid Source",
            "source_type": SourceType.API,
            "base_url": "https://example.test",
            "status": SourceStatus.PLANNED,
            "description": "Valid description.",
            "source_group": SourceGroup.UN_COMTRADE,
        }

        # Invalid source_type enum
        with self.assertRaisesRegex(ValueError, "source_type must be a SourceType"):
            Source(**{**base_kwargs, "source_type": "api"})  # type: ignore

        # Invalid status enum
        with self.assertRaisesRegex(ValueError, "status must be a SourceStatus"):
            Source(**{**base_kwargs, "status": "planned"})  # type: ignore

        # Invalid source_group enum
        with self.assertRaisesRegex(ValueError, "source_group must be a SourceGroup"):
            Source(**{**base_kwargs, "source_group": "un_comtrade"})  # type: ignore

        # Invalid URL schemes / fragments / empty host
        with self.assertRaisesRegex(ValueError, "base_url must be an HTTP"):
            Source(**{**base_kwargs, "base_url": "ftp://example.test"})
        with self.assertRaisesRegex(ValueError, "base_url must be an HTTP"):
            Source(**{**base_kwargs, "base_url": "https://example.test#fragment"})
        with self.assertRaisesRegex(ValueError, "base_url must be an HTTP"):
            Source(**{**base_kwargs, "base_url": "http://"})

    def test_collection_metadata_validation_edge_cases(self):
        valid_time = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)

        # collected_at must be datetime
        with self.assertRaisesRegex(ValueError, "collected_at must be a datetime"):
            CollectionMetadata(
                collected_at="2026-01-02T03:04:00Z",  # type: ignore
                source_id="un_comtrade",
                data_format="json",
            )

        # source_id must not be empty
        with self.assertRaisesRegex(ValueError, "source_id must not be empty"):
            CollectionMetadata(
                collected_at=valid_time,
                source_id="   ",
                data_format="json",
            )

        # version must not be empty when provided
        with self.assertRaisesRegex(ValueError, "version must not be empty"):
            CollectionMetadata(
                collected_at=valid_time,
                source_id="un_comtrade",
                data_format="json",
                version="   ",
            )

        # endpoint must not be empty when provided
        with self.assertRaisesRegex(ValueError, "endpoint must not be empty"):
            CollectionMetadata(
                collected_at=valid_time,
                source_id="un_comtrade",
                data_format="json",
                endpoint="   ",
            )

        # relative endpoint must not contain query or fragment
        with self.assertRaisesRegex(ValueError, "endpoint must not contain a query or fragment"):
            CollectionMetadata(
                collected_at=valid_time,
                source_id="un_comtrade",
                data_format="json",
                endpoint="/api/v1/preview?param=1",
            )
        with self.assertRaisesRegex(ValueError, "endpoint must not contain a query or fragment"):
            CollectionMetadata(
                collected_at=valid_time,
                source_id="un_comtrade",
                data_format="json",
                endpoint="/api/v1/preview#section",
            )


if __name__ == "__main__":
    unittest.main()
