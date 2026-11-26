import React, { useState } from 'react';
import { TrendingUp } from 'lucide-react';
import {
  MetricMode,
  TimeSeriesPoint,
  formatTons,
  formatUsdMillions,
} from '../data/marketOverviewData';

interface ImportTrendChartProps {
  data: TimeSeriesPoint[];
  granularity: 'yearly' | 'quarterly';
  onGranularityChange: (g: 'yearly' | 'quarterly') => void;
  metricMode: MetricMode;
  onMetricModeChange: (m: MetricMode) => void;
}

function buildTopRoundedBarPath(x: number, y: number, w: number, h: number, r: number): string {
  const radius = Math.min(r, w / 2, h);
  if (h <= 0) return '';
  return [
    `M ${x},${y + h}`,
    `L ${x},${y + radius}`,
    `Q ${x},${y} ${x + radius},${y}`,
    `L ${x + w - radius},${y}`,
    `Q ${x + w},${y} ${x + w},${y + radius}`,
    `L ${x + w},${y + h}`,
    'Z',
  ].join(' ');
}

export const ImportTrendChart: React.FC<ImportTrendChartProps> = ({
  data,
  granularity,
  onGranularityChange,
  metricMode,
  onMetricModeChange,
}) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const svgWidth = 680;
  const svgHeight = 290;
  const pad = { top: 26, right: 48, bottom: 40, left: 54 };
  const plotW = svgWidth - pad.left - pad.right;
  const plotH = svgHeight - pad.top - pad.bottom;

  const primaryValues = data.map((d) =>
    metricMode === 'value' ? d.importValueUsdM : d.importVolumeTons
  );
  const maxPrimary = Math.max(...primaryValues, 1) * 1.18;

  const growthVals = data
    .map((d) => d.yoyGrowthPct)
    .filter((v): v is number => v !== null);
  const minGrowth = Math.min(0, ...(growthVals.length ? growthVals : [0])) - 2;
  const maxGrowth = Math.max(15, ...(growthVals.length ? growthVals : [15])) + 3;
  const growthRange = maxGrowth - minGrowth || 1;

  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  const getBarGeometry = (idx: number) => {
    const slotW = plotW / Math.max(data.length, 1);
    const widthRatio = granularity === 'yearly' ? 0.36 : 0.46;
    const barW = Math.min(36, slotW * widthRatio);
    return {
      centerX: pad.left + idx * slotW + slotW / 2,
      barX: pad.left + idx * slotW + (slotW - barW) / 2,
      barW,
      slotW,
    };
  };

  const getPrimaryY = (val: number) => pad.top + plotH - (val / maxPrimary) * plotH;
  const getGrowthY = (g: number) => pad.top + plotH - ((g - minGrowth) / growthRange) * plotH;

  const growthPoints = data
    .map((d, idx) => {
      if (d.yoyGrowthPct === null) return null;
      const { centerX } = getBarGeometry(idx);
      return {
        idx,
        x: centerX,
        y: getGrowthY(d.yoyGrowthPct),
        val: d.yoyGrowthPct,
      };
    })
    .filter((p): p is { idx: number; x: number; y: number; val: number } => p !== null);

  const growthPolyline = growthPoints
    .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ');

  const hoveredPoint = hoveredIdx !== null ? data[hoveredIdx] : null;
  const hoveredCenterXPct =
    hoveredIdx !== null ? (getBarGeometry(hoveredIdx).centerX / svgWidth) * 100 : 50;

  return (
    <div className="flex h-full flex-col rounded-xl border border-[#E2E8F0] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
              <TrendingUp className="h-3.5 w-3.5" />
            </span>
            <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
              Xu hướng Quy mô nhập khẩu & Tốc độ tăng trưởng
            </h3>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            So sánh{' '}
            {metricMode === 'value'
              ? 'giá trị nhập khẩu (Triệu USD)'
              : 'khối lượng nhập khẩu (Tấn)'}{' '}
            và tăng trưởng YoY (%)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => onMetricModeChange('value')}
              className={`rounded-md px-2.5 py-1 transition ${
                metricMode === 'value'
                  ? 'bg-white text-slate-900 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Giá trị (USD)
            </button>
            <button
              type="button"
              onClick={() => onMetricModeChange('volume')}
              className={`rounded-md px-2.5 py-1 transition ${
                metricMode === 'volume'
                  ? 'bg-white text-slate-900 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Khối lượng (Tấn)
            </button>
          </div>

          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => onGranularityChange('yearly')}
              className={`rounded-md px-2.5 py-1 transition ${
                granularity === 'yearly'
                  ? 'bg-white text-slate-900 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Theo năm
            </button>
            <button
              type="button"
              onClick={() => onGranularityChange('quarterly')}
              className={`rounded-md px-2.5 py-1 transition ${
                granularity === 'quarterly'
                  ? 'bg-white text-slate-900 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Theo quý
            </button>
          </div>
        </div>
      </div>

      {/* Minimal Legend Strip */}
      <div className="mt-3.5 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <span className="inline-flex items-center gap-1.5 font-medium text-slate-600">
            <span className="h-2.5 w-2.5 rounded-[3px] bg-indigo-600" />
            {metricMode === 'value' ? 'Giá trị nhập khẩu' : 'Khối lượng nhập khẩu'}
          </span>
          <span className="inline-flex items-center gap-1.5 font-medium text-slate-600">
            <span className="h-0.5 w-4 rounded-full bg-teal-600" />
            <span className="h-2 w-2 -ml-3 rounded-full border-2 border-teal-600 bg-white" />
            Tăng trưởng YoY (%)
          </span>
        </div>
        <span className="text-[11px] text-slate-400">Di chuột lên cột để xem chi tiết</span>
      </div>

      {/* Chart Canvas */}
      <div className="relative mt-2 flex-1">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="h-full w-full select-none"
          role="img"
          aria-label="Biểu đồ xu hướng giá trị nhập khẩu và tốc độ tăng trưởng"
        >
          <defs>
            <linearGradient id="cleanBarGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4F46E5" stopOpacity="0.92" />
              <stop offset="100%" stopColor="#6366F1" stopOpacity="0.78" />
            </linearGradient>
          </defs>

          {/* Subtle dashed horizontal gridlines */}
          {yTicks.map((t) => {
            const y = pad.top + plotH * (1 - t);
            const leftVal = maxPrimary * t;
            const rightVal = minGrowth + growthRange * t;
            return (
              <g key={t}>
                <line
                  x1={pad.left}
                  y1={y}
                  x2={svgWidth - pad.right}
                  y2={y}
                  stroke="#E2E8F0"
                  strokeOpacity={t === 0 ? 1 : 0.8}
                  strokeDasharray={t === 0 ? undefined : '3 4'}
                  strokeWidth={1}
                />
                <text
                  x={pad.left - 8}
                  y={y + 3.5}
                  textAnchor="end"
                  className="fill-slate-400 text-[10px] tabular-nums"
                >
                  {metricMode === 'value'
                    ? leftVal >= 1000
                      ? `${(leftVal / 1000).toFixed(1)}B`
                      : `${Math.round(leftVal)}M`
                    : `${Math.round(leftVal / 1000)}K`}
                </text>
                <text
                  x={svgWidth - pad.right + 8}
                  y={y + 3.5}
                  textAnchor="start"
                  className="fill-slate-400 text-[10px] tabular-nums"
                >
                  {`${rightVal.toFixed(0)}%`}
                </text>
              </g>
            );
          })}

          {/* Bars with rounded top corners & generous spacing */}
          {data.map((d, idx) => {
            const val = metricMode === 'value' ? d.importValueUsdM : d.importVolumeTons;
            const { barX, barW, centerX, slotW } = getBarGeometry(idx);
            const y = getPrimaryY(val);
            const barH = Math.max(2, pad.top + plotH - y);
            const isHovered = hoveredIdx === idx;
            const barPath = buildTopRoundedBarPath(barX, y, barW, barH, 5);

            return (
              <g
                key={d.label}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                className="cursor-pointer"
              >
                <rect
                  x={pad.left + idx * slotW}
                  y={pad.top}
                  width={slotW}
                  height={plotH + pad.bottom}
                  fill="transparent"
                />
                {isHovered && (
                  <rect
                    x={pad.left + idx * slotW + 3}
                    y={pad.top}
                    width={slotW - 6}
                    height={plotH}
                    rx={6}
                    fill="#F1F5F9"
                    opacity={0.7}
                  />
                )}
                <path
                  d={barPath}
                  fill={isHovered ? '#4338CA' : 'url(#cleanBarGrad)'}
                  opacity={hoveredIdx !== null && !isHovered ? 0.55 : 1}
                  className="transition-opacity duration-150"
                />

                {(granularity === 'yearly' || isHovered) && (
                  <text
                    x={centerX}
                    y={Math.max(14, y - 7)}
                    textAnchor="middle"
                    className={`text-[10px] font-semibold tabular-nums ${
                      isHovered ? 'fill-indigo-700' : 'fill-slate-500'
                    }`}
                  >
                    {metricMode === 'value'
                      ? d.importValueUsdM >= 1000
                        ? `$${(d.importValueUsdM / 1000).toFixed(2)}B`
                        : `$${Math.round(d.importValueUsdM)}M`
                      : `${(d.importVolumeTons / 1000).toFixed(0)}K`}
                  </text>
                )}

                <text
                  x={centerX}
                  y={svgHeight - 15}
                  textAnchor="middle"
                  className={`text-[11px] font-medium tabular-nums ${
                    isHovered ? 'fill-slate-900 font-semibold' : 'fill-slate-500'
                  }`}
                >
                  {d.label}
                </text>
              </g>
            );
          })}

          {/* YoY Growth Line */}
          {growthPolyline && (
            <polyline
              fill="none"
              stroke="#0D9488"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              points={growthPolyline}
            />
          )}

          {/* Growth Points */}
          {growthPoints.map((pt) => {
            const isHovered = hoveredIdx === pt.idx;
            return (
              <circle
                key={pt.idx}
                cx={pt.x}
                cy={pt.y}
                r={isHovered ? 5 : 3.5}
                fill="#FFFFFF"
                stroke="#0D9488"
                strokeWidth={isHovered ? 2.5 : 2}
                className="pointer-events-none"
              />
            );
          })}
        </svg>

        {/* Crisp Floating Hover Tooltip */}
        {hoveredPoint && (
          <div
            className="pointer-events-none absolute top-2 z-20 -translate-x-1/2 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs shadow-md backdrop-blur-xs"
            style={{
              left: `${Math.min(84, Math.max(16, hoveredCenterXPct))}%`,
            }}
          >
            <p className="font-semibold text-slate-900">{hoveredPoint.subLabel}</p>
            <div className="mt-1 space-y-0.5 tabular-nums">
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-500">
                  {metricMode === 'value' ? 'Giá trị NK:' : 'Khối lượng:'}
                </span>
                <span className="font-semibold text-indigo-700">
                  {metricMode === 'value'
                    ? formatUsdMillions(hoveredPoint.importValueUsdM)
                    : formatTons(hoveredPoint.importVolumeTons)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-500">Tăng trưởng YoY:</span>
                <span
                  className={`font-semibold ${
                    (hoveredPoint.yoyGrowthPct ?? 0) >= 0
                      ? 'text-emerald-700'
                      : 'text-rose-700'
                  }`}
                >
                  {hoveredPoint.yoyGrowthPct !== null
                    ? `${hoveredPoint.yoyGrowthPct > 0 ? '+' : ''}${hoveredPoint.yoyGrowthPct}%`
                    : 'Kỳ gốc'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-500">Google Trends:</span>
                <span className="font-semibold text-slate-800">
                  {hoveredPoint.searchIndex}/100
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
