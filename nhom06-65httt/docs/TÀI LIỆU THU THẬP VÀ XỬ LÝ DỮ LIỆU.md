# TÀI LIỆU THU THẬP VÀ XỬ LÝ DỮ LIỆU

## Tổng quan công việc

### Mục tiêu

Đề tài hướng đến xây dựng hệ thống Business Intelligence phân tích thị hiếu tiêu dùng quốc tế và hỗ trợ quyết định đặt hàng xuất khẩu gốm sứ Việt Nam. Phần Thu thập dữ liệu và ETL có nhiệm vụ thu thập, lưu trữ nguyên bản, phân tích cấu trúc, làm sạch, chuẩn hóa, kiểm tra chất lượng, phát hiện trùng lặp, cách ly dữ liệu lỗi và chuẩn bị dữ liệu nguồn cho cơ sở dữ liệu đích.

### Phạm vi được phân công

- Xây dựng nền tảng cấu hình, logging, HTTP/API client, source registry và raw storage.
- Xây dựng collector/adapter cho UN Comtrade, Google Trends, Etsy, Amazon, Minh Long 1, Thế Giới Gốm và Bát Tràng.
- Xây dựng parser, ParsedRecord, normalizer, quality validator, deduplicator và quarantine.
- Chuẩn bị source-to-target mapping theo ERD, Data Dictionary, Star Schema và DDL đã có.
- Kiểm thử unit, tích hợp và kiểm thử đầu cuối ở mức pipeline hiện có.

Không có kết nối PostgreSQL, transaction hoặc database loader trong mã nguồn hiện tại. Mọi thay đổi ERD, DDL, khóa, grain và quy tắc upsert phải chờ thành viên phụ trách cơ sở dữ liệu.

### Ba nhóm sản phẩm bàn giao

1. **Chương trình thu thập và xử lý:** mã nguồn trong `nhom06-65httt/src/etl/`.
2. **Bộ dữ liệu:** incoming, raw, manifest, SHA-256 index và quarantine trong `nhom06-65httt/data/`.
3. **Tài liệu kỹ thuật:** tài liệu này mô tả nguồn, trường dữ liệu, quy trình, kết quả kiểm thử và hướng dẫn vận hành.

## Nguồn dữ liệu

| Nguồn | Địa chỉ hoặc định danh | Phương thức | Trạng thái thực tế | Giới hạn |
|---|---|---|---|---|
| UN Comtrade | `https://comtradeapi.un.org` | API preview, payload JSON | Có 18 collection thực tế | ITC Trade Map chưa có dữ liệu thực tế |
| Google Trends | `https://trends.google.com/trends/explore` | Xuất CSV thủ công | Có 132 CSV G1 thực tế, 132 collection | Không scraping hoặc API chưa được cấp |
| Minh Long 1 | `https://minhlong.com/collections/all/products.json` | JSON catalog qua HTTP | Có 1 collection; parser đọc 450 record | 450 payload record không đồng nghĩa catalog 297 sản phẩm đã duyệt |
| Thế Giới Gốm | `https://thegioigom.com/wp-json/wc/store/products` | WooCommerce Store API JSON | Có 1 collection; parser đọc 500 record | Cần kiểm tra danh mục và thuộc tính |
| Bát Tràng | `https://gombattrang.vn/wp-json/wc/store/products` | WooCommerce Store API JSON | Có 1 collection; parser đọc 304 record | 304 record thiếu `price_vnd` và đã được quarantine |
| Etsy | `https://openapi.etsy.com` | API/adapter và fixture | Chỉ có code/fixture | Chưa có collection raw thực tế |
| Amazon | `https://creatorsapi.amazon` | Creators API/adapter và fixture | Chỉ có code/fixture | Chưa có collection raw thực tế |
| ITC Trade Map | `https://www.trademap.org` | File adapter và fixture | Chưa có collection thực tế | Chưa xác nhận dữ liệu |
| Gốc Gốm Việt | `https://gocgomviet.com` | Source registry và fixture | Chưa có collection thực tế | Chưa xác nhận nguồn thu thập |

