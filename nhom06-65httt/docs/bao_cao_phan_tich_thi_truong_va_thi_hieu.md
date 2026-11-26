# BÁO CÁO PHÂN TÍCH THỊ TRƯỜNG, XU HƯỚNG VÀ THỊ HIẾU TIÊU DÙNG GỐM SỨ QUỐC TẾ

- **Đề tài:** Xây dựng hệ thống Business Intelligence phân tích thị hiếu tiêu dùng quốc tế và hỗ trợ ra quyết định đặt hàng xuất khẩu gốm sứ Việt Nam
- **Học phần:** Hệ thống Kinh doanh Thông minh (HTKDTM) – Nhóm 06 – Lớp 65HTTT
- **Người phụ trách:** Nguyễn Thế Nguyên (MSSV: 2351160539 – Phân tích thị hiếu và thị trường bằng AI)
- **Nguồn kết quả:** Kết xuất trực tiếp từ [run_pipeline.py](../src/ai_nlp/run_pipeline.py) tại thư mục `src/ai_nlp/outputs/` trên bộ dữ liệu benchmark chuẩn hóa ERD (`135` quốc gia, `240` sản phẩm quốc tế, `600` lượt đánh giá).

---

## 1. Phân Tích Quy Mô Và Tiềm Năng Thị Trường (FR-2.1 – Dashboard 1)

Hệ thống tổng hợp dữ liệu giao thương giai đoạn **2021–2023** của **135 quốc gia/vùng lãnh thổ** (mã HS `6911`, `6912`, `6913`), tính toán thị phần, tốc độ tăng trưởng kép **CAGR**, sức cầu tìm kiếm và xếp hạng theo **Điểm tiềm năng thị trường (`market_potential_score`, thang 0–100)**.

### Bảng xếp hạng Top 10 thị trường tiềm năng nhất (năm 2023)

| Hạng | Mã QG | Quốc gia | Kim ngạch 2023 (USD) | Thị phần (%) | CAGR 2021–2023 (%) | Điểm tìm kiếm TB | Điểm tiềm năng | Phân tầng thị trường |
| :-: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `USA` | United States | \$547,551,976.07 | 13.34% | +14.18% | 71.12 | **97.41** | Tier 1 - High Potential |
| 2 | `JPN` | Japan | \$222,987,703.07 | 5.43% | +9.79% | 65.25 | **72.31** | Tier 2 - Growing |
| 3 | `IND` | India | \$91,071,218.37 | 2.22% | +15.73% | 62.88 | **71.03** | Tier 2 - Growing |
| 4 | `DEU` | Germany | \$200,955,719.12 | 4.90% | +10.36% | 62.88 | **68.06** | Tier 2 - Growing |
| 5 | `KOR` | South Korea | \$119,998,047.60 | 2.92% | +12.39% | 62.88 | **67.54** | Tier 2 - Growing |
| 6 | `AUS` | Australia | \$94,916,453.60 | 2.31% | +11.75% | 62.88 | **64.69** | Tier 2 - Growing |
| 7 | `CAN` | Canada | \$102,183,956.55 | 2.49% | +10.29% | 62.88 | **62.80** | Tier 2 - Growing |
| 8 | `C67` | Partner Market 067 | \$31,539,679.19 | 0.77% | +15.36% | 62.88 | **62.35** | Tier 2 - Growing |
| 9 | `ARE` | United Arab Emirates | \$33,839,388.46 | 0.82% | +14.24% | 62.88 | **61.01** | Tier 2 - Growing |
| 10 | `C113` | Partner Market 113 | \$26,207,242.48 | 0.64% | +15.10% | 62.88 | **60.51** | Tier 2 - Growing |

**Nhận xét thị trường:**
- **Hoa Kỳ (`USA`)** là thị trường dẫn đầu tuyệt đối với kim ngạch năm 2023 đạt **\$547.55 triệu USD** (chiếm **13.34%** tổng giao thương mẫu), duy trì mức tăng trưởng kép **+14.18%/năm** và điểm quan tâm tìm kiếm cao nhất (**71.12**).
- **Nhật Bản (`JPN`)** và **Đức (`DEU`)** giữ vị trí trụ cột tại châu Á và châu Âu với quy mô lần lượt **\$222.99 triệu USD** (5.43% thị phần) và **\$200.96 triệu USD** (4.90% thị phần).
- **Ấn Độ (`IND`)** và **Hàn Quốc (`KOR`)** nổi lên là nhóm thị trường tăng trưởng nhanh (**CAGR +15.73%** và **+12.39%**).

---

## 2. Phân Tích Xu Hướng Tìm Kiếm 52 Tuần & Từ Khóa Bứt Phá (FR-2.2 – Dashboard 1 & 2)

