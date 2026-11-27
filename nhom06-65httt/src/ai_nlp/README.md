# Phân Hệ 2: Phân Tích Thị Trường, Thị Hiếu Và Mô Hình AI/NLP

- **Người phụ trách:** Nguyễn Thế Nguyên (MSSV: 2351160539 – Lớp 65HTTT)
- **Phạm vi nghiệp vụ:** FR-2.1 đến FR-2.5 trong [PHÂN TÍCH YÊU CẦU NGHIỆP VỤ.md](../../docs/PHÂN%20TÍCH%20YÊU%20CẦU%20NGHIỆP%20VỤ.md)

## 1. Cấu Trúc Thư Mục `src/ai_nlp/`

- `config.py`: Cấu hình kết nối PostgreSQL (`ceramic_bi_db`), 4 dòng sản phẩm chuẩn hóa (`TEA_SET`, `MUG_CUP`, `DINNERWARE`, `VASE_DECOR`), 5 nhóm thuộc tính và 5 khía cạnh đánh giá ABSA.
- `db_connector.py`: Đọc dữ liệu từ 13 bảng OLTP trong PostgreSQL, ghi kết quả AI/NLP vào `product_reviews`, `review_aspects` và đồng bộ bảng Star Schema (`dim_sentiment_aspect`, `fact_customer_review`). Hỗ trợ tải bộ dữ liệu benchmark chuẩn schema để chạy và kiểm thử độc lập.
- `market_analysis.py` (**FR-2.1**): Tính quy mô kim ngạch (USD, FOB, CIF, kg), thị phần, tăng trưởng YoY, CAGR, chỉ số sức cầu tìm kiếm và xếp hạng tiềm năng cho >130 quốc gia.
- `trend_analysis.py` (**FR-2.2**): Phân tích chuỗi thời gian 52 tuần Google Trends (MA 4 tuần, xu hướng, chỉ số mùa vụ theo quý), phân bố 51 bang/vùng và bảng xếp hạng từ khóa bứt phá (+140% đến +5.300%).
- `taste_analysis.py` (**FR-2.3**): Phân tích thị hiếu theo 5 nhóm thuộc tính (Dòng sản phẩm, Màu sắc, Hình dạng, Chất liệu, Phong cách), công năng (an toàn máy rửa bát, chịu nhiệt) và phân khúc giá theo quốc gia.
- `sentiment_model.py` (**FR-2.4**): Huấn luyện, đối chiếu 3 thuật toán qua Stratified 5-Fold CV (`LogisticRegression`, `CalibratedLinearSVC`, `ComplementNB`) trên đặc trưng Word + Char TF-IDF, đánh giá trên tập kiểm thử độc lập (`Positive`, `Neutral`, `Negative`).
- `aspect_extractor.py` (**FR-2.5**): Trích xuất 5 khía cạnh khen/chê (`Glaze Durability`, `Packaging`, `Design & Color`, `Heat/Dishwasher`, `Price/Value`), tách cụm từ `extracted_phrase`, đánh giá Precision/Recall/F1 trên tập kiểm thử và tổng hợp tỷ lệ phàn nàn theo thị trường.
- `dashboard_exporter.py` & `run_pipeline.py`: Xuất bộ dữ liệu kết quả CSV/JSON vào `outputs/` phục vụ Dashboard 1, 2, 3 và cập nhật CSDL khi chạy với `--save-db`.

## 2. Hướng Dẫn Cài Đặt Và Chạy

```powershell
cd nhom06-65httt
python -m venv src\ai_nlp\.venv
src\ai_nlp\.venv\Scripts\pip.exe install -r src\ai_nlp\requirements.txt

# Chay toan bo pipeline voi bo du lieu benchmark (offline)
src\ai_nlp\.venv\Scripts\python.exe -m src.ai_nlp.run_pipeline --source sample

# Chay voi PostgreSQL ceramic_bi_db va luu ket qua AI/NLP xuong CSDL
Copy-Item src\ai_nlp\.env.example src\ai_nlp\.env
src\ai_nlp\.venv\Scripts\python.exe -m src.ai_nlp.run_pipeline --source db --save-db

# Chay bo kiem thu tu dong
src\ai_nlp\.venv\Scripts\pytest.exe src\ai_nlp\tests -v
```
