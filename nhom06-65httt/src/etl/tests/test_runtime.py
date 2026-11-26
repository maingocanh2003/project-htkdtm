import unittest
from unittest.mock import Mock, call, patch

from etl import __main__
from etl.config import Settings
from etl.logging_config import configure_logging


class LoggingConfigurationTests(unittest.TestCase):
    def test_repeated_configuration_does_not_add_duplicate_handlers(self):
        logger = Mock()
        logger.handlers = []
        logger.addHandler.side_effect = logger.handlers.append

        with patch("etl.logging_config.logging.getLogger", return_value=logger):
            configured_logger = configure_logging(
                Settings(environment="test", log_level="WARNING")
            )
            configure_logging(Settings(log_level="DEBUG"))

        self.assertIs(configured_logger, logger)
        self.assertEqual(logger.addHandler.call_count, 1)
        self.assertEqual(
            logger.setLevel.call_args_list,
            [call("WARNING"), call("DEBUG")],
        )
        self.assertFalse(logger.propagate)


class EntryPointTests(unittest.TestCase):
    def test_main_loads_environment_and_logs_startup(self):
        logger = Mock()

        with (
            patch.dict(
                "os.environ",
                {"ETL_ENV": "test", "ETL_LOG_LEVEL": "WARNING"},
                clear=True,
            ),
            patch.object(__main__, "configure_logging", return_value=logger),
        ):
            result = __main__.main()

        self.assertEqual(result, 0)
        logger.info.assert_called_once_with(
            "ETL foundation started (environment=%s, log_level=%s)",
            "test",
            "WARNING",
        )


if __name__ == "__main__":
    unittest.main()
