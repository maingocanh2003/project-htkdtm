import React from 'react';

interface KilnScopeLogoProps {
  size?: number;
  showWordmark?: boolean;
  subtitle?: string;
}

/**
 * Custom geometric SVG brand mark for KilnScope:
 * Combines a minimalist ceramic vessel silhouette with a precision BI scope arc.
 */
export const KilnScopeLogo: React.FC<KilnScopeLogoProps> = ({
  size = 38,
  showWordmark = true,
  subtitle = 'Nhóm 06 • 65HTTT',
}) => {
  return (
    <div className="inline-flex items-center gap-3 select-none">
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
        aria-label="KilnScope Logo"
      >
        <defs>
          <linearGradient id="ksBgGrad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#1E293B" />
            <stop offset="100%" stopColor="#0F172A" />
          </linearGradient>
          <linearGradient id="ksAccentGrad" x1="10" y1="8" x2="30" y2="32" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#818CF8" />
            <stop offset="55%" stopColor="#6366F1" />
            <stop offset="100%" stopColor="#2DD4BF" />
          </linearGradient>
          <linearGradient id="ksRimGrad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#6366F1" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#2DD4BF" stopOpacity="0.25" />
          </linearGradient>
        </defs>

        {/* Outer squircle badge */}
        <rect x="1" y="1" width="38" height="38" rx="10" fill="url(#ksBgGrad)" />
        <rect
          x="1"
          y="1"
          width="38"
          height="38"
          rx="10"
          stroke="url(#ksRimGrad)"
          strokeWidth="1.25"
        />

        {/* Precision scope outer ring (broken arcs) */}
        <path
          d="M20 7.5C26.9 7.5 32.5 13.1 32.5 20"
          stroke="#2DD4BF"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeOpacity="0.85"
        />
        <path
          d="M20 32.5C13.1 32.5 7.5 26.9 7.5 20C7.5 15.8 9.6 12.1 12.8 9.8"
          stroke="#818CF8"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeOpacity="0.7"
        />

        {/* Minimalist ceramic vessel silhouette */}
        <path
          d="M16.5 12.5H23.5L22.2 15.2C24.8 16.8 26.2 19.6 25.6 22.8C25.1 25.5 23.4 27.6 21.8 28.8H18.2C16.6 27.6 14.9 25.5 14.4 22.8C13.8 19.6 15.2 16.8 17.8 15.2L16.5 12.5Z"
          fill="url(#ksAccentGrad)"
          fillOpacity="0.22"
          stroke="url(#ksAccentGrad)"
          strokeWidth="1.75"
          strokeLinejoin="round"
        />

        {/* Vessel collar & BI data pulse */}
        <path
          d="M16 12.5H24"
          stroke="#E0E7FF"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
        <path
          d="M17.2 22.5L19.1 20.5L20.6 21.8L22.8 19.2"
          stroke="#FFFFFF"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Scope target dot */}
        <circle cx="31.5" cy="12" r="1.8" fill="#2DD4BF" />
      </svg>

      {showWordmark && (
        <div className="leading-tight">
          <div className="font-display text-[15px] font-bold tracking-tight text-white">
            Kiln<span className="text-indigo-300">Scope</span>
          </div>
          {subtitle && (
            <p className="mt-0.5 text-[11px] font-medium text-slate-400">{subtitle}</p>
          )}
        </div>
      )}
    </div>
  );
};
