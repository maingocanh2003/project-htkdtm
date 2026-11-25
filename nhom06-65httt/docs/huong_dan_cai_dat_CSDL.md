# Hướng Dẫn Cài Đặt Cơ Sở Dữ Liệu PostgreSQL Bằng pgAdmin 4

Tài liệu này hướng dẫn các thành viên trong nhóm (**Nhóm 06 – 65HTTT**) cách khởi tạo Cơ sở dữ liệu PostgreSQL trên máy cá nhân thông qua công cụ **pgAdmin 4** từ 2 file thiết kế CSDL trong thư mục `src/database/`.

---

## 1. Danh Sách File Trong Thư Mục `src/database/`

- `01_init_oltp_erd_schema.sql`: Script khởi tạo **13 bảng** theo mô hình cơ sở dữ liệu quan hệ (**ERD – OLTP**).
- `02_init_olap_star_schema.sql`: Script khởi tạo **8 bảng** (5 bảng `dim_*` và 3 bảng `fact_*`) theo mô hình kho dữ liệu (**Star Schema – OLAP**) phục vụ phân tích BI.

---

## 2. Các Bước Thực Hiện Trên pgAdmin 4

### Bước 1: Kéo mã nguồn mới nhất từ nhánh của nhóm về máy
Mở Terminal / Git Bash tại thư mục dự án `project-htkdtm` và chạy lệnh:

```bash
git checkout nhom06-65httt
git pull origin nhom06-65httt
```

---

### Bước 2: Mở pgAdmin 4 và tạo Database mới
1. Mở ứng dụng **pgAdmin 4** trên máy tính.
2. Ở khung **Browser** bên trái, nhấn mở rộng **Servers** $\rightarrow$ chọn phiên bản **PostgreSQL** trên máy của bạn (nhập mật khẩu `postgres` nếu được yêu cầu).
3. Nhấp chuột phải vào mục **Databases** $\rightarrow$ chọn **Create** $\rightarrow$ **Database...**
4. Tại tab **General**:
   - Ô **Database**: Nhập tên cơ sở dữ liệu thống nhất cho cả nhóm là:
     ```text
     ceramic_bi_db
     ```
5. Tại tab **Definition** (kiểm tra mặc định):
   - **Encoding**: `UTF8` (để hiển thị đúng tiếng Việt).
6. Nhấn nút **Save** để tạo Database.

---

### Bước 3: Chạy file 01 – Tạo 13 bảng mô hình ERD (`01_init_oltp_erd_schema.sql`)
1. Ở cây thư mục bên trái, tìm đến database **`ceramic_bi_db`** vừa tạo.
2. Nhấp chuột phải vào **`ceramic_bi_db`** $\rightarrow$ chọn **Query Tool**.
3. Trên thanh công cụ phía trên của cửa sổ Query Tool, nhấn vào biểu tượng **Open File** (biểu tượng hình thư mục) hoặc nhấn tổ hợp phím `Ctrl + O`.
4. Tìm và chọn file:
   ```text
   project-htkdtm/nhom06-65httt/src/database/01_init_oltp_erd_schema.sql
   ```
5. Nhấn nút **Execute script** (biểu tượng hình tam giác ▶ trên thanh công cụ) hoặc nhấn phím **`F5`**.
6. Kiểm tra khung **Messages** ở phía dưới cùng: Nếu hiển thị **`Query returned successfully`** nghĩa là 13 bảng ERD đã được tạo thành công.

---

### Bước 4: Chạy file 02 – Tạo 8 bảng mô hình Star Schema (`02_init_olap_star_schema.sql`)
1. Vẫn tại cửa sổ **Query Tool** của database `ceramic_bi_db`, nhấn tiếp nút **Open File** (`Ctrl + O`).
2. Tìm và chọn file:
   ```text
   project-htkdtm/nhom06-65httt/src/database/02_init_olap_star_schema.sql
   ```
3. Nhấn nút **Execute script** (▶) hoặc phím **`F5`**.
4. Khi khung **Messages** báo **`Query returned successfully`**, toàn bộ 5 bảng Dimension và 3 bảng Fact của mô hình Star Schema đã được tạo xong.

---

### Bước 5: Kiểm tra danh sách 21 bảng đã tạo
1. Ở khung **Browser** bên trái của pgAdmin 4, mở rộng theo đường dẫn:
   `ceramic_bi_db` $\rightarrow$ `Schemas` $\rightarrow$ `public` $\rightarrow$ **`Tables`**.
2. Nhấp chuột phải vào mục **`Tables`** $\rightarrow$ chọn **Refresh**.
3. Mở rộng mục **`Tables`**, nếu thấy đầy đủ **21 bảng** dưới đây là cài đặt hoàn tất 100%:
   - **13 bảng ERD:** `countries`, `customers`, `market_products`, `market_regions`, `order_recommendations`, `product_categories`, `product_reviews`, `review_aspects`, `search_trends`, `supplier_products`, `suppliers`, `trade_statistics`, `trending_keywords`.
   - **8 bảng Star Schema:** `dim_market`, `dim_product`, `dim_sentiment_aspect`, `dim_supplier`, `dim_time`, `fact_customer_review`, `fact_market_demand`, `fact_supplier_recommendation`.

---

## 3. Thông Tin Kết Nối CSDL Thống Nhất Cho Code (Python / Backend / BI)

Khi các thành viên viết code Python (ETL của **Dương**, AI/NLP của **Nguyên**) hoặc kết nối Backend/Dashboard (của **Trung**), sử dụng chung cấu hình kết nối cục bộ như sau:

- **Host:** `localhost` (hoặc `127.0.0.1`)
- **Port:** `5432`
- **Database Name:** `ceramic_bi_db`
- **Username:** `postgres`
- **Password:** *(Mật khẩu PostgreSQL trên máy cá nhân của từng thành viên)*
- **Schema:** `public`
