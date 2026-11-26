"""Raw international-trade collection adapters for documented project sources."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from .http_client import HttpClient
from .raw_storage import CollectionStatus, RawStorage
from .source_registry import (
    CollectionMetadata,
    SourceGroup,
    SourceRegistry,
    SourceType,
)


_COMTRADE_PREVIEW_PATH = "/public/v1/preview/C/A/HS"
_COMTRADE_PREVIEW_LIMIT = 500
_COMTRADE_API_VERSION = "public/v1"


class TradeFlow(str, Enum):
    """Project trade flows mapped to the official UN Comtrade codes."""

    IMPORT = "M"
    EXPORT = "X"


@dataclass(frozen=True)
class TradeCollectionResult:
    """Validated response envelope and the ID of its preserved raw payload."""

    collection_id: str
    reported_count: int
    record_count: int
    status: CollectionStatus
    records: Tuple[Mapping[str, Any], ...]


class TradeResponseError(ValueError):
    """Raised when an API response cannot be used as a trade data envelope."""

    def __init__(
        self, message: str, collection_id: Optional[str] = None
    ) -> None:
        if collection_id is not None:
            message = f"{message}; raw collection_id={collection_id}"
        super().__init__(message)
        self.collection_id = collection_id


class UNComtradeCollector:
    """Collect one annual product selection through the keyless preview API.

    The documented preview limits results to 500 and does not specify pagination.
    """

    def __init__(
        self,
        http_client: HttpClient,
        raw_storage: RawStorage,
        source_registry: SourceRegistry,
    ) -> None:
        source = source_registry.get("un_comtrade")
        if source.source_group is not SourceGroup.UN_COMTRADE:
            raise ValueError("un_comtrade source has an unexpected source group")
        if source.source_type is not SourceType.API or source.base_url is None:
            raise ValueError("un_comtrade must be registered as an API source")
        self._http_client = http_client
        self._raw_storage = raw_storage
        self._base_url = source.base_url.rstrip("/")

    def collect(
        self,
        reporter_code: str,
        hs_code: str,
        year: int,
        flow: TradeFlow,
        partner_code: Optional[str] = None,
    ) -> TradeCollectionResult:
        """Fetch one reporter/product/year/flow selection and preserve its raw JSON."""
        self._validate_numeric_code(reporter_code, "reporter_code")
        self._validate_numeric_code(hs_code, "hs_code")
        if partner_code is not None:
            self._validate_numeric_code(partner_code, "partner_code")
        if type(year) is not int or not 1000 <= year <= 9999:
            raise ValueError("year must be a four-digit integer")
        if not isinstance(flow, TradeFlow):
            raise ValueError("flow must be a TradeFlow")

        request_parameters: Dict[str, str] = {
            "reporterCode": reporter_code,
            "period": str(year),
            "cmdCode": hs_code,
            "flowCode": flow.value,
        }
        if partner_code is not None:
            request_parameters["partnerCode"] = partner_code

        endpoint = f"{self._base_url}{_COMTRADE_PREVIEW_PATH}"
        response = self._http_client.get(endpoint, params=request_parameters)
        metadata = CollectionMetadata(
            collected_at=datetime.now(timezone.utc),
            source_id="un_comtrade",
            data_format="json",
            version=_COMTRADE_API_VERSION,
            endpoint=_COMTRADE_PREVIEW_PATH,
        )

        try:
            envelope, records = self._decode_response(response.body)
        except TradeResponseError as error:
            collection_id = self._raw_storage.save(
                response.body,
                metadata,
                request_parameters,
                status=CollectionStatus.FAILED,
            )
            raise TradeResponseError(error.args[0], collection_id) from error

        reported_count = envelope["count"]
        is_potentially_truncated = (
            len(records) >= _COMTRADE_PREVIEW_LIMIT
            or reported_count > len(records)
        )
        status = (
            CollectionStatus.PARTIAL
            if is_potentially_truncated
            else CollectionStatus.SUCCESS
        )
        collection_id = self._raw_storage.save(
            response.body,
            metadata,
            request_parameters,
            status=status,
        )
        return TradeCollectionResult(
            collection_id=collection_id,
            reported_count=reported_count,
            record_count=len(records),
            status=status,
            records=tuple(records),
        )

    @staticmethod
    def _validate_numeric_code(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
            raise ValueError(f"{field_name} must contain only ASCII digits")

    @staticmethod
    def _decode_response(
        payload: bytes,
    ) -> Tuple[Dict[str, Any], list[Dict[str, Any]]]:
        try:
            envelope = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TradeResponseError(
                "UN Comtrade response is not valid JSON"
            ) from error

        if not isinstance(envelope, dict):
            raise TradeResponseError("UN Comtrade response must be a JSON object")
        api_error = envelope.get("error", "")
        if api_error:
            raise TradeResponseError(f"UN Comtrade returned an API error: {api_error}")
        count = envelope.get("count")
        records = envelope.get("data")
        if type(count) is not int or count < 0:
            raise TradeResponseError("response count must be a nonnegative integer")
        if not isinstance(records, list) or not all(
            isinstance(record, dict) for record in records
        ):
            raise TradeResponseError("response data must be a list of objects")
        if count < len(records):
            raise TradeResponseError("response count is smaller than its data list")
        return envelope, records


class ITCTradeMapFileAdapter:
    """Preserve a locally supplied ITC export without assuming its file schema."""

    def __init__(
        self, raw_storage: RawStorage, source_registry: SourceRegistry
    ) -> None:
        source = source_registry.get("itc_trade_map")
        if source.source_group is not SourceGroup.ITC_TRADE_MAP:
            raise ValueError("itc_trade_map source has an unexpected source group")
        if source.source_type is not SourceType.FILE_DATASET:
            raise ValueError("itc_trade_map must be registered as a file dataset")
        self._raw_storage = raw_storage

    def ingest(self, payload: bytes, data_format: str) -> str:
        """Store supplied file bytes and provenance without parsing or transforming."""
        metadata = CollectionMetadata(
            collected_at=datetime.now(timezone.utc),
            source_id="itc_trade_map",
            data_format=data_format,
        )
        return self._raw_storage.save(
            payload,
            metadata,
            {"ingestion_method": "local_file"},
            status=CollectionStatus.SUCCESS,
        )
