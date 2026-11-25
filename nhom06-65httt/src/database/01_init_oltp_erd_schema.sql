-- =============================================================================
-- FILE 01: KHOI TAO CO SO DU LIEU QUAN HE (OLTP - ERD 13 BANG CHUAN 3NF)
-- De tai: He thong BI phan tich thi hieu tieu dung quoc te va ho tro ra quyet
--         dinh dat hang xuat khau gom su Viet Nam
-- Nhom thuc hien: Nhom 06 - Lop 65HTTT
-- Phu trach: Tran Mai Ngoc Anh (Phan tich nghiep vu & Thiet ke CSDL)
-- He quan tri CSDL: PostgreSQL
-- =============================================================================

SET client_encoding = 'UTF8';

-- Xoa bang cu theo thu tu phu thuoc khoa ngoai (neu chay lai script)
DROP TABLE IF EXISTS order_recommendations CASCADE;
DROP TABLE IF EXISTS supplier_products CASCADE;
DROP TABLE IF EXISTS suppliers CASCADE;
DROP TABLE IF EXISTS review_aspects CASCADE;
DROP TABLE IF EXISTS product_reviews CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS market_products CASCADE;
DROP TABLE IF EXISTS trending_keywords CASCADE;
DROP TABLE IF EXISTS search_trends CASCADE;
DROP TABLE IF EXISTS trade_statistics CASCADE;
DROP TABLE IF EXISTS product_categories CASCADE;
DROP TABLE IF EXISTS market_regions CASCADE;
DROP TABLE IF EXISTS countries CASCADE;

-- =============================================================================
-- NHOM 1: DOI TUONG THI TRUONG & XU HUONG (MARKET & TRENDS)
-- =============================================================================

-- Bang 1: countries (Danh muc Quoc gia / Thi truong quoc te)
CREATE TABLE countries (
    country_id       SERIAL PRIMARY KEY,
    country_code     VARCHAR(10) NOT NULL UNIQUE,
    country_name     VARCHAR(150) NOT NULL,
    region_continent VARCHAR(100),
    currency_code    VARCHAR(10),
    is_key_market    BOOLEAN DEFAULT FALSE
);
COMMENT ON TABLE countries IS 'Danh muc hon 130 quoc gia/vung lanh tho giao thuong gom su (UN Comtrade, ITC)';

-- Bang 2: market_regions (Danh muc Bang / Vung lanh tho - 51 bang tu Google Trends)
CREATE TABLE market_regions (
    region_id   SERIAL PRIMARY KEY,
    country_id  INTEGER NOT NULL REFERENCES countries(country_id) ON DELETE CASCADE,
    region_code VARCHAR(20) NOT NULL,
    region_name VARCHAR(150) NOT NULL,
    CONSTRAINT uq_country_region_code UNIQUE (country_id, region_code)
);
COMMENT ON TABLE market_regions IS 'Danh muc 51 bang/vung lanh tho phuc vu phan tich xu huong theo vung dia ly';

-- Bang 3: product_categories (Danh muc 4 dong san pham gom su chuan hoa)
CREATE TABLE product_categories (
    category_id      SERIAL PRIMARY KEY,
    category_code    VARCHAR(50) NOT NULL UNIQUE,
    category_name_vi VARCHAR(150) NOT NULL,
    category_name_en VARCHAR(150) NOT NULL,
    hs_code_mapping  VARCHAR(20)
);
COMMENT ON TABLE product_categories IS 'Danh muc 4 dong san pham gom su chu luc: Bo am chen, Ly coc su, Bat dia ban an, Lo hoa my nghe';

