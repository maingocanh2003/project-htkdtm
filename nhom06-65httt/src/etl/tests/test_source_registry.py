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
        sources = create_project_source_registry().list_sources()

        self.assertEqual(len(sources), 7)
        self.assertEqual(
            {source.source_group for source in sources},
            set(SourceGroup),
        )
        self.assertEqual(
            {source.source_type for source in sources},
            set(SourceType),
        )
        self.assertTrue(all(source.status is SourceStatus.PLANNED for source in sources))

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


if __name__ == "__main__":
    unittest.main()
