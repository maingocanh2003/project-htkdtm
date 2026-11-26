import React, { useMemo, useState } from 'react';
import {
  Activity,
  BarChart2,
  Building2,
  Calendar,
  Database,
  Download,
  Filter,
  Globe2,
  HeartHandshake,
  LayoutDashboard,
  Menu,
  PackageCheck,
  Palette,
  RotateCcw,
  ShoppingCart,
  Sparkles,
  TrendingUp,
  X,
} from 'lucide-react';
import {
  AVAILABLE_YEARS,
  COUNTRIES,
  CountrySummaryRow,
  MetricMode,
  PRODUCT_CATEGORIES,
  ProductCategoryId,
  QuarterFilter,
  computeCountrySummaries,
  computeTimeSeries,
  formatTons,
  formatUsdMillions,
} from './data/marketOverviewData';
import { KpiCard } from './components/KpiCard';
import { ImportTrendChart } from './components/ImportTrendChart';
import { MarketShareDonut } from './components/MarketShareDonut';
import { CountryMatrixChart } from './components/CountryMatrixChart';
import { CountryComparisonPanel } from './components/CountryComparisonPanel';
import { CountryRankingTable } from './components/CountryRankingTable';
import { CountryDetailDrawer } from './components/CountryDetailDrawer';
import { CountryFlag } from './components/CountryFlag';
import { CountryMultiSelect } from './components/CountryMultiSelect';
import { DataSchemaModal } from './components/DataSchemaModal';
import { KilnScopeLogo } from './components/KilnScopeLogo';
import { TasteDashboard } from './components/TasteDashboard';
import { CustomerSentimentDashboard } from './components/CustomerSentimentDashboard';
import { SuppliersProductsDashboard } from './components/SuppliersProductsDashboard';
import { OrderRecommendationModule } from './components/OrderRecommendationModule';
import {
  INITIAL_SUPPLIERS,
  INITIAL_SUPPLIER_PRODUCTS,
  SupplierProduct,
} from './data/suppliersData';

type NavModuleId =
  | 'dashboard1'
  | 'dashboard2'
  | 'dashboard3'
  | 'dashboard4'
  | 'decision';

const NAV_ITEMS: {
  id: NavModuleId;
  label: string;
  shortTag: string;
  icon: React.ReactNode;
  ready: boolean;
  description: string;
}[] = [
  {
    id: 'dashboard1',
    label: 'Tổng quan thị trường',
    shortTag: 'Dashboard 1',
    icon: <LayoutDashboard className="h-4 w-4" />,
    ready: true,
    description: 'Giá trị nhập khẩu, tốc độ tăng trưởng, so sánh các quốc gia.',
  },
  {
    id: 'dashboard2',
    label: 'Phân tích thị hiếu',
    shortTag: 'Dashboard 2',
    icon: <Palette className="h-4 w-4" />,
    ready: true,
    description: 'Nhóm sản phẩm, màu sắc, hình dạng, chất liệu & phong cách.',
  },
  {
    id: 'dashboard3',
    label: 'Phân tích khách hàng',
    shortTag: 'Dashboard 3',
    icon: <HeartHandshake className="h-4 w-4" />,
    ready: true,
    description: 'Điểm đánh giá, cảm xúc AI/NLP tích cực, trung lập & tiêu cực.',
  },
  {
    id: 'dashboard4',
    label: 'Sản phẩm & Nhà cung cấp',
    shortTag: 'Dashboard 4',
    icon: <Building2 className="h-4 w-4" />,
    ready: true,
    description: 'Giá nhập, năng lực cung ứng & mức độ phù hợp thị trường.',
  },
  {
    id: 'decision',
    label: 'Đề xuất đặt hàng',
    shortTag: 'DSS Module',
    icon: <ShoppingCart className="h-4 w-4" />,
    ready: true,
    description: 'Gợi ý sản phẩm, nhà cung cấp & số lượng đặt hàng tham khảo.',
  },
];

