import React from 'react';
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: React.ReactNode;
  subtitle: React.ReactNode;
  delta?: number | null;
  deltaLabel?: string;
  icon: React.ReactNode;
  sparkline?: number[];
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  subtitle,
  delta,
  deltaLabel,
  icon,
  sparkline,
}) => {
  const renderSparkline = () => {
    if (!sparkline || sparkline.length < 2) return null;
    const width = 76;
    const height = 28;
    const min = Math.min(...sparkline);
    const max = Math.max(...sparkline);
    const range = max - min || 1;

    const pts = sparkline.map((v, idx) => {
      const x = (idx / (sparkline.length - 1)) * width;
      const y = height - 4 - ((v - min) / range) * (height - 8);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const areaPts = `0,${height} ${pts.join(' ')} ${width},${height}`;

    return (
      <svg width={width} height={height} className="overflow-visible shrink-0" aria-hidden="true">
        <polygon points={areaPts} fill="rgba(79, 70, 229, 0.08)" />
        <polyline
          fill="none"
          stroke="#4F46E5"
          strokeWidth={1.75}
          strokeLinecap="round"
          strokeLinejoin="round"
          points={pts.join(' ')}
        />
      </svg>
    );
  };

  return (
    <div className="flex flex-col justify-between rounded-xl border border-[#E2E8F0] bg-white p-4.5 transition-colors duration-150 hover:border-slate-300">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
            {title}
          </p>
          <div className="mt-1.5 font-display text-2xl font-bold tracking-tight text-slate-900 tabular-nums">
            {value}
          </div>
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-slate-600">
          {icon}
        </div>
      </div>

      <div className="mt-3.5 flex items-end justify-between gap-2">
        <div className="min-w-0 space-y-1">
          {delta !== undefined && delta !== null && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span
                className={`inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-semibold tabular-nums ${
                  delta > 0
                    ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200/70'
                    : delta < 0
                      ? 'bg-rose-50 text-rose-700 ring-1 ring-rose-200/70'
                      : 'bg-slate-100 text-slate-600'
                }`}
              >
                {delta > 0 ? (
                  <ArrowUpRight className="h-3 w-3" />
                ) : delta < 0 ? (
                  <ArrowDownRight className="h-3 w-3" />
                ) : (
                  <Minus className="h-3 w-3" />
                )}
                {delta > 0 ? `+${delta.toFixed(1)}%` : `${delta.toFixed(1)}%`}
              </span>
              {deltaLabel && (
                <span className="text-[11px] text-slate-500">{deltaLabel}</span>
              )}
            </div>
          )}
          <div className="text-xs leading-snug text-slate-500 tabular-nums">{subtitle}</div>
        </div>
        {renderSparkline()}
      </div>
    </div>
  );
};
