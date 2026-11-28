# Hướng Dẫn Cài Đặt & Import Dữ Liệu Sạch Vào CSDL PostgreSQL (`ceramic_bi_db`)

Tài liệu này hướng dẫn các thành viên trong nhóm (**Nhóm 06 – 65HTTT**) cách khởi tạo Cơ sở dữ liệu PostgreSQL **`ceramic_bi_db`** và **import toàn bộ bộ dữ liệu thật đã làm sạch** từ thư mục `nhom06-65httt/data/integrated/` vào **21 bảng** (13 bảng OLTP ERD + 8 bảng OLAP Star Schema).

---

## 1. Cấu Trúc Thư Mục CSDL & Dữ Liệu Sạch Bàn Giao

1. **Thiết kế Schema SQL (`nhom06-65httt/src/database/`):**
   - `01_init_oltp_erd_schema.sql`: Khởi tạo **13 bảng** theo mô hình cơ sở dữ liệu quan hệ (**ERD – OLTP**).
   - `02_init_olap_star_schema.sql`: Khởi tạo **8 bảng** (5 bảng `dim_*` và 3 bảng `fact_*`) theo mô hình kho dữ liệu (**Star Schema – OLAP**).
2. **Bộ dữ liệu sạch thống nhất (`nhom06-65httt/data/integrated/`):**
   - Gồm **11 file CSV** (**35.398 bản ghi sạch** đã qua chuẩn hóa, kiểm định chất lượng và khử trùng lặp từ 8 nguồn: UN Comtrade, ITC Trade Map, Google Trends, Amazon, Etsy, Minh Long 1, Gốm Bát Tràng, Thế Giới Gốm) kèm file kiểm tra `integration_manifest.json`.
3. **Công cụ nạp CSDL tự động (`nhom06-65httt/src/etl/db_loader.py`):**
   - Script Python tự động tạo database `ceramic_bi_db`, tạo đủ 21 bảng, nạp toàn bộ 11 file CSV vào các bảng OLTP và đồng bộ sang các bảng Dimension/Fact của Star Schema.

---

## 2. Cách 1: Import Tự Động Toàn Bộ Bằng 1 Lệnh Python (Khuyên Dùng)

Đây là cách nhanh nhất và chính xác nhất (chỉ mất khoảng **3–5 giây**), không cần thao tác tay từng bảng trên pgAdmin 4.

### Bước 1: Kéo mã nguồn và dữ liệu mới nhất về máy
Mở Terminal / PowerShell tại thư mục gốc dự án `project-htkdtm`:

```powershell
git checkout nhom06-65httt
git pull origin nhom06-65httt
```

### Bước 2: Cài đặt thư viện kết nối PostgreSQL (nếu chưa cài)
```powershell
py -m pip install psycopg2-binary
```

### Bước 3: Chạy lệnh tự động khởi tạo CSDL và nạp dữ liệu sạch
Thay `MAT_KHAU_POSTGRES_CUA_BAN` bằng mật khẩu user `postgres` trên máy cá nhân của bạn:

```powershell
py nhom06-65httt\src\etl\db_loader.py --password "MAT_KHAU_POSTGRES_CUA_BAN"
```

*(Tùy chọn: Nếu PostgreSQL của bạn dùng cổng hoặc user khác mặc định, có thể truyền thêm `--host localhost --port 5432 --user postgres --dbname ceramic_bi_db`).*

### Kết quả hiển thị trên Terminal khi nạp thành công 100%:
```text
=== Loading PostgreSQL Database (localhost:5432/ceramic_bi_db) ===
  - countries                :     227 rows
  - market_regions           :     235 rows
  - product_categories       :       4 rows
  - trade_statistics         :  15,665 rows
  - search_trends            :   9,005 rows
  - trending_keywords        :   1,247 rows
  - market_products          :   1,693 rows
  - customers                :   1,186 rows
  - product_reviews          :   1,186 rows
  - suppliers                :       3 rows
  - supplier_products        :   4,947 rows
  - dim_time                 :     265 rows
  - dim_market               :     462 rows
  - dim_product              :   6,644 rows
  - dim_supplier             :       3 rows
  - fact_market_demand       :  15,665 rows
```

> **Lưu ý:** Nếu trong quá trình phát triển cần chạy lại pipeline làm sạch và xuất lại bộ CSV tích hợp từ `data/raw/`, chạy lần lượt 3 lệnh sau:
> ```powershell
> $env:PYTHONPATH="nhom06-65httt/src"
> py -m etl.pipeline --raw nhom06-65httt/data/raw --processed nhom06-65httt/data/processed --quarantine nhom06-65httt/data/quarantine
> py nhom06-65httt\src\etl\integrated_dataset_exporter.py
> py nhom06-65httt\src\etl\db_loader.py --password "MAT_KHAU_POSTGRES_CUA_BAN"
> ```

---

## 3. Cách 2: Khởi Tạo & Import Thủ Công Qua Giao Diện pgAdmin 4

Nếu thành viên muốn thao tác trực quan hoàn toàn trên **pgAdmin 4**, thực hiện lần lượt theo các bước sau:

### Bước 1: Tạo Database `ceramic_bi_db` trên pgAdmin 4
1. Mở **pgAdmin 4** $\rightarrow$ mở rộng **Servers** $\rightarrow$ chọn **PostgreSQL**.
2. Nhấp chuột phải vào **Databases** $\rightarrow$ **Create** $\rightarrow$ **Database...**
3. Tại tab **General**, nhập tên Database:
   ```text
   ceramic_bi_db
   ```
