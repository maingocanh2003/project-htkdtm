import React, { useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  Clock,
  DollarSign,
  Download,
  PackageCheck,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import {
  COUNTRIES,
  PRODUCT_CATEGORIES,
  QuarterFilter,
  computeCountrySummaries,
} from '../data/marketOverviewData';
import { COUNTRY_SENTIMENTS } from '../data/sentimentData';
import { DomesticSupplier, SupplierProduct } from '../data/suppliersData';
import { KpiCard } from './KpiCard';
import { CountryFlag } from './CountryFlag';

type StrategyMode = 'balanced' | 'margin' | 'fast' | 'taste';

interface OrderRecommendationModuleProps {
  suppliers: DomesticSupplier[];
  products: SupplierProduct[];
  initialCountry?: string;
}

export const OrderRecommendationModule: React.FC<OrderRecommendationModuleProps> = ({
  suppliers,
  products,
  initialCountry = 'US',
}) => {
  const [targetCountry, setTargetCountry] = useState<string>(initialCountry);
  const [budgetUsd, setBudgetUsd] = useState<number>(60000);
  const [quarter, setQuarter] = useState<Exclude<QuarterFilter, 'all'>>('Q4');
  const [strategy, setStrategy] = useState<StrategyMode>('balanced');

  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [customQuantities, setCustomQuantities] = useState<Record<string, number>>({});

  useEffect(() => {
    setTargetCountry(initialCountry);
  }, [initialCountry]);

  const countryMarketSummary = useMemo(() => {
    return computeCountrySummaries({
      selectedYear: 2025,
      selectedQuarter: quarter,
      selectedCategory: 'all',
      selectedCountries: [targetCountry],
    })[0];
  }, [targetCountry, quarter]);

  const countrySentiment = useMemo(() => {
    return COUNTRY_SENTIMENTS.find((s) => s.countryCode === targetCountry);
  }, [targetCountry]);

  const scoredCandidates = useMemo(() => {
    const seasonalFactor = quarter === 'Q4' ? 1.2 : quarter === 'Q3' ? 1.1 : quarter === 'Q1' ? 0.9 : 1.0;

    return products
      .map((p) => {
        const sup = suppliers.find((s) => s.id === p.supplierId)!;
        const marketFit = p.marketFitByCountry[targetCountry] ?? 75;
        const sentimentScore = countrySentiment ? countrySentiment.positivePct : 75;
        const marginPct = ((p.exportRefPriceUsd - p.importCostUsd) / p.exportRefPriceUsd) * 100;
        const speedScore = Math.max(40, 100 - (p.leadTimeDays - 10) * 2.5);
        const reliability = sup?.reliabilityScore ?? 85;

        let compositeScore = 0;
        if (strategy === 'balanced') {
          compositeScore =
            marketFit * 0.42 + marginPct * 0.65 * 0.25 + sentimentScore * 0.18 + reliability * 0.15;
        } else if (strategy === 'margin') {
          compositeScore = marginPct * 1.15 * 0.45 + marketFit * 0.35 + reliability * 0.2;
        } else if (strategy === 'fast') {
          compositeScore = speedScore * 0.45 + marketFit * 0.35 + reliability * 0.2;
        } else {
          compositeScore = marketFit * 0.6 + sentimentScore * 0.25 + reliability * 0.15;
        }

        const score = Math.min(99, Math.round(compositeScore));
        const category = PRODUCT_CATEGORIES.find((c) => c.id === p.categoryId);

        return {
          product: p,
          supplier: sup,
          category,
          marketFit,
          marginPct: Number(marginPct.toFixed(1)),
          score,
          seasonalFactor,
        };
      })
      .sort((a, b) => b.score - a.score);
  }, [products, suppliers, targetCountry, quarter, strategy, countrySentiment]);

  // Allocate budget across top 4 recommended products proportionally to their DSS score
  const recommendedAllocations = useMemo(() => {
    const top4 = scoredCandidates.slice(0, 4);
    const totalScore = top4.reduce((s, c) => s + c.score, 0) || 1;

    const map: Record<string, { defaultSelected: boolean; defaultQty: number }> = {};
    scoredCandidates.forEach((item, idx) => {
      if (idx < 4) {
        const allocatedBudget = budgetUsd * (item.score / totalScore);
        const rawQty = Math.round(allocatedBudget / item.product.importCostUsd / 50) * 50;
        const clampedQty = Math.min(
          item.product.maxOrderUnitsMonth,
          Math.max(item.product.moqUnits, rawQty)
        );
        map[item.product.id] = { defaultSelected: true, defaultQty: clampedQty };
      } else {
        map[item.product.id] = {
          defaultSelected: false,
          defaultQty: item.product.moqUnits,
        };
      }
    });
    return map;
  }, [scoredCandidates, budgetUsd]);

  // Reset manual overrides when core simulation inputs change
  useEffect(() => {
    setSelectedIds({});
    setCustomQuantities({});
  }, [targetCountry, budgetUsd, quarter, strategy]);

  const planRows = useMemo(() => {
    return scoredCandidates.map((item) => {
      const alloc = recommendedAllocations[item.product.id];
      const isSelected =
        selectedIds[item.product.id] !== undefined
          ? selectedIds[item.product.id]
          : alloc.defaultSelected;
      const qty =
        customQuantities[item.product.id] !== undefined
          ? customQuantities[item.product.id]
          : alloc.defaultQty;

      const totalCost = qty * item.product.importCostUsd;
      const totalRevenue = qty * item.product.exportRefPriceUsd;
      const estProfit = totalRevenue - totalCost;
      const exceedsCapacity = qty > item.product.maxOrderUnitsMonth;

      return {
        ...item,
        isSelected,
        qty,
        totalCost,
        totalRevenue,
        estProfit,
        exceedsCapacity,
      };
    });
  }, [scoredCandidates, recommendedAllocations, selectedIds, customQuantities]);

  const activePlan = planRows.filter((r) => r.isSelected);

  const planTotals = useMemo(() => {
    const totalUnits = activePlan.reduce((s, r) => s + r.qty, 0);
    const totalCost = activePlan.reduce((s, r) => s + r.totalCost, 0);
    const totalRevenue = activePlan.reduce((s, r) => s + r.totalRevenue, 0);
    const totalProfit = totalRevenue - totalCost;
    const avgMargin = totalRevenue > 0 ? (totalProfit / totalRevenue) * 100 : 0;
    const maxLeadTime =
      activePlan.length > 0 ? Math.max(...activePlan.map((r) => r.product.leadTimeDays)) : 0;
    const budgetUsagePct = budgetUsd > 0 ? (totalCost / budgetUsd) * 100 : 0;

    return {
      totalUnits,
      totalCost,
      totalRevenue,
      totalProfit,
      avgMargin: avgMargin.toFixed(1),
      maxLeadTime,
      budgetUsagePct: Number(budgetUsagePct.toFixed(1)),
    };
  }, [activePlan, budgetUsd]);

  const targetCountryMeta = COUNTRIES.find((c) => c.code === targetCountry);
  const topRec = activePlan[0] ?? planRows[0];

  const handleExportOrderPlan = () => {
    const headers = [
      'ThiTruong',
      'SKU',
      'SanPham',
      'NhaCungCap',
      'DiemDSS',
      'SoLuongDeXuat',
      'GiaNhap_USD',
      'TongChiPhi_USD',
      'LoiNhuanDuKien_USD',
      'LeadTime_Ngay',
    ];
    const lines = activePlan.map((r) =>
      [
        targetCountryMeta?.name ?? targetCountry,
        r.product.sku,
        `"${r.product.name}"`,
        `"${r.supplier?.name ?? ''}"`,
        r.score,
        r.qty,
        r.product.importCostUsd.toFixed(2),
        r.totalCost.toFixed(2),
        r.estProfit.toFixed(2),
        r.product.leadTimeDays,
      ].join(',')
    );
    const csv = '\uFEFF' + [headers.join(','), ...lines].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kilnscope_de_xuat_dat_hang_${targetCountry}_${quarter}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* Decision Parameters Bar */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 pr-1 text-xs font-semibold text-slate-600">
              <SlidersHorizontal className="h-3.5 w-3.5 text-indigo-600" />
              Tham số quyết định:
            </span>

            {/* Target Country */}
            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
              <CountryFlag code={targetCountry} size={14} />
              <span className="font-medium text-slate-500">Thị trường:</span>
              <select
                value={targetCountry}
                onChange={(e) => setTargetCountry(e.target.value)}
                className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Quarter */}
            <div className="inline-flex h-8.5 items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
              {(['Q1', 'Q2', 'Q3', 'Q4'] as const).map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setQuarter(q)}
                  className={`rounded-md px-2 py-1 font-medium transition ${
                    quarter === q
                      ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {q}
                </button>
              ))}
            </div>

            {/* Budget */}
            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs tabular-nums">
              <DollarSign className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-medium text-slate-500">Ngân sách:</span>
              <select
                value={budgetUsd}
                onChange={(e) => setBudgetUsd(Number(e.target.value))}
                className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                <option value={25000}>$25,000</option>
                <option value={45000}>$45,000</option>
                <option value={60000}>$60,000</option>
                <option value={100000}>$100,000</option>
                <option value={150000}>$150,000</option>
              </select>
            </div>

            {/* Strategy */}
            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
              <span className="font-medium text-slate-500">Chiến lược:</span>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as StrategyMode)}
                className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                <option value="balanced">Cân bằng tối ưu</option>
                <option value="taste">Ưu tiên khớp thị hiếu nhất</option>
                <option value="margin">Ưu tiên biên lợi nhuận cao</option>
                <option value="fast">Ưu tiên giao hàng nhanh</option>
              </select>
            </div>
          </div>

          <button
            type="button"
            onClick={handleExportOrderPlan}
            disabled={activePlan.length === 0}
            className="inline-flex h-8.5 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 text-xs font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            Xuất Phiếu Đặt Hàng
          </button>
        </div>
      </section>

      {/* Row 1: 4 Order Plan KPIs */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Tổng số lượng đề xuất"
          value={`${planTotals.totalUnits.toLocaleString('en-US')} SP`}
          subtitle={`Gồm ${activePlan.length} mã sản phẩm từ các làng nghề VN`}
          icon={<PackageCheck className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Tổng chi phí nhập dự kiến"
          value={`$${Math.round(planTotals.totalCost).toLocaleString('en-US')}`}
          subtitle={`Sử dụng ${planTotals.budgetUsagePct}% ngân sách ($${budgetUsd.toLocaleString('en-US')})`}
          icon={<DollarSign className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Lợi nhuận gộp ước tính"
          value={`$${Math.round(planTotals.totalProfit).toLocaleString('en-US')}`}
          subtitle={`Biên lợi nhuận gộp TB: ${planTotals.avgMargin}%`}
          delta={Number(planTotals.avgMargin)}
          deltaLabel="biên gộp"
          icon={<TrendingUp className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Thời gian cung ứng tối đa"
          value={`${planTotals.maxLeadTime} ngày`}
          subtitle={`Điểm tiềm năng ${targetCountryMeta?.name}: ${countryMarketSummary?.potentialScore ?? 85}/100`}
          icon={<Clock className="h-4.5 w-4.5" />}
        />
      </section>

      {/* Key Decision Insight Bar */}
      {topRec && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E2E8F0] bg-white px-4 py-3">
          <div className="flex items-start gap-2.5 text-xs leading-relaxed text-slate-600 sm:items-center">
            <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-indigo-200/80 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
              <Sparkles className="h-3 w-3" />
              Đề xuất trọng tâm
            </span>
            <p className="tabular-nums">
              Cho kế hoạch xuất khẩu sang{' '}
              <strong className="inline-flex items-center gap-1 text-slate-900">
                <CountryFlag code={targetCountry} size={13} />
                {targetCountryMeta?.name} ({quarter})
              </strong>
              , hệ thống ưu tiên đặt{' '}
              <strong className="text-indigo-700">
                {topRec.qty.toLocaleString('en-US')} SP {topRec.product.name}
              </strong>{' '}
              từ <strong>{topRec.supplier?.village}</strong> (Điểm DSS:{' '}
              <strong>{topRec.score}/100</strong>, khớp thị hiếu{' '}
              <strong>{topRec.marketFit}%</strong>).
            </p>
          </div>
        </section>
      )}

      {/* Row 2: Executive Decision Summary Cards (Answering the 5 report questions) */}
      <section className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-4 text-xs">
          <p className="text-[11px] font-semibold text-slate-400 uppercase">
            1. Thị trường & Nhóm SP ưu tiên
          </p>
          <p className="mt-1.5 font-semibold text-slate-900">
            {targetCountryMeta?.name} • {countryMarketSummary?.topCategory.name}
          </p>
          <p className="mt-1 leading-relaxed text-slate-500">
            {targetCountryMeta?.preferredStyle}. Màu sắc ưa chuộng:{' '}
            {targetCountryMeta?.preferredColors}.
          </p>
        </div>

        <div className="rounded-xl border border-[#E2E8F0] bg-white p-4 text-xs">
          <p className="text-[11px] font-semibold text-slate-400 uppercase">
            2. Nhà cung cấp & Năng lực đáp ứng
          </p>
          <p className="mt-1.5 font-semibold text-slate-900">
            {topRec?.supplier?.name}
          </p>
          <p className="mt-1 leading-relaxed text-slate-500 tabular-nums">
            Độ tin cậy {topRec?.supplier?.reliabilityScore}% • Công suất{' '}
            {topRec?.supplier?.monthlyCapacityUnits.toLocaleString('en-US')} SP/tháng •{' '}
            {topRec?.supplier?.certifications.join(', ')}.
          </p>
        </div>

        <div className="rounded-xl border border-[#E2E8F0] bg-white p-4 text-xs">
          <p className="text-[11px] font-semibold text-slate-400 uppercase">
            3. Lưu ý chất lượng từ AI/NLP
          </p>
          <p className="mt-1.5 font-semibold text-slate-900">
            Cần kiểm soát đóng gói chống sứt mẻ viền
          </p>
          <p className="mt-1 leading-relaxed text-slate-500 tabular-nums">
            Mức độ hài lòng hiện tại ở {targetCountryMeta?.name}:{' '}
            <strong className="text-emerald-700">
              {countrySentiment?.positivePct ?? 75}% Tích cực
            </strong>{' '}
            ({countrySentiment?.avgRating.toFixed(2) ?? '4.55'}★).
          </p>
        </div>
      </section>

      {/* Row 3: Interactive Order Recommendation Table */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
              Bảng Đề xuất Đặt hàng Chi tiết (Có thể điều chỉnh số lượng)
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              Tích chọn sản phẩm và điều chỉnh số lượng tham khảo để tính lại chi phí & lợi nhuận theo thời gian thực
            </p>
          </div>
          <span
            className={`rounded-md px-2.5 py-1 text-xs font-semibold tabular-nums ${
              planTotals.totalCost <= budgetUsd
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-amber-50 text-amber-700'
            }`}
          >
            {planTotals.totalCost <= budgetUsd
              ? `Trong ngân sách (còn $${Math.round(budgetUsd - planTotals.totalCost).toLocaleString('en-US')})`
              : `Vượt ngân sách $${Math.round(planTotals.totalCost - budgetUsd).toLocaleString('en-US')}`}
          </span>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[960px] border-collapse text-left text-xs tabular-nums">
            <thead>
              <tr className="border-y border-slate-200 bg-slate-50/80 text-[11px] font-semibold text-slate-500 uppercase">
                <th className="px-3 py-2.5 text-center">Chọn</th>
                <th className="px-3 py-2.5">Sản phẩm & Nhà cung cấp</th>
                <th className="px-3 py-2.5 text-center">Điểm DSS</th>
                <th className="px-3 py-2.5 text-right">Khớp thị hiếu</th>
                <th className="px-3 py-2.5 text-right">Giá nhập</th>
                <th className="px-3 py-2.5 text-center">Số lượng đề xuất</th>
                <th className="px-3 py-2.5 text-right">Thành tiền nhập</th>
                <th className="px-3 py-2.5 text-right">Lợi nhuận gộp</th>
                <th className="px-3 py-2.5 text-right">Lead time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {planRows.map((row) => (
                <tr
                  key={row.product.id}
                  className={row.isSelected ? 'bg-indigo-50/25' : 'opacity-70 hover:opacity-100'}
                >
                  <td className="px-3 py-3 text-center">
                    <input
                      type="checkbox"
                      checked={row.isSelected}
                      onChange={() =>
                        setSelectedIds((prev) => ({
                          ...prev,
                          [row.product.id]: !row.isSelected,
                        }))
                      }
                      className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    />
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] font-semibold text-slate-400">
                        {row.product.sku}
                      </span>
                      {row.score >= 85 && (
                        <span className="inline-flex items-center gap-0.5 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700">
                          <CheckCircle2 className="h-2.5 w-2.5" /> Khuyên dùng
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 font-semibold text-slate-900">{row.product.name}</p>
                    <p className="text-[11px] text-slate-500">
                      {row.supplier?.name} • MOQ: {row.product.moqUnits} • Tối đa:{' '}
                      {row.product.maxOrderUnitsMonth.toLocaleString('en-US')}/tháng
                    </p>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className="inline-flex rounded-md bg-slate-900 px-2 py-0.5 font-bold text-white">
                      {row.score}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right font-semibold text-indigo-700">
                    {row.marketFit}%
                  </td>
                  <td className="px-3 py-3 text-right font-medium text-slate-700">
                    ${row.product.importCostUsd.toFixed(2)}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <input
                      type="number"
                      min={row.product.moqUnits}
                      step={50}
                      value={row.qty}
                      onChange={(e) =>
                        setCustomQuantities((prev) => ({
                          ...prev,
                          [row.product.id]: Math.max(0, Number(e.target.value)),
                        }))
                      }
                      className={`w-24 rounded-lg border px-2 py-1 text-center font-semibold focus:outline-hidden ${
                        row.exceedsCapacity
                          ? 'border-rose-400 bg-rose-50 text-rose-700'
                          : 'border-slate-200 bg-white text-slate-900 focus:border-indigo-400'
                      }`}
                    />
                    {row.exceedsCapacity && (
                      <span className="mt-0.5 block text-[10px] font-medium text-rose-600">
                        Vượt công suất tháng
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-right font-bold text-slate-900">
                    ${Math.round(row.totalCost).toLocaleString('en-US')}
                  </td>
                  <td className="px-3 py-3 text-right font-semibold text-emerald-700">
                    +${Math.round(row.estProfit).toLocaleString('en-US')}
                    <span className="block text-[10px] font-normal text-slate-400">
                      ({row.marginPct}%)
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right text-slate-600">
                    {row.product.leadTimeDays} ngày
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
