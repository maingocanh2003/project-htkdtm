import React from 'react';

interface CountryFlagProps {
  code: string;
  size?: number;
  className?: string;
}

/**
 * Circular SVG country flag icons to ensure consistent, crisp rendering across all OSes
 * (avoiding Windows text fallback like "US", "KR").
 */
export const CountryFlag: React.FC<CountryFlagProps> = ({
  code,
  size = 18,
  className = '',
}) => {
  const renderFlagGraphic = () => {
    switch (code.toUpperCase()) {
      case 'US':
        return (
          <>
            <rect width="24" height="24" fill="#FFFFFF" />
            <rect y="0" width="24" height="2.4" fill="#DC2626" />
            <rect y="4.8" width="24" height="2.4" fill="#DC2626" />
            <rect y="9.6" width="24" height="2.4" fill="#DC2626" />
            <rect y="14.4" width="24" height="2.4" fill="#DC2626" />
            <rect y="19.2" width="24" height="2.4" fill="#DC2626" />
            <rect width="12" height="12" fill="#1E3A8A" />
            <circle cx="3.5" cy="3.5" r="0.9" fill="#FFFFFF" />
            <circle cx="6.5" cy="3.5" r="0.9" fill="#FFFFFF" />
            <circle cx="9.5" cy="3.5" r="0.9" fill="#FFFFFF" />
            <circle cx="5" cy="6.2" r="0.9" fill="#FFFFFF" />
            <circle cx="8" cy="6.2" r="0.9" fill="#FFFFFF" />
            <circle cx="3.5" cy="8.9" r="0.9" fill="#FFFFFF" />
            <circle cx="6.5" cy="8.9" r="0.9" fill="#FFFFFF" />
            <circle cx="9.5" cy="8.9" r="0.9" fill="#FFFFFF" />
          </>
        );
      case 'JP':
        return (
          <>
            <rect width="24" height="24" fill="#FFFFFF" />
            <circle cx="12" cy="12" r="5.5" fill="#DC2626" />
          </>
        );
      case 'DE':
        return (
          <>
            <rect y="0" width="24" height="8" fill="#111827" />
            <rect y="8" width="24" height="8" fill="#DC2626" />
            <rect y="16" width="24" height="8" fill="#FACC15" />
          </>
        );
      case 'FR':
        return (
          <>
            <rect x="0" width="8" height="24" fill="#1D4ED8" />
            <rect x="8" width="8" height="24" fill="#FFFFFF" />
            <rect x="16" width="8" height="24" fill="#DC2626" />
          </>
        );
      case 'GB':
        return (
          <>
            <rect width="24" height="24" fill="#1E3A8A" />
            <path d="M0,0 L24,24 M24,0 L0,24" stroke="#FFFFFF" strokeWidth="4" />
            <path d="M0,0 L24,24 M24,0 L0,24" stroke="#DC2626" strokeWidth="1.8" />
            <rect x="9.5" width="5" height="24" fill="#FFFFFF" />
            <rect y="9.5" width="24" height="5" fill="#FFFFFF" />
            <rect x="10.5" width="3" height="24" fill="#DC2626" />
            <rect y="10.5" width="24" height="3" fill="#DC2626" />
          </>
        );
      case 'KR':
        return (
          <>
            <rect width="24" height="24" fill="#FFFFFF" />
            <path d="M12,6.5 A5.5,5.5 0 0,1 12,17.5 A2.75,2.75 0 0,1 12,12 A2.75,2.75 0 0,0 12,6.5 Z" fill="#DC2626" />
            <path d="M12,17.5 A5.5,5.5 0 0,1 12,6.5 A2.75,2.75 0 0,1 12,12 A2.75,2.75 0 0,0 12,17.5 Z" fill="#1D4ED8" />
            <circle cx="12" cy="9.25" r="2.75" fill="#DC2626" />
            <circle cx="12" cy="14.75" r="2.75" fill="#1D4ED8" />
            <line x1="4" y1="6" x2="7" y2="3" stroke="#111827" strokeWidth="1.3" />
            <line x1="17" y1="3" x2="20" y2="6" stroke="#111827" strokeWidth="1.3" />
            <line x1="4" y1="18" x2="7" y2="21" stroke="#111827" strokeWidth="1.3" />
            <line x1="17" y1="21" x2="20" y2="18" stroke="#111827" strokeWidth="1.3" />
          </>
        );
      case 'AU':
        return (
          <>
            <rect width="24" height="24" fill="#1E3A8A" />
            <rect x="0" y="0" width="12" height="12" fill="#1E3A8A" />
            <rect x="4.5" y="0" width="3" height="12" fill="#FFFFFF" />
            <rect x="0" y="4.5" width="12" height="3" fill="#FFFFFF" />
            <rect x="5.2" y="0" width="1.6" height="12" fill="#DC2626" />
            <rect x="0" y="5.2" width="12" height="1.6" fill="#DC2626" />
            <circle cx="18" cy="7" r="1.3" fill="#FFFFFF" />
            <circle cx="19.5" cy="13" r="1.1" fill="#FFFFFF" />
            <circle cx="15" cy="16.5" r="1.3" fill="#FFFFFF" />
            <circle cx="6.5" cy="17.5" r="1.8" fill="#FFFFFF" />
          </>
        );
      case 'CA':
        return (
          <>
            <rect x="0" width="6" height="24" fill="#DC2626" />
            <rect x="6" width="12" height="24" fill="#FFFFFF" />
            <rect x="18" width="6" height="24" fill="#DC2626" />
            <path
              d="M12,6 L13.2,9.4 L16.2,8.8 L14.5,11.6 L16.4,13 L13,13.6 L12.5,17 L11.5,17 L11,13.6 L7.6,13 L9.5,11.6 L7.8,8.8 L10.8,9.4 Z"
              fill="#DC2626"
            />
          </>
        );
      case 'VN':
        return (
          <>
            <rect width="24" height="24" fill="#DC2626" />
            <polygon
              points="12,5.5 13.7,10.2 18.7,10.3 14.7,13.3 16.1,18.1 12,15.2 7.9,18.1 9.3,13.3 5.3,10.3 10.3,10.2"
              fill="#FACC15"
            />
          </>
        );
      default:
        return <rect width="24" height="24" fill="#94A3B8" />;
    }
  };

  const clipId = `flag-clip-${code.toLowerCase()}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={`inline-block shrink-0 rounded-full ring-1 ring-slate-200/90 ${className}`}
      aria-hidden="true"
    >
      <defs>
        <clipPath id={clipId}>
          <circle cx="12" cy="12" r="12" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`}>{renderFlagGraphic()}</g>
    </svg>
  );
};