-- Bang 4: trade_statistics (Thong ke Thuong mai Quoc te UN Comtrade & ITC Trade Map)
CREATE TABLE trade_statistics (
    trade_id            SERIAL PRIMARY KEY,
    reporter_country_id INTEGER NOT NULL REFERENCES countries(country_id) ON DELETE RESTRICT,
    partner_country_id  INTEGER NOT NULL REFERENCES countries(country_id) ON DELETE RESTRICT,
    year                INTEGER NOT NULL CHECK (year >= 2000 AND year <= 2100),
    trade_flow          VARCHAR(20) NOT NULL CHECK (trade_flow IN ('Export', 'Import')),
    hs_code             VARCHAR(20) NOT NULL,
    cmd_desc            TEXT,
    trade_value_usd     NUMERIC(18,2) NOT NULL CHECK (trade_value_usd >= 0),
    fob_value_usd       NUMERIC(18,2) CHECK (fob_value_usd >= 0),
    cif_value_usd       NUMERIC(18,2) CHECK (cif_value_usd >= 0),
    net_weight_kg       NUMERIC(18,2) CHECK (net_weight_kg >= 0),
    qty_unit            VARCHAR(50),
    qty_amount          NUMERIC(18,2) CHECK (qty_amount >= 0),
    market_share_pct    NUMERIC(6,2) CHECK (market_share_pct >= 0 AND market_share_pct <= 100),
    yoy_growth_rate     NUMERIC(8,2),
    data_source         VARCHAR(50) DEFAULT 'UN Comtrade'
);
COMMENT ON TABLE trade_statistics IS 'Du lieu giao thuong gom su quoc te giai doan 2021-2023 voi 14 chi tieu kinh te';

-- Bang 5: search_trends (Du lieu Xu huong Tim kiem Google Trends 52 tuan)
CREATE TABLE search_trends (
    trend_id        SERIAL PRIMARY KEY,
    country_id      INTEGER NOT NULL REFERENCES countries(country_id) ON DELETE CASCADE,
    region_id       INTEGER REFERENCES market_regions(region_id) ON DELETE SET NULL,
    category_id     INTEGER NOT NULL REFERENCES product_categories(category_id) ON DELETE CASCADE,
    search_term     VARCHAR(150) NOT NULL,
    week_start_date DATE NOT NULL,
    week_number     INTEGER CHECK (week_number BETWEEN 1 AND 53),
    interest_score  INTEGER NOT NULL CHECK (interest_score BETWEEN 0 AND 100)
);
COMMENT ON TABLE search_trends IS 'Chuoi thoi gian 52 tuan do luong muc do quan tam tim kiem (0-100) tren Google Trends';

-- Bang 6: trending_keywords (Danh muc Tu khoa Thinh hanh & But pha +140% den +5300%)
CREATE TABLE trending_keywords (
    keyword_id             SERIAL PRIMARY KEY,
    country_id             INTEGER NOT NULL REFERENCES countries(country_id) ON DELETE CASCADE,
    category_id            INTEGER NOT NULL REFERENCES product_categories(category_id) ON DELETE CASCADE,
    keyword_text           VARCHAR(200) NOT NULL,
    related_attribute_type VARCHAR(50) CHECK (related_attribute_type IN ('style', 'color', 'material', 'shape', 'feature', 'general')),
    growth_pct             NUMERIC(10,2) NOT NULL,
    trend_classification   VARCHAR(50) DEFAULT 'Rising' CHECK (trend_classification IN ('Breakout', 'Rising', 'Top')),
    recorded_period        VARCHAR(50) DEFAULT 'Last 12 Months'
);
COMMENT ON TABLE trending_keywords IS 'Danh muc cac tu khoa gom su thinh hanh co toc do tang truong tim kiem but pha';

-- =============================================================================
-- NHOM 2: DOI TUONG SAN PHAM QUOC TE, KHACH HANG & DANH GIA AI/NLP
-- =============================================================================

