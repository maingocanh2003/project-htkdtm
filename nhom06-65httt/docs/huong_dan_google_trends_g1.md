# Thu thập Google Trends G1 – 6 thị trường

Chỉ thu thập thủ công từ Google Trends Explore:
<https://trends.google.com/trends/explore>. Không dùng API chưa được cấp quyền
và không scrape website.

## Thiết lập thống nhất

- Lặp lại lần lượt cho sáu quốc gia: VN (Vietnam), US (United States),
  JP (Japan), DE (Germany), FR (France), IN (India).
- Thời gian: Past 5 years
- Danh mục: All categories
- Loại tìm kiếm: Web Search
- Từ khóa, đúng thứ tự khi Compare: `ceramic`, `ceramics`, `pottery`, `porcelain`, `stoneware`

## Quy ước tên file

Thay `{GEO}` bằng một trong `VN`, `US`, `JP`, `DE`, `FR`, `IN`; thay
`YYYYMMDD` bằng ngày export thực tế. Mỗi thị trường cần đủ 22 CSV, tổng cộng
132 file.

### Compare

```text
g1_{GEO}_compare5_interest_over_time_YYYYMMDD.csv
g1_{GEO}_compare5_interest_by_region_YYYYMMDD.csv
```

### Related Queries và Related Topics

Lặp lại từng mẫu cho cả năm từ khóa và các section `top`, `rising`:

```text
g1_{GEO}_{KEYWORD}_related_queries_top_YYYYMMDD.csv
g1_{GEO}_{KEYWORD}_related_queries_rising_YYYYMMDD.csv
g1_{GEO}_{KEYWORD}_related_topics_top_YYYYMMDD.csv
g1_{GEO}_{KEYWORD}_related_topics_rising_YYYYMMDD.csv
```

## Các bước thao tác

1. Mở Explore; chọn một trong sáu quốc gia và đặt Past 5 years, All categories, Web Search.
2. Với Compare, thêm đủ 5 từ khóa giữ nguyên như trên. Tải riêng biểu đồ Interest over time và Interest by region.
3. Với từng từ khóa, mở Related queries và Related topics; tải riêng mục Top và Rising. Không gộp Related của nhiều từ khóa vào cùng file.
4. Lặp lại cho đủ sáu quốc gia. Đặt toàn bộ 132 CSV vào:
   `nhom06-65httt/data/incoming/google_trends/`.
5. Từ thư mục gốc repository, chạy thử kiểm tra:

   ```powershell
   python nhom06-65httt\src\etl\google_trends_csv_importer.py --dry-run
   ```

6. Nếu báo cáo không có file Rejected, import bằng:

   ```powershell
   python nhom06-65httt\src\etl\google_trends_csv_importer.py
   ```

Importer báo cáo Imported, Would import, Skipped và Rejected; collection được lưu trong
`nhom06-65httt/data/raw/google_trends/`. File trùng SHA-256 sẽ bị bỏ qua. Dry-run không
ghi collection hoặc import index. Không dùng API chưa được cấp quyền và không scrape
website.
