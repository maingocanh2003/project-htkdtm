export type ProductCategoryId =
  | 'all'
  | 'household'
  | 'decor'
  | 'tableware'
  | 'artisan';

export type QuarterFilter = 'all' | 'Q1' | 'Q2' | 'Q3' | 'Q4';

export type MetricMode = 'value' | 'volume';

export interface CategoryMeta {
  id: Exclude<ProductCategoryId, 'all'>;
  name: string;
  shortName: string;
  hsCode: string;
  color: string;
  bgSoft: string;
  textColor: string;
}

export interface CountryMeta {
  code: string;
  name: string;
  region: 'Bắc Mỹ' | 'Châu Á' | 'Châu Âu' | 'Châu Đại Dương';
  flag: string;
  color: string;
  preferredStyle: string;
  preferredColors: string;
  tariffNote: string;
  vnAdvantage: string;
}

export interface TradeFactRecord {
  year: number;
  quarter: Exclude<QuarterFilter, 'all'>;
  countryCode: string;
  categoryId: Exclude<ProductCategoryId, 'all'>;
  importValueUsdM: number; // Triệu USD
  importVolumeTons: number; // Tấn
  searchInterestIndex: number; // Google Trends 0 - 100
  vietnamSharePct: number; // Thị phần gốm sứ VN (%)
  avgUnitPriceUsdKg: number; // Đơn giá bình quân USD/kg
}

export interface CompetitorShare {
  countryCode: string;
  origins: {
    name: string;
    sharePct: number;
    color: string;
  }[];
}

export const PRODUCT_CATEGORIES: CategoryMeta[] = [
  {
    id: 'household',
    name: 'Đồ gia dụng gốm sứ',
    shortName: 'Đồ gia dụng',
    hsCode: 'HS 6912',
    color: '#4F46E5',
    bgSoft: 'bg-indigo-50',
    textColor: 'text-indigo-700',
  },
  {
    id: 'decor',
    name: 'Đồ trang trí & Nội thất',
    shortName: 'Đồ trang trí',
    hsCode: 'HS 6913',
    color: '#0284C7',
    bgSoft: 'bg-sky-50',
    textColor: 'text-sky-700',
  },
  {
    id: 'tableware',
    name: 'Bộ ấm chén & Bát đĩa',
    shortName: 'Ấm chén & Bát đĩa',
    hsCode: 'HS 6911',
    color: '#0D9488',
    bgSoft: 'bg-teal-50',
    textColor: 'text-teal-700',
  },
  {
    id: 'artisan',
    name: 'Thủ công mỹ nghệ',
    shortName: 'Thủ công mỹ nghệ',
    hsCode: 'HS 6914',
    color: '#64748B',
    bgSoft: 'bg-slate-100',
    textColor: 'text-slate-700',
  },
];

