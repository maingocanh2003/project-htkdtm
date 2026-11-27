# ĐÁNH GIÁ MÔ HÌNH AI/NLP PHÂN TÍCH CẢM XÚC VÀ TRÍCH XUẤT KHÍA CẠNH

- **Đề tài:** Xây dựng hệ thống Business Intelligence phân tích thị hiếu tiêu dùng quốc tế và hỗ trợ ra quyết định đặt hàng xuất khẩu gốm sứ Việt Nam
- **Học phần:** Hệ thống Kinh doanh Thông minh (HTKDTM) – Nhóm 06 – Lớp 65HTTT
- **Người phụ trách:** Nguyễn Thế Nguyên (MSSV: 2351160539 – Phân tích thị hiếu và thị trường bằng AI)
- **Mã nguồn liên quan:** [sentiment_model.py](../src/ai_nlp/sentiment_model.py), [aspect_extractor.py](../src/ai_nlp/aspect_extractor.py)

---

## 1. Mô Hình Phân Loại Cảm Xúc Đánh Giá (Sentiment Analysis – FR-2.4)

### 1.1. Quy trình tiền xử lý và trích chọn đặc trưng
1. **Hợp nhất văn bản:** Kết hợp trường `review_title` và `review_text` từ bảng `product_reviews`.
2. **Bảo toàn ngữ nghĩa phủ định (`clean_review_text`):** Chuẩn hóa chữ thường, giữ nguyên các cụm phủ định đặc thù gốm sứ thành token ghép (ví dụ: `not dishwasher` $\rightarrow$ `not_dishwasher`, `no chipping` $\rightarrow$ `not_chipping`).
3. **Biểu diễn đặc trưng kết hợp (`FeatureUnion`):**
   - **Word TF-IDF:** `ngram_range=(1, 2)`, `min_df=2`, `max_features=8000`, `sublinear_tf=True` nhằm nắm bắt cụm từ chuyên ngành (*"chipped rim"*, *"double-boxed"*, *"dishwasher safe"*).
   - **Character TF-IDF:** `analyzer='char_wb'`, `ngram_range=(3, 5)`, `min_df=3`, `max_features=8000` giúp tăng độ bền với biến thể hình thái từ và lỗi chính tả nhẹ.

### 1.2. So sánh thuật toán qua Stratified 5-Fold Cross-Validation
Tập dữ liệu đánh giá benchmark gồm **600 lượt nhận xét** (tỷ lệ lớp: 55% `Positive`, 20% `Neutral`, 25% `Negative`) được chia phân tầng theo tỷ lệ **80% huấn luyện (480 mẫu)** / **20% kiểm thử độc lập (120 mẫu)** với `random_state=42`.

| Thuật toán ứng viên | CV Macro-F1 (Mean) | Độ lệch chuẩn (Std) | Ghi chú lựa chọn |
| :--- | :---: | :---: | :--- |
| **`LogisticRegression`** (`C=2.0`, `class_weight='balanced'`) | **1.0000** | 0.0000 | **Được chọn** (xác suất hiệu chỉnh trực tiếp cho `sentiment_score`) |
| `CalibratedLinearSVC` (`CalibratedClassifierCV`, `cv=3`) | 1.0000 | 0.0000 | Tương đương về Macro-F1 trên CV |
| `ComplementNB` (`alpha=0.5`) | 0.9874 | 0.0119 | Làm mô hình nền (baseline) |

### 1.3. Kết quả đánh giá trên tập kiểm thử độc lập (120 mẫu)
- **Accuracy:** `1.0000` (100.00%)
- **Macro-F1:** `1.0000` | **Weighted-F1:** `1.0000`

| Nhãn cảm xúc | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `Positive` | 1.0000 | 1.0000 | 1.0000 | 66 |
| `Neutral` | 1.0000 | 1.0000 | 1.0000 | 24 |
| `Negative` | 1.0000 | 1.0000 | 1.0000 | 30 |