Nguồn thực tế chỉ được ghi khi có payload/manifest trong `data/raw/` hoặc CSV incoming đã import.

## Chương trình thu thập dữ liệu

### Kiến trúc mã nguồn

Thư mục chính là `nhom06-65httt/src/etl/`.

| Nhóm | Tệp chính | Chức năng |
|---|---|---|
| Nền tảng | `config.py`, `logging_config.py`, `__main__.py` | Cấu hình, logging và runtime |
| Registry | `source_registry.py` | Danh mục nguồn, loại nguồn, URL, nhóm nguồn, trạng thái |
| HTTP | `http_client.py` | GET, timeout, retry, status code, Retry-After, pagination |
| Raw Storage | `raw_storage.py` | Lưu payload bytes và manifest append-only |
| UN Comtrade | `trade_collector.py`, `trade_parser.py` | Thu thập và parse JSON thương mại |
| Google Trends | `google_trends_collector.py`, `google_trends_csv_importer.py`, `trends_parser.py` | Import và parse CSV G1 |
| Sản phẩm quốc tế | `marketplace_parser.py`, `product_response.py` | Parse Etsy/Amazon |
| Đánh giá | `review_collector.py`, `review_parser.py` | Thu thập và parse review |
| Nhà cung trong nước | `domestic_supplier_collector.py`, `domestic_parser.py`, `bat_trang_collector.py` | Thu thập và parse catalog |
| Xử lý | `parsed_record.py`, `normalizer.py`, `quality_validator.py`, `deduplicator.py`, `quarantine.py` | Parse, chuẩn hóa, kiểm tra, trùng và cách ly |
| Mapping | `source_to_target_mapping.py` | Mapping sang 13 bảng OLTP |

### Công nghệ và thư viện

- Python với thư viện chuẩn: `argparse`, `csv`, `dataclasses`, `hashlib`, `json`, `pathlib`, `urllib`, `unittest`, `Decimal`.
- Không phát hiện `psycopg`, SQLAlchemy hoặc database driver trong mã nguồn hiện tại.
- Không có `requirements.txt`, `pyproject.toml` hoặc manifest dependency Python.
- PostgreSQL chỉ có DDL trong `src/database/`; chưa có module kết nối/nạp dữ liệu.

### UN Comtrade

`UNComtradeCollector` nhận quốc gia, mã hàng, năm và luồng thương mại. Payload được lưu bằng `RawStorage`; mỗi collection có `payload.bin` và `manifest.json`. `UNComtradeParser` tạo `ParsedTradePayload`.

Kết quả thực tế:

- 18 collection.
- 574 record parse.
- 574 record valid.
- 0 record invalid.

### Google Trends

G1 gồm `ceramic`, `ceramics`, `pottery`, `porcelain`, `stoneware` tại VN, US, JP, DE, FR và IN.

Mỗi thị trường gồm:

- Interest Over Time.
- Interest by Region.
- Related Queries Top/Rising.
- Related Topics Top/Rising.
- Tổng 22 CSV/thị trường và 132 CSV toàn bộ.

Importer kiểm tra tên file, geo, keyword, chart, header, cột, SHA-256 và import index. Dry-run không ghi collection hoặc index.

Lệnh dry-run:

```powershell
python nhom06-65httt\src\etl\google_trends_csv_importer.py --dry-run
```

Lệnh import:

```powershell
python nhom06-65httt\src\etl\google_trends_csv_importer.py
```

### Etsy, Amazon và review

Có adapter/parser/collector, fixture và unit test. Chưa có collection raw thực tế nên không thể tuyên bố đã thu thập dữ liệu sản phẩm hoặc review thực tế.

### Nhà cung trong nước

- Minh Long 1: JSON catalog qua HTTP; parser đọc 450 record.
- Thế Giới Gốm: WooCommerce Store API JSON; parser đọc 500 record.
- Bát Tràng: WooCommerce Store API, paging; parser đọc 304 record.

Với Bát Tràng, `price_vnd` là `null` cho toàn bộ 304 payload record. Không điền số vào giá thiếu.

