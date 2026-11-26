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

    def test_custom_http_settings_are_parsed_correctly(self):
        settings = Settings.from_env(
            {
                "ETL_HTTP_TIMEOUT_SECONDS": " 15.5 ",
                "ETL_HTTP_MAX_RETRIES": " 5 ",
                "ETL_HTTP_BACKOFF_SECONDS": " 1.25 ",
                "ETL_HTTP_MAX_RETRY_DELAY_SECONDS": " 45.0 ",
            }
        )
        self.assertEqual(settings.http_timeout_seconds, 15.5)
        self.assertEqual(settings.http_max_retries, 5)
        self.assertEqual(settings.http_backoff_seconds, 1.25)
        self.assertEqual(settings.http_max_retry_delay_seconds, 45.0)

    def test_invalid_http_timeout_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_TIMEOUT_SECONDS"):
            Settings.from_env({"ETL_HTTP_TIMEOUT_SECONDS": "0"})
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_TIMEOUT_SECONDS"):
            Settings.from_env({"ETL_HTTP_TIMEOUT_SECONDS": "-5"})
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_TIMEOUT_SECONDS"):
            Settings.from_env({"ETL_HTTP_TIMEOUT_SECONDS": "fast"})
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_TIMEOUT_SECONDS"):
            Settings.from_env({"ETL_HTTP_TIMEOUT_SECONDS": "nan"})

    def test_invalid_http_max_retries_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_MAX_RETRIES"):
            Settings.from_env({"ETL_HTTP_MAX_RETRIES": "three"})
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_MAX_RETRIES"):
            Settings.from_env({"ETL_HTTP_MAX_RETRIES": "-1"})
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_MAX_RETRIES"):
            Settings.from_env({"ETL_HTTP_MAX_RETRIES": "11"})

    def test_invalid_http_backoff_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_BACKOFF_SECONDS"):
            Settings.from_env({"ETL_HTTP_BACKOFF_SECONDS": "-0.1"})

    def test_invalid_http_max_retry_delay_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_MAX_RETRY_DELAY_SECONDS"):
            Settings.from_env({"ETL_HTTP_MAX_RETRY_DELAY_SECONDS": "0"})
        with self.assertRaisesRegex(ValueError, "ETL_HTTP_MAX_RETRY_DELAY_SECONDS"):
            Settings.from_env({"ETL_HTTP_MAX_RETRY_DELAY_SECONDS": "-10"})


if __name__ == "__main__":
    unittest.main()