**Ma trận nhầm lẫn (Confusion Matrix – hàng: thực tế, cột: dự đoán `[Positive, Neutral, Negative]`):**

```text
[[66,  0,  0],
 [ 0, 24,  0],
 [ 0,  0, 30]]
```

**Đối chiếu chéo với thang điểm 1–5 sao (`rating_vs_sentiment_check`):**
- Nhóm dự đoán `Negative` (30 mẫu): điểm sao trung bình = **1.63 sao**
- Nhóm dự đoán `Neutral` (24 mẫu): điểm sao trung bình = **3.00 sao**
- Nhóm dự đoán `Positive` (66 mẫu): điểm sao trung bình = **4.64 sao**

> [!NOTE]
> Kết quả 100% trên tập benchmark phản ánh đặc tính phân tách rõ của tập dữ liệu kiểm thử chuẩn hóa; khi nạp thêm dữ liệu thô đa dạng từ Amazon/Etsy trong `ceramic_bi_db`, pipeline `CeramicSentimentModel` hỗ trợ tái huấn luyện hoặc tinh chỉnh ngưỡng xác suất `sentiment_score` thông qua tham số `--source db`.

---

## 2. Mô Hình Trích Xuất Khía Cạnh Khen / Chê (ABSA – FR-2.5)

### 2.1. Kiến trúc tách mệnh đề và nhận diện 5 khía cạnh
Một nhận xét thực tế thường chứa đồng thời lời khen và phàn nàn trên các khía cạnh khác nhau. Bộ trích xuất trong `aspect_extractor.py` thực hiện:
1. **Tách mệnh đề (`split_clauses`):** Tách câu theo dấu câu (`. ! ? ;`) và liên từ đối lập (`however`, `but`, `although`, `though`, `yet`).
2. **Ánh xạ 5 nhóm khía cạnh chuẩn Star Schema:**
   - `Glaze Durability` (Độ bền lớp men, rạn men, trầy xước, sứt mẻ)
   - `Packaging` (Đóng gói, xốp chống sốc, vỡ trong quá trình vận chuyển)
   - `Design & Color` (Thiết kế, màu sắc, họa tiết, hình dáng)
   - `Heat/Dishwasher` (Khả năng chịu nhiệt, an toàn máy rửa bát / lò vi sóng)
   - `Price/Value` (Mức giá và giá trị sử dụng tương xứng)
3. **Phân loại thái độ cấp mệnh đề (`_score_clause_sentiment`):** Kết hợp từ điển cực tính chuyên ngành gốm sứ và mẫu phủ định (nhận diện chính xác *"no breakage"*, *"zero crazing"* là `Positive`, còn *"not dishwasher safe"* là `Negative`).

### 2.2. Kết quả đánh giá ABSA trên tập kiểm thử (120 bình luận)

| Chỉ số đánh giá tổng hợp | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: |
| **Aspect Category Detection** (Nhận diện đúng khía cạnh) | **0.9275** | **0.9890** | **0.9572** |
| **Joint Aspect + Sentiment** (Đúng đồng thời khía cạnh & thái độ khen/chê) | **0.9275** | **0.9890** | **0.9572** |

**Chi tiết theo từng khía cạnh trên tập kiểm thử:**

| Khía cạnh (`aspect_category`) | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `Packaging` | 1.0000 | 1.0000 | **1.0000** | 35 |
| `Heat/Dishwasher` | 0.9512 | 1.0000 | **0.9750** | 39 |
| `Price/Value` | 0.9500 | 1.0000 | **0.9744** | 38 |
| `Glaze Durability` | 0.8542 | 1.0000 | **0.9213** | 41 |
| `Design & Color` | 0.8966 | 0.9286 | **0.9123** | 28 |

Trên toàn bộ 600 bình luận, hệ thống trích xuất được **946 bản ghi khía cạnh** kèm cụm từ minh chứng (`extracted_phrase`), sẵn sàng ghi vào bảng `review_aspects` và đồng bộ sang `fact_customer_review` trong PostgreSQL.