### Lệnh pipeline audit

```powershell
python nhom06-65httt\src\etl\pipeline_audit.py --raw nhom06-65httt\data\raw
```

Audit là read-only; không ghi raw, quarantine, manifest hoặc database.

## Dữ liệu thu thập

### Cấu trúc dữ liệu

```text
data/incoming/google_trends/
data/raw/<source>/<collection_id>/payload.bin
data/raw/<source>/<collection_id>/manifest.json
data/quarantine/<source>/entries/*.json
```

- `incoming`: CSV/file đầu vào.
- `raw`: payload nguyên bản, append-only.
- `manifest`: provenance, checksum, source, thời gian và request parameters.
- `quarantine`: bản ghi lỗi hoặc trùng tiềm năng kèm nguyên nhân.
- Google import index: `data/incoming/google_trends/.imported_sha256_index.json`.

### Manifest

`manifest.json` chứa:

- `collection_id`;
- `metadata.source_id`;
- `metadata.collected_at`;
- `metadata.data_format`;
- `metadata.status`;
- `metadata.checksum.algorithm`;
- `metadata.checksum.value`;
- `metadata.request_parameters`;
- `payload_file`.

`RawStorage` xác thực SHA-256 payload khi đọc. Google importer ghi SHA-256 theo collection trong import index để phát hiện trùng.

### Thống kê thực tế

| Nguồn | Incoming/file | Collection | Parsed | Valid | Invalid/quarantine |
|---|---:|---:|---:|---:|---:|
| UN Comtrade | — | 18 | 574 | 574 | 0 |
| Google Trends | 132 CSV | 132 | 4.868 | 4.868 | 0 invalid; 4 duplicate candidates |
| Minh Long 1 | — | 1 | 450 | 450 | 0 |
| Thế Giới Gốm | — | 1 | 500 | 500 | 0 |
| Bát Tràng | — | 1 | 304 | 0 | 304 |
| Etsy/Amazon/ITC/Gốc Gốm Việt | 0 | 0 | 0 | 0 | 0 |

Số collection không bằng số bản ghi. Số payload record không bằng số catalog được duyệt.

### Google Trends theo thị trường

| Thị trường | File | Parsed/valid |
|---|---:|---:|
| VN | 22 | 796 |
| US | 22 | 862 |
| JP | 22 | 770 |
| DE | 22 | 827 |
| FR | 22 | 767 |
| IN | 22 | 846 |
| Tổng | 132 | 4.868 |

Interest Over Time mỗi file có 61 dòng theo cadence monthly. Số dòng Interest by Region thay đổi theo dữ liệu thực tế từng thị trường.

### UN Comtrade

| Tên trường nguồn | Ý nghĩa | Kiểu | Trường sau xử lý | Quy tắc |
|---|---|---|---|---|
| `reporterCode` | Quốc gia báo cáo | string/number | `reporter_country_id` | Chuẩn hóa và tra cứu |
| `partnerCode` | Quốc gia đối tác | string/number | `partner_country_id` | Chuẩn hóa và tra cứu |
| `partnerISO`, `reporterISO` | Mã ISO quốc gia | string | country code | Hỗ trợ mapping |
| `period` | Năm/kỳ báo cáo | string/number | `year` | Kiểm tra 2000–2100 |
| `flowCode` | Luồng thương mại | string | `trade_flow` | `X -> Export`, `M -> Import` |
| `cmdCode` | Mã HS | string/number | `hs_code` | Chuẩn hóa mã hàng |
| `cmdDesc` | Mô tả hàng | string | `cmd_desc` | Chuẩn hóa văn bản |
| `primaryValue` | Kim ngạch | number/string | `trade_value_usd` | Decimal không âm |
| `netWgt` | Khối lượng tịnh | number/string | `net_weight_kg` | Số không âm, cho phép thiếu |
| `fobvalue` | Giá trị FOB | number/string | `fob_value_usd` | Cần xác minh parser/mapping |
| `cifvalue` | Giá trị CIF | number/string | `cif_value_usd` | Cần xác minh parser/mapping |
| `qty`, `qtyUnitAbbr` | Số lượng và đơn vị | number/string | `qty_amount`, `qty_unit` | Cho phép thiếu |
| `count` | Số record server báo | integer | `reported_count` | Không thay bằng số record parse |
| `data` | Mảng record thương mại | array | `ParsedTradeRecord[]` | Mỗi phần tử tạo một record |