-- Bang 7: market_products (San pham gom su quoc te tren Etsy, Amazon)
CREATE TABLE market_products (
    market_product_id  SERIAL PRIMARY KEY,
    external_sku       VARCHAR(100) UNIQUE,
    platform_source    VARCHAR(50) NOT NULL,
    target_country_id  INTEGER NOT NULL REFERENCES countries(country_id) ON DELETE RESTRICT,
    category_id        INTEGER NOT NULL REFERENCES product_categories(category_id) ON DELETE RESTRICT,
    product_name       VARCHAR(300) NOT NULL,
    price_usd          NUMERIC(10,2) NOT NULL CHECK (price_usd >= 0),
    price_segment      VARCHAR(50),
    color              VARCHAR(100),
    shape              VARCHAR(100),
    material           VARCHAR(100),
    style              VARCHAR(100),
    is_dishwasher_safe BOOLEAN DEFAULT FALSE,
    is_microwave_safe  BOOLEAN DEFAULT FALSE,
    avg_rating         NUMERIC(3,2) CHECK (avg_rating BETWEEN 0 AND 5),
    review_count       INTEGER DEFAULT 0 CHECK (review_count >= 0),
    image_url          TEXT,
    product_url        TEXT
);
COMMENT ON TABLE market_products IS 'Danh muc san pham gom su quoc te (Etsy, Amazon) kem 5 nhom thuoc tinh thi hieu';

-- Bang 8: customers (Khach hang / Nguoi danh gia quoc te)
CREATE TABLE customers (
    customer_id          SERIAL PRIMARY KEY,
    external_reviewer_id VARCHAR(100),
    reviewer_name        VARCHAR(150),
    country_id           INTEGER REFERENCES countries(country_id) ON DELETE SET NULL,
    platform_source      VARCHAR(50) NOT NULL,
    verified_purchase    BOOLEAN DEFAULT TRUE
);
COMMENT ON TABLE customers IS 'Thong tin nguoi tieu dung quoc te mua va danh gia san pham tren Etsy, Amazon';

-- Bang 9: product_reviews (Danh gia san pham 1-5 sao & Phan loai cam xuc AI/NLP)
CREATE TABLE product_reviews (
    review_id         SERIAL PRIMARY KEY,
    market_product_id INTEGER NOT NULL REFERENCES market_products(market_product_id) ON DELETE CASCADE,
    customer_id       INTEGER REFERENCES customers(customer_id) ON DELETE SET NULL,
    rating_stars      INTEGER NOT NULL CHECK (rating_stars BETWEEN 1 AND 5),
    review_title      VARCHAR(250),
    review_text       TEXT NOT NULL,
    review_date       DATE,
    sentiment_label   VARCHAR(20) CHECK (sentiment_label IN ('Positive', 'Neutral', 'Negative')),
    sentiment_score   NUMERIC(5,4) CHECK (sentiment_score BETWEEN 0 AND 1)
);
COMMENT ON TABLE product_reviews IS 'Danh gia chi tiet cua khach hang va nhan cam xuc (Positive/Neutral/Negative) tu AI/NLP';

-- Bang 10: review_aspects (Trich xuat Khia canh Khen / Che bang AI/NLP)
CREATE TABLE review_aspects (
    aspect_id        SERIAL PRIMARY KEY,
    review_id        INTEGER NOT NULL REFERENCES product_reviews(review_id) ON DELETE CASCADE,
    aspect_category  VARCHAR(100) NOT NULL,
    aspect_sentiment VARCHAR(20) NOT NULL CHECK (aspect_sentiment IN ('Positive', 'Neutral', 'Negative')),
    extracted_phrase VARCHAR(250)
);
COMMENT ON TABLE review_aspects IS 'Cac khia canh san pham duoc khen/che (Do ben men, Bao bi dong goi, Chiu nhiet, Thiet ke, Gia ca)';

-- =============================================================================
-- NHOM 3: DOI TUONG NHA CUNG CAP NOI DIA & DE XUAT DAT HANG (DSS)
-- =============================================================================

-- Bang 11: suppliers (Ho so Co so san xuat gom su trong nuoc: Minh Long 1, Bat Trang)
CREATE TABLE suppliers (
    supplier_id          SERIAL PRIMARY KEY,
    supplier_code        VARCHAR(50) NOT NULL UNIQUE,
    supplier_name        VARCHAR(200) NOT NULL,
    address              TEXT NOT NULL,
    hotline              VARCHAR(50),
    website_url          VARCHAR(250),
    specialization       VARCHAR(250),
    min_monthly_capacity INTEGER NOT NULL CHECK (min_monthly_capacity >= 0),
    max_monthly_capacity INTEGER NOT NULL CHECK (max_monthly_capacity >= min_monthly_capacity),
    avg_lead_time_days   INTEGER NOT NULL CHECK (avg_lead_time_days > 0),
    total_catalog_items  INTEGER DEFAULT 0 CHECK (total_catalog_items >= 0),
    reliability_rating   NUMERIC(3,2) DEFAULT 4.50 CHECK (reliability_rating BETWEEN 0 AND 5)
);
COMMENT ON TABLE suppliers IS 'Ho so nang luc cac co so san xuat gom su Viet Nam (Minh Long 1, Bat Trang)';