### 2.1. Diễn biến theo chuỗi thời gian 52 tuần
- Dòng **Ly cốc sứ (`MUG_CUP`)** có mức độ quan tâm tìm kiếm cao nhất trên cả 5 thị trường lớn, dẫn đầu tại Mỹ (**79.83** điểm TB, đạt đỉnh 100 tại tuần 44) và Nhật Bản (**72.88** điểm, tăng nửa cuối năm H2 so với H1 là **+10.79%**).
- Dòng **Bát đĩa bàn ăn (`DINNERWARE`)** thể hiện xu hướng tăng trưởng mạnh (`Strong Uptrend`) tại Mỹ (**+10.20%**), Đức (**+11.29%**) và Anh (**+11.46%**), đạt đỉnh vào giai đoạn tuần 45–52 (mùa mua sắm cuối năm).
- Dòng **Lọ hoa mỹ nghệ (`VASE_DECOR`)** tại Mỹ ghi nhận xu hướng `Strong Uptrend` với mức tăng H2/H1 đạt **+9.97%**, đỉnh điểm tuần 49.

### 2.2. Phân bố địa lý 51 bang/vùng tại Hoa Kỳ
Trong 51 bang/vùng lãnh thổ Hoa Kỳ được theo dõi, nhóm dẫn đầu nhu cầu tìm kiếm gốm sứ gồm: **Oregon** (88.75), **Colorado** (85.25), **Florida** (82.00), **Washington** (81.75), **New York** (81.00), **Texas** (79.75) và **California** (79.25).

### 2.3. Từ khóa thịnh hành bứt phá (+145% đến +5.300%)

| Hạng | Quốc gia | Dòng sản phẩm | Từ khóa bứt phá | Thuộc tính liên quan | Tăng trưởng | Phân loại |
| :-: | :---: | :--- | :--- | :---: | :---: | :---: |
| 1 | `USA` | Lọ hoa mỹ nghệ | `wabi sabi ceramic vase` | `style` | **+5,300%** | Breakout |
| 2 | `JPN` | Bộ ấm chén | `minimalist natural clay tea set` | `style` | **+2,400%** | Breakout |
| 3 | `USA` | Bát đĩa bàn ăn | `speckled stoneware dinnerware` | `material` | **+1,850%** | Breakout |
| 4 | `JPN` | Bát đĩa bàn ăn | `japanese earth tone ceramic bowl` | `color` | **+980%** | Breakout |
| 5 | `FRA` | Lọ hoa mỹ nghệ | `artisan terracotta table vase` | `material` | **+760%** | Rising |
| 6 | `USA` | Ly cốc sứ | `dishwasher safe ceramic mug` | `feature` | **+640%** | Rising |

---

## 3. Phân Tích Thị Hiếu Theo 5 Nhóm Thuộc Tính & Phân Khúc Giá (FR-2.3 – Dashboard 2)

Từ 240 sản phẩm quốc tế trên Etsy và Amazon tại 5 thị trường mục tiêu (`USA`, `JPN`, `DEU`, `FRA`, `GBR`), bảng hồ sơ thị hiếu cho thấy sự khác biệt rõ rệt về thẩm mỹ và yêu cầu kỹ thuật:

| Quốc gia | Dòng SP nổi bật | Màu sắc ưa chuộng | Hình dáng | Chất liệu | Phong cách | Phân khúc giá | Giá TB (USD) | An toàn máy rửa bát | Chịu nhiệt |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **Mỹ (`USA`)** | Bộ ấm chén (25.0%) | Natural Beige (25.0%), Cobalt Blue (25.0%) | Oval (37.5%) | Earthenware (35.4%) | Modern (37.5%) | Mid-range \$20–\$60 (52.1%) | \$60.17 | **91.67%** | 81.25% |
| **Nhật (`JPN`)** | Ly cốc sứ (25.0%) | Brown (33.3%), Celadon Green (27.1%) | Organic Artistic (39.6%) | Stoneware (54.2%) | Handmade Rustic (41.7%) | Premium >\$60 (64.6%) | \$68.55 | 66.67% | 79.17% |
| **Đức (`DEU`)** | Bát đĩa bàn ăn (25.0%) | Cobalt Blue (35.4%), Gray (22.9%) | Oval (35.4%) | Porcelain (50.0%) | Modern (54.2%) | Mid-range \$20–\$60 (64.6%) | \$51.27 | **95.83%** | 72.92% |
| **Pháp (`FRA`)** | Bát đĩa bàn ăn (25.0%) | Cobalt Blue (29.2%), Multicolor (29.2%) | Round (35.4%) | Earthenware (43.8%) | Traditional (33.3%) | Premium >\$60 (70.8%) | \$73.88 | 79.17% | **85.42%** |
| **Anh (`GBR`)** | Bộ ấm chén (25.0%) | White (45.8%), Cobalt Blue (27.1%) | Oval (50.0%) | Stoneware (54.2%) | Modern (35.4%) | Mid-range \$20–\$60 (64.6%) | \$48.00 | 83.33% | 83.33% |

