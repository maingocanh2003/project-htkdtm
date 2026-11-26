import React, { useState } from 'react';
import { Globe2, Layers } from 'lucide-react';
import {
  COMPETITOR_SHARES,
  CountrySummaryRow,
  PRODUCT_CATEGORIES,
  formatUsdMillions,
} from '../data/marketOverviewData';
import { CountryFlag } from './CountryFlag';

interface CountryComparisonPanelProps {
  rows: CountrySummaryRow[];
  highlightedCountry: string | null;
  onSelectCountry: (countryCode: string) => void;
}

export const CountryComparisonPanel: React.FC<CountryComparisonPanelProps> = ({
  rows,
  highlightedCountry,
  onSelectCountry,
}) => {
  const [activeTab, setActiveTab] = useState<'category' | 'competitors'>('category');

  const topRows = rows.slice(0, 6);
  const maxCountryVal = Math.max(...topRows.map((r) => r.importValueUsdM), 1);

  const selectedCompetitorCountryCode =
    highlightedCountry && COMPETITOR_SHARES.some((c) => c.countryCode === highlightedCountry)
      ? highlightedCountry
      : rows[0]?.country.code ?? 'US';

  const competitorData = COMPETITOR_SHARES.find(
    (c) => c.countryCode === selectedCompetitorCountryCode
  );
  const activeCountryMeta = rows.find(
    (r) => r.country.code === selectedCompetitorCountryCode
  )?.country;

  return (
    <div className="flex h-full flex-col rounded-xl border border-[#E2E8F0] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
              {activeTab === 'category' ? (
                <Layers className="h-3.5 w-3.5" />
              ) : (
                <Globe2 className="h-3.5 w-3.5" />
              )}
            </span>
            <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
              {activeTab === 'category'
                ? 'So sánh Quốc gia theo Nhóm sản phẩm'
                : 'Cạnh tranh Nguồn cung tại Thị trường'}
            </h3>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {activeTab === 'category'
              ? 'Phân bổ giá trị nhập khẩu giữa 4 nhóm sản phẩm gốm sứ'
              : 'Thị phần xuất khẩu của Việt Nam so với các quốc gia đối thủ'}
          </p>
        </div>

        <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
          <button
            type="button"
            onClick={() => setActiveTab('category')}
            className={`rounded-md px-2.5 py-1 transition ${
              activeTab === 'category'
                ? 'bg-white text-slate-900 shadow-2xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Nhóm sản phẩm
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('competitors')}
            className={`rounded-md px-2.5 py-1 transition ${
              activeTab === 'competitors'
                ? 'bg-white text-slate-900 shadow-2xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Đối thủ nguồn cung
          </button>
        </div>
      </div>

      {activeTab === 'category' ? (
        <div className="mt-4 flex flex-1 flex-col justify-between">
          <div className="mb-3 flex flex-wrap gap-3 text-xs">
            {PRODUCT_CATEGORIES.map((cat) => (
              <span key={cat.id} className="inline-flex items-center gap-1.5 text-slate-600">
                <span
                  className="h-2 w-2 rounded-[2px]"
                  style={{ backgroundColor: cat.color }}
                />
                {cat.shortName}
              </span>
            ))}
          </div>

          <div className="space-y-3">
            {topRows.map((row) => {
              const totalWidthPct = (row.importValueUsdM / maxCountryVal) * 100;
              const isSelected = highlightedCountry === row.country.code;

              return (
                <button
                  key={row.country.code}
                  type="button"
                  onClick={() => onSelectCountry(row.country.code)}
                  className={`block w-full rounded-lg p-2 text-left transition ${
                    isSelected ? 'bg-indigo-50/70 ring-1 ring-indigo-200' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="inline-flex items-center gap-2 font-semibold text-slate-800">
                      <CountryFlag code={row.country.code} size={16} />
                      <span>{row.country.name}</span>
                    </span>
                    <div className="flex items-center gap-2 tabular-nums">
                      <span className="font-bold text-slate-900">
                        {formatUsdMillions(row.importValueUsdM)}
                      </span>
                      <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-700">
                        +{row.yoyGrowthPct}%
                      </span>
                    </div>
                  </div>

                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="flex h-full overflow-hidden rounded-full transition-all duration-300"
                      style={{ width: `${Math.max(4, totalWidthPct)}%` }}
                    >
                      {PRODUCT_CATEGORIES.map((cat) => {
                        const catVal = row.categoryBreakdown[cat.id];
                        const segPct =
                          row.importValueUsdM > 0 ? (catVal / row.importValueUsdM) * 100 : 0;
                        if (segPct <= 0) return null;
                        return (
                          <div
                            key={cat.id}
                            title={`${cat.shortName}: ${formatUsdMillions(catVal)} (${segPct.toFixed(1)}%)`}
                            style={{
                              width: `${segPct}%`,
                              backgroundColor: cat.color,
                            }}
                            className="h-full border-r border-white/50 last:border-r-0"
                          />
                        );
                      })}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="mt-4 flex flex-1 flex-col justify-between">
          <div className="flex flex-wrap gap-1.5">
            {rows.map((r) => (
              <button
                key={r.country.code}
                type="button"
                onClick={() => onSelectCountry(r.country.code)}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                  r.country.code === selectedCompetitorCountryCode
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-700 font-semibold'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                <CountryFlag code={r.country.code} size={14} />
                <span>{r.country.name}</span>
              </button>
            ))}
          </div>

          {competitorData && activeCountryMeta && (
            <div className="mt-4 space-y-2.5">
              {competitorData.origins.map((origin) => {
                const isVn = origin.name === 'Việt Nam';
                return (
                  <div
                    key={origin.name}
                    className={`rounded-lg p-2.5 ${
                      isVn
                        ? 'border border-indigo-200 bg-indigo-50/70'
                        : 'border border-slate-100 bg-slate-50/60'
                    }`}
                  >
                    <div className="mb-1.5 flex items-center justify-between text-xs">
                      <span
                        className={`inline-flex items-center gap-1.5 font-semibold ${
                          isVn ? 'text-indigo-800' : 'text-slate-700'
                        }`}
                      >
                        {isVn && <CountryFlag code="VN" size={14} />}
                        <span>{origin.name}</span>
                        {isVn && (
                          <span className="ml-1 rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                            Mục tiêu mở rộng
                          </span>
                        )}
                      </span>
                      <span className="font-bold text-slate-900 tabular-nums">
                        {origin.sharePct.toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200/70">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${origin.sharePct}%`,
                          backgroundColor: origin.color,
                        }}
                      />
                    </div>
                  </div>
                );
              })}

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                <span className="font-semibold text-slate-900">
                  Thuế quan & Lợi thế tại {activeCountryMeta.name}:{' '}
                </span>
                {activeCountryMeta.tariffNote}. {activeCountryMeta.vnAdvantage}.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
