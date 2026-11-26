import React, { useState } from 'react';
import { Compass } from 'lucide-react';
import { CountrySummaryRow, formatUsdMillions } from '../data/marketOverviewData';
import { CountryFlag } from './CountryFlag';

interface CountryMatrixChartProps {
  rows: CountrySummaryRow[];
  onSelectCountry: (countryCode: string) => void;
}

const TIER_META: Record<
  CountrySummaryRow['tier'],
  { label: string; badgeClass: string; color: string }
> = {
  star: {
    label: 'Ngôi sao tăng trưởng',
    badgeClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    color: '#4F46E5',
  },
  anchor: {
    label: 'Thị trường chủ lực',
    badgeClass: 'bg-sky-50 text-sky-700 border-sky-200',
    color: '#0284C7',
  },
  emerging: {
    label: 'Ngách tăng trưởng nhanh',
    badgeClass: 'bg-teal-50 text-teal-700 border-teal-200',
    color: '#0D9488',
  },
  stable: {
    label: 'Ổn định / Chọn lọc',
    badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
    color: '#64748B',
  },
};

export const CountryMatrixChart: React.FC<CountryMatrixChartProps> = ({
  rows,
  onSelectCountry,
}) => {
  const [hoveredCode, setHoveredCode] = useState<string | null>(null);

  const svgW = 540;
  const svgH = 300;
  const pad = { top: 24, right: 24, bottom: 38, left: 46 };
  const plotW = svgW - pad.left - pad.right;
  const plotH = svgH - pad.top - pad.bottom;

  const maxX = Math.max(...rows.map((r) => r.importValueUsdM), 100) * 1.15;
  const minY = Math.min(0, ...rows.map((r) => r.yoyGrowthPct)) - 1;
  const maxY = Math.max(15, ...rows.map((r) => r.yoyGrowthPct)) + 2.5;
  const rangeY = maxY - minY || 1;

  const avgX = rows.reduce((s, r) => s + r.importValueUsdM, 0) / Math.max(rows.length, 1);
  const avgY = rows.reduce((s, r) => s + r.yoyGrowthPct, 0) / Math.max(rows.length, 1);

  const getX = (val: number) => pad.left + (val / maxX) * plotW;
  const getY = (g: number) => pad.top + plotH - ((g - minY) / rangeY) * plotH;

  const midX = getX(avgX);
  const midY = getY(avgY);

  const hovered = rows.find((r) => r.country.code === hoveredCode) ?? null;

  return (
    <div className="flex h-full flex-col rounded-xl border border-[#E2E8F0] bg-white p-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
            <Compass className="h-3.5 w-3.5" />
          </span>
          <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
            Ma trận Định vị Thị trường (Quy mô × Tăng trưởng)
          </h3>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Kích thước điểm thể hiện chỉ số quan tâm tìm kiếm (Google Trends)
        </p>
      </div>

      {/* Quadrant legend */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {(['star', 'anchor', 'emerging', 'stable'] as const).map((tier) => (
          <span
            key={tier}
            className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium ${TIER_META[tier].badgeClass}`}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: TIER_META[tier].color }}
            />
            {TIER_META[tier].label}
          </span>
        ))}
      </div>

      <div className="relative mt-3 flex-1">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="h-full w-full select-none">
          {/* Subtle Quadrant Tint */}
          <rect
            x={midX}
            y={pad.top}
            width={Math.max(0, svgW - pad.right - midX)}
            height={Math.max(0, midY - pad.top)}
            fill="#EEF2FF"
            opacity={0.4}
          />
          <rect
            x={pad.left}
            y={pad.top}
            width={Math.max(0, midX - pad.left)}
            height={Math.max(0, midY - pad.top)}
            fill="#F0FDFA"
            opacity={0.45}
          />

          {/* Grid & Axes */}
          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const y = pad.top + plotH * (1 - t);
            const yVal = minY + rangeY * t;
            const x = pad.left + plotW * t;
            const xVal = maxX * t;
            return (
              <g key={t}>
                <line
                  x1={pad.left}
                  y1={y}
                  x2={svgW - pad.right}
                  y2={y}
                  stroke="#E2E8F0"
                  strokeDasharray="3 4"
                />
                <text
                  x={pad.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="fill-slate-400 text-[10px] tabular-nums"
                >
                  {yVal.toFixed(0)}%
                </text>
                <text
                  x={x}
                  y={svgH - 18}
                  textAnchor="middle"
                  className="fill-slate-400 text-[10px] tabular-nums"
                >
                  {xVal >= 1000 ? `$${(xVal / 1000).toFixed(1)}B` : `$${Math.round(xVal)}M`}
                </text>
              </g>
            );
          })}

          {/* Average reference crosshairs */}
          <line
            x1={midX}
            y1={pad.top}
            x2={midX}
            y2={pad.top + plotH}
            stroke="#CBD5E1"
            strokeDasharray="4 4"
            strokeWidth={1.1}
          />
          <line
            x1={pad.left}
            y1={midY}
            x2={svgW - pad.right}
            y2={midY}
            stroke="#CBD5E1"
            strokeDasharray="4 4"
            strokeWidth={1.1}
          />

          <text
            x={svgW - pad.right - 6}
            y={pad.top + 13}
            textAnchor="end"
            className="fill-indigo-600/80 text-[10px] font-semibold"
          >
            Ưu tiên mở rộng
          </text>
          <text
            x={pad.left + 6}
            y={pad.top + 13}
            textAnchor="start"
            className="fill-teal-700/80 text-[10px] font-semibold"
          >
            Tăng tốc nhanh
          </text>

          <text
            x={pad.left + plotW / 2}
            y={svgH - 4}
            textAnchor="middle"
            className="fill-slate-500 text-[10px] font-medium"
          >
            Giá trị nhập khẩu (USD) →
          </text>

          {/* Bubbles */}
          {rows.map((r) => {
            const cx = getX(r.importValueUsdM);
            const cy = getY(r.yoyGrowthPct);
            const radius = 8 + ((r.avgSearchIndex - 50) / 50) * 10;
            const isHovered = hoveredCode === r.country.code;
            const tierColor = TIER_META[r.tier].color;

            return (
              <g
                key={r.country.code}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredCode(r.country.code)}
                onMouseLeave={() => setHoveredCode(null)}
                onClick={() => onSelectCountry(r.country.code)}
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? radius + 3 : radius}
                  fill={tierColor}
                  fillOpacity={isHovered ? 0.92 : 0.72}
                  stroke="#FFFFFF"
                  strokeWidth={2}
                  className="transition-all duration-150"
                />
                <text
                  x={cx}
                  y={cy - radius - 5}
                  textAnchor="middle"
                  className={`text-[11px] font-semibold ${
                    isHovered ? 'fill-slate-900' : 'fill-slate-700'
                  }`}
                >
                  {r.country.name}
                </text>
              </g>
            );
          })}
        </svg>

        {hovered && (
          <div className="pointer-events-none absolute right-3 bottom-8 rounded-lg border border-slate-200 bg-white/95 p-3 shadow-md backdrop-blur-xs">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
              <CountryFlag code={hovered.country.code} size={16} />
              <span>{hovered.country.name}</span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600 tabular-nums">
                {hovered.potentialScore}/100
              </span>
            </div>
            <div className="mt-1.5 grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px] tabular-nums">
              <span className="text-slate-500">Giá trị NK:</span>
              <span className="font-semibold text-slate-900">
                {formatUsdMillions(hovered.importValueUsdM)}
              </span>
              <span className="text-slate-500">Tăng trưởng YoY:</span>
              <span className="font-semibold text-emerald-700">+{hovered.yoyGrowthPct}%</span>
              <span className="text-slate-500">Google Trends:</span>
              <span className="font-semibold text-indigo-700">{hovered.avgSearchIndex}/100</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
