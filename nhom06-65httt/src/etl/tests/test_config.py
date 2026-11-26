import unittest
from pathlib import Path

from etl.config import Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_are_used_when_environment_is_empty(self):
        settings = Settings.from_env({})

        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.raw_data_dir, Path("data/raw"))

    def test_raw_data_directory_can_be_configured(self):
        settings = Settings.from_env(
            {"ETL_RAW_DATA_DIR": "  local/raw-data  "}
        )

        self.assertEqual(settings.raw_data_dir, Path("local/raw-data"))

    def test_empty_raw_data_directory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ETL_RAW_DATA_DIR"):
            Settings.from_env({"ETL_RAW_DATA_DIR": " "})

    def test_environment_values_are_trimmed_and_log_level_normalized(self):
        settings = Settings.from_env(
            {"ETL_ENV": "  test ", "ETL_LOG_LEVEL": " debug "}
        )

        self.assertEqual(settings.environment, "test")
        self.assertEqual(settings.log_level, "DEBUG")

    def test_empty_environment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ETL_ENV"):
            Settings.from_env({"ETL_ENV": " "})

    def test_unknown_log_level_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ETL_LOG_LEVEL"):
            Settings.from_env({"ETL_LOG_LEVEL": "verbose-ish"})


if __name__ == "__main__":
    unittest.main()
