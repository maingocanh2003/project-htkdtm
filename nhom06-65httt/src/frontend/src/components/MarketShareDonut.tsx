import React, { useState } from 'react';
import { PieChart } from 'lucide-react';
import {
  CountrySummaryRow,
  MetricMode,
  formatTons,
  formatUsdMillions,
} from '../data/marketOverviewData';
import { CountryFlag } from './CountryFlag';

interface MarketShareDonutProps {
  rows: CountrySummaryRow[];
  metricMode: MetricMode;
  highlightedCountry: string | null;
  onSelectCountry: (countryCode: string) => void;
}

export const MarketShareDonut: React.FC<MarketShareDonutProps> = ({
  rows,
  metricMode,
  highlightedCountry,
  onSelectCountry,
}) => {
  const [hoveredCode, setHoveredCode] = useState<string | null>(null);

  const totalMetric = rows.reduce(
    (s, r) => s + (metricMode === 'value' ? r.importValueUsdM : r.importVolumeTons),
    0
  );

  // Thin ring: outer diameter ~176 (r=78 + stroke/2=10 => 88), inner cutout ~77%
  const radius = 78;
  const strokeWidth = 18;
  const circumference = 2 * Math.PI * radius;
  let cumulativeFraction = 0;

  const segments = rows.map((row) => {
    const val = metricMode === 'value' ? row.importValueUsdM : row.importVolumeTons;
    const fraction = totalMetric > 0 ? val / totalMetric : 0;
    const dashArray = `${(fraction * circumference).toFixed(2)} ${circumference.toFixed(2)}`;
    const dashOffset = -cumulativeFraction * circumference;
    cumulativeFraction += fraction;

    return {
      row,
      val,
      pct: fraction * 100,
      dashArray,
      dashOffset,
    };
  });

  const activeCode = hoveredCode ?? highlightedCountry;
  const activeSeg = segments.find((s) => s.row.country.code === activeCode);

  return (
    <div className="flex h-full flex-col rounded-xl border border-[#E2E8F0] bg-white p-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
            <PieChart className="h-3.5 w-3.5" />
          </span>
          <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
            Cơ cấu Thị phần nhập khẩu
          </h3>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Phân bổ tỷ trọng giữa các quốc gia (nhấn để lọc nổi bật)
        </p>
      </div>

      <div className="mt-4 flex flex-1 flex-col items-center justify-between">
        <div className="relative flex h-48 w-48 items-center justify-center">
          <svg viewBox="0 0 196 196" className="h-full w-full -rotate-90">
            <circle
              cx={98}
              cy={98}
              r={radius}
              fill="none"
              stroke="#F1F5F9"
              strokeWidth={strokeWidth}
            />
            {segments.map((seg) => {
              const isActive = activeCode === seg.row.country.code;
              const isDimmed = activeCode !== null && !isActive;
              return (
                <circle
                  key={seg.row.country.code}
                  cx={98}
                  cy={98}
                  r={radius}
                  fill="none"
                  stroke={seg.row.country.color}
                  strokeWidth={isActive ? strokeWidth + 4 : strokeWidth}
                  strokeDasharray={seg.dashArray}
                  strokeDashoffset={seg.dashOffset}
                  opacity={isDimmed ? 0.3 : 1}
                  className="cursor-pointer transition-all duration-150"
                  onMouseEnter={() => setHoveredCode(seg.row.country.code)}
                  onMouseLeave={() => setHoveredCode(null)}
                  onClick={() => onSelectCountry(seg.row.country.code)}
                />
              );
            })}
          </svg>

          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-6 text-center">
            {activeSeg ? (
              <>
                <CountryFlag code={activeSeg.row.country.code} size={20} />
                <span className="mt-1.5 text-xs font-medium text-slate-500">
                  {activeSeg.row.country.name}
                </span>
                <span className="font-display text-xl font-bold text-slate-900 tabular-nums">
                  {activeSeg.pct.toFixed(1)}%
                </span>
                <span className="text-[11px] font-semibold text-indigo-600 tabular-nums">
                  {metricMode === 'value'
                    ? formatUsdMillions(activeSeg.row.importValueUsdM)
                    : formatTons(activeSeg.row.importVolumeTons)}
                </span>
              </>
            ) : (
              <>
                <span className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
                  Tổng quy mô
                </span>
                <span className="mt-0.5 font-display text-xl font-bold text-slate-900 tabular-nums">
                  {metricMode === 'value'
                    ? formatUsdMillions(totalMetric)
                    : formatTons(totalMetric)}
                </span>
                <span className="mt-0.5 text-[11px] text-slate-500 tabular-nums">
                  {rows.length} thị trường
                </span>
              </>
            )}
          </div>
        </div>

        {/* Clean Legend */}
        <div className="mt-4 grid w-full grid-cols-2 gap-1">
          {segments.map((seg) => {
            const isSelected = highlightedCountry === seg.row.country.code;
            return (
              <button
                key={seg.row.country.code}
                type="button"
                onMouseEnter={() => setHoveredCode(seg.row.country.code)}
                onMouseLeave={() => setHoveredCode(null)}
                onClick={() => onSelectCountry(seg.row.country.code)}
                className={`flex items-center justify-between rounded-lg px-2 py-1.5 text-left text-xs transition ${
                  isSelected
                    ? 'bg-indigo-50 ring-1 ring-indigo-200'
                    : 'hover:bg-slate-50'
                }`}
              >
                <span className="flex min-w-0 items-center gap-1.5">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: seg.row.country.color }}
                  />
                  <CountryFlag code={seg.row.country.code} size={14} />
                  <span className="truncate font-medium text-slate-700">
                    {seg.row.country.name}
                  </span>
                </span>
                <span className="ml-1 shrink-0 font-semibold text-slate-900 tabular-nums">
                  {seg.pct.toFixed(1)}%
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
