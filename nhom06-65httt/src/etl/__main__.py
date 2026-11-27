"""Command-line entry point for checking the ETL runtime."""

from .config import Settings
from .logging_config import configure_logging


def main() -> int:
    """Load configuration and report that the ETL foundation can start."""
    settings = Settings.from_env()
    logger = configure_logging(settings)
    logger.info(
        "ETL foundation started (environment=%s, log_level=%s)",
        settings.environment,
        settings.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
