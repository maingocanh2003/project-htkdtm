# ĐẶC TẢ CÁC ĐỐI TƯỢNG DỮ LIỆU VÀ TỪ ĐIỂN DỮ LIỆU (DATA DICTIONARY)

- **Đề tài:** Xây dựng hệ thống Business Intelligence phân tích thị hiếu tiêu dùng quốc tế và hỗ trợ ra quyết định đặt hàng xuất khẩu gốm sứ Việt Nam
- **Học phần:** Hệ thống Kinh doanh Thông minh (HTKDTM)
- **Nhóm thực hiện:** Nhóm 06 – Lớp 65HTTT
- **Người phụ trách:** Trần Mai Ngọc Anh (Nhóm trưởng – Phân tích nghiệp vụ & Thiết kế CSDL)

---

## 1. Tổng Quan Các Nhóm Đối Tượng Dữ Liệu Cần Quản Lý

Dựa trên tài liệu phân tích yêu cầu nghiệp vụ ([PHÂN TÍCH YÊU CẦU NGHIỆP VỤ.md](file:///d:/SUBJECTS/HTKDTM/project-htkdtm/nhom06-65httt/docs/01_phan_tich_yeu_cau_nghiep_vu.md)), hệ thống quản lý **5 nhóm đối tượng dữ liệu cốt lõi**, được chuẩn hóa thành **13 bảng thực thể** trong cơ sở dữ liệu PostgreSQL:

|     STT     | Nhóm đối tượng nghiệp vụ                   | Tên bảng vật lý (PostgreSQL) | Mô tả vai trò & Nguồn dữ liệu                                                                                                                     |
| :---------: | :------------------------------------------------ | :------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1** | **Thị trường & Xu hướng**              | `countries`                    | Danh mục hơn 130 quốc gia/vùng lãnh thổ giao thương gốm sứ (UN Comtrade, ITC).                                                                |
|            |                                                   | `market_regions`               | Danh mục 51 bang/vùng lãnh thổ trực thuộc quốc gia phục vụ phân tích xu hướng vùng (Google Trends).                                       |
|            |                                                   | `trade_statistics`             | Dữ liệu thống kê thương mại quốc tế giai đoạn 2021–2023 với 14 chỉ tiêu kinh tế (UN Comtrade, ITC).                                     |
|            |                                                   | `search_trends`                | Chuỗi dữ liệu mức độ quan tâm tìm kiếm liên tục trong 52 tuần theo nhóm sản phẩm và vùng (Google Trends).                              |
|            |                                                   | `trending_keywords`            | Danh mục các từ khóa gốm sứ thịnh hành và mức độ tăng trưởng bứt phá từ +140% đến +5.300% (Google Trends).                          |
| **2** | **Sản phẩm & Thuộc tính**               | `product_categories`           | Danh mục chuẩn hóa 4 dòng sản phẩm gốm sứ chủ lực (Bộ ấm chén, Ly cốc sứ, Bát đĩa bàn ăn, Lọ hoa mỹ nghệ).                       |
|            |                                                   | `market_products`              | Danh mục sản phẩm gốm sứ đang tiêu thụ trên thị trường quốc tế kèm 5 nhóm thuộc tính thị hiếu (Etsy, Amazon).                       |
|            |                                                   | `supplier_products`            | Danh mục 341 sản phẩm gốm sứ nội địa của các xưởng Việt Nam kèm thuộc tính kỹ thuật và giá niêm yết (Minh Long 1, Bát Tràng).   |
| **3** | **Khách hàng**                            | `customers`                    | Thông tin định danh người mua / người để lại đánh giá trên các sàn thương mại điện tử quốc tế (Etsy, Amazon).                   |
| **4** | **Đánh giá & Phân tích AI/NLP**        | `product_reviews`              | Nội dung nhận xét, điểm sao (1–5) và nhãn cảm xúc tổng thể (Tích cực/Trung lập/Tiêu cực) do mô hình AI/NLP phân loại.              |
|            |                                                   | `review_aspects`               | Các khía cạnh sản phẩm cụ thể được khách hàng khen ngợi hoặc phàn nàn (độ bền men, bao bì, chịu nhiệt...) do AI/NLP trích xuất. |
| **5** | **Nhà cung cấp & Hỗ trợ quyết định** | `suppliers`                    | Hồ sơ năng lực các cơ sở sản xuất gốm sứ trong nước (Minh Long 1, Bát Tràng): công suất, thời gian giao hàng, liên hệ.             |
|            |                                                   | `order_recommendations`        | Bảng lưu kết quả đối chiếu cung – cầu (Matching) và đề xuất sản phẩm, nhà cung cấp, số lượng đặt hàng theo thị trường.        |

---

## 2. Đặc Tả Chi Tiết Từ Điển Dữ Liệu (Data Dictionary)

### 2.1. Nhóm đối tượng Thị trường & Xu hướng

#### Bảng 1: `countries` (Danh mục Quốc gia / Thị trường quốc tế)

Lưu trữ thông tin định danh của hơn 130 quốc gia/vùng lãnh thổ đối tác thương mại gốm sứ.

| STT | Tên trường (Column) | Kiểu dữ liệu (PostgreSQL) | Ràng buộc          | Mô tả chi tiết                                               | Ví dụ giá trị                                  |
| :-: | :--------------------- | :--------------------------- | :------------------- | :-------------------------------------------------------------- | :------------------------------------------------- |
|  1  | `country_id`         | `SERIAL`                   | `PRIMARY KEY`      | Khóa chính tự tăng định danh quốc gia                    | `1`, `2`, `3`                                |
|  2  | `country_code`       | `VARCHAR(10)`              | `UNIQUE, NOT NULL` | Mã quốc gia theo chuẩn ISO 3166-1 alpha-3 / UN M49           | `'USA'`, `'JPN'`, `'DEU'`                    |
|  3  | `country_name`       | `VARCHAR(150)`             | `NOT NULL`         | Tên quốc gia (Tiếng Việt / Tiếng Anh chuẩn hóa)          | `'United States'`, `'Japan'`, `'Germany'`    |
|  4  | `region_continent`   | `VARCHAR(100)`             | `NULL`             | Khu vực địa lý / Châu lục                                 | `'North America'`, `'East Asia'`, `'Europe'` |
|  5  | `currency_code`      | `VARCHAR(10)`              | `NULL`             | Đơn vị tiền tệ bản địa của thị trường               | `'USD'`, `'JPY'`, `'EUR'`                    |
|  6  | `is_key_market`      | `BOOLEAN`                  | `DEFAULT FALSE`    | Đánh dấu thị trường mục tiêu trọng điểm của dự án | `TRUE`                                           |

#### Bảng 2: `market_regions` (Danh mục Bang / Vùng lãnh thổ)

Lưu trữ 51 bang/vùng lãnh thổ phục vụ phân tích mức độ quan tâm chi tiết từ Google Trends.

| STT | Tên trường (Column) | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                     | Mô tả chi tiết                             | Ví dụ giá trị                             |
| :-: | :--------------------- | :--------------------------- | :------------------------------ | :-------------------------------------------- | :-------------------------------------------- |
|  1  | `region_id`          | `SERIAL`                   | `PRIMARY KEY`                 | Khóa chính tự tăng định danh vùng/bang | `1`, `2`                                  |
|  2  | `country_id`         | `INTEGER`                  | `FK -> countries(country_id)` | Quốc gia trực thuộc                        | `1` (USA)                                   |
|  3  | `region_code`        | `VARCHAR(20)`              | `NOT NULL`                    | Mã bang/vùng địa lý                      | `'US-CA'`, `'US-NY'`, `'US-TX'`         |
|  4  | `region_name`        | `VARCHAR(150)`             | `NOT NULL`                    | Tên bang hoặc vùng lãnh thổ              | `'California'`, `'New York'`, `'Texas'` |

#### Bảng 3: `trade_statistics` (Thống kê Thương mại Quốc tế UN Comtrade & ITC Trade Map)

Lưu trữ các bản ghi giao thương xuất nhập khẩu gốm sứ liên tục trong 3 năm (2021–2023) với 14 chỉ tiêu kinh tế.

| STT | Tên trường (Column)  | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                        | Mô tả chi tiết                                                         | Ví dụ giá trị                    |
| :-: | :---------------------- | :--------------------------- | :--------------------------------- | :------------------------------------------------------------------------ | :----------------------------------- |
|  1  | `trade_id`            | `SERIAL`                   | `PRIMARY KEY`                    | Khóa chính tự tăng của bản ghi thương mại                        | `101`                              |
|  2  | `reporter_country_id` | `INTEGER`                  | `FK -> countries(country_id)`    | Quốc gia báo cáo (Việt Nam hoặc quốc gia nhập khẩu)               | `1`                                |
|  3  | `partner_country_id`  | `INTEGER`                  | `FK -> countries(country_id)`    | Quốc gia đối tác giao thương (>130 quốc gia)                       | `2` (USA)                          |
|  4  | `year`                | `INTEGER`                  | `NOT NULL, CHECK (year >= 2000)` | Năm thống kê thương mại                                             | `2021`, `2022`, `2023`         |
|  5  | `trade_flow`          | `VARCHAR(20)`              | `NOT NULL`                       | Luồng thương mại (`Export` - Xuất khẩu, `Import` - Nhập khẩu) | `'Export'`, `'Import'`           |
|  6  | `hs_code`             | `VARCHAR(20)`              | `NOT NULL`                       | Mã HS phân loại mặt hàng gốm sứ quốc tế (Chương 69)            | `'6911'`, `'6912'`, `'6913'`   |
|  7  | `cmd_desc`            | `TEXT`                     | `NULL`                           | Mô tả mặt hàng gốm sứ theo chuẩn HS                                | `'Ceramic tableware, kitchenware'` |
|  8  | `trade_value_usd`     | `NUMERIC(18,2)`            | `NOT NULL`                       | Tổng kim ngạch thương mại (USD)                                      | `145230000.00`                     |
|  9  | `fob_value_usd`       | `NUMERIC(18,2)`            | `NULL`                           | Trị giá hàng hóa theo điều kiện FOB (USD)                          | `142000000.00`                     |
| 10 | `cif_value_usd`       | `NUMERIC(18,2)`            | `NULL`                           | Trị giá hàng hóa theo điều kiện CIF (USD)                          | `145230000.00`                     |
| 11 | `net_weight_kg`       | `NUMERIC(18,2)`            | `NULL`                           | Khối lượng tịnh của hàng hóa (kg)                                  | `38500000.00`                      |
| 12 | `qty_unit`            | `VARCHAR(50)`              | `NULL`                           | Đơn vị tính số lượng hàng hóa                                    | `'kg'`, `'Number of items'`      |
| 13 | `qty_amount`          | `NUMERIC(18,2)`            | `NULL`                           | Số lượng hàng hóa theo đơn vị tính                               | `38500000.00`                      |
| 14 | `market_share_pct`    | `NUMERIC(6,2)`             | `NULL`                           | Thị phần / Tỷ trọng đóng góp của thị trường (%)                | `18.45`                            |
| 15 | `yoy_growth_rate`     | `NUMERIC(8,2)`             | `NULL`                           | Tốc độ tăng trưởng kim ngạch so với năm liền trước (%)        | `12.30`                            |
| 16 | `data_source`         | `VARCHAR(50)`              | `DEFAULT 'UN Comtrade'`          | Nguồn dữ liệu (`UN Comtrade` / `ITC Trade Map`)                    | `'UN Comtrade'`                    |

#### Bảng 4: `search_trends` (Dữ liệu Xu hướng Tìm kiếm Google Trends)

Lưu trữ chuỗi thời gian 52 tuần và mức độ quan tâm theo vùng địa lý đối với 4 nhóm sản phẩm gốm sứ chủ lực.

| STT | Tên trường (Column) | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                                  | Mô tả chi tiết                                              | Ví dụ giá trị                                    |
| :-: | :--------------------- | :--------------------------- | :------------------------------------------- | :------------------------------------------------------------- | :--------------------------------------------------- |
|  1  | `trend_id`           | `SERIAL`                   | `PRIMARY KEY`                              | Khóa chính tự tăng                                         | `1`                                                |
|  2  | `country_id`         | `INTEGER`                  | `FK -> countries(country_id)`              | Quốc gia tìm kiếm                                           | `1` (USA)                                          |
|  3  | `region_id`          | `INTEGER`                  | `FK -> market_regions(region_id), NULL`    | Bang/Vùng lãnh thổ (nếu là dữ liệu cấp bang)           | `5` (California)                                   |
|  4  | `category_id`        | `INTEGER`                  | `FK -> product_categories(category_id)`    | Nhóm sản phẩm gốm sứ chủ lực (1 trong 4 nhóm)          | `2` (Bộ ấm chén)                                |
|  5  | `search_term`        | `VARCHAR(150)`             | `NOT NULL`                                 | Cụm từ khóa truy vấn trên Google Trends                   | `'ceramic dinnerware'`, `'handmade pottery mug'` |
|  6  | `week_start_date`    | `DATE`                     | `NOT NULL`                                 | Ngày bắt đầu của tuần khảo sát (trong chuỗi 52 tuần) | `'2023-10-01'`                                     |
|  7  | `week_number`        | `INTEGER`                  | `CHECK (week_number BETWEEN 1 AND 53)`     | Số thứ tự tuần trong năm (1–52)                          | `40`                                               |
|  8  | `interest_score`     | `INTEGER`                  | `CHECK (interest_score BETWEEN 0 AND 100)` | Điểm mức độ quan tâm tìm kiếm chuẩn hóa (0–100)     | `84`                                               |

#### Bảng 5: `trending_keywords` (Danh mục Từ khóa Thịnh hành & Bứt phá)

Lưu trữ các từ khóa phong cách gốm sứ có mức tăng trưởng tìm kiếm đột biến (+140% đến +5.300%).

| STT | Tên trường (Column)     | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                               | Mô tả chi tiết                                                             | Ví dụ giá trị                                   |
| :-: | :------------------------- | :--------------------------- | :---------------------------------------- | :---------------------------------------------------------------------------- | :-------------------------------------------------- |
|  1  | `keyword_id`             | `SERIAL`                   | `PRIMARY KEY`                           | Khóa chính tự tăng                                                        | `1`                                               |
|  2  | `country_id`             | `INTEGER`                  | `FK -> countries(country_id)`           | Thị trường ghi nhận từ khóa thịnh hành                                | `1` (USA)                                         |
|  3  | `category_id`            | `INTEGER`                  | `FK -> product_categories(category_id)` | Nhóm sản phẩm liên quan                                                   | `4` (Lọ hoa / Trang trí)                        |
|  4  | `keyword_text`           | `VARCHAR(200)`             | `NOT NULL`                              | Nội dung từ khóa thịnh hành                                              | `'artisan ceramic vase'`, `'wabi sabi pottery'` |
|  5  | `related_attribute_type` | `VARCHAR(50)`              | `NULL`                                  | Nhóm thuộc tính liên quan (`style`, `color`, `material`, `shape`) | `'style'`                                         |
|  6  | `growth_pct`             | `NUMERIC(10,2)`            | `NOT NULL`                              | Tỷ lệ tăng trưởng tìm kiếm (% tăng từ +140% đến +5.300%)           | `5300.00`, `240.00`                             |
|  7  | `trend_classification`   | `VARCHAR(50)`              | `DEFAULT 'Rising'`                      | Phân loại độ bứt phá (`Breakout`, `Rising`, `Top`)                | `'Breakout'`                                      |
|  8  | `recorded_period`        | `VARCHAR(50)`              | `NULL`                                  | Giai đoạn ghi nhận xu hướng                                              | `'Last 12 Months'`                                |

---

### 2.2. Nhóm đối tượng Sản phẩm & Thuộc tính

#### Bảng 6: `product_categories` (Danh mục Dòng sản phẩm gốm sứ chuẩn hóa)

Bảng danh mục dùng chung để ánh xạ đồng nhất giữa sản phẩm quốc tế (Etsy/Amazon), xu hướng Google Trends và 341 sản phẩm nội địa (Minh Long 1, Bát Tràng).

| STT | Tên trường (Column) | Kiểu dữ liệu (PostgreSQL) | Ràng buộc          | Mô tả chi tiết                                        | Ví dụ giá trị                                                                           |
| :-: | :--------------------- | :--------------------------- | :------------------- | :------------------------------------------------------- | :------------------------------------------------------------------------------------------ |
|  1  | `category_id`        | `SERIAL`                   | `PRIMARY KEY`      | Khóa chính tự tăng (1 đến 4 cho 4 dòng chủ lực) | `1`, `2`, `3`, `4`                                                                  |
|  2  | `category_code`      | `VARCHAR(50)`              | `UNIQUE, NOT NULL` | Mã định danh dòng sản phẩm                         | `'TEA_SET'`, `'MUG_CUP'`, `'DINNERWARE'`, `'VASE_DECOR'`                            |
|  3  | `category_name_vi`   | `VARCHAR(150)`             | `NOT NULL`         | Tên dòng sản phẩm tiếng Việt                       | `'Bộ ấm chén'`, `'Ly cốc sứ'`, `'Bát đĩa bàn ăn'`, `'Lọ hoa mỹ nghệ'`  |
|  4  | `category_name_en`   | `VARCHAR(150)`             | `NOT NULL`         | Tên dòng sản phẩm tiếng Anh tương ứng            | `'Ceramic Tea Set'`, `'Ceramic Mug & Cup'`, `'Dinnerware Set'`, `'Decorative Vase'` |
|  5  | `hs_code_mapping`    | `VARCHAR(20)`              | `NULL`             | Mã HS thương mại quốc tế liên kết                | `'6911'`, `'6912'`, `'6913'`                                                          |

#### Bảng 7: `market_products` (Sản phẩm gốm sứ quốc tế trên Etsy, Amazon)

Lưu trữ sản phẩm đang chào bán trên các sàn TMĐT quốc tế cùng đầy đủ các thuộc tính thị hiếu đã bóc tách.

| STT | Tên trường (Column) | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                               | Mô tả chi tiết                                                                 | Ví dụ giá trị                                     |
| :-: | :--------------------- | :--------------------------- | :---------------------------------------- | :-------------------------------------------------------------------------------- | :---------------------------------------------------- |
|  1  | `market_product_id`  | `SERIAL`                   | `PRIMARY KEY`                           | Khóa chính tự tăng                                                            | `1001`                                              |
|  2  | `external_sku`       | `VARCHAR(100)`             | `UNIQUE, NULL`                          | Mã sản phẩm gốc trên sàn (ASIN của Amazon / Listing ID của Etsy)          | `'B09X123456'`, `'ET-889120'`                     |
|  3  | `platform_source`    | `VARCHAR(50)`              | `NOT NULL`                              | Nền tảng thu thập (`Etsy`, `Amazon`, `International Retail`)             | `'Etsy'`, `'Amazon'`                              |
|  4  | `target_country_id`  | `INTEGER`                  | `FK -> countries(country_id)`           | Thị trường tiêu thụ chính của sản phẩm                                   | `1` (USA)                                           |
|  5  | `category_id`        | `INTEGER`                  | `FK -> product_categories(category_id)` | Dòng sản phẩm chuẩn hóa                                                      | `3` (Bát đĩa bàn ăn)                           |
|  6  | `product_name`       | `VARCHAR(300)`             | `NOT NULL`                              | Tên sản phẩm trên sàn quốc tế                                              | `'Minimalist Speckled Stoneware Dinner Set'`        |
|  7  | `price_usd`          | `NUMERIC(10,2)`            | `NOT NULL, CHECK (price_usd >= 0)`      | Giá bán niêm yết bằng USD                                                    | `48.99`                                             |
|  8  | `price_segment`      | `VARCHAR(50)`              | `NULL`                                  | Phân khúc giá (`Budget <$20`, `Mid-range $20-$60`, `Premium >$60`)       | `'Mid-range'`                                       |
|  9  | `color`              | `VARCHAR(100)`             | `NULL`                                  | Thuộc tính Màu sắc (Trắng, xanh, nâu, màu tự nhiên, đa sắc...)         | `'Natural Beige'`, `'Cobalt Blue'`, `'White'`   |
| 10 | `shape`              | `VARCHAR(100)`             | `NULL`                                  | Thuộc tính Hình dạng (Tròn, vuông, oval, hình dáng nghệ thuật...)       | `'Round'`, `'Oval'`, `'Organic Artistic'`       |
| 11 | `material`           | `VARCHAR(100)`             | `NULL`                                  | Thuộc tính Chất liệu & Men nung (Gốm, sứ, stoneware, men rạn...)           | `'Stoneware'`, `'Porcelain'`, `'Earthenware'`   |
| 12 | `style`              | `VARCHAR(100)`             | `NULL`                                  | Thuộc tính Phong cách (Truyền thống, tối giản, hiện đại, thủ công...) | `'Minimalist'`, `'Handmade Rustic'`, `'Modern'` |
| 13 | `is_dishwasher_safe` | `BOOLEAN`                  | `DEFAULT FALSE`                         | Đặc tính an toàn với máy rửa bát                                          | `TRUE`                                              |
| 14 | `is_microwave_safe`  | `BOOLEAN`                  | `DEFAULT FALSE`                         | Đặc tính chịu nhiệt / an toàn lò vi sóng                                  | `TRUE`                                              |
| 15 | `avg_rating`         | `NUMERIC(3,2)`             | `CHECK (avg_rating BETWEEN 0 AND 5)`    | Điểm đánh giá trung bình trên sàn (1.00 – 5.00)                          | `4.65`                                              |
| 16 | `review_count`       | `INTEGER`                  | `DEFAULT 0`                             | Tổng số lượt đánh giá của sản phẩm                                      | `128`                                               |
| 17 | `image_url`          | `TEXT`                     | `NULL`                                  | Đường dẫn hình ảnh sản phẩm                                               | `'https://...'`                                     |
| 18 | `product_url`        | `TEXT`                     | `NULL`                                  | Liên kết sản phẩm gốc trên sàn                                             | `'https://...'`                                     |

#### Bảng 8: `supplier_products` (Danh mục 341 Sản phẩm gốm sứ nội địa)

Lưu trữ 341 sản phẩm thu thập từ Gốm sứ Minh Long 1 (297 sản phẩm) và Gốm sứ Bát Tràng (44 sản phẩm), có cấu trúc thuộc tính tương đồng với `market_products` để phục vụ thuật toán đối chiếu cung – cầu.

| STT | Tên trường (Column)  | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                                | Mô tả chi tiết                                                                     | Ví dụ giá trị                                   |
| :-: | :---------------------- | :--------------------------- | :----------------------------------------- | :------------------------------------------------------------------------------------ | :-------------------------------------------------- |
|  1  | `supplier_product_id` | `SERIAL`                   | `PRIMARY KEY`                            | Khóa chính tự tăng                                                                | `1` (đến `341`)                               |
|  2  | `supplier_id`         | `INTEGER`                  | `FK -> suppliers(supplier_id), NOT NULL` | Liên kết đến cơ sở sản xuất (Minh Long 1 hoặc Bát Tràng)                   | `1` (Minh Long 1)                                 |
|  3  | `category_id`         | `INTEGER`                  | `FK -> product_categories(category_id)`  | Dòng sản phẩm (Bộ ấm chén, Ly cốc sứ, Bát đĩa bàn ăn, Lọ hoa mỹ nghệ) | `1` (Bộ ấm chén)                               |
|  4  | `product_code`        | `VARCHAR(100)`             | `UNIQUE, NULL`                           | Mã sản phẩm của nhà sản xuất                                                   | `'ML-AC-001'`, `'BT-LH-012'`                    |
|  5  | `product_name`        | `VARCHAR(300)`             | `NOT NULL`                               | Tên sản phẩm gốm sứ nội địa                                                   | `'Bộ trà 0.7L Jasmine Trắng Ngà'`             |
|  6  | `price_vnd`           | `NUMERIC(14,2)`            | `NOT NULL, CHECK (price_vnd >= 0)`       | Giá niêm yết / Giá nhập tại xưởng (VNĐ)                                      | `450000.00`                                       |
|  7  | `price_usd_equiv`     | `NUMERIC(10,2)`            | `NULL`                                   | Giá nhập quy đổi sang USD để so sánh biên giá quốc tế                      | `18.00`                                           |
|  8  | `color`               | `VARCHAR(100)`             | `NULL`                                   | Màu sắc chuẩn hóa của sản phẩm                                                 | `'Trắng'`, `'Xanh lam'`, `'Nâu tự nhiên'` |
|  9  | `shape`               | `VARCHAR(100)`             | `NULL`                                   | Hình dạng sản phẩm                                                                | `'Tròn'`, `'Vuông'`, `'Nghệ thuật'`       |
| 10 | `material`            | `VARCHAR(100)`             | `NULL`                                   | Chất liệu và loại men (Sứ cao cấp, Gốm thủ công, Men rạn, Men ngọc...)     | `'Sứ cao cấp'`, `'Gốm men rạn'`             |
| 11 | `style`               | `VARCHAR(100)`             | `NULL`                                   | Phong cách thiết kế (Tối giản, Truyền thống, Hiện đại, Thủ công)          | `'Tối giản'`, `'Truyền thống'`              |
| 12 | `is_dishwasher_safe`  | `BOOLEAN`                  | `DEFAULT TRUE`                           | Khả năng sử dụng an toàn với máy rửa bát                                     | `TRUE`                                            |
| 13 | `is_heat_resistant`   | `BOOLEAN`                  | `DEFAULT TRUE`                           | Khả năng chịu nhiệt cao / lò vi sóng                                            | `TRUE`                                            |
| 14 | `min_order_qty`       | `INTEGER`                  | `DEFAULT 100`                            | Số lượng đặt hàng tối thiểu (MOQ) cho mẫu sản phẩm                         | `200`                                             |
| 15 | `image_url`           | `TEXT`                     | `NULL`                                   | Đường dẫn hình ảnh sản phẩm                                                   | `'https://...'`                                   |
| 16 | `product_url`         | `TEXT`                     | `NULL`                                   | Đường dẫn trang sản phẩm gốc của nhà sản xuất                              | `'https://minhlong.com/...'`                      |

---

### 2.3. Nhóm đối tượng Khách hàng

#### Bảng 9: `customers` (Khách hàng / Người đánh giá quốc tế)

Lưu trữ thông tin định danh khách hàng đã mua và đánh giá sản phẩm trên các nền tảng thương mại điện tử quốc tế.

| STT | Tên trường (Column)   | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                           | Mô tả chi tiết                                          | Ví dụ giá trị                     |
| :-: | :----------------------- | :--------------------------- | :------------------------------------ | :--------------------------------------------------------- | :------------------------------------ |
|  1  | `customer_id`          | `SERIAL`                   | `PRIMARY KEY`                       | Khóa chính tự tăng định danh khách hàng            | `501`                               |
|  2  | `external_reviewer_id` | `VARCHAR(100)`             | `NULL`                              | Mã định danh tài khoản người dùng trên sàn TMĐT | `'AMZ_USR_9921'`                    |
|  3  | `reviewer_name`        | `VARCHAR(150)`             | `NULL`                              | Tên hiển thị của khách hàng                          | `'Sarah Jenkins'`, `'Kenji Sato'` |
|  4  | `country_id`           | `INTEGER`                  | `FK -> countries(country_id), NULL` | Quốc gia của khách hàng                                | `1` (USA)                           |
|  5  | `platform_source`      | `VARCHAR(50)`              | `NOT NULL`                          | Nền tảng mua sắm (`Etsy`, `Amazon`)                 | `'Amazon'`, `'Etsy'`              |
|  6  | `verified_purchase`    | `BOOLEAN`                  | `DEFAULT TRUE`                      | Trạng thái xác thực đã mua hàng thực tế           | `TRUE`                              |

---

### 2.4. Nhóm đối tượng Đánh giá & Kết quả phân tích AI/NLP

#### Bảng 10: `product_reviews` (Đánh giá sản phẩm & Phân loại cảm xúc AI/NLP)

Lưu trữ toàn bộ lượt nhận xét chi tiết của người tiêu dùng quốc tế trên thang điểm 1–5 sao cùng nhãn cảm xúc do mô hình AI/NLP của hệ thống phân loại.

| STT | Tên trường (Column) | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                                                        | Mô tả chi tiết                                                                                                   | Ví dụ giá trị                                                       |
| :-: | :--------------------- | :--------------------------- | :----------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------- |
|  1  | `review_id`          | `SERIAL`                   | `PRIMARY KEY`                                                    | Khóa chính tự tăng của lượt đánh giá                                                                      | `5001`                                                                |
|  2  | `market_product_id`  | `INTEGER`                  | `FK -> market_products(market_product_id), NOT NULL`             | Sản phẩm quốc tế được đánh giá                                                                            | `1001`                                                                |
|  3  | `customer_id`        | `INTEGER`                  | `FK -> customers(customer_id), NULL`                             | Khách hàng thực hiện đánh giá                                                                                | `501`                                                                 |
|  4  | `rating_stars`       | `INTEGER`                  | `NOT NULL, CHECK (rating_stars BETWEEN 1 AND 5)`                 | Điểm đánh giá theo thang 1 – 5 sao                                                                            | `5`, `4`, `2`                                                     |
|  5  | `review_title`       | `VARCHAR(250)`             | `NULL`                                                           | Tiêu đề ngắn của nhận xét                                                                                    | `'Beautiful glaze, sturdy packaging!'`                                |
|  6  | `review_text`        | `TEXT`                     | `NOT NULL`                                                       | Nội dung văn bản nhận xét chi tiết của khách hàng                                                          | `'The ceramic glaze is gorgeous and survives the dishwasher well...'` |
|  7  | `review_date`        | `DATE`                     | `NULL`                                                           | Ngày đăng đánh giá                                                                                            | `'2023-11-15'`                                                        |
|  8  | `sentiment_label`    | `VARCHAR(20)`              | `CHECK (sentiment_label IN ('Positive', 'Neutral', 'Negative'))` | Nhãn cảm xúc do AI/NLP phân loại (`Positive`: Tích cực, `Neutral`: Trung lập, `Negative`: Tiêu cực) | `'Positive'`                                                          |
|  9  | `sentiment_score`    | `NUMERIC(5,4)`             | `NULL`                                                           | Điểm xác suất tin cậy của mô hình AI/NLP (0.0000 – 1.0000)                                                 | `0.9425`                                                              |

#### Bảng 11: `review_aspects` (Trích xuất Khía cạnh Khen / Chê bằng AI/NLP)

Một đánh giá có thể nhắc đến nhiều khía cạnh khác nhau (ví dụ: khen màu men đẹp nhưng phàn nàn hộp đóng gói mỏng). Bảng này lưu chi tiết từng khía cạnh được mô hình NLP bóc tách từ `product_reviews`.

| STT | Tên trường (Column) | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                                                         | Mô tả chi tiết                                                                                                                                                                                            | Ví dụ giá trị                                               |
| :-: | :--------------------- | :--------------------------- | :------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------- |
|  1  | `aspect_id`          | `SERIAL`                   | `PRIMARY KEY`                                                     | Khóa chính tự tăng                                                                                                                                                                                       | `1`                                                           |
|  2  | `review_id`          | `INTEGER`                  | `FK -> product_reviews(review_id), NOT NULL`                      | Liên kết đến bản ghi đánh giá gốc                                                                                                                                                                   | `5001`                                                        |
|  3  | `aspect_category`    | `VARCHAR(100)`             | `NOT NULL`                                                        | Nhóm khía cạnh sản phẩm (`Glaze Durability` - Độ bền men, `Packaging` - Đóng gói, `Design & Color` - Thiết kế/Màu sắc, `Heat/Dishwasher` - Chịu nhiệt, `Price/Value` - Giá trị) | `'Glaze Durability'`, `'Packaging'`                         |
|  4  | `aspect_sentiment`   | `VARCHAR(20)`              | `CHECK (aspect_sentiment IN ('Positive', 'Neutral', 'Negative'))` | Thái độ khen (`Positive`) hay phàn nàn (`Negative`) đối với khía cạnh đó                                                                                                                     | `'Positive'`, `'Negative'`                                  |
|  5  | `extracted_phrase`   | `VARCHAR(250)`             | `NULL`                                                            | Cụm từ thực tế trích xuất từ bình luận                                                                                                                                                              | `'glaze is chip-resistant'`, `'arrived with broken handle'` |

---

### 2.5. Nhóm đối tượng Nhà cung cấp & Hỗ trợ quyết định đặt hàng

#### Bảng 12: `suppliers` (Hồ sơ Nhà cung cấp / Cơ sở sản xuất trong nước)

Lưu trữ thông tin định danh và năng lực sản xuất của các cơ sở sản xuất gốm sứ đầu ngành tại Việt Nam (Gốm sứ Minh Long 1, Gốm sứ Bát Tràng,...).

| STT | Tên trường (Column)   | Kiểu dữ liệu (PostgreSQL) | Ràng buộc          | Mô tả chi tiết                                                             | Ví dụ giá trị                                                                                        |
| :-: | :----------------------- | :--------------------------- | :------------------- | :---------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------- |
|  1  | `supplier_id`          | `SERIAL`                   | `PRIMARY KEY`      | Khóa chính tự tăng định danh nhà cung cấp                             | `1`, `2`                                                                                             |
|  2  | `supplier_code`        | `VARCHAR(50)`              | `UNIQUE, NOT NULL` | Mã định danh nhà cung cấp                                                | `'NCC_MINHLONG1'`, `'NCC_BATTRANG'`                                                                  |
|  3  | `supplier_name`        | `VARCHAR(200)`             | `NOT NULL`         | Tên cơ sở sản xuất / doanh nghiệp cung ứng                             | `'Công ty TNHH Minh Long 1'`, `'Làng nghề Gốm sứ Bát Tràng'`                                  |
|  4  | `address`              | `TEXT`                     | `NOT NULL`         | Địa chỉ xưởng sản xuất / trụ sở chính                               | `'333 Hưng Định 24, Thuận An, Bình Dương'`, `'Gia Lâm, Hà Nội'`                            |
|  5  | `hotline`              | `VARCHAR(50)`              | `NULL`             | Số điện thoại liên hệ đặt hàng                                       | `'0274 366 8899'`                                                                                      |
|  6  | `website_url`          | `VARCHAR(250)`             | `NULL`             | Địa chỉ website chính thức                                               | `'https://minhlong.com'`, `'https://battrang.info'`                                                  |
|  7  | `specialization`       | `VARCHAR(250)`             | `NULL`             | Thế mạnh dòng sản phẩm chủ lực                                         | `'Sứ gia dụng cao cấp, bộ bàn ăn, ấm trà'`, `'Gốm thủ công mỹ nghệ, lọ hoa, men rạn'` |
|  8  | `min_monthly_capacity` | `INTEGER`                  | `NOT NULL`         | Năng lực sản xuất tối thiểu (sản phẩm/tháng)                         | `10000`, `100000`                                                                                    |
|  9  | `max_monthly_capacity` | `INTEGER`                  | `NOT NULL`         | Năng lực sản xuất tối đa (từ 10.000 đến >500.000 sản phẩm/tháng)  | `500000`, `50000`                                                                                    |
| 10 | `avg_lead_time_days`   | `INTEGER`                  | `NOT NULL`         | Thời gian sản xuất và giao hàng cam kết trung bình (ngày)             | `14`, `21`                                                                                           |
| 11 | `total_catalog_items`  | `INTEGER`                  | `DEFAULT 0`        | Tổng số mã sản phẩm hiện có trong danh mục (297 SP / 44 SP)           | `297`, `44`                                                                                          |
| 12 | `reliability_rating`   | `NUMERIC(3,2)`             | `DEFAULT 4.50`     | Điểm đánh giá uy tín và chất lượng hoàn thiện của xưởng (1–5) | `4.85`                                                                                                 |

#### Bảng 13: `order_recommendations` (Đề xuất Đặt hàng Xuất khẩu – DSS)

Lưu trữ kết quả phân tích đối chiếu giữa thị hiếu từng quốc gia với sản phẩm và năng lực nhà cung cấp nội địa, phục vụ trực tiếp cho màn hình Hỗ trợ ra quyết định.

| STT | Tên trường (Column)       | Kiểu dữ liệu (PostgreSQL) | Ràng buộc                                                | Mô tả chi tiết                                                                                                                                                           | Ví dụ giá trị                                                                                                             |
| :-: | :--------------------------- | :--------------------------- | :--------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------- |
|  1  | `recommendation_id`        | `SERIAL`                   | `PRIMARY KEY`                                            | Khóa chính tự tăng                                                                                                                                                      | `1`                                                                                                                         |
|  2  | `target_country_id`        | `INTEGER`                  | `FK -> countries(country_id), NOT NULL`                  | Thị trường xuất khẩu mục tiêu (Mỹ, Nhật, Đức,...)                                                                                                                | `1` (USA)                                                                                                                   |
|  3  | `supplier_product_id`      | `INTEGER`                  | `FK -> supplier_products(supplier_product_id), NOT NULL` | Sản phẩm nội địa được đề xuất đặt hàng                                                                                                                        | `15`                                                                                                                        |
|  4  | `supplier_id`              | `INTEGER`                  | `FK -> suppliers(supplier_id), NOT NULL`                 | Nhà cung cấp được khuyến nghị                                                                                                                                        | `1` (Minh Long 1)                                                                                                           |
|  5  | `attribute_match_score`    | `NUMERIC(5,2)`             | `CHECK (attribute_match_score BETWEEN 0 AND 100)`        | Điểm độ khớp về thuộc tính (màu sắc, hình dáng, chất liệu, phong cách) với thị hiếu thị trường (0–100)                                                | `92.50`                                                                                                                     |
|  6  | `market_demand_score`      | `NUMERIC(5,2)`             | `CHECK (market_demand_score BETWEEN 0 AND 100)`          | Điểm sức cầu thị trường (kết hợp quy mô nhập khẩu + Google Trends)                                                                                              | `88.00`                                                                                                                     |
|  7  | `estimated_margin_pct`     | `NUMERIC(6,2)`             | `NULL`                                                   | Biên lợi nhuận gộp ước tính dựa trên chênh lệch giá bán quốc tế và giá nhập nội địa (%)                                                                | `58.40`                                                                                                                     |
|  8  | `overall_matching_score`   | `NUMERIC(5,2)`             | `NOT NULL`                                               | Điểm tổng hợp xếp hạng mức độ ưu tiên đặt hàng (0–100)                                                                                                       | `90.20`                                                                                                                     |
|  9  | `recommended_order_qty`    | `INTEGER`                  | `NOT NULL, CHECK (recommended_order_qty > 0)`            | Số lượng đặt hàng tham khảo (sản phẩm)                                                                                                                             | `2500`                                                                                                                      |
| 10 | `estimated_total_cost_vnd` | `NUMERIC(18,2)`            | `NULL`                                                   | Tổng chi phí nhập hàng dự kiến (VNĐ)                                                                                                                                 | `1125000000.00`                                                                                                             |
| 11 | `quality_packaging_notes`  | `TEXT`                     | `NULL`                                                   | Khuyến nghị kỹ thuật rút ra từ phân tích AI/NLP đánh giá khách hàng (VD: yêu cầu đóng gói xốp chống sốc 2 lớp, kiểm tra men an toàn máy rửa bát) | `'Thị trường Mỹ có 18% phàn nàn vỡ khi vận chuyển: Cần yêu cầu xưởng đóng hộp xốp định hình 2 lớp.'` |
| 12 | `created_at`               | `TIMESTAMP`                | `DEFAULT CURRENT_TIMESTAMP`                              | Thời điểm hệ thống sinh đề xuất                                                                                                                                     | `'2026-11-25 08:00:00'`                                                                                                     |

---

## 3. Quy Tắc Ánh Xạ & Chuẩn Hóa Dữ Liệu Giữa Các Thành Viên

Để đảm bảo dữ liệu do **Dương (Thu thập & ETL)**, **Nguyên (AI/NLP)** và **Trung (Website & Dashboard BI)** kết nối trơn tru trên cơ sở dữ liệu của **Ngọc Anh**, các bảng trên tuân thủ 3 quy tắc tích hợp:

1. **Chuẩn hóa Khóa ngoại Danh mục (`category_id` và `country_id`):**
   - Mọi dữ liệu thương mại (UN Comtrade), xu hướng (Google Trends), sản phẩm quốc tế (Etsy/Amazon) và sản phẩm nội địa (Minh Long 1, Bát Tràng) đều ánh xạ chung về bảng `countries` (theo mã ISO3) và bảng `product_categories` (4 dòng sản phẩm chính).
2. **Đồng bộ Bộ 5 Thuộc tính Sản phẩm giữa Quốc tế và Nội địa:**
   - Hai bảng `market_products` và `supplier_products` cùng chia sẻ bộ cột thuộc tính chuẩn hóa: `color` (Màu sắc), `shape` (Hình dạng), `material` (Chất liệu), `style` (Phong cách), và `is_dishwasher_safe` / `is_heat_resistant` (Đặc tính kỹ thuật) để thuật toán đối chiếu (Matching) có thể so khớp trực tiếp bằng truy vấn SQL hoặc Python.
3. **Lưu trữ đầu ra của AI/NLP trực tiếp trong CSDL:**
   - Kết quả mô hình phân loại cảm xúc của bạn Nguyên sẽ cập nhật trực tiếp vào cột `sentiment_label`, `sentiment_score` của bảng `product_reviews` và bảng chi tiết `review_aspects`, giúp bạn Trung truy vấn vẽ Dashboard 3 mà không cần chạy lại mô hình AI mỗi lần tải trang.