### Google Trends

Interest Over Time có cột thời gian `Time`, `Week` hoặc `Month` và các cột `ceramic`, `ceramics`, `pottery`, `porcelain`, `stoneware`. Giá trị `0` được giữ riêng theo từng keyword.

Interest by Region dùng `Region`, `Subregion`, `City` hoặc `Metro`. Tên vùng là nhãn dimension, không được normalize thành ngày.

Related Queries/Topics dùng:

- `query` hoặc `topic`;
- `search interest`;
- `increase percent`;
- `Breakout` giữ nguyên chuỗi;
- phần trăm và số âm giữ nguyên chuỗi.

Metadata importer bổ sung `source`, `source_type`, `geo`, `geo_name`, `time_range`, `data_type`, `related_section`, `filename`, `original_filename`, `collected_at`, `data_format` và `sha256`.

### Nhà cung trong nước

Payload gồm khối `supplier` và `products`.

| Trường nguồn | Ý nghĩa | Trường sau xử lý | Quy tắc |
|---|---|---|---|
| `source_product_id` | Mã sản phẩm nguồn | `source_product_id` | Bắt buộc |
| `name` | Tên sản phẩm | `name` | Giữ chuỗi |
| `description` | Mô tả | `description` | Chuẩn hóa HTML khi source cung cấp |
| `category` | Danh mục nguồn | `category` | Chờ mapping danh mục đích |
| `material` | Chất liệu | `material` | Giữ hoặc `null` |
| `origin_region` | Vùng gốc | `origin_region` | Không suy luận |
| `price_vnd` | Giá VND | `price_vnd_str` | Trường bắt buộc ở validator |
| `currency` | Đơn vị tiền | `currency` | Giữ giá trị source |
| `moq` | Số lượng tối thiểu | `moq` | `null` nếu thiếu |
| `lead_time_days` | Thời gian giao hàng | `lead_time_days` | Không suy luận |
| `product_url` | URL sản phẩm | `product_url` | Giữ provenance |
| `image_url` | URL ảnh | `image_url` | Giữ nếu có |

## Quy trình xử lý và làm sạch dữ liệu

### Parsing

- `UNComtradeParser` tạo `ParsedTradePayload`.
- `GoogleTrendsParser` tạo `ParsedTrendsPayload`.
- `DomesticSupplierCatalogParser` tạo `ParsedDomesticPayload`.
- Marketplace/review parser tạo payload tương ứng.

Parser không thay giá trị thiếu thành `0`, `null` hoặc nhãn suy diễn nếu nguồn không cung cấp bằng chứng.

### Normalization

`normalizer.py` chuẩn hóa chuỗi, ngày, số, quốc gia và category theo quy tắc đã xác nhận. Region và related term được giữ dưới dạng chuỗi; `Breakout`, phần trăm, số âm và `0` không bị biến thành điểm interest 0–100.

### Validation

`quality_validator.py` kiểm tra required field, kiểu dữ liệu, khoảng giá trị, ngày tháng, quy tắc nghiệp vụ và provenance.

Google Trends Related không áp dụng range 0–100 của interest score. Bát Tràng 304 record mất `price_vnd` nên không qua validation.

### Deduplication

`deduplicator.py` phân biệt exact duplicate, potential duplicate và pending key confirmation. Candidate key Google Trends gồm source, period kind, data type, source keyword, related section, period và các giá trị.

Deduplication không xóa dữ liệu raw.

### Quarantine

`quarantine.py` lưu entity type, reason, provenance, record snapshot, error codes/reasons và recovery history.

Google có 4 duplicate candidates tiềm năng: DE 3, VN 1. Bát Tràng có 304 record invalid do thiếu giá.

### Source-to-target mapping