export function App() {
  const [activeNav, setActiveNav] = useState<NavModuleId>('dashboard1');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [schemaModalOpen, setSchemaModalOpen] = useState(false);

  // Dashboard 1 Interactive Filters
  const [selectedYear, setSelectedYear] = useState<number | 'all'>(2025);
  const [selectedQuarter, setSelectedQuarter] = useState<QuarterFilter>('all');
  const [selectedCategory, setSelectedCategory] = useState<ProductCategoryId>('all');
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [granularity, setGranularity] = useState<'yearly' | 'quarterly'>('yearly');
  const [metricMode, setMetricMode] = useState<MetricMode>('value');
  const [highlightedCountry, setHighlightedCountry] = useState<string | null>(null);
  const [inspectedCountry, setInspectedCountry] = useState<CountrySummaryRow | null>(null);

  // Shared state for Dashboard 4 (Products & Suppliers CRUD) & Decision Support Module
  const [supplierProducts, setSupplierProducts] = useState<SupplierProduct[]>(
    INITIAL_SUPPLIER_PRODUCTS
  );
  const [decisionCountry, setDecisionCountry] = useState<string>('US');

  const handleAddProduct = (product: SupplierProduct) => {
    setSupplierProducts((prev) => [product, ...prev]);
  };

  const handleUpdateProduct = (updated: SupplierProduct) => {
    setSupplierProducts((prev) =>
      prev.map((p) => (p.id === updated.id ? updated : p))
    );
  };

  const handleDeleteProduct = (id: string) => {
    setSupplierProducts((prev) => prev.filter((p) => p.id !== id));
  };

  const toggleCountryFilter = (code: string) => {
    setSelectedCountries((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const resetFilters = () => {
    setSelectedYear(2025);
    setSelectedQuarter('all');
    setSelectedCategory('all');
    setSelectedCountries([]);
    setHighlightedCountry(null);
  };

  const countryRows = useMemo(
    () =>
      computeCountrySummaries({
        selectedYear,
        selectedQuarter,
        selectedCategory,
        selectedCountries,
      }),
    [selectedYear, selectedQuarter, selectedCategory, selectedCountries]
  );

  const timeSeries = useMemo(
    () =>
      computeTimeSeries({
        granularity,
        selectedYear,
        selectedQuarter,
        selectedCategory,
        selectedCountries,
      }),
    [granularity, selectedYear, selectedQuarter, selectedCategory, selectedCountries]
  );

  // Executive KPI aggregates
  const kpiStats = useMemo(() => {
    const totalVal = countryRows.reduce((s, r) => s + r.importValueUsdM, 0);
    const totalPrevVal = countryRows.reduce((s, r) => s + r.prevImportValueUsdM, 0);
    const totalVol = countryRows.reduce((s, r) => s + r.importVolumeTons, 0);

    const weightedGrowth =
      totalPrevVal > 0 && selectedYear !== 2021
        ? ((totalVal - totalPrevVal) / totalPrevVal) * 100
        : countryRows.reduce((s, r) => s + r.yoyGrowthPct, 0) / Math.max(countryRows.length, 1);

    const avgGrowth =
      selectedYear === 'all'
        ? countryRows.reduce((s, r) => s + r.yoyGrowthPct, 0) / Math.max(countryRows.length, 1)
        : weightedGrowth;

    const topByValue = countryRows[0];
    const fastestGrowing = [...countryRows].sort((a, b) => b.yoyGrowthPct - a.yoyGrowthPct)[0];

    const avgSearch =
      countryRows.length > 0
        ? Math.round(
            countryRows.reduce((s, r) => s + r.avgSearchIndex, 0) / countryRows.length
          )
        : 0;

    const avgVnShare =
      countryRows.length > 0
        ? (
            countryRows.reduce((s, r) => s + r.avgVnSharePct, 0) / countryRows.length
          ).toFixed(1)
        : '0.0';

    const sparkValues = timeSeries.map((t) =>
      metricMode === 'value' ? t.importValueUsdM : t.importVolumeTons
    );
    const sparkGrowth = timeSeries
      .map((t) => t.yoyGrowthPct)
      .filter((v): v is number => v !== null);
    const sparkTrends = timeSeries.map((t) => t.searchIndex);

    return {
      totalVal,
      totalVol,
      avgGrowth: Number(avgGrowth.toFixed(1)),
      topByValue,
      fastestGrowing,
      avgSearch,
      avgVnShare,
      sparkValues,
      sparkGrowth,
      sparkTrends,
    };
  }, [countryRows, timeSeries, metricMode, selectedYear]);

  const handleSelectCountryHighlight = (code: string) => {
    setHighlightedCountry((prev) => (prev === code ? null : code));
  };

  const handleExportCsv = () => {
    const headers = [
      'QuocGia',
      'KhuVuc',
      'GiaTriNK_TrieuUSD',
      'KhoiLuong_Tan',
      'TangTruong_YoY_Pct',
      'CAGR_21_25_Pct',
      'GoogleTrends',
      'ThiPhanVN_Pct',
      'NhomNoiBat',
      'DiemTiemNang',
    ];
    const lines = countryRows.map((r) =>
      [
        r.country.name,
        r.country.region,
        r.importValueUsdM,
        r.importVolumeTons,
        r.yoyGrowthPct,
        r.cagr2125Pct,
        r.avgSearchIndex,
        r.avgVnSharePct,
        r.topCategory.shortName,
        r.potentialScore,
      ].join(',')
    );
    const csv = '\uFEFF' + [headers.join(','), ...lines].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kilnscope_dashboard1_tong_quan_thi_truong_${selectedYear}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const hasCustomFilter =
    selectedYear !== 2025 ||
    selectedQuarter !== 'all' ||
    selectedCategory !== 'all' ||
    selectedCountries.length > 0;

  return (
    <div className="flex min-h-screen bg-[#F8FAFC] text-slate-900">
      {/* Refined Dark Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-800/90 bg-[#0F172A] text-slate-100 lg:flex">
        {/* Brand */}
        <div className="border-b border-slate-800/80 px-5 py-4">
          <KilnScopeLogo size={38} subtitle="Nhóm 06 • 65HTTT" />
        </div>

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto px-3 py-5">
          <p className="mb-2.5 px-3 text-[10px] font-semibold tracking-wider text-slate-500 uppercase">
            Phân hệ BI & Quyết định
          </p>
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const isActive = activeNav === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveNav(item.id)}
                  className={`group relative flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition-colors ${
                    isActive
                      ? 'border border-white/10 bg-white/[0.08] text-white'
                      : 'border border-transparent text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
                  }`}
                >
                  {isActive && (
                    <span className="absolute top-2 bottom-2 left-0 w-[3px] rounded-r-full bg-indigo-400" />
                  )}
                  <span className="flex items-center gap-2.5">
                    <span
                      className={`flex h-7 w-7 items-center justify-center rounded-md ${
                        isActive
                          ? 'bg-indigo-500/20 text-indigo-300'
                          : 'text-slate-400 group-hover:text-slate-200'
                      }`}
                    >
                      {item.icon}
                    </span>
                    <span>
                      <span className="block text-[10px] font-semibold tracking-wide text-slate-400 uppercase">
                        {item.shortTag}
                      </span>
                      <span className="block text-xs font-medium">{item.label}</span>
                    </span>
                  </span>
                  {item.ready ? (
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-emerald-400"
                      title="Đã hoàn thiện"
                    />
                  ) : (
                    <span className="rounded bg-slate-800/90 px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
                      Sắp có
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Compact Data Schema Trigger & ETL Footer */}
        <div className="space-y-2.5 border-t border-slate-800/80 p-3.5">
          <button
            type="button"
            onClick={() => setSchemaModalOpen(true)}
            className="flex w-full items-center justify-between rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2 text-left text-xs font-medium text-slate-300 transition hover:border-slate-700 hover:bg-slate-800/80 hover:text-white"
          >
            <span className="flex items-center gap-2">
              <Database className="h-3.5 w-3.5 text-indigo-400" />
              <span>Data Schema</span>
            </span>
            <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
              Star (4)
            </span>
          </button>

          <div className="flex items-center justify-between px-1 text-[11px] text-slate-500">
            <span>Đồng bộ ETL</span>
            <span className="inline-flex items-center gap-1.5 font-medium text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              PostgreSQL Ready
            </span>
          </div>
        </div>
      </aside>

      {/* Mobile Drawer Nav */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-slate-900/60"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative z-10 flex w-64 flex-col bg-[#0F172A] p-4 text-slate-100">
            <div className="mb-4 flex items-center justify-between">
              <KilnScopeLogo size={32} subtitle="Nhóm 06 • 65HTTT" />
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex-1 space-y-1">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setActiveNav(item.id);
                    setMobileMenuOpen(false);
                  }}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs font-medium ${
                    activeNav === item.id
                      ? 'border border-white/10 bg-white/[0.08] text-white'
                      : 'text-slate-400 hover:bg-white/[0.04]'
                  }`}
                >
                  {item.icon}
                  <span>
                    {item.shortTag}: {item.label}
                  </span>
                </button>
              ))}
            </nav>
            <button
              type="button"
              onClick={() => {
                setMobileMenuOpen(false);
                setSchemaModalOpen(true);
              }}
              className="mt-4 flex w-full items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-300"
            >
              <Database className="h-3.5 w-3.5 text-indigo-400" />
              <span>Data Schema</span>
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Header */}
        <header className="sticky top-0 z-30 border-b border-[#E2E8F0] bg-white/90 backdrop-blur-md">
          <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileMenuOpen(true)}
                className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 lg:hidden"
                aria-label="Mở menu"
              >
                <Menu className="h-5 w-5" />
              </button>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-indigo-200/80 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
                    {NAV_ITEMS.find((i) => i.id === activeNav)?.shortTag}
                  </span>
                  <h1 className="font-display text-base font-bold tracking-tight text-slate-900 sm:text-lg">
                    {NAV_ITEMS.find((i) => i.id === activeNav)?.label}
                  </h1>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">
                  Phân tích thị trường nhập khẩu & hỗ trợ quyết định đặt hàng xuất khẩu gốm sứ Việt Nam
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="hidden items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px] font-medium text-slate-600 sm:inline-flex">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                UN Comtrade • ITC Trade Map • Google Trends
              </span>
              {activeNav === 'dashboard1' && (
                <button
                  type="button"
                  onClick={handleExportCsv}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-indigo-700"
                >
                  <Download className="h-3.5 w-3.5" />
                  Xuất CSV
                </button>
              )}
            </div>
          </div>
        </header>

        {/* Body */}
        <main className="mx-auto w-full max-w-[1440px] flex-1 space-y-4 px-4 py-5 sm:px-6 lg:px-8">
          {activeNav === 'dashboard1' ? (
            <>
              {/* Compact Single-Row Filter Bar */}
              <section className="rounded-xl border border-[#E2E8F0] bg-white px-4 py-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 pr-1 text-xs font-semibold text-slate-600">
                      <Filter className="h-3.5 w-3.5 text-indigo-600" />
                      Bộ lọc:
                    </span>

                    {/* Year Select */}
                    <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
                      <Calendar className="h-3.5 w-3.5 text-slate-400" />
                      <span className="font-medium text-slate-500">Năm:</span>
                      <select
                        value={selectedYear}
                        onChange={(e) =>
                          setSelectedYear(
                            e.target.value === 'all' ? 'all' : Number(e.target.value)
                          )
                        }
                        className="bg-transparent font-semibold text-slate-900 tabular-nums focus:outline-hidden"
                      >
                        <option value="all">2021–2025</option>
                        {[...AVAILABLE_YEARS].reverse().map((yr) => (
                          <option key={yr} value={yr}>
                            {yr}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Quarter Pills */}
                    <div className="inline-flex h-8.5 items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
                      {(['all', 'Q1', 'Q2', 'Q3', 'Q4'] as const).map((q) => (
                        <button
                          key={q}
                          type="button"
                          onClick={() => setSelectedQuarter(q)}
                          className={`rounded-md px-2.5 py-1 font-medium transition ${
                            selectedQuarter === q
                              ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                              : 'text-slate-500 hover:text-slate-800'
                          }`}
                        >
                          {q === 'all' ? 'Cả năm' : q}
                        </button>
                      ))}
                    </div>

                    {/* Product Category Select */}
                    <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
                      <PackageCheck className="h-3.5 w-3.5 text-slate-400" />
                      <span className="font-medium text-slate-500">Nhóm SP:</span>
                      <select
                        value={selectedCategory}
                        onChange={(e) =>
                          setSelectedCategory(e.target.value as ProductCategoryId)
                        }
                        className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
                      >
                        <option value="all">Tất cả gốm sứ</option>
                        {PRODUCT_CATEGORIES.map((cat) => (
                          <option key={cat.id} value={cat.id}>
                            {cat.shortName}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Country Multi-Select Dropdown */}
                    <CountryMultiSelect
                      countries={COUNTRIES}
                      selectedCodes={selectedCountries}
                      onToggleCountry={toggleCountryFilter}
                      onClearAll={() => setSelectedCountries([])}
                    />
                  </div>

                  {hasCustomFilter && (
                    <button
                      type="button"
                      onClick={resetFilters}
                      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      Đặt lại
                    </button>
                  )}
                </div>
              </section>

              {/* Row 1: 4 Clean SaaS KPI Cards (No top gradient bars, no truncation) */}
              <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <KpiCard
                  title="Tổng quy mô nhập khẩu"
                  value={
                    metricMode === 'value'
                      ? formatUsdMillions(kpiStats.totalVal)
                      : formatTons(kpiStats.totalVol)
                  }
                  subtitle={
                    metricMode === 'value'
                      ? `Sản lượng: ${formatTons(kpiStats.totalVol)}`
                      : `Giá trị: ${formatUsdMillions(kpiStats.totalVal)}`
                  }
                  delta={kpiStats.avgGrowth}
                  deltaLabel="so với cùng kỳ"
                  icon={<BarChart2 className="h-4.5 w-4.5" />}
                  sparkline={kpiStats.sparkValues}
                />

                <KpiCard
                  title="Tốc độ tăng trưởng TB"
                  value={`+${kpiStats.avgGrowth}%`}
                  subtitle={
                    kpiStats.fastestGrowing ? (
                      <span className="inline-flex items-center gap-1.5">
                        <CountryFlag code={kpiStats.fastestGrowing.country.code} size={14} />
                        <span>{kpiStats.fastestGrowing.country.name} tăng nhanh nhất</span>
                      </span>
                    ) : (
                      'Theo kỳ đã chọn'
                    )
                  }
                  delta={kpiStats.fastestGrowing?.yoyGrowthPct ?? null}
                  deltaLabel="đỉnh YoY"
                  icon={<TrendingUp className="h-4.5 w-4.5" />}
                  sparkline={kpiStats.sparkGrowth}
                />

                <KpiCard
                  title="Thị trường dẫn đầu"
                  value={
                    kpiStats.topByValue ? (
                      <span className="inline-flex items-center gap-2">
                        <CountryFlag code={kpiStats.topByValue.country.code} size={22} />
                        <span>{kpiStats.topByValue.country.name}</span>
                      </span>
                    ) : (
                      '—'
                    )
                  }
                  subtitle={
                    kpiStats.topByValue
                      ? `${formatUsdMillions(kpiStats.topByValue.importValueUsdM)} • ${kpiStats.topByValue.marketSharePct}% thị phần`
                      : 'Chưa có dữ liệu'
                  }
                  delta={kpiStats.topByValue?.yoyGrowthPct ?? null}
                  deltaLabel="YoY"
                  icon={<Globe2 className="h-4.5 w-4.5" />}
                />

                <KpiCard
                  title="Quan tâm tìm kiếm & Thị phần VN"
                  value={`${kpiStats.avgSearch}/100`}
                  subtitle={
                    <span className="inline-flex items-center gap-1.5">
                      <CountryFlag code="VN" size={14} />
                      <span>Thị phần VN bình quân: {kpiStats.avgVnShare}%</span>
                    </span>
                  }
                  icon={<Activity className="h-4.5 w-4.5" />}
                  sparkline={kpiStats.sparkTrends}
                />
              </section>

              {/* Key Insight Summary Bar (Directly under KPI row) */}
              {kpiStats.topByValue && kpiStats.fastestGrowing && (
                <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E2E8F0] bg-white px-4 py-3">
                  <div className="flex items-start gap-2.5 text-xs leading-relaxed text-slate-600 sm:items-center">
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-indigo-200/80 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
                      <Sparkles className="h-3 w-3" />
                      Key Insight
                    </span>
                    <p className="tabular-nums">
                      <strong className="inline-flex items-center gap-1 text-slate-900">
                        <CountryFlag code={kpiStats.topByValue.country.code} size={13} />
                        {kpiStats.topByValue.country.name}
                      </strong>{' '}
                      dẫn đầu quy mô ({formatUsdMillions(kpiStats.topByValue.importValueUsdM)}, chiếm{' '}
                      {kpiStats.topByValue.marketSharePct}% với nhóm{' '}
                      <strong className="text-slate-800">
                        {kpiStats.topByValue.topCategory.shortName}
                      </strong>
                      ), trong khi{' '}
                      <strong className="inline-flex items-center gap-1 text-slate-900">
                        <CountryFlag code={kpiStats.fastestGrowing.country.code} size={13} />
                        {kpiStats.fastestGrowing.country.name}
                      </strong>{' '}
                      bứt phá nhanh nhất (
                      <strong className="text-emerald-700">
                        +{kpiStats.fastestGrowing.yoyGrowthPct}% YoY
                      </strong>
                      , Trends {kpiStats.fastestGrowing.avgSearchIndex}/100).
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setInspectedCountry(kpiStats.topByValue)}
                    className="shrink-0 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
                  >
                    Hồ sơ {kpiStats.topByValue.country.name}
                  </button>
                </section>
              )}

              {/* Row 2: Trend Combo Chart (8 cols) + Market Share Donut (4 cols) */}
              <section className="grid grid-cols-1 gap-4 xl:grid-cols-12">
                <div className="xl:col-span-8">
                  <ImportTrendChart
                    data={timeSeries}
                    granularity={granularity}
                    onGranularityChange={setGranularity}
                    metricMode={metricMode}
                    onMetricModeChange={setMetricMode}
                  />
                </div>
                <div className="xl:col-span-4">
                  <MarketShareDonut
                    rows={countryRows}
                    metricMode={metricMode}
                    highlightedCountry={highlightedCountry}
                    onSelectCountry={handleSelectCountryHighlight}
                  />
                </div>
              </section>

              {/* Row 3: Positioning Matrix (6 cols) + Country Comparison Panel (6 cols) */}
              <section className="grid grid-cols-1 gap-4 xl:grid-cols-12">
                <div className="xl:col-span-6">
                  <CountryMatrixChart
                    rows={countryRows}
                    onSelectCountry={(code) => {
                      const found = countryRows.find((r) => r.country.code === code);
                      if (found) setInspectedCountry(found);
                    }}
                  />
                </div>
                <div className="xl:col-span-6">
                  <CountryComparisonPanel
                    rows={countryRows}
                    highlightedCountry={highlightedCountry}
                    onSelectCountry={handleSelectCountryHighlight}
                  />
                </div>
              </section>

              {/* Row 4: Full Ranking Table */}
              <section>
                <CountryRankingTable
                  rows={countryRows}
                  onInspectCountry={setInspectedCountry}
                  onExportCsv={handleExportCsv}
                />
              </section>
            </>
          ) : activeNav === 'dashboard2' ? (
            <TasteDashboard />
          ) : activeNav === 'dashboard3' ? (
            <CustomerSentimentDashboard />
          ) : activeNav === 'dashboard4' ? (
            <SuppliersProductsDashboard
              suppliers={INITIAL_SUPPLIERS}
              products={supplierProducts}
              onAddProduct={handleAddProduct}
              onUpdateProduct={handleUpdateProduct}
              onDeleteProduct={handleDeleteProduct}
              onGoToDecision={(countryCode) => {
                setDecisionCountry(countryCode);
                setActiveNav('decision');
              }}
            />
          ) : (
            <OrderRecommendationModule
              suppliers={INITIAL_SUPPLIERS}
              products={supplierProducts}
              initialCountry={decisionCountry}
            />
          )}
        </main>
      </div>

      {/* Modals & Drawers */}
      <CountryDetailDrawer
        row={inspectedCountry}
        onClose={() => setInspectedCountry(null)}
      />
      <DataSchemaModal
        open={schemaModalOpen}
        onClose={() => setSchemaModalOpen(false)}
      />
    </div>
  );
}

export default App;