export const COUNTRIES: CountryMeta[] = [
  {
    code: 'US',
    name: 'Mỹ',
    region: 'Bắc Mỹ',
    flag: '🇺🇸',
    color: '#4338CA',
    preferredStyle: 'Hiện đại, đa sắc, tối giản Bắc Âu',
    preferredColors: 'Trắng ngà, Xanh cobalt, Terracotta',
    tariffNote: 'Thuế MFN ~4.5%–9.8%, cơ hội dịch chuyển chuỗi cung ứng ngoài TQ',
    vnAdvantage: 'Lợi thế chi phí & mẫu mã thủ công Bát Tràng / Bình Dương',
  },
  {
    code: 'JP',
    name: 'Nhật Bản',
    region: 'Châu Á',
    flag: '🇯🇵',
    color: '#4F46E5',
    preferredStyle: 'Tối giản (Wabi-sabi), tinh xảo, men tự nhiên',
    preferredColors: 'Men tro, Nâu đất, Trắng sứ, Xanh rêu',
    tariffNote: 'Hiệp định VJEPA & CPTPP: thuế nhập khẩu gốm sứ 0%',
    vnAdvantage: 'Thị phần VN cao hàng đầu, tiêu chuẩn chất lượng đồng bộ',
  },
  {
    code: 'DE',
    name: 'Đức',
    region: 'Châu Âu',
    flag: '🇩🇪',
    color: '#6366F1',
    preferredStyle: 'Thiết kế đơn giản, bền bỉ, tính ứng dụng cao',
    preferredColors: 'Trắng tinh, Xám đá, Xanh dương nhạt',
    tariffNote: 'EVFTA xóa bỏ dần thuế quan về 0%, yêu cầu chứng nhận an toàn chì/cadimi',
    vnAdvantage: 'Đáp ứng tốt phân khúc trung-cao cấp, thân thiện môi trường',
  },
  {
    code: 'FR',
    name: 'Pháp',
    region: 'Châu Âu',
    flag: '🇫🇷',
    color: '#0284C7',
    preferredStyle: 'Nghệ thuật, thủ công tinh tế, phong cách Địa Trung Hải',
    preferredColors: 'Kem, Xanh olive, Vàng đất, Men rạn',
    tariffNote: 'EVFTA ưu đãi thuế 0% với C/O EUR.1',
    vnAdvantage: 'Dòng bình hoa & đồ trang trí thủ công được đánh giá cao',
  },
  {
    code: 'GB',
    name: 'Anh',
    region: 'Châu Âu',
    flag: '🇬🇧',
    color: '#0D9488',
    preferredStyle: 'Cổ điển pha hiện đại, bộ trà & đồ bàn ăn',
    preferredColors: 'Trắng sứ, Xanh lam cổ điển, Pastel',
    tariffNote: 'UKVFTA miễn giảm thuế quan cho gốm sứ xuất xứ Việt Nam',
    vnAdvantage: 'Nhu cầu ổn định cho bộ ấm chén và chậu trang trí sân vườn',
  },
  {
    code: 'KR',
    name: 'Hàn Quốc',
    region: 'Châu Á',
    flag: '🇰🇷',
    color: '#38BDF8',
    preferredStyle: 'Tối giản trẻ trung, gốm bàn ăn & phụ kiện decor',
    preferredColors: 'Be, Trắng sữa, Pastel, Men mờ',
    tariffNote: 'VKFTA & RCEP hỗ trợ thuế suất ưu đãi 0%–2%',
    vnAdvantage: 'Tốc độ tăng trưởng nhanh nhất châu Á nhờ xu hướng decor tại gia',
  },
  {
    code: 'AU',
    name: 'Úc',
    region: 'Châu Đại Dương',
    flag: '🇦🇺',
    color: '#64748B',
    preferredStyle: 'Tự nhiên, bền vững, đồ trang trí ngoài trời & gia dụng',
    preferredColors: 'Đất nung, Xanh biển, Trắng kem',
    tariffNote: 'AANZFTA & CPTPP: thuế suất nhập khẩu 0%',
    vnAdvantage: 'Chậu gốm ngoài trời & đồ gia dụng tăng trưởng mạnh',
  },
  {
    code: 'CA',
    name: 'Canada',
    region: 'Bắc Mỹ',
    flag: '🇨🇦',
    color: '#94A3B8',
    preferredStyle: 'Ấm cúng, thủ công, đa năng sử dụng hàng ngày',
    preferredColors: 'Trắng, Nâu gỗ, Xanh rừng',
    tariffNote: 'CPTPP hưởng ưu đãi thuế 0% khi đáp ứng quy tắc xuất xứ',
    vnAdvantage: 'Tăng trưởng ổn định nhờ mở rộng kênh bán lẻ trực tuyến',
  },
];

