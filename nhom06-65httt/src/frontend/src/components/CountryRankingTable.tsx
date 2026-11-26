import React, { useMemo, useState } from 'react';
import { ArrowDownUp, ChevronRight, Download, Search, Table2 } from 'lucide-react';
import {
  CountrySummaryRow,
  formatTons,
  formatUsdMillions,
} from '../data/marketOverviewData';
import { CountryFlag } from './CountryFlag';

interface CountryRankingTableProps {
  rows: CountrySummaryRow[];
  onInspectCountry: (row: CountrySummaryRow) => void;
  onExportCsv: () => void;
}

type SortKey =
  | 'importValueUsdM'
  | 'yoyGrowthPct'
  | 'cagr2125Pct'
  | 'avgSearchIndex'
  | 'avgVnSharePct'
  | 'potentialScore';

export const CountryRankingTable: React.FC<CountryRankingTableProps> = ({
  rows,
  onInspectCountry,
  onExportCsv,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('importValueUsdM');
  const [sortAsc, setSortAsc] = useState(false);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc((prev) => !prev);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const filteredAndSorted = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const list = q
      ? rows.filter(
          (r) =>
            r.country.name.toLowerCase().includes(q) ||
            r.country.region.toLowerCase().includes(q) ||
            r.topCategory.shortName.toLowerCase().includes(q)
        )
      : rows;

    return [...list].sort((a, b) => {
      const diff = a[sortKey] - b[sortKey];
      return sortAsc ? diff : -diff;
    });
  }, [rows, searchQuery, sortKey, sortAsc]);

  const SortButton = ({ label, column }: { label: string; column: SortKey }) => {
    const active = sortKey === column;
    return (
      <button
        type="button"
        onClick={() => handleSort(column)}
        className={`inline-flex items-center gap-1 font-semibold transition ${
          active ? 'text-indigo-700' : 'text-slate-500 hover:text-slate-900'
        }`}
      >
        {label}
        <ArrowDownUp className={`h-3 w-3 ${active ? 'opacity-100' : 'opacity-40'}`} />
      </button>
    );
  };

  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-slate-600">
              <Table2 className="h-3.5 w-3.5" />
            </span>
            <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
              Bảng So sánh & Xếp hạng Chi tiết các Thị trường
            </h3>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Nhấn vào từng dòng quốc gia để mở hồ sơ thị trường, thị hiếu và ưu đãi thuế quan
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm quốc gia, khu vực..."
              className="w-48 rounded-lg border border-slate-200 bg-slate-50/70 py-1.5 pr-3 pl-8 text-xs text-slate-800 placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:outline-hidden"
            />
          </div>
          <button
            type="button"
            onClick={onExportCsv}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5 text-slate-500" />
            Xuất CSV
          </button>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[880px] border-collapse text-left text-xs">
          <thead>
            <tr className="border-y border-slate-200 bg-slate-50/80 text-[11px] tracking-wide text-slate-500 uppercase">
              <th className="px-3.5 py-2.5 font-semibold">#</th>
              <th className="px-3.5 py-2.5 font-semibold">Quốc gia</th>
              <th className="px-3.5 py-2.5 text-right">
                <SortButton label="Giá trị NK" column="importValueUsdM" />
              </th>
              <th className="px-3.5 py-2.5 text-right font-semibold">Khối lượng</th>
              <th className="px-3.5 py-2.5 text-right">
                <SortButton label="YoY (%)" column="yoyGrowthPct" />
              </th>
              <th className="px-3.5 py-2.5 text-right">
                <SortButton label="CAGR 21-25" column="cagr2125Pct" />
              </th>
              <th className="px-3.5 py-2.5 text-center">
                <SortButton label="Google Trends" column="avgSearchIndex" />
              </th>
              <th className="px-3.5 py-2.5 text-right">
                <SortButton label="Thị phần VN" column="avgVnSharePct" />
              </th>
              <th className="px-3.5 py-2.5 font-semibold">Nhóm SP nổi bật</th>
              <th className="px-3.5 py-2.5">
                <SortButton label="Điểm tiềm năng" column="potentialScore" />
              </th>
              <th className="px-3 py-2.5 text-right font-semibold">Chi tiết</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 tabular-nums">
            {filteredAndSorted.map((row, idx) => (
              <tr
                key={row.country.code}
                onClick={() => onInspectCountry(row)}
                className="group cursor-pointer transition-colors hover:bg-slate-50/90"
              >
                <td className="px-3.5 py-3 font-semibold text-slate-400">{idx + 1}</td>
                <td className="px-3.5 py-3">
                  <div className="flex items-center gap-2.5">
                    <CountryFlag code={row.country.code} size={20} />
                    <div>
                      <p className="font-semibold text-slate-900 group-hover:text-indigo-700">
                        {row.country.name}
                      </p>
                      <p className="text-[11px] text-slate-400">{row.country.region}</p>
                    </div>
                  </div>
                </td>
                <td className="px-3.5 py-3 text-right font-bold text-slate-900">
                  {formatUsdMillions(row.importValueUsdM)}
                  <span className="block text-[10px] font-normal text-slate-400">
                    {row.marketSharePct}% thị phần
                  </span>
                </td>
                <td className="px-3.5 py-3 text-right font-medium text-slate-600">
                  {formatTons(row.importVolumeTons)}
                </td>
                <td className="px-3.5 py-3 text-right">
                  <span
                    className={`inline-flex rounded-md px-1.5 py-0.5 font-semibold ${
                      row.yoyGrowthPct >= 0
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-rose-50 text-rose-700'
                    }`}
                  >
                    {row.yoyGrowthPct >= 0 ? `+${row.yoyGrowthPct}%` : `${row.yoyGrowthPct}%`}
                  </span>
                </td>
                <td className="px-3.5 py-3 text-right font-medium text-slate-700">
                  +{row.cagr2125Pct}%
                </td>
                <td className="px-3.5 py-3">
                  <div className="mx-auto flex w-20 items-center gap-1.5">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-indigo-500"
                        style={{ width: `${row.avgSearchIndex}%` }}
                      />
                    </div>
                    <span className="font-semibold text-slate-700">{row.avgSearchIndex}</span>
                  </div>
                </td>
                <td className="px-3.5 py-3 text-right font-semibold text-indigo-700">
                  {row.avgVnSharePct}%
                </td>
                <td className="px-3.5 py-3">
                  <span
                    className={`inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium ${row.topCategory.bgSoft} ${row.topCategory.textColor}`}
                  >
                    {row.topCategory.shortName}
                  </span>
                </td>
                <td className="px-3.5 py-3">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-indigo-600"
                        style={{ width: `${row.potentialScore}%` }}
                      />
                    </div>
                    <span className="font-bold text-slate-900">{row.potentialScore}</span>
                  </div>
                </td>
                <td className="px-3 py-3 text-right">
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 transition group-hover:bg-indigo-50 group-hover:text-indigo-700">
                    <ChevronRight className="h-4 w-4" />
                  </span>
                </td>
              </tr>
            ))}

            {filteredAndSorted.length === 0 && (
              <tr>
                <td colSpan={11} className="py-8 text-center text-slate-400">
                  Không tìm thấy thị trường phù hợp với từ khóa "{searchQuery}".
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
