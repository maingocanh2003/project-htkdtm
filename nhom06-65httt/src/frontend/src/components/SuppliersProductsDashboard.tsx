import React, { useMemo, useState } from 'react';
import {
  Building2,
  Clock,
  DollarSign,
  Edit3,
  Filter,
  Package,
  Plus,
  Search,
  ShoppingCart,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import {
  COUNTRIES,
  PRODUCT_CATEGORIES,
  ProductCategoryId,
} from '../data/marketOverviewData';
import { DomesticSupplier, SupplierProduct } from '../data/suppliersData';
import { KpiCard } from './KpiCard';
import { CountryFlag } from './CountryFlag';

interface SuppliersProductsDashboardProps {
  suppliers: DomesticSupplier[];
  products: SupplierProduct[];
  onAddProduct: (product: SupplierProduct) => void;
  onUpdateProduct: (product: SupplierProduct) => void;
  onDeleteProduct: (id: string) => void;
  onGoToDecision: (targetCountryCode: string) => void;
}

export const SuppliersProductsDashboard: React.FC<SuppliersProductsDashboardProps> = ({
  suppliers,
  products,
  onAddProduct,
  onUpdateProduct,
  onDeleteProduct,
  onGoToDecision,
}) => {
  const [targetCountry, setTargetCountry] = useState<string>('US');
  const [selectedCategory, setSelectedCategory] = useState<ProductCategoryId>('all');
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Modal state for Add / Edit Product
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<SupplierProduct | null>(null);
  const [formState, setFormState] = useState({
    sku: '',
    name: '',
    categoryId: 'decor' as Exclude<ProductCategoryId, 'all'>,
    supplierId: suppliers[0]?.id ?? '',
    color: 'Trắng ngà / Men mờ',
    shape: 'Tròn cổ điển',
    material: 'Stoneware',
    style: 'Tối giản',
    importCostUsd: 8.5,
    exportRefPriceUsd: 19.5,
    moqUnits: 400,
    leadTimeDays: 18,
    maxOrderUnitsMonth: 8000,
    targetFitScore: 90,
    notes: '',
  });

  const filteredProducts = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return products
      .filter((p) => {
        const catOk = selectedCategory === 'all' || p.categoryId === selectedCategory;
        const supOk = selectedSupplierId === 'all' || p.supplierId === selectedSupplierId;
        const sup = suppliers.find((s) => s.id === p.supplierId);
        const searchOk =
          !q ||
          p.name.toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q) ||
          (sup?.name.toLowerCase().includes(q) ?? false);
        return catOk && supOk && searchOk;
      })
      .sort(
        (a, b) =>
          (b.marketFitByCountry[targetCountry] ?? 0) -
          (a.marketFitByCountry[targetCountry] ?? 0)
      );
  }, [products, suppliers, selectedCategory, selectedSupplierId, searchQuery, targetCountry]);

  const kpis = useMemo(() => {
    const count = filteredProducts.length;
    const avgCost =
      count > 0
        ? filteredProducts.reduce((s, p) => s + p.importCostUsd, 0) / count
        : 0;
    const avgMarginPct =
      count > 0
        ? filteredProducts.reduce(
            (s, p) =>
              s + ((p.exportRefPriceUsd - p.importCostUsd) / p.exportRefPriceUsd) * 100,
            0
          ) / count
        : 0;
    const totalCapacity = filteredProducts.reduce((s, p) => s + p.maxOrderUnitsMonth, 0);
    const avgFit =
      count > 0
        ? Math.round(
            filteredProducts.reduce(
              (s, p) => s + (p.marketFitByCountry[targetCountry] ?? 75),
              0
            ) / count
          )
        : 0;

    return {
      count,
      supplierCount: new Set(filteredProducts.map((p) => p.supplierId)).size,
      avgCost: avgCost.toFixed(2),
      avgMarginPct: avgMarginPct.toFixed(1),
      totalCapacity,
      avgFit,
    };
  }, [filteredProducts, targetCountry]);

  const targetCountryMeta = COUNTRIES.find((c) => c.code === targetCountry);
  const topProduct = filteredProducts[0];
  const topProductSupplier = topProduct
    ? suppliers.find((s) => s.id === topProduct.supplierId)
    : null;

  const openAddModal = () => {
    setEditingProduct(null);
    setFormState({
      sku: `KS-NEW-${String(products.length + 1).padStart(2, '0')}`,
      name: '',
      categoryId: 'decor',
      supplierId: suppliers[0]?.id ?? '',
      color: 'Trắng ngà / Men mờ',
      shape: 'Tròn cổ điển',
      material: 'Stoneware',
      style: 'Tối giản',
      importCostUsd: 8.5,
      exportRefPriceUsd: 19.5,
      moqUnits: 400,
      leadTimeDays: 18,
      maxOrderUnitsMonth: 8000,
      targetFitScore: 90,
      notes: '',
    });
    setModalOpen(true);
  };

  const openEditModal = (product: SupplierProduct) => {
    setEditingProduct(product);
    setFormState({
      sku: product.sku,
      name: product.name,
      categoryId: product.categoryId,
      supplierId: product.supplierId,
      color: product.color,
      shape: product.shape,
      material: product.material,
      style: product.style,
      importCostUsd: product.importCostUsd,
      exportRefPriceUsd: product.exportRefPriceUsd,
      moqUnits: product.moqUnits,
      leadTimeDays: product.leadTimeDays,
      maxOrderUnitsMonth: product.maxOrderUnitsMonth,
      targetFitScore: product.marketFitByCountry[targetCountry] ?? 82,
      notes: product.notes,
    });
    setModalOpen(true);
  };

  const handleSaveProduct = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formState.name.trim()) return;

    const fitMap: Record<string, number> = editingProduct
      ? { ...editingProduct.marketFitByCountry, [targetCountry]: formState.targetFitScore }
      : {
          US: 84,
          JP: 82,
          DE: 83,
          FR: 81,
          GB: 80,
          KR: 85,
          AU: 82,
          CA: 81,
          [targetCountry]: formState.targetFitScore,
        };

    const payload: SupplierProduct = {
      id: editingProduct?.id ?? `sp-${Date.now()}`,
      sku: formState.sku.trim() || `KS-${Date.now()}`,
      name: formState.name.trim(),
      categoryId: formState.categoryId,
      supplierId: formState.supplierId,
      color: formState.color,
      colorSwatch: editingProduct?.colorSwatch ?? '#E2E8F0',
      shape: formState.shape,
      material: formState.material,
      style: formState.style,
      importCostUsd: Number(formState.importCostUsd),
      exportRefPriceUsd: Number(formState.exportRefPriceUsd),
      moqUnits: Number(formState.moqUnits),
      leadTimeDays: Number(formState.leadTimeDays),
      maxOrderUnitsMonth: Number(formState.maxOrderUnitsMonth),
      marketFitByCountry: fitMap,
      notes: formState.notes || 'Đã kiểm định chất lượng xuất khẩu.',
    };

    if (editingProduct) {
      onUpdateProduct(payload);
    } else {
      onAddProduct(payload);
    }
    setModalOpen(false);
  };

  const maxSupCapacity = Math.max(...suppliers.map((s) => s.monthlyCapacityUnits), 1);

  return (
    <div className="space-y-4">
      {/* Compact Single-Row Filter + Action Bar */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 pr-1 text-xs font-semibold text-slate-600">
              <Filter className="h-3.5 w-3.5 text-indigo-600" />
              Đối chiếu nguồn cung:
            </span>

            {/* Target Country */}
            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
              <CountryFlag code={targetCountry} size={14} />
              <span className="font-medium text-slate-500">Thị trường:</span>
              <select
                value={targetCountry}
                onChange={(e) => setTargetCountry(e.target.value)}
                className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Category */}
            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
              <span className="font-medium text-slate-500">Nhóm SP:</span>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value as ProductCategoryId)}
                className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                <option value="all">Tất cả nhóm SP</option>
                {PRODUCT_CATEGORIES.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.shortName}
                  </option>
                ))}
              </select>
            </div>

            {/* Supplier */}
            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
              <Building2 className="h-3.5 w-3.5 text-slate-400" />
              <select
                value={selectedSupplierId}
                onChange={(e) => setSelectedSupplierId(e.target.value)}
                className="max-w-44 truncate bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                <option value="all">Tất cả nhà cung cấp ({suppliers.length})</option>
                {suppliers.map((sup) => (
                  <option key={sup.id} value={sup.id}>
                    {sup.village} ({sup.province})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="button"
            onClick={openAddModal}
            className="inline-flex h-8.5 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 text-xs font-semibold text-white transition hover:bg-indigo-700"
          >
            <Plus className="h-3.5 w-3.5" />
            Thêm sản phẩm
          </button>
        </div>
      </section>

      {/* Row 1: 4 KPI Cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Danh mục sản phẩm đạt chuẩn"
          value={`${kpis.count} mẫu`}
          subtitle={`Thuộc ${kpis.supplierCount} cơ sở sản xuất trong nước`}
          icon={<Package className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Giá nhập TB & Biên lợi nhuận"
          value={`$${kpis.avgCost} / SP`}
          subtitle={`Biên lợi nhuận gộp dự kiến: ${kpis.avgMarginPct}%`}
          icon={<DollarSign className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Tổng năng lực cung ứng / tháng"
          value={`${kpis.totalCapacity.toLocaleString('en-US')} SP`}
          subtitle="Sẵn sàng đáp ứng đơn hàng xuất khẩu"
          icon={<Building2 className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Mức độ phù hợp thị trường"
          value={`${kpis.avgFit} / 100`}
          subtitle={
            <span className="inline-flex items-center gap-1.5">
              <CountryFlag code={targetCountry} size={14} />
              <span>Đối chiếu thị hiếu tại {targetCountryMeta?.name}</span>
            </span>
          }
          icon={<Sparkles className="h-4.5 w-4.5" />}
        />
      </section>

      {/* Key Insight Bar */}
      {topProduct && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E2E8F0] bg-white px-4 py-3">
          <div className="flex items-start gap-2.5 text-xs leading-relaxed text-slate-600 sm:items-center">
            <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-indigo-200/80 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
              <Sparkles className="h-3 w-3" />
              Key Insight
            </span>
            <p className="tabular-nums">
              Tại thị trường{' '}
              <strong className="inline-flex items-center gap-1 text-slate-900">
                <CountryFlag code={targetCountry} size={13} />
                {targetCountryMeta?.name}
              </strong>
              , mẫu <strong className="text-slate-900">{topProduct.name}</strong> từ{' '}
              <strong className="text-indigo-700">{topProductSupplier?.village}</strong> đạt điểm phù hợp cao nhất (
              <strong>{topProduct.marketFitByCountry[targetCountry] ?? 0}/100</strong>) với giá nhập{' '}
              <strong>${topProduct.importCostUsd.toFixed(2)}/SP</strong>.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onGoToDecision(targetCountry)}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100"
          >
            <ShoppingCart className="h-3.5 w-3.5" />
            Lập đề xuất đặt hàng
          </button>
        </section>
      )}

      {/* Row 2: Supplier Capacity & Lead Time Cards */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
              Năng lực Cung ứng & Độ tin cậy Nhà sản xuất Việt Nam
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              So sánh công suất tháng, thời gian giao hàng (Lead Time) và chứng nhận xuất khẩu
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          {suppliers.map((sup) => {
            const capPct = Math.round((sup.monthlyCapacityUnits / maxSupCapacity) * 100);
            const active = selectedSupplierId === sup.id;
            return (
              <button
                key={sup.id}
                type="button"
                onClick={() =>
                  setSelectedSupplierId(active ? 'all' : sup.id)
                }
                className={`flex flex-col justify-between rounded-xl border p-3.5 text-left transition ${
                  active
                    ? 'border-indigo-400 bg-indigo-50/40'
                    : 'border-[#E2E8F0] bg-slate-50/40 hover:border-slate-300'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[11px] font-semibold text-indigo-700">
                      {sup.province}
                    </span>
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 tabular-nums">
                      Uy tín {sup.reliabilityScore}%
                    </span>
                  </div>
                  <p className="mt-1 text-xs font-bold text-slate-900">{sup.name}</p>
                  <p className="mt-1 text-[11px] leading-snug text-slate-500">{sup.contactNote}</p>
                </div>

                <div className="mt-3 space-y-2 border-t border-slate-200/70 pt-2.5 tabular-nums">
                  <div>
                    <div className="mb-1 flex justify-between text-[11px]">
                      <span className="text-slate-500">Công suất/tháng</span>
                      <span className="font-bold text-slate-900">
                        {sup.monthlyCapacityUnits.toLocaleString('en-US')}
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200/80">
                      <div
                        className="h-full rounded-full bg-indigo-600"
                        style={{ width: `${capPct}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-600">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3 text-slate-400" />
                      {sup.leadTimeDays} ngày
                    </span>
                    <span className="truncate font-medium text-slate-500">
                      {sup.certifications[0]}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Row 3: Product & Supplier Management Table */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
              Quản lý Danh mục Sản phẩm & Giá nhập Nhà cung cấp ({filteredProducts.length})
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              Thêm, chỉnh sửa thông số sản phẩm hoặc đối chiếu mức độ phù hợp với thị trường {targetCountryMeta?.name}
            </p>
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm tên SP, mã SKU, NCC..."
              className="w-56 rounded-lg border border-slate-200 bg-slate-50/70 py-1.5 pr-3 pl-8 text-xs text-slate-800 placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:outline-hidden"
            />
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[960px] border-collapse text-left text-xs tabular-nums">
            <thead>
              <tr className="border-y border-slate-200 bg-slate-50/80 text-[11px] font-semibold text-slate-500 uppercase">
                <th className="px-3 py-2.5">Mã & Sản phẩm</th>
                <th className="px-3 py-2.5">Nhà cung cấp</th>
                <th className="px-3 py-2.5">Thuộc tính</th>
                <th className="px-3 py-2.5 text-right">Giá nhập</th>
                <th className="px-3 py-2.5 text-right">Giá xuất TK</th>
                <th className="px-3 py-2.5 text-right">Biên LN</th>
                <th className="px-3 py-2.5 text-right">Công suất / MOQ</th>
                <th className="px-3 py-2.5 text-right">Lead time</th>
                <th className="px-3 py-2.5">Phù hợp ({targetCountryMeta?.name})</th>
                <th className="px-3 py-2.5 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredProducts.map((p) => {
                const sup = suppliers.find((s) => s.id === p.supplierId);
                const marginPct =
                  ((p.exportRefPriceUsd - p.importCostUsd) / p.exportRefPriceUsd) * 100;
                const fit = p.marketFitByCountry[targetCountry] ?? 78;

                return (
                  <tr key={p.id} className="hover:bg-slate-50/80">
                    <td className="px-3 py-3">
                      <span className="font-mono text-[10px] font-semibold text-slate-400">
                        {p.sku}
                      </span>
                      <p className="font-semibold text-slate-900">{p.name}</p>
                    </td>
                    <td className="px-3 py-3">
                      <p className="font-medium text-slate-800">{sup?.village}</p>
                      <p className="text-[11px] text-slate-400">{sup?.province}</p>
                    </td>
                    <td className="px-3 py-3 text-slate-600">
                      <p>{p.material} • {p.style}</p>
                      <p className="text-[11px] text-slate-400">{p.color}</p>
                    </td>
                    <td className="px-3 py-3 text-right font-bold text-slate-900">
                      ${p.importCostUsd.toFixed(2)}
                    </td>
                    <td className="px-3 py-3 text-right text-slate-600">
                      ${p.exportRefPriceUsd.toFixed(2)}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span className="rounded bg-emerald-50 px-1.5 py-0.5 font-semibold text-emerald-700">
                        +{marginPct.toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right text-slate-700">
                      <span className="font-semibold">
                        {p.maxOrderUnitsMonth.toLocaleString('en-US')}
                      </span>
                      <span className="block text-[10px] text-slate-400">
                        MOQ: {p.moqUnits}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right text-slate-600">
                      {p.leadTimeDays} ngày
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-14 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${
                              fit >= 90 ? 'bg-indigo-600' : fit >= 80 ? 'bg-teal-600' : 'bg-slate-400'
                            }`}
                            style={{ width: `${fit}%` }}
                          />
                        </div>
                        <span className="font-bold text-slate-900">{fit}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="inline-flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => openEditModal(p)}
                          className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-indigo-700"
                          title="Chỉnh sửa sản phẩm"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => onDeleteProduct(p.id)}
                          className="rounded-md p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
                          title="Xóa sản phẩm"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Add / Edit Product Modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 p-4 backdrop-blur-[2px]"
          onClick={() => setModalOpen(false)}
        >
          <form
            onSubmit={handleSaveProduct}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-xl"
          >
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <h3 className="font-display text-sm font-bold text-slate-900">
                {editingProduct ? 'Cập nhật Thông tin Sản phẩm' : 'Thêm Sản phẩm Gốm sứ Mới'}
              </h3>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 p-5 text-xs">
              <div>
                <label className="mb-1 block font-semibold text-slate-600">Mã SKU</label>
                <input
                  type="text"
                  required
                  value={formState.sku}
                  onChange={(e) => setFormState({ ...formState, sku: e.target.value })}
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 focus:border-indigo-400 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-slate-600">Nhóm sản phẩm</label>
                <select
                  value={formState.categoryId}
                  onChange={(e) =>
                    setFormState({
                      ...formState,
                      categoryId: e.target.value as Exclude<ProductCategoryId, 'all'>,
                    })
                  }
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 focus:border-indigo-400 focus:outline-hidden"
                >
                  {PRODUCT_CATEGORIES.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.shortName}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="mb-1 block font-semibold text-slate-600">Tên sản phẩm</label>
                <input
                  type="text"
                  required
                  placeholder="Ví dụ: Bình hoa men ngọc dáng giọt nước"
                  value={formState.name}
                  onChange={(e) => setFormState({ ...formState, name: e.target.value })}
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 focus:border-indigo-400 focus:outline-hidden"
                />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block font-semibold text-slate-600">Nhà cung cấp</label>
                <select
                  value={formState.supplierId}
                  onChange={(e) => setFormState({ ...formState, supplierId: e.target.value })}
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 focus:border-indigo-400 focus:outline-hidden"
                >
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.province})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block font-semibold text-slate-600">Chất liệu</label>
                <input
                  type="text"
                  value={formState.material}
                  onChange={(e) => setFormState({ ...formState, material: e.target.value })}
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 focus:border-indigo-400 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-slate-600">Phong cách</label>
                <input
                  type="text"
                  value={formState.style}
                  onChange={(e) => setFormState({ ...formState, style: e.target.value })}
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 focus:border-indigo-400 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-slate-600">Giá nhập (USD)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0.5"
                  required
                  value={formState.importCostUsd}
                  onChange={(e) =>
                    setFormState({ ...formState, importCostUsd: Number(e.target.value) })
                  }
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 tabular-nums focus:border-indigo-400 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-slate-600">
                  Giá xuất tham khảo (USD)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="1"
                  required
                  value={formState.exportRefPriceUsd}
                  onChange={(e) =>
                    setFormState({ ...formState, exportRefPriceUsd: Number(e.target.value) })
                  }
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 tabular-nums focus:border-indigo-400 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-slate-600">
                  Công suất/tháng (SP)
                </label>
                <input
                  type="number"
                  min="100"
                  required
                  value={formState.maxOrderUnitsMonth}
                  onChange={(e) =>
                    setFormState({ ...formState, maxOrderUnitsMonth: Number(e.target.value) })
                  }
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 tabular-nums focus:border-indigo-400 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="mb-1 block font-semibold text-slate-600">
                  Phù hợp {targetCountryMeta?.name} (%)
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  required
                  value={formState.targetFitScore}
                  onChange={(e) =>
                    setFormState({ ...formState, targetFitScore: Number(e.target.value) })
                  }
                  className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 tabular-nums focus:border-indigo-400 focus:outline-hidden"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              >
                Hủy
              </button>
              <button
                type="submit"
                className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
              >
                {editingProduct ? 'Lưu thay đổi' : 'Thêm sản phẩm'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