4. Tại tab **Definition**, đảm bảo **Encoding** là `UTF8` $\rightarrow$ nhấn **Save**.

### Bước 2: Chạy 2 script khởi tạo 21 bảng (`01` và `02`)
1. Nhấp chuột phải vào database **`ceramic_bi_db`** $\rightarrow$ chọn **Query Tool**.
2. Nhấn biểu tượng **Open File** (`Ctrl + O`), mở và nhấn **`F5` (Execute)** lần lượt 2 file theo đúng thứ tự:
   - File 1: `nhom06-65httt/src/database/01_init_oltp_erd_schema.sql` (Tạo 13 bảng ERD)
   - File 2: `nhom06-65httt/src/database/02_init_olap_star_schema.sql` (Tạo 8 bảng Star Schema)

### Bước 3: Import 11 file CSV trong `nhom06-65httt/data/integrated/` theo đúng thứ tự Khóa Ngoại (Foreign Key)
Để không bị lỗi ràng buộc khóa ngoại (`FOREIGN KEY constraint`), **bắt buộc import theo đúng thứ tự từ 1 đến 11** dưới đây.

Với mỗi bảng, nhấp chuột phải vào tên bảng trong `ceramic_bi_db` $\rightarrow$ `Schemas` $\rightarrow$ `public` $\rightarrow$ `Tables` $\rightarrow$ chọn **Import/Export Data...**:
- **Import/Export:** Chọn **Import**
- **Filename:** Chọn file `.csv` tương ứng trong `nhom06-65httt/data/integrated/`
- **Format:** `csv` | **Encoding:** `UTF8`
- **Header:** Bật **`Yes`** (ON) | **Delimiter:** `,` (dấu phẩy)

| Thứ tự Import | Tên bảng trong pgAdmin 4 | File CSV chọn từ `nhom06-65httt/data/integrated/` | Số dòng chuẩn sau Import |
|:---:|---|---|---:|
| **1** | `countries` | `countries.csv` | **227** |
| **2** | `market_regions` | `market_regions.csv` | **235** |
| **3** | `product_categories` | `product_categories.csv` | **4** |
| **4** | `suppliers` | `suppliers.csv` | **3** |
| **5** | `trade_statistics` | `trade_statistics.csv` | **15.665** |
| **6** | `search_trends` | `search_trends.csv` | **9.005** |
| **7** | `trending_keywords` | `trending_keywords.csv` | **1.247** |
| **8** | `market_products` | `market_products.csv` | **1.693** |
| **9** | `customers` | `customers.csv` | **1.186** |
| **10** | `product_reviews` | `product_reviews.csv` | **1.186** |
| **11** | `supplier_products` | `supplier_products.csv` | **4.947** |

---

## 4. Kiểm Tra Đối Soát Dữ Liệu Sau Khi Import

Sau khi hoàn tất Cách 1 (hoặc Cách 2), mở **Query Tool** của `ceramic_bi_db` trên pgAdmin 4 và chạy câu truy vấn kiểm tra nhanh sau:

```sql
SELECT 'countries' AS table_name, COUNT(*) AS row_count FROM countries
UNION ALL SELECT 'market_regions', COUNT(*) FROM market_regions
UNION ALL SELECT 'product_categories', COUNT(*) FROM product_categories
UNION ALL SELECT 'trade_statistics', COUNT(*) FROM trade_statistics
UNION ALL SELECT 'search_trends', COUNT(*) FROM search_trends
UNION ALL SELECT 'trending_keywords', COUNT(*) FROM trending_keywords
UNION ALL SELECT 'market_products', COUNT(*) FROM market_products
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'product_reviews', COUNT(*) FROM product_reviews
UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
UNION ALL SELECT 'supplier_products', COUNT(*) FROM supplier_products
UNION ALL SELECT 'dim_time', COUNT(*) FROM dim_time
UNION ALL SELECT 'dim_market', COUNT(*) FROM dim_market
UNION ALL SELECT 'dim_product', COUNT(*) FROM dim_product
UNION ALL SELECT 'dim_supplier', COUNT(*) FROM dim_supplier
UNION ALL SELECT 'fact_market_demand', COUNT(*) FROM fact_market_demand;
```

Nếu tổng số dòng khớp với bảng thống kê ở Mục 2 (**35.398 dòng OLTP** và **23.039 dòng Star Schema**), cơ sở dữ liệu của bạn đã đồng bộ 100% với dữ liệu chuẩn của nhóm!

---

## 5. Thông Tin Kết Nối CSDL Thống Nhất Cho Các Phân Hệ Tiếp Theo (AI/NLP & Dashboard)

- **Host:** `localhost` (hoặc `127.0.0.1`)
- **Port:** `5432`
- **Database Name:** `ceramic_bi_db`
- **Username:** `postgres`
- **Password:** *(Mật khẩu PostgreSQL trên máy cá nhân của từng thành viên)*
- **Schema:** `public`

Sau khi nạp dữ liệu xong, thành viên phụ trách **Phân hệ 2 (AI/NLP)** có thể chạy ngay mô hình phân tích cảm xúc và trích xuất khía cạnh trực tiếp trên dữ liệu thật trong PostgreSQL bằng lệnh:

```powershell
py -m src.ai_nlp.run_pipeline --source db --save-db
```
*(Lệnh này sẽ tự động điền tiếp kết quả cảm xúc vào bảng `product_reviews`, `review_aspects`, `dim_sentiment_aspect` và `fact_customer_review`).*
