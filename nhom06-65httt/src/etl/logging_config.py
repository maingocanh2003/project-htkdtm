"""Shared logging setup for ETL commands and modules."""

import logging

from .config import Settings


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure and return the shared ETL logger without duplicate handlers."""
    logger = logging.getLogger("etl")
    logger.setLevel(settings.log_level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s"
            )
        )
        logger.addHandler(handler)

    return logger