export const COMPETITOR_SHARES: CompetitorShare[] = [
  {
    countryCode: 'US',
    origins: [
      { name: 'Trung Quốc', sharePct: 46.2, color: '#64748B' },
      { name: 'Mexico & EU', sharePct: 21.8, color: '#94A3B8' },
      { name: 'Việt Nam', sharePct: 11.4, color: '#4F46E5' },
      { name: 'Thái Lan', sharePct: 8.1, color: '#0D9488' },
      { name: 'Khác', sharePct: 12.5, color: '#CBD5E1' },
    ],
  },
  {
    countryCode: 'JP',
    origins: [
      { name: 'Trung Quốc', sharePct: 41.5, color: '#64748B' },
      { name: 'Việt Nam', sharePct: 22.6, color: '#4F46E5' },
      { name: 'Thái Lan', sharePct: 14.3, color: '#0D9488' },
      { name: 'EU & Anh', sharePct: 10.2, color: '#94A3B8' },
      { name: 'Khác', sharePct: 11.4, color: '#CBD5E1' },
    ],
  },
  {
    countryCode: 'DE',
    origins: [
      { name: 'Nội khối EU (Bồ Đào Nha/Ý)', sharePct: 44.0, color: '#94A3B8' },
      { name: 'Trung Quốc', sharePct: 33.8, color: '#64748B' },
      { name: 'Việt Nam', sharePct: 9.4, color: '#4F46E5' },
      { name: 'Thái Lan', sharePct: 5.2, color: '#0D9488' },
      { name: 'Khác', sharePct: 7.6, color: '#CBD5E1' },
    ],
  },
  {
    countryCode: 'FR',
    origins: [
      { name: 'Nội khối EU (Ý/TBN/BĐN)', sharePct: 48.5, color: '#94A3B8' },
      { name: 'Trung Quốc', sharePct: 28.4, color: '#64748B' },
      { name: 'Việt Nam', sharePct: 8.9, color: '#4F46E5' },
      { name: 'Thái Lan', sharePct: 4.8, color: '#0D9488' },
      { name: 'Khác', sharePct: 9.4, color: '#CBD5E1' },
    ],
  },
  {
    countryCode: 'GB',
    origins: [
      { name: 'Trung Quốc', sharePct: 42.1, color: '#64748B' },
      { name: 'EU (BĐN/Đức)', sharePct: 29.5, color: '#94A3B8' },
      { name: 'Việt Nam', sharePct: 10.8, color: '#4F46E5' },
      { name: 'Thái Lan', sharePct: 6.4, color: '#0D9488' },
      { name: 'Khác', sharePct: 11.2, color: '#CBD5E1' },
    ],
  },
  {
    countryCode: 'KR',
    origins: [
      { name: 'Trung Quốc', sharePct: 49.0, color: '#64748B' },
      { name: 'Nhật Bản & EU', sharePct: 20.5, color: '#94A3B8' },
      { name: 'Việt Nam', sharePct: 15.2, color: '#4F46E5' },
      { name: 'Thái Lan', sharePct: 6.8, color: '#0D9488' },
      { name: 'Khác', sharePct: 8.5, color: '#CBD5E1' },
    ],
  },
  {
    countryCode: 'AU',
    origins: [
      { name: 'Trung Quốc', sharePct: 44.8, color: '#64748B' },
      { name: 'Việt Nam', sharePct: 16.5, color: '#4F46E5' },
      { name: 'EU & Anh', sharePct: 15.9, color: '#94A3B8' },
      { name: 'Thái Lan', sharePct: 9.3, color: '#0D9488' },
      { name: 'Khác', sharePct: 13.5, color: '#CBD5E1' },
    ],
  },
  {
    countryCode: 'CA',
    origins: [
      { name: 'Trung Quốc', sharePct: 43.2, color: '#64748B' },
      { name: 'Mỹ & EU', sharePct: 28.1, color: '#94A3B8' },
      { name: 'Việt Nam', sharePct: 12.1, color: '#4F46E5' },
      { name: 'Thái Lan', sharePct: 6.9, color: '#0D9488' },
      { name: 'Khác', sharePct: 9.7, color: '#CBD5E1' },
    ],
  },
];

