import React from 'react';
import {
  Award,
  CheckCircle2,
  Globe,
  Palette,
  ShieldCheck,
  TrendingUp,
  X,
} from 'lucide-react';
import {
  AVAILABLE_YEARS,
  COMPETITOR_SHARES,
  CountrySummaryRow,
  PRODUCT_CATEGORIES,
  TRADE_FACTS,
  formatTons,
  formatUsdMillions,
} from '../data/marketOverviewData';
import { CountryFlag } from './CountryFlag';

interface CountryDetailDrawerProps {
  row: CountrySummaryRow | null;
  onClose: () => void;
}

export const CountryDetailDrawer: React.FC<CountryDetailDrawerProps> = ({ row, onClose }) => {
  if (!row) return null;

  const yearlyTrend = AVAILABLE_YEARS.map((year) => {
    const val = TRADE_FACTS.filter(
      (r) => r.countryCode === row.country.code && r.year === year
    ).reduce((s, r) => s + r.importValueUsdM, 0);
    return { year, val: Number(val.toFixed(1)) };
  });

  const maxYearVal = Math.max(...yearlyTrend.map((y) => y.val), 1);
  const competitors =
    COMPETITOR_SHARES.find((c) => c.countryCode === row.country.code)?.origins ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto border-l border-slate-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 px-6 py-4 backdrop-blur-xs">
          <div className="flex items-center gap-3">
            <CountryFlag code={row.country.code} size={36} />
            <div>
              <h2 className="font-display text-base font-bold text-slate-900">
                Hồ sơ Thị trường: {row.country.name}
              </h2>
              <p className="text-xs text-slate-500 tabular-nums">
                Khu vực {row.country.region} • Điểm tiềm năng: {row.potentialScore}/100
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="Đóng chi tiết"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-6">
          <div className="grid grid-cols-2 gap-3 tabular-nums">
            <div className="rounded-xl border border-[#E2E8F0] bg-slate-50/70 p-3.5">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">
                Giá trị nhập khẩu (lọc)
              </span>
              <p className="mt-1 font-display text-xl font-bold text-slate-900">
                {formatUsdMillions(row.importValueUsdM)}
              </p>
              <span className="text-xs text-slate-500">{formatTons(row.importVolumeTons)}</span>
            </div>
            <div className="rounded-xl border border-[#E2E8F0] bg-slate-50/70 p-3.5">
              <span className="text-[11px] font-semibold text-slate-500 uppercase">
                Tăng trưởng & Thị phần VN
              </span>
              <p className="mt-1 font-display text-xl font-bold text-emerald-700">
                +{row.yoyGrowthPct}% YoY
              </p>
              <span className="text-xs text-slate-600">
                Thị phần VN: <strong className="text-indigo-700">{row.avgVnSharePct}%</strong>
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-[#E2E8F0] p-4">
            <div className="mb-3 flex items-center gap-2 text-xs font-bold text-slate-800">
              <TrendingUp className="h-4 w-4 text-indigo-600" />
              Quy mô nhập khẩu 2021 – 2025 (Triệu USD)
            </div>
            <div className="grid grid-cols-5 items-end gap-2.5 pt-4 tabular-nums">
              {yearlyTrend.map((item) => {
                const hPct = Math.max(18, (item.val / maxYearVal) * 100);
                return (
                  <div key={item.year} className="flex flex-col items-center gap-1.5">
                    <span className="text-[10px] font-semibold text-slate-700">
                      ${Math.round(item.val)}M
                    </span>
                    <div className="flex h-24 w-full items-end rounded-lg bg-slate-100 p-1">
                      <div
                        className="w-full rounded-t-md bg-indigo-600 transition-all"
                        style={{ height: `${hPct}%` }}
                      />
                    </div>
                    <span className="text-[11px] font-medium text-slate-500">{item.year}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-xl border border-[#E2E8F0] p-4">
            <div className="mb-3 flex items-center gap-2 text-xs font-bold text-slate-800">
              <Award className="h-4 w-4 text-teal-600" />
              Cơ cấu theo nhóm sản phẩm gốm sứ
            </div>
            <div className="space-y-2.5 tabular-nums">
              {PRODUCT_CATEGORIES.map((cat) => {
                const val = row.categoryBreakdown[cat.id];
                const pct = row.importValueUsdM > 0 ? (val / row.importValueUsdM) * 100 : 0;
                return (
                  <div key={cat.id}>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="font-medium text-slate-700">{cat.name}</span>
                      <span className="font-semibold text-slate-900">
                        {formatUsdMillions(val)} ({pct.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${pct}%`, backgroundColor: cat.color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-3 rounded-xl border border-[#E2E8F0] bg-slate-50/70 p-4 text-xs">
            <div className="flex items-start gap-2.5">
              <Palette className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
              <div>
                <p className="font-semibold text-slate-900">Thị hiếu & Màu sắc ưa chuộng</p>
                <p className="mt-0.5 text-slate-600">
                  Phong cách: {row.country.preferredStyle}. Màu sắc: {row.country.preferredColors}.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2.5">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" />
              <div>
                <p className="font-semibold text-slate-900">Chính sách thuế quan & Xuất xứ</p>
                <p className="mt-0.5 text-slate-600">{row.country.tariffNote}.</p>
              </div>
            </div>
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              <div>
                <p className="font-semibold text-slate-900">Lợi thế cạnh tranh gốm sứ Việt Nam</p>
                <p className="mt-0.5 text-slate-600">{row.country.vnAdvantage}.</p>
              </div>
            </div>
          </div>

          {competitors.length > 0 && (
            <div className="rounded-xl border border-[#E2E8F0] p-4">
              <div className="mb-2.5 flex items-center gap-2 text-xs font-bold text-slate-800">
                <Globe className="h-4 w-4 text-indigo-600" />
                Top quốc gia cung ứng tại {row.country.name}
              </div>
              <div className="flex flex-wrap gap-2 tabular-nums">
                {competitors.map((c) => (
                  <span
                    key={c.name}
                    className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${
                      c.name === 'Việt Nam'
                        ? 'border-indigo-300 bg-indigo-50 text-indigo-800 font-semibold'
                        : 'border-slate-200 bg-white text-slate-700'
                    }`}
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: c.color }}
                    />
                    {c.name}: {c.sharePct}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
