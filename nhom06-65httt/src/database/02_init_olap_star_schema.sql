-- =============================================================================
-- FILE 02: KHOI TAO MO HINH KHO DU LIEU STAR SCHEMA (OLAP - BI DATA WAREHOUSE)
-- De tai: He thong BI phan tich thi hieu tieu dung quoc te va ho tro ra quyet
--         dinh dat hang xuat khau gom su Viet Nam
-- Nhom thuc hien: Nhom 06 - Lop 65HTTT
-- Phu trach: Tran Mai Ngoc Anh (Phan tich nghiep vu & Thiet ke CSDL)
-- He quan tri CSDL: PostgreSQL
-- =============================================================================

SET client_encoding = 'UTF8';

-- Xoa cac bang Fact va Dimension cu (neu chay lai script)
DROP TABLE IF EXISTS fact_supplier_recommendation CASCADE;
DROP TABLE IF EXISTS fact_customer_review CASCADE;
DROP TABLE IF EXISTS fact_market_demand CASCADE;
DROP TABLE IF EXISTS dim_sentiment_aspect CASCADE;
DROP TABLE IF EXISTS dim_supplier CASCADE;
DROP TABLE IF EXISTS dim_product CASCADE;
DROP TABLE IF EXISTS dim_market CASCADE;
DROP TABLE IF EXISTS dim_time CASCADE;

-- =============================================================================
-- 1. KHOI TAO 5 BANG CHIEU PHAN TICH (DIMENSION TABLES)
-- =============================================================================

-- Bang Chieu 1: dim_time (Chieu Thoi gian: Nam, Quy, Thang, Tuan, Ngay)
CREATE TABLE dim_time (
    time_key     SERIAL PRIMARY KEY,
    full_date    DATE NOT NULL UNIQUE,
    year         INTEGER NOT NULL,
    quarter      INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month        INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    week_of_year INTEGER NOT NULL CHECK (week_of_year BETWEEN 1 AND 53),
    period_label VARCHAR(50)
);
COMMENT ON TABLE dim_time IS 'Chieu Thoi gian phuc vu phan tich theo Nam (2021-2023), Quy, Thang va 52 Tuan Google Trends';

-- Bang Chieu 2: dim_market (Chieu Quoc gia & Vung thi truong)
CREATE TABLE dim_market (
    market_key        SERIAL PRIMARY KEY,
    source_country_id INTEGER NOT NULL,
    country_code      VARCHAR(10) NOT NULL,
    country_name      VARCHAR(150) NOT NULL,
    region_continent  VARCHAR(100),
    state_region_code VARCHAR(20) DEFAULT 'ALL',
    state_region_name VARCHAR(150) DEFAULT 'National',
    currency_code     VARCHAR(10),
    is_key_market     BOOLEAN DEFAULT FALSE,
    CONSTRAINT uq_dim_market UNIQUE (source_country_id, state_region_code)
);
COMMENT ON TABLE dim_market IS 'Chieu Dia ly & Thi truong gop phang Quoc gia (>130 nuoc) va Bang/Vung lanh tho (51 bang)';

-- Bang Chieu 3: dim_product (Chieu San pham & 5 Nhom Thuoc tinh Thi hieu)
CREATE TABLE dim_product (
    product_key        SERIAL PRIMARY KEY,
    source_product_id  INTEGER,
    product_origin     VARCHAR(30) NOT NULL CHECK (product_origin IN ('International', 'Domestic', 'Category_Level')),
    category_code      VARCHAR(50) NOT NULL,
    category_name_vi   VARCHAR(150) NOT NULL,
    category_name_en   VARCHAR(150) NOT NULL,
    hs_code            VARCHAR(20),
    product_name       VARCHAR(300) NOT NULL,
    color              VARCHAR(100),
    shape              VARCHAR(100),
    material           VARCHAR(100),
    style              VARCHAR(100),
    is_dishwasher_safe BOOLEAN DEFAULT FALSE,
    is_heat_resistant  BOOLEAN DEFAULT FALSE,
    price_segment      VARCHAR(50)
);
COMMENT ON TABLE dim_product IS 'Chieu San pham & Thuoc tinh (Mau sac, Hinh dang, Chat lieu, Phong cach, Cong nang, Phan khuc gia)';

-- Bang Chieu 4: dim_supplier (Chieu Nha cung cap noi dia)
CREATE TABLE dim_supplier (
    supplier_key         SERIAL PRIMARY KEY,
    source_supplier_id   INTEGER NOT NULL UNIQUE,
    supplier_code        VARCHAR(50) NOT NULL,
    supplier_name        VARCHAR(200) NOT NULL,
    address              TEXT,
    specialization       VARCHAR(250),
    min_monthly_capacity INTEGER NOT NULL,
    max_monthly_capacity INTEGER NOT NULL,
    avg_lead_time_days   INTEGER NOT NULL,
    reliability_rating   NUMERIC(3,2)
);
COMMENT ON TABLE dim_supplier IS 'Chieu Nha cung cap gom su trong nuoc (Minh Long 1, Bat Trang)';