export const AVAILABLE_YEARS = [2021, 2022, 2023, 2024, 2025] as const;

// Base 2021 annual values (Million USD) & category splits & annual growth rates by country
// Reflects realistic UN Comtrade / ITC Trade Map scale for ceramic tableware, decor & craft imports
interface CountryBaseline {
  base2021UsdM: number;
  annualGrowthRates: Record<number, number>; // multiplier vs previous year
  categoryWeights: Record<Exclude<ProductCategoryId, 'all'>, number>;
  baseSearchIndex: number;
  baseVnSharePct: number;
  unitPriceUsdKg: number;
}

const COUNTRY_BASELINES: Record<string, CountryBaseline> = {
  US: {
    base2021UsdM: 760,
    annualGrowthRates: { 2021: 1, 2022: 1.092, 2023: 1.045, 2024: 1.118, 2025: 1.134 },
    categoryWeights: { household: 0.36, decor: 0.31, tableware: 0.21, artisan: 0.12 },
    baseSearchIndex: 82,
    baseVnSharePct: 9.2,
    unitPriceUsdKg: 4.85,
  },
  JP: {
    base2021UsdM: 410,
    annualGrowthRates: { 2021: 1, 2022: 1.058, 2023: 1.041, 2024: 1.084, 2025: 1.096 },
    categoryWeights: { household: 0.28, decor: 0.19, tableware: 0.41, artisan: 0.12 },
    baseSearchIndex: 76,
    baseVnSharePct: 19.8,
    unitPriceUsdKg: 5.9,
  },
  DE: {
    base2021UsdM: 395,
    annualGrowthRates: { 2021: 1, 2022: 1.048, 2023: 1.022, 2024: 1.079, 2025: 1.088 },
    categoryWeights: { household: 0.42, decor: 0.27, tableware: 0.22, artisan: 0.09 },
    baseSearchIndex: 71,
    baseVnSharePct: 7.8,
    unitPriceUsdKg: 5.4,
  },
  FR: {
    base2021UsdM: 285,
    annualGrowthRates: { 2021: 1, 2022: 1.061, 2023: 1.036, 2024: 1.091, 2025: 1.104 },
    categoryWeights: { household: 0.29, decor: 0.35, tableware: 0.19, artisan: 0.17 },
    baseSearchIndex: 69,
    baseVnSharePct: 7.4,
    unitPriceUsdKg: 5.65,
  },
  GB: {
    base2021UsdM: 268,
    annualGrowthRates: { 2021: 1, 2022: 1.052, 2023: 1.031, 2024: 1.074, 2025: 1.082 },
    categoryWeights: { household: 0.31, decor: 0.24, tableware: 0.34, artisan: 0.11 },
    baseSearchIndex: 67,
    baseVnSharePct: 9.1,
    unitPriceUsdKg: 5.25,
  },
  KR: {
    base2021UsdM: 175,
    annualGrowthRates: { 2021: 1, 2022: 1.135, 2023: 1.112, 2024: 1.158, 2025: 1.174 },
    categoryWeights: { household: 0.34, decor: 0.28, tableware: 0.29, artisan: 0.09 },
    baseSearchIndex: 84,
    baseVnSharePct: 12.6,
    unitPriceUsdKg: 4.95,
  },
  AU: {
    base2021UsdM: 148,
    annualGrowthRates: { 2021: 1, 2022: 1.108, 2023: 1.089, 2024: 1.136, 2025: 1.149 },
    categoryWeights: { household: 0.33, decor: 0.34, tableware: 0.18, artisan: 0.15 },
    baseSearchIndex: 74,
    baseVnSharePct: 13.8,
    unitPriceUsdKg: 4.7,
  },
  CA: {
    base2021UsdM: 132,
    annualGrowthRates: { 2021: 1, 2022: 1.074, 2023: 1.058, 2024: 1.095, 2025: 1.112 },
    categoryWeights: { household: 0.37, decor: 0.26, tableware: 0.24, artisan: 0.13 },
    baseSearchIndex: 65,
    baseVnSharePct: 10.4,
    unitPriceUsdKg: 4.6,
  },
};