-- Bang 12: supplier_products (Danh muc 341 san pham gom su noi dia)
CREATE TABLE supplier_products (
    supplier_product_id SERIAL PRIMARY KEY,
    supplier_id         INTEGER NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    category_id         INTEGER NOT NULL REFERENCES product_categories(category_id) ON DELETE RESTRICT,
    product_code        VARCHAR(100) UNIQUE,
    product_name        VARCHAR(300) NOT NULL,
    price_vnd           NUMERIC(14,2) NOT NULL CHECK (price_vnd >= 0),
    price_usd_equiv     NUMERIC(10,2) CHECK (price_usd_equiv >= 0),
    color               VARCHAR(100),
    shape               VARCHAR(100),
    material            VARCHAR(100),
    style               VARCHAR(100),
    is_dishwasher_safe  BOOLEAN DEFAULT TRUE,
    is_heat_resistant   BOOLEAN DEFAULT TRUE,
    min_order_qty       INTEGER DEFAULT 100 CHECK (min_order_qty > 0),
    image_url           TEXT,
    product_url         TEXT
);
COMMENT ON TABLE supplier_products IS 'Danh muc 341 san pham gom su noi dia (Minh Long 1: 297 SP, Bat Trang: 44 SP)';

-- Bang 13: order_recommendations (De xuat Dat hang Xuat khau - DSS)
CREATE TABLE order_recommendations (
    recommendation_id        SERIAL PRIMARY KEY,
    target_country_id        INTEGER NOT NULL REFERENCES countries(country_id) ON DELETE CASCADE,
    supplier_product_id      INTEGER NOT NULL REFERENCES supplier_products(supplier_product_id) ON DELETE CASCADE,
    supplier_id              INTEGER NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    attribute_match_score    NUMERIC(5,2) CHECK (attribute_match_score BETWEEN 0 AND 100),
    market_demand_score      NUMERIC(5,2) CHECK (market_demand_score BETWEEN 0 AND 100),
    estimated_margin_pct     NUMERIC(6,2),
    overall_matching_score   NUMERIC(5,2) NOT NULL CHECK (overall_matching_score BETWEEN 0 AND 100),
    recommended_order_qty    INTEGER NOT NULL CHECK (recommended_order_qty > 0),
    estimated_total_cost_vnd NUMERIC(18,2) CHECK (estimated_total_cost_vnd >= 0),
    quality_packaging_notes  TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE order_recommendations IS 'Ket qua doi chieu cung - cau va de xuat san pham, nha cung cap, so luong dat hang tham khao';

-- =============================================================================
-- TAO CHI MUC (INDEXES) TOI UU TRUY VAN
-- =============================================================================
CREATE INDEX idx_trade_partner_year ON trade_statistics(partner_country_id, year);
CREATE INDEX idx_trends_country_cat ON search_trends(country_id, category_id, week_start_date);
CREATE INDEX idx_mprod_country_cat ON market_products(target_country_id, category_id);
CREATE INDEX idx_mprod_attributes ON market_products(color, shape, material, style);
CREATE INDEX idx_sprod_supplier_cat ON supplier_products(supplier_id, category_id);
CREATE INDEX idx_sprod_attributes ON supplier_products(color, shape, material, style);
CREATE INDEX idx_reviews_product_sentiment ON product_reviews(market_product_id, sentiment_label);
CREATE INDEX idx_aspects_category_sentiment ON review_aspects(aspect_category, aspect_sentiment);
CREATE INDEX idx_rec_country_score ON order_recommendations(target_country_id, overall_matching_score DESC);
