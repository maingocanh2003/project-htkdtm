"""Environment-backed configuration for the ETL foundation."""

import logging
import os
from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class Settings:
    """Runtime settings that do not contain source or database credentials."""

    environment: str = "development"
    log_level: str = "INFO"

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

        return cls(environment=environment, log_level=log_level)
