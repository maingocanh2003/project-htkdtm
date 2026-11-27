"""Domestic supplier and product data collector for Vietnamese ceramic sources.

Phân biệt rõ:
- Thông tin doanh nghiệp (SupplierRecord)
- Thông tin sản phẩm (SupplierProductRecord)
- Thông tin thương mại (CommercialInfo, chỉ ghi nhận khi nguồn cung cấp)

Không tự khẳng định năng lực sản xuất, công suất hoặc lead time
nếu nguồn không cung cấp.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .http_client import HttpClient
from .raw_storage import CollectionStatus, RawStorage
from .source_registry import (
    CollectionMetadata,
    SourceGroup,
    SourceRegistry,
    SourceStatus,
    SourceType,
)


# ---------------------------------------------------------------------------
# Source constants
# ---------------------------------------------------------------------------

_MINH_LONG_SOURCE_ID = "minh_long_1"
_BAT_TRANG_SOURCE_ID = "bat_trang"
_THEGIOIGOM_SOURCE_ID = "thegioigom"
_GOC_GOM_SOURCE_ID = "goc_gom_viet"

_DATA_FORMAT = "json"
_COLLECTOR_VERSION = "d9/v1"


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommercialInfo:
    """Thông tin thương mại — chỉ điền khi nguồn cung cấp rõ ràng.

    Không tự suy diễn giá, MOQ, lead_time hay công suất từ ngữ cảnh.
    """

    price_vnd: Optional[Decimal]       # giá niêm yết từ nguồn
    currency: Optional[str]            # mã tiền tệ, ví dụ "VND"
    moq: Optional[int]                 # đơn hàng tối thiểu (source-provided)
    lead_time_days: Optional[int]      # thời gian sản xuất (source-provided)
    wholesale_available: Optional[bool]


@dataclass(frozen=True)
class SupplierProductRecord:
    """Thông tin sản phẩm thu thập được từ catalog nhà cung cấp nội địa."""

    source_id: str
    source_product_id: str            # ID hoặc SKU từ nguồn
    product_url: Optional[str]
    name: Optional[str]
    description: Optional[str]
    category: Optional[str]
    material: Optional[str]           # vật liệu (gốm, sứ, …)
    origin_region: Optional[str]      # vùng sản xuất (Bát Tràng, Minh Long…)
    commercial: CommercialInfo


@dataclass(frozen=True)
class SupplierRecord:
    """Thông tin doanh nghiệp nhà cung cấp nội địa."""

    source_id: str
    supplier_name: str
    tax_code: Optional[str]            # Mã số thuế (nếu có)
    address: Optional[str]
    province: Optional[str]
    website: Optional[str]
    phone: Optional[str]
    business_type: Optional[str]       # sản xuất, phân phối, xuất khẩu…
    # Năng lực sản xuất – chỉ ghi nhận khi nguồn cung cấp
    declared_capacity_note: Optional[str]


@dataclass(frozen=True)
class DomesticSupplierCollectionResult:
    """Kết quả thu thập một phiên: nhà cung cấp + danh sách sản phẩm."""

    collection_id: str
    source_id: str
    supplier: Optional[SupplierRecord]
    products: Tuple[SupplierProductRecord, ...]
    record_count: int
    status: CollectionStatus
    collected_at: datetime
    source_url: str                    # URL thực tế đã thu thập


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DomesticSupplierResponseError(ValueError):
    """Raised khi response không parse được hoặc không phù hợp schema."""

    def __init__(
        self, message: str, collection_id: Optional[str] = None
    ) -> None:
        if collection_id is not None:
            message = f"{message}; raw collection_id={collection_id}"
        super().__init__(message)
        self.collection_id = collection_id


# ---------------------------------------------------------------------------
# Collector — HTTP-based (nguồn công khai, không cần API key)
# ---------------------------------------------------------------------------


class DomesticSupplierHttpCollector:
    """Thu thập catalog sản phẩm từ website công khai của nhà cung cấp nội địa.

    Chỉ dùng HTTP GET trên endpoint công khai (không cần key).
    Mỗi source phải ở trạng thái ACTIVE trước khi collect.
    """

    def __init__(
        self,
        source_id: str,
        http_client: HttpClient,
        raw_storage: RawStorage,
        source_registry: SourceRegistry,
    ) -> None:
        source = source_registry.get(source_id)
        if source.source_group is not SourceGroup.DOMESTIC_SUPPLIER_CATALOGS:
            raise ValueError(
                f"{source_id} is not in DOMESTIC_SUPPLIER_CATALOGS group"
            )
        if source.source_type is not SourceType.API or source.base_url is None:
            raise ValueError(
                f"{source_id} must be registered as an API source with a base_url"
            )
        if source.status is not SourceStatus.ACTIVE:
            raise ValueError(
                f"{source_id} source must be ACTIVE before collection"
            )
        self._source_id = source_id
        self._base_url = source.base_url.rstrip("/")
        self._http_client = http_client
        self._raw_storage = raw_storage

    def collect_products(
        self,
        endpoint: str,
        request_parameters: Optional[Mapping[str, object]] = None,
    ) -> DomesticSupplierCollectionResult:
        """Fetch sản phẩm từ endpoint và lưu raw payload + provenance.

        Args:
            endpoint: đường dẫn tương đối (ví dụ "/api/products") hoặc
                      URL đầy đủ cùng origin.
            request_parameters: query params bổ sung (trang, danh mục…).

        Returns:
            DomesticSupplierCollectionResult chứa records đã parse và
            collection_id dùng để đọc lại raw payload.
        """
        if not endpoint or not isinstance(endpoint, str):
            raise ValueError("endpoint must be a non-empty string")
        if endpoint.startswith("/"):
            request_url = f"{self._base_url}{endpoint}"
        else:
            request_url = endpoint

        params = dict(request_parameters) if request_parameters else {}
        response = self._http_client.get(request_url, params=params or None)

        metadata = CollectionMetadata(
            collected_at=datetime.now(timezone.utc),
            source_id=self._source_id,
            data_format=_DATA_FORMAT,
            version=_COLLECTOR_VERSION,
            endpoint=endpoint if endpoint.startswith("/") else None,
        )
        full_params: Dict[str, Any] = {
            "endpoint": endpoint,
            **{k: str(v) for k, v in params.items()},
        }

        try:
            products, supplier = _parse_supplier_response(
                response.body, self._source_id
            )
        except DomesticSupplierResponseError as parse_error:
            collection_id = self._raw_storage.save(
                response.body,
                metadata,
                full_params,
                status=CollectionStatus.FAILED,
            )
            raise DomesticSupplierResponseError(
                parse_error.args[0], collection_id
            ) from parse_error

        collection_id = self._raw_storage.save(
            response.body,
            metadata,
            full_params,
            status=CollectionStatus.SUCCESS,
        )
        return DomesticSupplierCollectionResult(
            collection_id=collection_id,
            source_id=self._source_id,
            supplier=supplier,
            products=tuple(products),
            record_count=len(products),
            status=CollectionStatus.SUCCESS,
            collected_at=metadata.collected_at,
            source_url=response.url,
        )


# ---------------------------------------------------------------------------
# File-based ingest adapter (dùng khi nhà cung cấp gửi file/catalog)
# ---------------------------------------------------------------------------


class DomesticSupplierFileAdapter:
    """Nhận file catalog từ nhà cung cấp và lưu raw + provenance.

    Không parse schema — giữ bytes nguyên vẹn.
    """

    def __init__(
        self,
        source_id: str,
        raw_storage: RawStorage,
        source_registry: SourceRegistry,
    ) -> None:
        source = source_registry.get(source_id)
        if source.source_group is not SourceGroup.DOMESTIC_SUPPLIER_CATALOGS:
            raise ValueError(
                f"{source_id} is not in DOMESTIC_SUPPLIER_CATALOGS group"
            )
        self._source_id = source_id
        self._raw_storage = raw_storage

    def ingest(
        self,
        payload: bytes,
        data_format: str,
        origin_url: Optional[str] = None,
    ) -> str:
        """Lưu bytes catalog và provenance; trả về collection_id."""
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        if not data_format or not isinstance(data_format, str):
            raise ValueError("data_format must be a non-empty string")

        metadata = CollectionMetadata(
            collected_at=datetime.now(timezone.utc),
            source_id=self._source_id,
            data_format=data_format,
            version=_COLLECTOR_VERSION,
        )
        params: Dict[str, Any] = {"ingestion_method": "local_file"}
        if origin_url is not None:
            params["origin_url"] = origin_url
        return self._raw_storage.save(
            payload,
            metadata,
            params,
            status=CollectionStatus.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Response parser — nhận JSON từ nguồn theo schema D9
# ---------------------------------------------------------------------------


def _parse_supplier_response(
    payload: bytes,
    source_id: str,
) -> Tuple[List[SupplierProductRecord], Optional[SupplierRecord]]:
    """Parse JSON response theo schema D9.

    Schema mong đợi (tất cả trường đều optional ngoài source_product_id):
    {
      "supplier": { ... },   // optional — thông tin doanh nghiệp
      "products": [          // list sản phẩm
        {
          "source_product_id": "...",
          "name": "...",
          "description": "...",
          "product_url": "...",
          "category": "...",
          "material": "...",
          "origin_region": "...",
          "price_vnd": 150000,         // chỉ khi nguồn cung cấp
          "currency": "VND",
          "moq": 10,                   // chỉ khi nguồn cung cấp
          "lead_time_days": 7,         // chỉ khi nguồn cung cấp
          "wholesale_available": true
        }
      ]
    }
    """
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    try:
        body = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomesticSupplierResponseError(
            "response is not valid JSON"
        ) from exc

    if not isinstance(body, dict):
        raise DomesticSupplierResponseError(
            "response must be a JSON object"
        )

    supplier = _parse_supplier_block(body.get("supplier"), source_id)

    products_raw = body.get("products")
    if products_raw is None:
        products_raw = []
    if not isinstance(products_raw, list):
        raise DomesticSupplierResponseError(
            "products must be a JSON array"
        )

    products = [
        _parse_product(item, source_id, index)
        for index, item in enumerate(products_raw)
    ]
    return products, supplier


def _parse_supplier_block(
    block: Any, source_id: str
) -> Optional[SupplierRecord]:
    if block is None:
        return None
    if not isinstance(block, dict):
        raise DomesticSupplierResponseError(
            "supplier block must be a JSON object"
        )
    supplier_name = block.get("supplier_name", "")
    if not isinstance(supplier_name, str) or not supplier_name.strip():
        raise DomesticSupplierResponseError(
            "supplier.supplier_name must be a non-empty string"
        )
    tax_code = _optional_str(block.get("tax_code"), "supplier.tax_code")
    if tax_code is not None and not re.fullmatch(r"[0-9\-]{10,14}", tax_code):
        raise DomesticSupplierResponseError(
            "supplier.tax_code must be a valid Vietnamese tax code (10-14 digits)"
        )
    return SupplierRecord(
        source_id=source_id,
        supplier_name=supplier_name.strip(),
        tax_code=tax_code,
        address=_optional_str(block.get("address"), "supplier.address"),
        province=_optional_str(block.get("province"), "supplier.province"),
        website=_optional_str(block.get("website"), "supplier.website"),
        phone=_optional_str(block.get("phone"), "supplier.phone"),
        business_type=_optional_str(
            block.get("business_type"), "supplier.business_type"
        ),
        # Năng lực sản xuất chỉ ghi nhận khi nguồn cung cấp — không suy diễn
        declared_capacity_note=_optional_str(
            block.get("declared_capacity_note"),
            "supplier.declared_capacity_note",
        ),
    )


def _parse_product(
    item: Any, source_id: str, index: int
) -> SupplierProductRecord:
    if not isinstance(item, dict):
        raise DomesticSupplierResponseError(
            f"products[{index}] must be a JSON object"
        )

    source_product_id = item.get("source_product_id")
    if not isinstance(source_product_id, str) or not source_product_id.strip():
        raise DomesticSupplierResponseError(
            f"products[{index}].source_product_id must be a non-empty string"
        )

    # Thông tin thương mại — chỉ ghi nhận khi nguồn cung cấp
    commercial = _parse_commercial(item, index)

    return SupplierProductRecord(
        source_id=source_id,
        source_product_id=source_product_id.strip(),
        product_url=_optional_str(item.get("product_url"), f"products[{index}].product_url"),
        name=_optional_str(item.get("name"), f"products[{index}].name"),
        description=_optional_str(
            item.get("description"), f"products[{index}].description"
        ),
        category=_optional_str(item.get("category"), f"products[{index}].category"),
        material=_optional_str(item.get("material"), f"products[{index}].material"),
        origin_region=_optional_str(
            item.get("origin_region"), f"products[{index}].origin_region"
        ),
        commercial=commercial,
    )


def _parse_commercial(item: Dict[str, Any], index: int) -> CommercialInfo:
    """Parse thông tin thương mại — không suy diễn khi trường vắng."""
    price_raw = item.get("price_vnd")
    price_vnd: Optional[Decimal] = None
    if price_raw is not None:
        try:
            price_vnd = Decimal(str(price_raw))
        except InvalidOperation as exc:
            raise DomesticSupplierResponseError(
                f"products[{index}].price_vnd is not a valid number"
            ) from exc
        if not price_vnd.is_finite() or price_vnd < 0:
            raise DomesticSupplierResponseError(
                f"products[{index}].price_vnd must be finite and nonnegative"
            )

    currency = None
    if price_vnd is not None:
        currency_raw = item.get("currency")
        if currency_raw is not None:
            if not isinstance(currency_raw, str) or not currency_raw.strip():
                raise DomesticSupplierResponseError(
                    f"products[{index}].currency must be a non-empty string"
                )
            currency = currency_raw.strip().upper()
        else:
            currency = "VND"  # mặc định khi price_vnd được cung cấp

    moq_raw = item.get("moq")
    moq: Optional[int] = None
    if moq_raw is not None:
        if type(moq_raw) is not int or moq_raw < 1:
            raise DomesticSupplierResponseError(
                f"products[{index}].moq must be a positive integer"
            )
        moq = moq_raw

    lead_time_raw = item.get("lead_time_days")
    lead_time_days: Optional[int] = None
    if lead_time_raw is not None:
        if type(lead_time_raw) is not int or lead_time_raw < 0:
            raise DomesticSupplierResponseError(
                f"products[{index}].lead_time_days must be a nonnegative integer"
            )
        lead_time_days = lead_time_raw

    wholesale_raw = item.get("wholesale_available")
    wholesale: Optional[bool] = None
    if wholesale_raw is not None:
        if not isinstance(wholesale_raw, bool):
            raise DomesticSupplierResponseError(
                f"products[{index}].wholesale_available must be a boolean"
            )
        wholesale = wholesale_raw

    return CommercialInfo(
        price_vnd=price_vnd,
        currency=currency,
        moq=moq,
        lead_time_days=lead_time_days,
        wholesale_available=wholesale,
    )


def _optional_str(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomesticSupplierResponseError(
            f"{field_name} must be a string"
        )
    return value if value.strip() else None