**Khuyến nghị lựa chọn mẫu mã cho từng thị trường:**
- **Mỹ & Đức:** Ưu tiên tuyệt đối tiêu chuẩn **an toàn máy rửa bát** (`91.67%` tại Mỹ và `95.83%` tại Đức), tầm giá **Mid-range \$20–\$60**, thiết kế **Modern**, chất liệu Porcelain/Earthenware.
- **Nhật Bản:** Tập trung phân khúc **Premium (>\$60)** với tông màu tự nhiên/men ngọc (**Brown**, **Celadon Green**), dáng **Organic Artistic**, chất liệu **Stoneware** phong cách thủ công (**Handmade Rustic**).
- **Pháp:** Ưa chuộng phân khúc **Premium (>\$60)** (giá TB **\$73.88**), phong cách **Traditional**, chú trọng khả năng chịu nhiệt (**85.42%**).

---

## 4. Phân Tích Cảm Xúc & Khía Cạnh Khen/Chê Từ Khách Hàng AI/NLP (FR-2.4 & FR-2.5 – Dashboard 3)

### 4.1. Phân bố cảm xúc tổng thể theo quốc gia (600 đánh giá)

| Quốc gia | Tổng lượt đánh giá | Tích cực (`Positive`) | Trung lập (`Neutral`) | Tiêu cực (`Negative`) |
| :---: | :---: | :---: | :---: | :---: |
| `USA` | 144 | 90 | 24 | 30 |
| `JPN` | 144 | 75 | 36 | 33 |
| `DEU` | 120 | 63 | 20 | 37 |
| `FRA` | 96 | 58 | 18 | 20 |
| `GBR` | 96 | 44 | 22 | 30 |

### 4.2. Các điểm nghẽn chất lượng nổi bật từ trích xuất khía cạnh (`nlp_aspect_quality_notes.csv`)
Phân tích 946 lượt đề cập khía cạnh cho thấy những cảnh báo kỹ thuật cần lưu ý trước khi đặt hàng sản xuất trong nước:
- **Độ bền lớp men (`Glaze Durability`):** Tỷ lệ phàn nàn cao ở nhóm Lọ hoa Nhật (`80.00%` trên 10 lượt đề cập), Bộ ấm chén Nhật (`66.67%`), Bộ ấm chén Đức (`66.67%`) và Ly cốc sứ Pháp (`60.00%`) $\rightarrow$ *Cần kiểm soát chặt độ dày lớp men chống rạn và chống trầy xước dao nĩa.*
- **Đóng gói chống vỡ (`Packaging`):** Nhóm Ly cốc sứ tại Anh ghi nhận tỷ lệ phàn nàn đóng gói **`66.67%`** $\rightarrow$ *Bắt buộc yêu cầu nhà cung cấp dùng hộp carton 2 lớp và xốp định hình chống sốc khi xuất khẩu.*
- **Thiết kế & Giá trị (`Design & Color`, `Price/Value`):** Nhóm Bát đĩa bàn ăn Anh (`75.00%` phàn nàn màu/kiểu dáng) và Bộ ấm chén Đức (`66.67%`) cho thấy cần kiểm tra đồng nhất màu men thực tế so với ảnh mẫu.

---

## 5. Danh Mục Tệp Kết Quả Bàn Giao Cho Dashboard BI

Toàn bộ kết quả đã được xuất sẵn sàng dưới dạng CSV và JSON tổng hợp tại `src/ai_nlp/outputs/`:
- **Phục vụ Dashboard 1 (Tổng quan thị trường):** `market_yearly_metrics.csv`, `market_potential_ranking.csv`, `key_markets_hs_breakdown.csv`, `trend_regional_51_states.csv`
- **Phục vụ Dashboard 2 (Phân tích thị hiếu):** `trend_weekly_trajectory.csv`, `trend_seasonality_quarterly.csv`, `trend_breakout_keywords.csv`, `taste_attribute_preferences.csv`, `taste_country_profiles.csv`, `taste_functional_features.csv`, `taste_price_distribution.csv`
- **Phục vụ Dashboard 3 (Phân tích khách hàng AI/NLP):** `nlp_review_predictions.csv`, `nlp_sentiment_summary.csv`, `nlp_review_aspects.csv`, `nlp_aspect_market_summary.csv`, `nlp_aspect_quality_notes.csv`
- **Gói JSON tổng hợp cho API/Website:** `dashboard_analysis_bundle.json`