`source_to_target_mapping.py` mô tả mapping vào 13 bảng OLTP và phân loại direct, transform, dependency, no source, not applicable, pending confirmation và unresolved FK.

Mapping hiện là specification/result; chưa nạp database.

## Kết quả thực hiện

### Chức năng đã hoàn thành

- Cấu hình, logging và HTTP retry/pagination.
- Source registry và Raw Storage với SHA-256.
- UN Comtrade collector/parser.
- Google Trends importer, parser và multi-market metadata.
- Marketplace/review adapters.
- Domestic supplier collectors.
- Normalizer, validator, deduplicator và quarantine.
- Source-to-target mapping specification.
- Pipeline audit read-only.
- Unit và toàn bộ test ETL.

### Chức năng có code nhưng chưa có dữ liệu thực tế

- Etsy/Amazon product adapter.
- Etsy review collector/parser.
- ITC Trade Map file adapter.
- Gốc Gốm Việt source registry/fixture.

### Chức năng chưa triển khai

- PostgreSQL connection.
- Transaction và rollback.
- OLTP insert/upsert.
- OLAP dimension/fact load.
- Pipeline liên tục từ source đến database.
- Persistent processed storage ngoài RawStorage/quarantine.

### Kết quả kiểm thử

Google Trends D6:

```powershell
Set-Location nhom06-65httt\src
python -m unittest etl.tests.test_google_trends_d6
```

Kết quả: **58 test PASS**.

Toàn bộ test ETL:

```powershell
Set-Location nhom06-65httt\src
python -m unittest discover -s etl/tests
```

Kết quả: **420 test PASS**.

Pipeline audit thực tế:

```powershell
python nhom06-65httt\src\etl\pipeline_audit.py --raw nhom06-65httt\data\raw
```

| Nguồn | Collection | Parsed | Valid | Invalid | Parser error | Duplicate candidate |
|---|---:|---:|---:|---:|---:|---:|
| UN Comtrade | 18 | 574 | 574 | 0 | 0 | 0 |
| Google Trends | 132 | 4.868 | 4.868 | 0 | 0 | 4 |
| Minh Long 1 | 1 | 450 | 450 | 0 | 0 | 0 |
| Thế Giới Gốm | 1 | 500 | 500 | 0 | 0 | 0 |
| Bát Tràng | 1 | 304 | 0 | 304 | 0 | 0 |

Kiểm tra diff:

```powershell
git diff --check
```

Kết quả: PASS. Git có cảnh báo line-ending LF/CRLF trong một số file; không có lỗi whitespace.

## Tích hợp cơ sở dữ liệu

### Tài liệu đích

- `src/database/01_init_oltp_erd_schema.sql`
- `src/database/02_init_olap_star_schema.sql`
- `docs/thiet_ke_erd.md`
- `docs/thiet_ke_star_schema.md`
- `docs/ĐẶC TẢ TỪ ĐIỂN DỮ LIỆU.md`

### Mapping đã chuẩn bị

| Nhóm dữ liệu | Trường nguồn | Bảng đích chính | Trạng thái |
|---|---|---|---|
| Thương mại | reporter/partner/year/flow/HS/value | `trade_statistics` | Field đã mapping; chờ seed country và quy tắc upsert |
| Google Trends | geo/region/time/term/score | `search_trends`, `trending_keywords` | Mapping partial; chờ country/category/region seed |
| Sản phẩm quốc tế | listing/item/price/category | `market_products` | Chưa có dữ liệu raw thực tế |
| Review | rating/text/date/product | `product_reviews`, `customers`, `review_aspects` | Chưa có dữ liệu raw thực tế |
| Nhà cung | supplier/product/category/price | `suppliers`, `supplier_products` | Parsed; chờ supplier/category key và quy tắc upsert |

### Dependency cần phối hợp

Thành viên thiết kế cơ sở dữ liệu cần xác nhận:

- primary key, foreign key, unique key;
- natural key và quy tắc upsert;
- danh mục country/category/market region;
- grain của từng fact;
- dimension key;
- quy tắc tạo dim_time/dim_market/dim_product/dim_supplier/dim_sentiment_aspect;
- quy tắc nạp OLTP và OLAP.