const QUARTER_SEASONALITY: Record<Exclude<QuarterFilter, 'all'>, number> = {
  Q1: 0.215,
  Q2: 0.238,
  Q3: 0.262,
  Q4: 0.285,
};

const CATEGORY_GROWTH_TILT: Record<Exclude<ProductCategoryId, 'all'>, number> = {
  household: 1.0,
  decor: 1.03,
  tableware: 1.015,
  artisan: 1.045,
};

const CATEGORY_SEARCH_BOOST: Record<Exclude<ProductCategoryId, 'all'>, number> = {
  household: 2,
  decor: 6,
  tableware: 4,
  artisan: -3,
};

// Build deterministic Star Schema fact dataset (8 countries * 5 years * 4 quarters * 4 categories = 640 fact rows)
export const TRADE_FACTS: TradeFactRecord[] = (() => {
  const rows: TradeFactRecord[] = [];
  const quarters: Exclude<QuarterFilter, 'all'>[] = ['Q1', 'Q2', 'Q3', 'Q4'];
  const categories: Exclude<ProductCategoryId, 'all'>[] = [
    'household',
    'decor',
    'tableware',
    'artisan',
  ];

  for (const country of COUNTRIES) {
    const base = COUNTRY_BASELINES[country.code];
    let cumulativeMultiplier = 1;

    for (const year of AVAILABLE_YEARS) {
      if (year > 2021) {
        cumulativeMultiplier *= base.annualGrowthRates[year];
      }
      const yearIndexOffset = year - 2021;

      for (const quarter of quarters) {
        const qShare = QUARTER_SEASONALITY[quarter];
        const qSearchBoost = quarter === 'Q4' ? 7 : quarter === 'Q3' ? 3 : quarter === 'Q1' ? -4 : 0;

        for (const categoryId of categories) {
          const catTilt = Math.pow(CATEGORY_GROWTH_TILT[categoryId], yearIndexOffset);
          const annualUsd = base.base2021UsdM * cumulativeMultiplier * base.categoryWeights[categoryId] * catTilt;
          const quarterUsd = Number((annualUsd * qShare).toFixed(2));
          const unitPrice = Number((base.unitPriceUsdKg * (1 + yearIndexOffset * 0.018)).toFixed(2));
          const tons = Math.round((quarterUsd * 1000) / unitPrice);

          const rawSearch =
            base.baseSearchIndex +
            yearIndexOffset * 2.4 +
            qSearchBoost +
            CATEGORY_SEARCH_BOOST[categoryId];
          const searchInterestIndex = Math.min(99, Math.max(42, Math.round(rawSearch)));

          const vnShare = Number(
            (
              base.baseVnSharePct +
              yearIndexOffset * 0.65 +
              (categoryId === 'artisan' ? 2.4 : categoryId === 'tableware' ? 1.1 : 0)
            ).toFixed(1)
          );

          rows.push({
            year,
            quarter,
            countryCode: country.code,
            categoryId,
            importValueUsdM: quarterUsd,
            importVolumeTons: tons,
            searchInterestIndex,
            vietnamSharePct: vnShare,
            avgUnitPriceUsdKg: unitPrice,
          });
        }
      }
    }
  }

  return rows;
})();

export interface CountrySummaryRow {
  country: CountryMeta;
  importValueUsdM: number;
  prevImportValueUsdM: number;
  yoyGrowthPct: number;
  cagr2125Pct: number;
  importVolumeTons: number;
  marketSharePct: number;
  avgSearchIndex: number;
  avgVnSharePct: number;
  potentialScore: number; // 0 - 100 composite score
  topCategory: CategoryMeta;
  categoryBreakdown: Record<Exclude<ProductCategoryId, 'all'>, number>;
  tier: 'star' | 'anchor' | 'emerging' | 'stable';
}

