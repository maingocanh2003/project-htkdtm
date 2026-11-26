import React, { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, Globe2 } from 'lucide-react';
import { CountryMeta } from '../data/marketOverviewData';
import { CountryFlag } from './CountryFlag';

interface CountryMultiSelectProps {
  countries: CountryMeta[];
  selectedCodes: string[];
  onToggleCountry: (code: string) => void;
  onClearAll: () => void;
}

export const CountryMultiSelect: React.FC<CountryMultiSelectProps> = ({
  countries,
  selectedCodes,
  onToggleCountry,
  onClearAll,
}) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedList = countries.filter((c) => selectedCodes.includes(c.code));

  const getSummaryLabel = () => {
    if (selectedList.length === 0) {
      return `Tất cả (${countries.length})`;
    }
    if (selectedList.length <= 2) {
      return selectedList.map((c) => c.name).join(', ');
    }
    return `${selectedList[0].name}, ${selectedList[1].name} (+${selectedList.length - 2})`;
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`inline-flex h-8.5 items-center gap-2 rounded-lg border px-2.5 text-xs transition ${
          selectedCodes.length > 0
            ? 'border-indigo-300 bg-indigo-50/70 text-indigo-800'
            : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
        }`}
      >
        <Globe2 className="h-3.5 w-3.5 text-slate-400" />
        <span className="text-slate-500 font-medium">Quốc gia:</span>
        <span className="font-semibold text-slate-900">{getSummaryLabel()}</span>
        <ChevronDown
          className={`h-3.5 w-3.5 text-slate-400 transition-transform ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {open && (
        <div className="absolute right-0 z-40 mt-1.5 w-64 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg shadow-slate-900/8">
          <div className="flex items-center justify-between border-b border-slate-100 px-2.5 py-1.5">
            <span className="text-[11px] font-semibold text-slate-500">
              Chọn thị trường ({selectedCodes.length || countries.length}/{countries.length})
            </span>
            {selectedCodes.length > 0 && (
              <button
                type="button"
                onClick={onClearAll}
                className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-700"
              >
                Chọn tất cả
              </button>
            )}
          </div>

          <div className="mt-1 max-h-60 space-y-0.5 overflow-y-auto">
            {countries.map((c) => {
              const checked = selectedCodes.includes(c.code);
              return (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => onToggleCountry(c.code)}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs transition ${
                    checked
                      ? 'bg-indigo-50/80 text-indigo-900'
                      : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <CountryFlag code={c.code} size={16} />
                    <span className="font-medium">{c.name}</span>
                    <span className="text-[10px] text-slate-400">{c.region}</span>
                  </span>
                  <span
                    className={`flex h-4 w-4 items-center justify-center rounded border ${
                      checked
                        ? 'border-indigo-600 bg-indigo-600 text-white'
                        : 'border-slate-300 bg-white'
                    }`}
                  >
                    {checked && <Check className="h-3 w-3" />}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
