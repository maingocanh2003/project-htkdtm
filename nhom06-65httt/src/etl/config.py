"""Environment-backed configuration for the ETL foundation."""

import math
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


@dataclass(frozen=True)
class Settings:
    """Runtime settings that do not contain source or database credentials."""

    environment: str = "development"
    log_level: str = "INFO"
    raw_data_dir: Path = Path("data/raw")
    http_timeout_seconds: float = 10.0
    http_max_retries: int = 3
    http_backoff_seconds: float = 0.5
    http_max_retry_delay_seconds: float = 60.0

    @classmethod
    def from_env(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> "Settings":
        """Build settings from ETL_* variables, or from the process environment."""
        values = os.environ if environ is None else environ
        environment = values.get("ETL_ENV", "development").strip()
        if not environment:
            raise ValueError("ETL_ENV must not be empty")

        log_level = values.get("ETL_LOG_LEVEL", "INFO").strip().upper()
        if not isinstance(logging.getLevelName(log_level), int):
            raise ValueError("ETL_LOG_LEVEL must be a recognized logging level")

        raw_data_dir_value = values.get("ETL_RAW_DATA_DIR", "data/raw").strip()
        if not raw_data_dir_value:
            raise ValueError("ETL_RAW_DATA_DIR must not be empty")

        http_timeout_seconds = _positive_float(
            values, "ETL_HTTP_TIMEOUT_SECONDS", 10.0
        )
        http_max_retries_value = values.get("ETL_HTTP_MAX_RETRIES", "3").strip()
        try:
            http_max_retries = int(http_max_retries_value)
        except ValueError as error:
            raise ValueError("ETL_HTTP_MAX_RETRIES must be an integer") from error
        if not 0 <= http_max_retries <= 10:
            raise ValueError("ETL_HTTP_MAX_RETRIES must be between 0 and 10")
        http_backoff_seconds = _nonnegative_float(
            values, "ETL_HTTP_BACKOFF_SECONDS", 0.5
        )
        http_max_retry_delay_seconds = _positive_float(
            values, "ETL_HTTP_MAX_RETRY_DELAY_SECONDS", 60.0
        )

        return cls(
            environment=environment,
            log_level=log_level,
            raw_data_dir=Path(raw_data_dir_value),
            http_timeout_seconds=http_timeout_seconds,
            http_max_retries=http_max_retries,
            http_backoff_seconds=http_backoff_seconds,
            http_max_retry_delay_seconds=http_max_retry_delay_seconds,
        )


def _positive_float(
    values: Mapping[str, str], key: str, default: float
) -> float:
    value = _parse_float(values, key, default)
    if value <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return value


def _nonnegative_float(
    values: Mapping[str, str], key: str, default: float
) -> float:
    value = _parse_float(values, key, default)
    if value < 0:
        raise ValueError(f"{key} must not be negative")
    return value


def _parse_float(values: Mapping[str, str], key: str, default: float) -> float:
    raw_value = values.get(key, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{key} must be a number") from error
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value