-- Bang Chieu 5: dim_sentiment_aspect (Chieu Cam xuc & Khia canh danh gia AI/NLP)
CREATE TABLE dim_sentiment_aspect (
    aspect_key           SERIAL PRIMARY KEY,
    platform_source      VARCHAR(50) NOT NULL,
    sentiment_label      VARCHAR(20) NOT NULL,
    aspect_category      VARCHAR(100) NOT NULL,
    aspect_sentiment     VARCHAR(20) NOT NULL,
    is_verified_purchase BOOLEAN DEFAULT TRUE,
    CONSTRAINT uq_dim_sentiment_aspect UNIQUE (platform_source, sentiment_label, aspect_category, aspect_sentiment, is_verified_purchase)
);
COMMENT ON TABLE dim_sentiment_aspect IS 'Chieu Phan tich Cam xuc (Positive/Neutral/Negative) va Khia canh khen/che tu AI/NLP';

-- =============================================================================
-- 2. KHOI TAO 3 BANG SU KIEN (FACT TABLES) CHUA CAC CHI SO DO LUONG (MEASURES)
-- =============================================================================

-- Bang Fact 1: fact_market_demand (Thuong mai quoc te & Xu huong tim kiem)
CREATE TABLE fact_market_demand (
    fact_demand_id        SERIAL PRIMARY KEY,
    time_key              INTEGER NOT NULL REFERENCES dim_time(time_key) ON DELETE RESTRICT,
    market_key            INTEGER NOT NULL REFERENCES dim_market(market_key) ON DELETE RESTRICT,
    product_key           INTEGER NOT NULL REFERENCES dim_product(product_key) ON DELETE RESTRICT,
    trade_flow            VARCHAR(20),
    trade_value_usd       NUMERIC(18,2) DEFAULT 0,
    fob_value_usd         NUMERIC(18,2) DEFAULT 0,
    cif_value_usd         NUMERIC(18,2) DEFAULT 0,
    net_weight_kg         NUMERIC(18,2) DEFAULT 0,
    qty_amount            NUMERIC(18,2) DEFAULT 0,
    market_share_pct      NUMERIC(6,2),
    yoy_growth_rate       NUMERIC(8,2),
    search_interest_score INTEGER,
    keyword_breakout_pct  NUMERIC(10,2)
);
COMMENT ON TABLE fact_market_demand IS 'Bang Fact luu cac chi so Quy mo nhap khau, Toc do tang truong, Thi phan va Muc do quan tam';

-- Bang Fact 2: fact_customer_review (Phan tich Thi hieu & Danh gia khach hang AI/NLP)
CREATE TABLE fact_customer_review (
    fact_review_id       SERIAL PRIMARY KEY,
    time_key             INTEGER NOT NULL REFERENCES dim_time(time_key) ON DELETE RESTRICT,
    market_key           INTEGER NOT NULL REFERENCES dim_market(market_key) ON DELETE RESTRICT,
    product_key          INTEGER NOT NULL REFERENCES dim_product(product_key) ON DELETE RESTRICT,
    aspect_key           INTEGER NOT NULL REFERENCES dim_sentiment_aspect(aspect_key) ON DELETE RESTRICT,
    rating_stars         INTEGER NOT NULL CHECK (rating_stars BETWEEN 1 AND 5),
    sentiment_score      NUMERIC(5,4),
    market_price_usd     NUMERIC(10,2),
    review_count         INTEGER DEFAULT 1,
    positive_review_flag INTEGER DEFAULT 0 CHECK (positive_review_flag IN (0, 1)),
    negative_review_flag INTEGER DEFAULT 0 CHECK (negative_review_flag IN (0, 1))
);
COMMENT ON TABLE fact_customer_review IS 'Bang Fact luu Diem danh gia (1-5 sao), Diem cam xuc AI, Gia ban quoc te va Co khen/che';

-- Bang Fact 3: fact_supplier_recommendation (Doi chieu Nha cung cap & De xuat dat hang)
CREATE TABLE fact_supplier_recommendation (
    fact_recommendation_id    SERIAL PRIMARY KEY,
    time_key                  INTEGER NOT NULL REFERENCES dim_time(time_key) ON DELETE RESTRICT,
    market_key                INTEGER NOT NULL REFERENCES dim_market(market_key) ON DELETE RESTRICT,
    product_key               INTEGER NOT NULL REFERENCES dim_product(product_key) ON DELETE RESTRICT,
    supplier_key              INTEGER NOT NULL REFERENCES dim_supplier(supplier_key) ON DELETE RESTRICT,
    domestic_price_vnd        NUMERIC(14,2),
    domestic_price_usd        NUMERIC(10,2),
    supplier_monthly_capacity INTEGER,
    lead_time_days            INTEGER,
    attribute_match_score     NUMERIC(5,2),
    market_demand_score       NUMERIC(5,2),
    estimated_margin_pct      NUMERIC(6,2),
    overall_matching_score    NUMERIC(5,2) NOT NULL,
    recommended_order_qty     INTEGER NOT NULL,
    estimated_total_cost_vnd  NUMERIC(18,2)
);
COMMENT ON TABLE fact_supplier_recommendation IS 'Bang Fact luu Gia nhap, Nang luc cung ung, Diem phu hop thi truong va So luong dat hang de xuat';

-- =============================================================================
-- 3. TAO CHI MUC (INDEXES) TOI UU TRUY VAN CHO CAC BANG FACT
-- =============================================================================
CREATE INDEX idx_fact_demand_keys ON fact_market_demand(time_key, market_key, product_key);
CREATE INDEX idx_fact_review_keys ON fact_customer_review(time_key, market_key, product_key, aspect_key);
CREATE INDEX idx_fact_rec_keys ON fact_supplier_recommendation(time_key, market_key, product_key, supplier_key);