export function computeCountrySummaries(params: {
  selectedYear: number | 'all';
  selectedQuarter: QuarterFilter;
  selectedCategory: ProductCategoryId;
  selectedCountries: string[]; // empty = all
}): CountrySummaryRow[] {
  const { selectedYear, selectedQuarter, selectedCategory, selectedCountries } = params;
  const activeYear = selectedYear === 'all' ? 2025 : selectedYear;
  const prevYear = activeYear > 2021 ? activeYear - 1 : 2021;

  const targetCountries =
    selectedCountries.length > 0
      ? COUNTRIES.filter((c) => selectedCountries.includes(c.code))
      : COUNTRIES;

  const matchesFilter = (r: TradeFactRecord, yearOverride?: number) => {
    const yOk =
      yearOverride !== undefined
        ? r.year === yearOverride
        : selectedYear === 'all'
          ? true
          : r.year === selectedYear;
    const qOk = selectedQuarter === 'all' ? true : r.quarter === selectedQuarter;
    const cOk = selectedCategory === 'all' ? true : r.categoryId === selectedCategory;
    return yOk && qOk && cOk;
  };

  const totalMarketValueAllSelectedCountries = targetCountries.reduce((acc, country) => {
    const rows = TRADE_FACTS.filter((r) => r.countryCode === country.code && matchesFilter(r));
    return acc + rows.reduce((s, r) => s + r.importValueUsdM, 0);
  }, 0);

  const rawList = targetCountries.map((country) => {
    const currRows = TRADE_FACTS.filter((r) => r.countryCode === country.code && matchesFilter(r));
    // For YoY growth, compare activeYear vs prevYear (even if selectedYear === 'all', show latest 2025 vs 2024 YoY)
    const currYearRows = TRADE_FACTS.filter(
      (r) => r.countryCode === country.code && matchesFilter(r, activeYear)
    );
    const prevYearRows = TRADE_FACTS.filter(
      (r) => r.countryCode === country.code && matchesFilter(r, prevYear)
    );

    const importValueUsdM = currRows.reduce((s, r) => s + r.importValueUsdM, 0);
    const importVolumeTons = currRows.reduce((s, r) => s + r.importVolumeTons, 0);

    const currYearVal = currYearRows.reduce((s, r) => s + r.importValueUsdM, 0);
    const prevYearVal = prevYearRows.reduce((s, r) => s + r.importValueUsdM, 0);
    const yoyGrowthPct =
      activeYear === 2021 || prevYearVal === 0
        ? 8.4
        : ((currYearVal - prevYearVal) / prevYearVal) * 100;

    // 2021-2025 CAGR under current quarter & category filter
    const val2021 = TRADE_FACTS.filter(
      (r) => r.countryCode === country.code && matchesFilter(r, 2021)
    ).reduce((s, r) => s + r.importValueUsdM, 0);
    const val2025 = TRADE_FACTS.filter(
      (r) => r.countryCode === country.code && matchesFilter(r, 2025)
    ).reduce((s, r) => s + r.importValueUsdM, 0);
    const cagr2125Pct = val2021 > 0 ? (Math.pow(val2025 / val2021, 1 / 4) - 1) * 100 : 0;

    const avgSearchIndex =
      currRows.length > 0
        ? currRows.reduce((s, r) => s + r.searchInterestIndex, 0) / currRows.length
        : 0;

    const avgVnSharePct =
      currRows.length > 0
        ? currRows.reduce((s, r) => s + r.vietnamSharePct, 0) / currRows.length
        : 0;

    const categoryBreakdown: Record<Exclude<ProductCategoryId, 'all'>, number> = {
      household: 0,
      decor: 0,
      tableware: 0,
      artisan: 0,
    };
    for (const r of currRows) {
      categoryBreakdown[r.categoryId] += r.importValueUsdM;
    }

    // Find top category (when selectedCategory === 'all', show dominant category overall)
    const fullCatRows = TRADE_FACTS.filter(
      (r) =>
        r.countryCode === country.code &&
        (selectedYear === 'all' ? true : r.year === selectedYear) &&
        (selectedQuarter === 'all' ? true : r.quarter === selectedQuarter)
    );
    const fullBreakdown: Record<Exclude<ProductCategoryId, 'all'>, number> = {
      household: 0,
      decor: 0,
      tableware: 0,
      artisan: 0,
    };
    for (const r of fullCatRows) {
      fullBreakdown[r.categoryId] += r.importValueUsdM;
    }
    const topCatId = (Object.entries(fullBreakdown).sort((a, b) => b[1] - a[1])[0]?.[0] ??
      'household') as Exclude<ProductCategoryId, 'all'>;
    const topCategory = PRODUCT_CATEGORIES.find((c) => c.id === topCatId)!;

    const marketSharePct =
      totalMarketValueAllSelectedCountries > 0
        ? (importValueUsdM / totalMarketValueAllSelectedCountries) * 100
        : 0;

    return {
      country,
      importValueUsdM: Number(importValueUsdM.toFixed(1)),
      prevImportValueUsdM: Number(prevYearVal.toFixed(1)),
      yoyGrowthPct: Number(yoyGrowthPct.toFixed(1)),
      cagr2125Pct: Number(cagr2125Pct.toFixed(1)),
      importVolumeTons,
      marketSharePct: Number(marketSharePct.toFixed(1)),
      avgSearchIndex: Math.round(avgSearchIndex),
      avgVnSharePct: Number(avgVnSharePct.toFixed(1)),
      topCategory,
      categoryBreakdown,
    };
  });

  const maxVal = Math.max(...rawList.map((r) => r.importValueUsdM), 1);
  const maxGrowth = Math.max(...rawList.map((r) => r.yoyGrowthPct), 1);
  const avgVal = rawList.reduce((s, r) => s + r.importValueUsdM, 0) / Math.max(rawList.length, 1);
  const avgGrowth = rawList.reduce((s, r) => s + r.yoyGrowthPct, 0) / Math.max(rawList.length, 1);

  return rawList
    .map((item) => {
      // Composite BI Market Potential Score (0-100): 40% Scale + 35% Growth + 25% Search Interest
      const scaleScore = (item.importValueUsdM / maxVal) * 40;
      const growthScore = (Math.max(0, item.yoyGrowthPct) / Math.max(maxGrowth, 1)) * 35;
      const trendScore = (item.avgSearchIndex / 100) * 25;
      const potentialScore = Math.min(99, Math.round(scaleScore + growthScore + trendScore));

      let tier: CountrySummaryRow['tier'] = 'stable';
      if (item.importValueUsdM >= avgVal && item.yoyGrowthPct >= avgGrowth) {
        tier = 'star';
      } else if (item.importValueUsdM >= avgVal && item.yoyGrowthPct < avgGrowth) {
        tier = 'anchor';
      } else if (item.importValueUsdM < avgVal && item.yoyGrowthPct >= avgGrowth) {
        tier = 'emerging';
      } else {
        tier = 'stable';
      }

      return {
        ...item,
        potentialScore,
        tier,
      };
    })
    .sort((a, b) => b.importValueUsdM - a.importValueUsdM);
}