ERD, DDL và Star Schema không được thay đổi trước khi có xác nhận chính thức.

### Tình trạng kết nối và nạp dữ liệu

- Không có database URL hoặc connection module.
- Không có secret database trong repository.
- Không kết nối PostgreSQL trong kiểm thử.
- Không insert/update dữ liệu thực tế vào OLTP hoặc OLAP.

## Hướng dẫn vận hành

### Điều kiện môi trường

- Python trên Windows hoặc môi trường tương thích.
- Không cần PostgreSQL để chạy parser và audit.
- Không có dependency database Python hiện tại.

### Google dry-run

```powershell
python nhom06-65httt\src\etl\google_trends_csv_importer.py --dry-run
```

Dry-run không ghi collection hoặc import index.

### Google import

```powershell
python nhom06-65httt\src\etl\google_trends_csv_importer.py
```

Chỉ chạy import khi không có `Rejected`. SHA trùng sẽ bị skip.

### Pipeline audit

```powershell
python nhom06-65httt\src\etl\pipeline_audit.py --raw nhom06-65httt\data\raw
```

Audit không ghi dữ liệu.

### Test

```powershell
Set-Location nhom06-65httt\src
python -m unittest discover -s etl/tests
Set-Location ..\..
git diff --check
```

### Lỗi thường gặp

- `Rejected`: tên file, geo, chart title hoặc header không khớp quy tắc G1.
- `Skipped_duplicate`: SHA-256 đã tồn tại trong import index.
- `missing_required_field` Bát Tràng: source không cung cấp `price_vnd`.
- Không thay `null`, `Breakout` hoặc phần trăm thành số.
- Không kết nối PostgreSQL khi chưa có module, credential và dependency.

## Tổng hợp sản phẩm bàn giao và công việc còn lại

### Chương trình

Đã hoàn thành:

- foundation và logging;
- source registry;
- HTTP/API client;
- raw storage và provenance;
- UN Comtrade/Google Trends/digital product/domestic supplier collectors;
- parser, normalizer, validator, deduplicator và quarantine;
- source-to-target mapping;
- pipeline audit read-only;
- test suite.

Chưa hoàn thành:

- database connection;
- transaction;
- OLTP/OLAP loader;
- persistent processed storage;
- pipeline liên tục nguồn-to-database.

### Bộ dữ liệu

- UN Comtrade: 18 collection/574 record.
- Google Trends: 132 CSV/132 collection/4.868 record.
- Minh Long 1: 1 collection/450 payload record.
- Thế Giới Gốm: 1 collection/500 payload record.
- Bát Tràng: 1 collection/304 payload record invalid.
- Incoming Google giữ 132 CSV và import SHA index.
- Quarantine Google giữ 4 entry.
- Quarantine Bát Tràng giữ dữ liệu hiện có.

### Tài liệu kỹ thuật

Tài liệu này mô tả:

- nguồn dữ liệu;
- địa chỉ và phương thức thu thập;
- trường dữ liệu thực tế;
- RawStorage/manifest/checksum;
- parse/normalization/validation/dedup/quarantine;
- source-to-target mapping;
- kết quả kiểm thử và audit;
- hướng dẫn chạy;
- giới hạn và công việc còn lại.

### Công việc cần tiếp tục

1. Thành viên database xác nhận khóa, seed và quy tắc upsert.
2. Hoàn thiện natural key và unresolved FK.
3. Xác nhận grain của 3 bảng Fact và dimension key OLAP.
4. Xây dựng database connection và transaction module.
5. Triển khai OLTP loader sau khi quy tắc upsert được duyệt.
6. Triển khai OLAP loader sau khi grain/key dimension được duyệt.
7. Bổ sung end-to-end integration test.
8. Xác nhận dữ liệu thực tế Etsy, Amazon, review, ITC và Gốc Gốm Việt.
9. Rà soát 4 duplicate candidate Google và 304 record invalid Bát Tràng trước nạp.
