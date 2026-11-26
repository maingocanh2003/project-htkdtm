import React from 'react';
import { Database, GitBranch, Layers, Server, X } from 'lucide-react';

interface DataSchemaModalProps {
  open: boolean;
  onClose: () => void;
}

const STAR_TABLES = [
  {
    name: 'fact_trade_market',
    role: 'Fact Table',
    desc: 'Lưu trữ giá trị nhập khẩu (USD), khối lượng (tấn), đơn giá bình quân, chỉ số Google Trends và thị phần gốm sứ Việt Nam theo từng kỳ.',
    columns: ['time_key', 'country_key', 'category_key', 'import_value_usd', 'import_volume_tons', 'search_index', 'vn_share_pct'],
  },
  {
    name: 'dim_country',
    role: 'Dimension',
    desc: 'Thông tin quốc gia nhập khẩu, khu vực địa lý, hiệp định thuế quan (EVFTA, CPTPP, VJEPA) và thị hiếu đặc trưng.',
    columns: ['country_key', 'country_code', 'country_name', 'region', 'tariff_policy'],
  },
  {
    name: 'dim_time',
    role: 'Dimension',
    desc: 'Chiều thời gian chuẩn hóa theo Năm (2021–2025) và Quý (Q1–Q4) phục vụ tính toán YoY & CAGR.',
    columns: ['time_key', 'year', 'quarter', 'seasonality_weight'],
  },
  {
    name: 'dim_category',
    role: 'Dimension',
    desc: 'Phân nhóm sản phẩm gốm sứ theo mã HS quốc tế (6911, 6912, 6913, 6914).',
    columns: ['category_key', 'category_name', 'hs_code'],
  },
];

export const DataSchemaModal: React.FC<DataSchemaModalProps> = ({ open, onClose }) => {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 p-4 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-indigo-600">
              <Database className="h-4.5 w-4.5" />
            </div>
            <div>
              <h2 className="font-display text-base font-bold text-slate-900">
                Kiến trúc Dữ liệu Star Schema — KilnScope
              </h2>
              <p className="text-xs text-slate-500">
                Nguồn ETL: UN Comtrade • ITC Trade Map • Google Trends • PostgreSQL
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="Đóng Data Schema"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[75vh] space-y-4 overflow-y-auto p-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                <Server className="h-3.5 w-3.5 text-indigo-600" />
                Kho lưu trữ
              </div>
              <p className="mt-1 text-xs text-slate-500">PostgreSQL Star Schema chuẩn hóa 4 chiều phân tích.</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                <Layers className="h-3.5 w-3.5 text-indigo-600" />
                Độ chi tiết (Grain)
              </div>
              <p className="mt-1 text-xs text-slate-500 tabular-nums">8 quốc gia × 5 năm × 4 quý × 4 nhóm SP (640 bản ghi).</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                <GitBranch className="h-3.5 w-3.5 text-emerald-600" />
                Trạng thái ETL
              </div>
              <p className="mt-1 text-xs font-medium text-emerald-700">Đã làm sạch & đồng bộ chuẩn BI</p>
            </div>
          </div>

          <div className="space-y-2.5">
            {STAR_TABLES.map((tbl) => (
              <div
                key={tbl.name}
                className="rounded-xl border border-slate-200 bg-white p-3.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-bold text-slate-900">{tbl.name}</span>
                  <span
                    className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                      tbl.role === 'Fact Table'
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {tbl.role}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{tbl.desc}</p>
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {tbl.columns.map((col) => (
                    <span
                      key={col}
                      className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] text-slate-600"
                    >
                      {col}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