export interface TimeSeriesPoint {
  label: string;
  subLabel: string;
  importValueUsdM: number;
  importVolumeTons: number;
  yoyGrowthPct: number | null;
  searchIndex: number;
}

export function computeTimeSeries(params: {
  granularity: 'yearly' | 'quarterly';
  selectedYear: number | 'all';
  selectedQuarter: QuarterFilter;
  selectedCategory: ProductCategoryId;
  selectedCountries: string[];
}): TimeSeriesPoint[] {
  const { granularity, selectedYear, selectedQuarter, selectedCategory, selectedCountries } = params;

  const filterCountryCat = (r: TradeFactRecord) =>
    (selectedCountries.length === 0 || selectedCountries.includes(r.countryCode)) &&
    (selectedCategory === 'all' || r.categoryId === selectedCategory);

  if (granularity === 'yearly') {
    const points = AVAILABLE_YEARS.map((year) => {
      const rows = TRADE_FACTS.filter(
        (r) =>
          r.year === year &&
          (selectedQuarter === 'all' || r.quarter === selectedQuarter) &&
          filterCountryCat(r)
      );
      const val = rows.reduce((s, r) => s + r.importValueUsdM, 0);
      const vol = rows.reduce((s, r) => s + r.importVolumeTons, 0);
      const search =
        rows.length > 0 ? rows.reduce((s, r) => s + r.searchInterestIndex, 0) / rows.length : 0;

      return {
        year,
        val,
        vol,
        search: Math.round(search),
      };
    });

    return points.map((p, idx) => {
      const prev = idx > 0 ? points[idx - 1].val : null;
      const yoy = prev && prev > 0 ? Number((((p.val - prev) / prev) * 100).toFixed(1)) : null;
      return {
        label: String(p.year),
        subLabel: selectedQuarter === 'all' ? 'Cả năm' : selectedQuarter,
        importValueUsdM: Number(p.val.toFixed(1)),
        importVolumeTons: p.vol,
        yoyGrowthPct: yoy,
        searchIndex: p.search,
      };
    });
  }

  // Quarterly granularity across years (or selectedYear if single year picked, show 2024-2025 or all 20 quarters)
  const yearsToShow =
    selectedYear === 'all'
      ? [2023, 2024, 2025]
      : [Math.max(2021, selectedYear - 1), selectedYear];
  const quarters: Exclude<QuarterFilter, 'all'>[] = ['Q1', 'Q2', 'Q3', 'Q4'];
  const rawQuarters: { year: number; quarter: Exclude<QuarterFilter, 'all'>; val: number; vol: number; search: number }[] = [];

  for (const year of yearsToShow) {
    for (const q of quarters) {
      const rows = TRADE_FACTS.filter(
        (r) => r.year === year && r.quarter === q && filterCountryCat(r)
      );
      const val = rows.reduce((s, r) => s + r.importValueUsdM, 0);
      const vol = rows.reduce((s, r) => s + r.importVolumeTons, 0);
      const search =
        rows.length > 0 ? rows.reduce((s, r) => s + r.searchInterestIndex, 0) / rows.length : 0;
      rawQuarters.push({ year, quarter: q, val, vol, search: Math.round(search) });
    }
  }

  return rawQuarters.map((item) => {
    const prevYearSameQ = TRADE_FACTS.filter(
      (r) => r.year === item.year - 1 && r.quarter === item.quarter && filterCountryCat(r)
    ).reduce((s, r) => s + r.importValueUsdM, 0);

    const yoy =
      prevYearSameQ > 0
        ? Number((((item.val - prevYearSameQ) / prevYearSameQ) * 100).toFixed(1))
        : null;

    return {
      label: `${item.quarter}/${String(item.year).slice(2)}`,
      subLabel: `${item.quarter} ${item.year}`,
      importValueUsdM: Number(item.val.toFixed(1)),
      importVolumeTons: item.vol,
      yoyGrowthPct: yoy,
      searchIndex: item.search,
    };
  });
}

export function formatUsdMillions(valueM: number): string {
  if (valueM >= 1000) {
    return `$${(valueM / 1000).toFixed(2)} Tỷ`;
  }
  return `$${valueM.toLocaleString('en-US', { maximumFractionDigits: 1 })} Tr`;
}

export function formatTons(tons: number): string {
  if (tons >= 1000) {
    return `${(tons / 1000).toFixed(1)}K tấn`;
  }
  return `${tons.toLocaleString('en-US')} tấn`;
}
