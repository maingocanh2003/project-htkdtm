import React, { useMemo, useState } from 'react';
import {
  DollarSign,
  Filter,
  Layers,
  Palette,
  RotateCcw,
  Shapes,
  ShoppingBag,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import {
  COUNTRIES,
  PRODUCT_CATEGORIES,
  ProductCategoryId,
} from '../data/marketOverviewData';
import {
  CeramicPlatform,
  TASTE_PROFILES,
  TRENDING_TASTE_COMBOS,
} from '../data/tasteData';
import { KpiCard } from './KpiCard';
import { CountryFlag } from './CountryFlag';

export const TasteDashboard: React.FC = () => {
  const [selectedCountry, setSelectedCountry] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<ProductCategoryId>('all');
  const [selectedPlatform, setSelectedPlatform] = useState<CeramicPlatform>('all');
  const [matrixAttr, setMatrixAttr] = useState<'styles' | 'colors' | 'materials'>('styles');

  const hasCustomFilter =
    selectedCountry !== 'all' || selectedCategory !== 'all' || selectedPlatform !== 'all';

  const resetFilters = () => {
    setSelectedCountry('all');
    setSelectedCategory('all');
    setSelectedPlatform('all');
  };

  const activeProfiles = useMemo(() => {
    const base =
      selectedCountry === 'all'
        ? TASTE_PROFILES
        : TASTE_PROFILES.filter((p) => p.countryCode === selectedCountry);
    return base;
  }, [selectedCountry]);

  // Platform weighting multiplier (slight shift when filtering Etsy vs Amazon)
  const platformTilt = (name: string): number => {
    if (selectedPlatform === 'Etsy') {
      if (name.includes('Thủ công') || name.includes('nghệ thuật') || name.includes('Màu tự nhiên')) {
        return 1.16;
      }
      return 0.94;
    }
    if (selectedPlatform === 'Amazon') {
      if (name.includes('Tối giản') || name.includes('Sứ') || name.includes('Stoneware') || name.includes('Tròn')) {
        return 1.12;
      }
      return 0.95;
    }
    return 1;
  };

  const aggregated = useMemo(() => {
    const aggregateList = (
      getter: (p: (typeof TASTE_PROFILES)[number]) => {
        name: string;
        sharePct: number;
        growthPct: number;
        swatch?: string;
      }[]
    ) => {
      const map = new Map<
        string,
        { name: string; totalShare: number; totalGrowth: number; count: number; swatch?: string }
      >();

      for (const profile of activeProfiles) {
        for (const item of getter(profile)) {
          const tiltedShare = item.sharePct * platformTilt(item.name);
          const existing = map.get(item.name);
          if (existing) {
            existing.totalShare += tiltedShare;
            existing.totalGrowth += item.growthPct;
            existing.count += 1;
          } else {
            map.set(item.name, {
              name: item.name,
              totalShare: tiltedShare,
              totalGrowth: item.growthPct,
              count: 1,
              swatch: item.swatch,
            });
          }
        }
      }

      const raw = Array.from(map.values()).map((v) => ({
        name: v.name,
        rawShare: v.totalShare / v.count,
        growthPct: Number((v.totalGrowth / v.count).toFixed(1)),
        swatch: v.swatch,
      }));
      const sum = raw.reduce((s, r) => s + r.rawShare, 0) || 1;
      return raw
        .map((r) => ({
          name: r.name,
          sharePct: Number(((r.rawShare / sum) * 100).toFixed(1)),
          growthPct: r.growthPct,
          swatch: r.swatch,
        }))
        .sort((a, b) => b.sharePct - a.sharePct);
    };

    const colors = aggregateList((p) => p.colors);
    const styles = aggregateList((p) => p.styles);
    const shapes = aggregateList((p) => p.shapes);
    const materials = aggregateList((p) => p.materials);
    const productTypes = aggregateList((p) => p.topProductTypes);
    const priceRanges = aggregateList((p) =>
      p.priceRanges.map((pr) => ({ name: pr.label, sharePct: pr.sharePct, growthPct: 0 }))
    );

    const avgPrice =
      activeProfiles.reduce((s, p) => s + p.avgPriceUsd, 0) /
      Math.max(activeProfiles.length, 1);

    const avgEtsyShare =
      activeProfiles.reduce((s, p) => s + p.platformBias.Etsy, 0) /
      Math.max(activeProfiles.length, 1);

    return {
      colors,
      styles,
      shapes,
      materials,
      productTypes,
      priceRanges,
      avgPrice: Number(avgPrice.toFixed(1)),
      avgEtsyShare: Math.round(avgEtsyShare),
    };
  }, [activeProfiles, selectedPlatform]);

  const filteredCombos = useMemo(() => {
    return TRENDING_TASTE_COMBOS.filter((item) => {
      const countryOk = selectedCountry === 'all' || item.countryCode === selectedCountry;
      const catOk = selectedCategory === 'all' || item.categoryId === selectedCategory;
      return countryOk && catOk;
    }).sort((a, b) => b.demandGrowthPct - a.demandGrowthPct);
  }, [selectedCountry, selectedCategory]);

  const topColor = aggregated.colors[0];
  const topStyle = aggregated.styles[0];
  const topMaterial = aggregated.materials[0];
  const topShape = aggregated.shapes[0];
  const topProductType = aggregated.productTypes[0];

  const activeCountryMeta =
    selectedCountry !== 'all' ? COUNTRIES.find((c) => c.code === selectedCountry) : null;
  const activeCountryProfile =
    selectedCountry !== 'all' ? TASTE_PROFILES.find((p) => p.countryCode === selectedCountry) : null;

  // Matrix columns for heatmap
  const matrixColumns = useMemo(() => {
    if (matrixAttr === 'styles') {
      return TASTE_PROFILES[0].styles.map((s) => s.name);
    }
    if (matrixAttr === 'colors') {
      return ['Trắng ngà / Kem', 'Màu tự nhiên / Men tro', 'Xanh Cobalt / Biển', 'Nâu đất / Terracotta', 'Màu đa sắc / Họa tiết'];
    }
    return ['Stoneware', 'Sứ (Porcelain)', 'Gốm thủ công'];
  }, [matrixAttr]);

  const getMatrixScore = (countryCode: string, colName: string) => {
    const profile = TASTE_PROFILES.find((p) => p.countryCode === countryCode);
    if (!profile) return 0;
    const list =
      matrixAttr === 'styles'
        ? profile.styles
        : matrixAttr === 'colors'
          ? profile.colors
          : profile.materials;

    // Flexible prefix match for standardized column names across countries
    const keyword = colName.split('/')[0].split('(')[0].trim().toLowerCase();
    const match = list.find((item) => item.name.toLowerCase().includes(keyword.slice(0, 6)));
    return match ? match.sharePct : 12;
  };

  return (
    <div className="space-y-4">
      {/* Compact Single-Row Filter Bar */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 pr-1 text-xs font-semibold text-slate-600">
              <Filter className="h-3.5 w-3.5 text-indigo-600" />
              Bộ lọc thị hiếu:
            </span>

            {/* Country Select */}
            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
              {selectedCountry !== 'all' && (
                <CountryFlag code={selectedCountry} size={14} />
              )}
              <span className="font-medium text-slate-500">Thị trường:</span>
              <select
                value={selectedCountry}
                onChange={(e) => setSelectedCountry(e.target.value)}
                className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                <option value="all">Tất cả 8 quốc gia</option>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name} ({c.region})
                  </option>
                ))}
              </select>
            </div>

            {/* Category Select */}
            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
              <Layers className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-medium text-slate-500">Nhóm SP:</span>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value as ProductCategoryId)}
                className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                <option value="all">Tất cả nhóm gốm sứ</option>
                {PRODUCT_CATEGORIES.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.shortName}
                  </option>
                ))}
              </select>
            </div>

            {/* Platform Pills */}
            <div className="inline-flex h-8.5 items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
              {(['all', 'Amazon', 'Etsy'] as const).map((plat) => (
                <button
                  key={plat}
                  type="button"
                  onClick={() => setSelectedPlatform(plat)}
                  className={`rounded-md px-2.5 py-1 font-medium transition ${
                    selectedPlatform === plat
                      ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {plat === 'all' ? 'Tất cả sàn TMĐT' : plat}
                </button>
              ))}
            </div>
          </div>

          {hasCustomFilter && (
            <button
              type="button"
              onClick={resetFilters}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Đặt lại
            </button>
          )}
        </div>
      </section>

      {/* Row 1: 4 Clean KPI Cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Màu sắc ưa chuộng nhất"
          value={
            <span className="inline-flex items-center gap-2">
              {topColor?.swatch && (
                <span
                  className="h-4.5 w-4.5 rounded-full border border-slate-300"
                  style={{ backgroundColor: topColor.swatch }}
                />
              )}
              <span>{topColor?.name.split('/')[0].trim() ?? '—'}</span>
            </span>
          }
          subtitle={`Chiếm ${topColor?.sharePct ?? 0}% nhu cầu tìm kiếm & mua sắm`}
          delta={topColor?.growthPct ?? null}
          deltaLabel="tăng trưởng"
          icon={<Palette className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Phong cách & Chất liệu dẫn đầu"
          value={topStyle?.name.split('(')[0].trim() ?? '—'}
          subtitle={`Chất liệu chủ lực: ${topMaterial?.name ?? 'Stoneware'} (${topMaterial?.sharePct ?? 0}%)`}
          delta={topStyle?.growthPct ?? null}
          deltaLabel="xu hướng"
          icon={<TrendingUp className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Hình dạng & Dòng sản phẩm"
          value={topShape?.name.split('/')[0].trim() ?? '—'}
          subtitle={`Nhóm nổi bật: ${topProductType?.name ?? 'Bát & Đĩa'} (${topProductType?.sharePct ?? 0}%)`}
          delta={topShape?.growthPct ?? null}
          deltaLabel="YoY"
          icon={<Shapes className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Mức giá bán lẻ TB quốc tế"
          value={`$${aggregated.avgPrice}`}
          subtitle={`Phân bổ sàn: ${100 - aggregated.avgEtsyShare}% Amazon • ${aggregated.avgEtsyShare}% Etsy`}
          icon={<DollarSign className="h-4.5 w-4.5" />}
        />
      </section>

      {/* Key Insight Bar */}
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E2E8F0] bg-white px-4 py-3">
        <div className="flex items-start gap-2.5 text-xs leading-relaxed text-slate-600 sm:items-center">
          <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-indigo-200/80 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
            <Sparkles className="h-3 w-3" />
            Key Insight
          </span>
          <p className="tabular-nums">
            {activeCountryMeta && activeCountryProfile ? (
              <>
                <strong className="inline-flex items-center gap-1 text-slate-900">
                  <CountryFlag code={activeCountryMeta.code} size={13} />
                  {activeCountryMeta.name}:
                </strong>{' '}
                {activeCountryProfile.summaryNote}
              </>
            ) : (
              <>
                Toàn thị trường ghi nhận phong cách <strong className="text-slate-900">Tối giản & Hiện đại</strong> cùng chất liệu{' '}
                <strong className="text-slate-900">Stoneware</strong> dẫn đầu đà tăng trưởng; phân khúc giá{' '}
                <strong className="text-indigo-700">$30 – $60</strong> chiếm tỷ trọng cao nhất (trên 41% đơn hàng).
              </>
            )}
          </p>
        </div>
      </section>

      {/* Row 2: Color Breakdown (4 cols) + Style & Product Type (4 cols) + Material & Price Tiers (4 cols) */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Colors */}
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 lg:col-span-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
              <Palette className="h-3.5 w-3.5" />
            </span>
            <h3 className="font-display text-sm font-bold text-slate-900">
              Màu sắc được ưa chuộng
            </h3>
          </div>
          <p className="mt-1 text-xs text-slate-500">Tỷ trọng quan tâm & tốc độ tăng trưởng màu men</p>

          <div className="mt-4 space-y-3 tabular-nums">
            {aggregated.colors.map((item) => (
              <div key={item.name}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="inline-flex items-center gap-2 font-medium text-slate-700">
                    <span
                      className="h-3 w-3 shrink-0 rounded-full border border-slate-300"
                      style={{ backgroundColor: item.swatch ?? '#CBD5E1' }}
                    />
                    <span>{item.name}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{item.sharePct}%</span>
                    <span className="text-[11px] font-medium text-emerald-700">
                      +{item.growthPct}%
                    </span>
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-indigo-600 transition-all duration-300"
                    style={{ width: `${Math.min(100, item.sharePct * 2.1)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Styles & Shapes */}
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 lg:col-span-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
              <Shapes className="h-3.5 w-3.5" />
            </span>
            <h3 className="font-display text-sm font-bold text-slate-900">
              Phong cách & Hình dạng
            </h3>
          </div>
          <p className="mt-1 text-xs text-slate-500">Thị hiếu thiết kế theo nhóm sản phẩm gốm sứ</p>

          <div className="mt-4 space-y-2.5 tabular-nums">
            <p className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
              Phong cách thiết kế
            </p>
            {aggregated.styles.map((item, i) => (
              <div key={item.name} className="flex items-center justify-between gap-2 text-xs">
                <span className="w-36 truncate font-medium text-slate-700">{item.name}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min(100, item.sharePct * 2)}%`,
                      backgroundColor: i === 0 ? '#4F46E5' : i === 1 ? '#0284C7' : '#64748B',
                    }}
                  />
                </div>
                <span className="w-10 text-right font-semibold text-slate-900">
                  {item.sharePct}%
                </span>
              </div>
            ))}
          </div>

          <div className="mt-5 space-y-2 border-t border-slate-100 pt-4 tabular-nums">
            <p className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
              Hình dạng phổ biến
            </p>
            <div className="grid grid-cols-2 gap-2">
              {aggregated.shapes.map((sh) => (
                <div
                  key={sh.name}
                  className="rounded-lg border border-slate-200/80 bg-slate-50/70 px-2.5 py-2"
                >
                  <p className="text-[11px] font-medium text-slate-600">{sh.name}</p>
                  <div className="mt-0.5 flex items-baseline justify-between">
                    <span className="font-display text-sm font-bold text-slate-900">
                      {sh.sharePct}%
                    </span>
                    <span className="text-[10px] font-semibold text-emerald-700">
                      +{sh.growthPct}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Materials & Price Brackets */}
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 lg:col-span-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
              <ShoppingBag className="h-3.5 w-3.5" />
            </span>
            <h3 className="font-display text-sm font-bold text-slate-900">
              Chất liệu & Phân khúc giá
            </h3>
          </div>
          <p className="mt-1 text-xs text-slate-500">Tỷ trọng chất liệu và mức giá sẵn sàng chi trả</p>

          <div className="mt-4 space-y-2.5 tabular-nums">
            <p className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
              Chất liệu gốm sứ
            </p>
            {aggregated.materials.map((mat, idx) => (
              <div
                key={mat.name}
                className="rounded-lg border border-slate-100 bg-slate-50/70 px-3 py-2"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800">{mat.name}</span>
                  <span className="font-bold text-slate-900">{mat.sharePct}%</span>
                </div>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-200/70">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${mat.sharePct}%`,
                      backgroundColor: idx === 0 ? '#4F46E5' : idx === 1 ? '#0D9488' : '#64748B',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 border-t border-slate-100 pt-4 tabular-nums">
            <p className="mb-2.5 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
              Phân bố mức giá bán lẻ (USD)
            </p>
            <div className="grid grid-cols-4 items-end gap-2 pt-2">
              {aggregated.priceRanges.map((pr) => (
                <div key={pr.name} className="flex flex-col items-center gap-1">
                  <span className="text-[10px] font-bold text-slate-800">{pr.sharePct}%</span>
                  <div className="flex h-16 w-full items-end rounded-md bg-slate-100 p-1">
                    <div
                      className="w-full rounded-t bg-indigo-600"
                      style={{ height: `${Math.max(16, pr.sharePct * 2)}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-medium text-slate-500">{pr.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Row 3: Cross-Country Taste Heatmap Matrix */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
              Ma trận Thị hiếu theo Quốc gia (Heatmap %)
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              So sánh mức độ ưa chuộng thuộc tính sản phẩm giữa 8 thị trường trọng điểm
            </p>
          </div>
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
            {(
              [
                { id: 'styles', label: 'Phong cách' },
                { id: 'colors', label: 'Màu sắc' },
                { id: 'materials', label: 'Chất liệu' },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setMatrixAttr(tab.id)}
                className={`rounded-md px-2.5 py-1 transition ${
                  matrixAttr === tab.id
                    ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[740px] border-collapse text-xs tabular-nums">
            <thead>
              <tr className="border-y border-slate-200 bg-slate-50/80 text-[11px] font-semibold text-slate-500 uppercase">
                <th className="px-3.5 py-2.5 text-left">Quốc gia</th>
                {matrixColumns.map((col) => (
                  <th key={col} className="px-3 py-2.5 text-center">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {COUNTRIES.map((c) => (
                <tr
                  key={c.code}
                  onClick={() => setSelectedCountry(c.code === selectedCountry ? 'all' : c.code)}
                  className={`cursor-pointer transition hover:bg-slate-50 ${
                    selectedCountry === c.code ? 'bg-indigo-50/40' : ''
                  }`}
                >
                  <td className="px-3.5 py-2.5 font-semibold text-slate-900">
                    <span className="inline-flex items-center gap-2">
                      <CountryFlag code={c.code} size={18} />
                      <span>{c.name}</span>
                    </span>
                  </td>
                  {matrixColumns.map((col) => {
                    const val = getMatrixScore(c.code, col);
                    const bgClass =
                      val >= 40
                        ? 'bg-indigo-600 text-white font-bold'
                        : val >= 30
                          ? 'bg-indigo-100 text-indigo-900 font-semibold'
                          : val >= 20
                            ? 'bg-slate-100 text-slate-800 font-medium'
                            : 'bg-slate-50 text-slate-500';
                    return (
                      <td key={col} className="px-2 py-2 text-center">
                        <span
                          className={`inline-block w-16 rounded-md py-1 text-[11px] ${bgClass}`}
                        >
                          {val}%
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Row 4: Trending Product Attribute Combos */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white p-5">
        <div>
          <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
            Tổ hợp Thị hiếu Tăng trưởng & Giảm sức hút
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Xác định các dòng sản phẩm đang lên hoặc có dấu hiệu bão hòa để định hướng đặt hàng
          </p>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[820px] border-collapse text-left text-xs tabular-nums">
            <thead>
              <tr className="border-y border-slate-200 bg-slate-50/80 text-[11px] font-semibold text-slate-500 uppercase">
                <th className="px-3.5 py-2.5">Thị trường</th>
                <th className="px-3.5 py-2.5">Dòng sản phẩm</th>
                <th className="px-3.5 py-2.5">Màu sắc</th>
                <th className="px-3.5 py-2.5">Hình dạng & Chất liệu</th>
                <th className="px-3.5 py-2.5">Phong cách</th>
                <th className="px-3.5 py-2.5 text-right">Giá TB</th>
                <th className="px-3.5 py-2.5 text-right">Tăng trưởng</th>
                <th className="px-3.5 py-2.5 text-right">Trạng thái</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredCombos.map((combo) => {
                const country = COUNTRIES.find((c) => c.code === combo.countryCode);
                return (
                  <tr key={combo.id} className="hover:bg-slate-50/80">
                    <td className="px-3.5 py-3 font-semibold text-slate-800">
                      <span className="inline-flex items-center gap-2">
                        <CountryFlag code={combo.countryCode} size={18} />
                        <span>{country?.name}</span>
                      </span>
                    </td>
                    <td className="px-3.5 py-3 font-semibold text-slate-900">
                      {combo.productType}
                    </td>
                    <td className="px-3.5 py-3">
                      <span className="inline-flex items-center gap-1.5 text-slate-700">
                        <span
                          className="h-2.5 w-2.5 rounded-full border border-slate-300"
                          style={{ backgroundColor: combo.colorSwatch }}
                        />
                        {combo.color}
                      </span>
                    </td>
                    <td className="px-3.5 py-3 text-slate-600">
                      {combo.shape} • {combo.material}
                    </td>
                    <td className="px-3.5 py-3">
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                        {combo.style}
                      </span>
                    </td>
                    <td className="px-3.5 py-3 text-right font-semibold text-slate-900">
                      ${combo.avgPriceUsd.toFixed(1)}
                    </td>
                    <td className="px-3.5 py-3 text-right">
                      <span
                        className={`inline-flex rounded-md px-1.5 py-0.5 font-semibold ${
                          combo.demandGrowthPct >= 0
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-rose-50 text-rose-700'
                        }`}
                      >
                        {combo.demandGrowthPct >= 0
                          ? `+${combo.demandGrowthPct}%`
                          : `${combo.demandGrowthPct}%`}
                      </span>
                    </td>
                    <td className="px-3.5 py-3 text-right">
                      <span
                        className={`inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                          combo.status === 'rising'
                            ? 'bg-indigo-50 text-indigo-700'
                            : combo.status === 'steady'
                              ? 'bg-slate-100 text-slate-700'
                              : 'bg-rose-50 text-rose-700'
                        }`}
                      >
                        {combo.status === 'rising'
                          ? 'Tăng sức hút'
                          : combo.status === 'steady'
                            ? 'Ổn định'
                            : 'Giảm sức hút'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
