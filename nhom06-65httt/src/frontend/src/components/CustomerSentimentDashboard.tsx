import React, { useMemo, useState } from 'react';
import {
  AlertTriangle,
  BrainCircuit,
  Filter,
  MessageSquareQuote,
  RotateCcw,
  SmilePlus,
  Sparkles,
  Star,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import {
  COUNTRIES,
  PRODUCT_CATEGORIES,
  ProductCategoryId,
} from '../data/marketOverviewData';
import {
  ASPECT_SENTIMENTS,
  COUNTRY_SENTIMENTS,
  NLP_MODEL_EVALUATION,
  REVIEW_SAMPLES,
  SentimentLabel,
} from '../data/sentimentData';
import { KpiCard } from './KpiCard';
import { CountryFlag } from './CountryFlag';

export const CustomerSentimentDashboard: React.FC = () => {
  const [selectedCountry, setSelectedCountry] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<ProductCategoryId>('all');
  const [selectedSentiment, setSelectedSentiment] = useState<'all' | SentimentLabel>('all');

  const hasCustomFilter =
    selectedCountry !== 'all' || selectedCategory !== 'all' || selectedSentiment !== 'all';

  const resetFilters = () => {
    setSelectedCountry('all');
    setSelectedCategory('all');
    setSelectedSentiment('all');
  };

  const activeCountries = useMemo(() => {
    return selectedCountry === 'all'
      ? COUNTRY_SENTIMENTS
      : COUNTRY_SENTIMENTS.filter((c) => c.countryCode === selectedCountry);
  }, [selectedCountry]);

  const kpis = useMemo(() => {
    const totalReviews = activeCountries.reduce((s, c) => s + c.totalReviews, 0);
    const weightedRating =
      totalReviews > 0
        ? activeCountries.reduce((s, c) => s + c.avgRating * c.totalReviews, 0) / totalReviews
        : 0;
    const weightedPos =
      totalReviews > 0
        ? activeCountries.reduce((s, c) => s + c.positivePct * c.totalReviews, 0) / totalReviews
        : 0;
    const weightedNeu =
      totalReviews > 0
        ? activeCountries.reduce((s, c) => s + c.neutralPct * c.totalReviews, 0) / totalReviews
        : 0;
    const weightedNeg =
      totalReviews > 0
        ? activeCountries.reduce((s, c) => s + c.negativePct * c.totalReviews, 0) / totalReviews
        : 0;

    return {
      totalReviews,
      avgRating: weightedRating.toFixed(2),
      positivePct: Number(weightedPos.toFixed(1)),
      neutralPct: Number(weightedNeu.toFixed(1)),
      negativePct: Number(weightedNeg.toFixed(1)),
    };
  }, [activeCountries]);

  const filteredReviews = useMemo(() => {
    return REVIEW_SAMPLES.filter((r) => {
      const cOk = selectedCountry === 'all' || r.countryCode === selectedCountry;
      const catOk = selectedCategory === 'all' || r.categoryId === selectedCategory;
      const sOk = selectedSentiment === 'all' || r.sentiment === selectedSentiment;
      return cOk && catOk && sOk;
    });
  }, [selectedCountry, selectedCategory, selectedSentiment]);

  const maxAspectCount = Math.max(
    ...ASPECT_SENTIMENTS.map((a) => Math.max(a.praiseCount, a.complaintCount)),
    1
  );

  return (
    <div className="space-y-4">
      {/* Compact Single-Row Filter Bar */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 pr-1 text-xs font-semibold text-slate-600">
              <Filter className="h-3.5 w-3.5 text-indigo-600" />
              Bộ lọc đánh giá:
            </span>

            <div className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs">
              {selectedCountry !== 'all' && <CountryFlag code={selectedCountry} size={14} />}
              <span className="font-medium text-slate-500">Thị trường:</span>
              <select
                value={selectedCountry}
                onChange={(e) => setSelectedCountry(e.target.value)}
                className="bg-transparent font-semibold text-slate-900 focus:outline-hidden"
              >
                <option value="all">Tất cả 8 quốc gia</option>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

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

            <div className="inline-flex h-8.5 items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
              {(
                [
                  { id: 'all', label: 'Tất cả cảm xúc' },
                  { id: 'positive', label: 'Tích cực' },
                  { id: 'neutral', label: 'Trung lập' },
                  { id: 'negative', label: 'Tiêu cực' },
                ] as const
              ).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelectedSentiment(s.id)}
                  className={`rounded-md px-2.5 py-1 font-medium transition ${
                    selectedSentiment === s.id
                      ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {s.label}
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
          title="Điểm đánh giá trung bình"
          value={`${kpis.avgRating} / 5.0`}
          subtitle={`Tổng hợp ${kpis.totalReviews.toLocaleString('en-US')} đánh giá quốc tế`}
          icon={<Star className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Tỷ lệ cảm xúc Tích cực"
          value={`${kpis.positivePct}%`}
          subtitle={`Trung lập chiếm ${kpis.neutralPct}% tổng phản hồi`}
          delta={3.4}
          deltaLabel="so với quý trước"
          icon={<SmilePlus className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Tỷ lệ cảm xúc Tiêu cực"
          value={`${kpis.negativePct}%`}
          subtitle="Tập trung phàn nàn: mẻ viền khi vận chuyển"
          delta={-1.8}
          deltaLabel="giảm phàn nàn"
          icon={<AlertTriangle className="h-4.5 w-4.5" />}
        />

        <KpiCard
          title="Độ chính xác AI/NLP (Test)"
          value={`${NLP_MODEL_EVALUATION.macroF1Pct}% F1`}
          subtitle={`Accuracy ${NLP_MODEL_EVALUATION.accuracyPct}% • Precision ${NLP_MODEL_EVALUATION.precisionPct}%`}
          icon={<BrainCircuit className="h-4.5 w-4.5" />}
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
            Khách hàng đánh giá rất cao <strong className="text-slate-900">chất lượng men (90.7% khen ngợi)</strong> và{' '}
            <strong className="text-slate-900">thiết kế kiểu dáng (93.1% khen ngợi)</strong>; điểm nghẽn lớn nhất cần yêu cầu nhà cung cấp khắc phục là{' '}
            <strong className="text-rose-700">đóng gói chống sốc</strong> (chiếm 34.5% tổng số phàn nàn).
          </p>
        </div>
      </section>

      {/* Row 2: Sentiment by Country (7 cols) + AI/NLP Model Evaluation (5 cols) */}
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 xl:col-span-7">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
                Phân bố Cảm xúc & Điểm đánh giá theo Quốc gia
              </h3>
              <p className="mt-0.5 text-xs text-slate-500">
                Kết quả phân loại 3 lớp cảm xúc từ mô hình AI/NLP
              </p>
            </div>
            <div className="flex items-center gap-3 text-[11px] font-medium text-slate-600">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500" /> Tích cực
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-slate-300" /> Trung lập
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-rose-500" /> Tiêu cực
              </span>
            </div>
          </div>

          <div className="mt-4 space-y-3 tabular-nums">
            {COUNTRY_SENTIMENTS.map((item) => {
              const country = COUNTRIES.find((c) => c.code === item.countryCode)!;
              const isSelected = selectedCountry === item.countryCode;
              return (
                <button
                  key={item.countryCode}
                  type="button"
                  onClick={() =>
                    setSelectedCountry(isSelected ? 'all' : item.countryCode)
                  }
                  className={`block w-full rounded-lg p-2 text-left transition ${
                    isSelected ? 'bg-indigo-50/70 ring-1 ring-indigo-200' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="inline-flex items-center gap-2 font-semibold text-slate-800">
                      <CountryFlag code={item.countryCode} size={16} />
                      <span>{country.name}</span>
                      <span className="text-[11px] font-normal text-slate-400">
                        ({item.totalReviews.toLocaleString('en-US')} lượt)
                      </span>
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="inline-flex items-center gap-1 font-semibold text-slate-900">
                        <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                        {item.avgRating.toFixed(2)}
                      </span>
                      <span className="w-12 text-right font-semibold text-emerald-700">
                        {item.positivePct}%
                      </span>
                      <span className="w-11 text-right font-medium text-rose-600">
                        {item.negativePct}%
                      </span>
                    </div>
                  </div>
                  <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full bg-emerald-500"
                      style={{ width: `${item.positivePct}%` }}
                    />
                    <div
                      className="h-full bg-slate-300"
                      style={{ width: `${item.neutralPct}%` }}
                    />
                    <div
                      className="h-full bg-rose-500"
                      style={{ width: `${item.negativePct}%` }}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* AI/NLP Model Evaluation Card */}
        <div className="flex flex-col justify-between rounded-xl border border-[#E2E8F0] bg-white p-5 xl:col-span-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
                <BrainCircuit className="h-3.5 w-3.5" />
              </span>
              <div>
                <h3 className="font-display text-sm font-bold text-slate-900">
                  Đánh giá Mô hình AI/NLP trên Tập kiểm thử
                </h3>
                <p className="text-[11px] text-slate-500">
                  {NLP_MODEL_EVALUATION.modelName} • {NLP_MODEL_EVALUATION.datasetSplit}
                </p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-4 gap-2 tabular-nums">
              {[
                { label: 'Accuracy', val: `${NLP_MODEL_EVALUATION.accuracyPct}%` },
                { label: 'Macro F1', val: `${NLP_MODEL_EVALUATION.macroF1Pct}%` },
                { label: 'Precision', val: `${NLP_MODEL_EVALUATION.precisionPct}%` },
                { label: 'Recall', val: `${NLP_MODEL_EVALUATION.recallPct}%` },
              ].map((m) => (
                <div
                  key={m.label}
                  className="rounded-lg border border-slate-200/80 bg-slate-50/70 p-2.5 text-center"
                >
                  <p className="text-[10px] font-semibold text-slate-500 uppercase">{m.label}</p>
                  <p className="mt-0.5 font-display text-sm font-bold text-indigo-700">{m.val}</p>
                </div>
              ))}
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs tabular-nums">
                <thead>
                  <tr className="border-y border-slate-200 bg-slate-50 text-[10px] font-semibold text-slate-500 uppercase">
                    <th className="px-2.5 py-2">Lớp cảm xúc</th>
                    <th className="px-2.5 py-2 text-right">Precision</th>
                    <th className="px-2.5 py-2 text-right">Recall</th>
                    <th className="px-2.5 py-2 text-right">F1-Score</th>
                    <th className="px-2.5 py-2 text-right">Support</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {NLP_MODEL_EVALUATION.perClass.map((cls) => (
                    <tr key={cls.label}>
                      <td className="px-2.5 py-2 font-semibold text-slate-800">{cls.label}</td>
                      <td className="px-2.5 py-2 text-right text-slate-600">{cls.precision}%</td>
                      <td className="px-2.5 py-2 text-right text-slate-600">{cls.recall}%</td>
                      <td className="px-2.5 py-2 text-right font-bold text-indigo-700">{cls.f1}%</td>
                      <td className="px-2.5 py-2 text-right text-slate-500">{cls.support}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-600">
            Mô hình đạt độ tin cậy cao nhất ở lớp <strong className="text-emerald-700">Tích cực (94.9% F1)</strong> và{' '}
            <strong className="text-rose-700">Tiêu cực (92.0% F1)</strong>, đảm bảo phát hiện chính xác các sản phẩm có lỗi chất lượng trước khi tái đặt hàng.
          </div>
        </div>
      </section>

      {/* Row 3: Aspect-Based Praise vs Complaint Extraction */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white p-5">
        <div>
          <h3 className="font-display text-sm font-bold text-slate-900 sm:text-base">
            Trích xuất Đặc điểm được Khen ngợi & Phàn nàn (Aspect Sentiment)
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            So sánh số lượt nhắc tích cực (bên phải) và tiêu cực (bên trái) trên từng thuộc tính sản phẩm
          </p>
        </div>

        <div className="mt-4 space-y-3 tabular-nums">
          {ASPECT_SENTIMENTS.map((asp) => {
            const praiseW = (asp.praiseCount / maxAspectCount) * 100;
            const complaintW = (asp.complaintCount / maxAspectCount) * 100;
            return (
              <div
                key={asp.aspect}
                className="grid grid-cols-1 items-center gap-3 rounded-lg border border-slate-100 bg-slate-50/40 p-3 lg:grid-cols-12"
              >
                <div className="lg:col-span-3">
                  <p className="text-xs font-bold text-slate-900">{asp.aspect}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    Khen: <strong className="text-emerald-700">{asp.praiseCount}</strong> • Chê:{' '}
                    <strong className="text-rose-600">{asp.complaintCount}</strong>
                  </p>
                </div>

                {/* Diverging Bar */}
                <div className="flex items-center gap-2 lg:col-span-5">
                  <div className="flex flex-1 justify-end overflow-hidden rounded-l-full bg-slate-100">
                    <div
                      className="h-2.5 rounded-l-full bg-rose-500"
                      style={{ width: `${Math.max(4, complaintW)}%` }}
                    />
                  </div>
                  <div className="h-4 w-px bg-slate-300" />
                  <div className="flex flex-1 overflow-hidden rounded-r-full bg-slate-100">
                    <div
                      className="h-2.5 rounded-r-full bg-emerald-500"
                      style={{ width: `${Math.max(4, praiseW)}%` }}
                    />
                  </div>
                </div>

                <div className="space-y-1 text-[11px] lg:col-span-4">
                  <p className="flex items-start gap-1.5 text-emerald-800">
                    <ThumbsUp className="mt-0.5 h-3 w-3 shrink-0 text-emerald-600" />
                    <span>{asp.praiseExample}</span>
                  </p>
                  <p className="flex items-start gap-1.5 text-rose-800">
                    <ThumbsDown className="mt-0.5 h-3 w-3 shrink-0 text-rose-600" />
                    <span>{asp.complaintExample}</span>
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Row 4: Sample Annotated Reviews */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white p-5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200/80 bg-slate-50 text-indigo-600">
              <MessageSquareQuote className="h-3.5 w-3.5" />
            </span>
            <div>
              <h3 className="font-display text-sm font-bold text-slate-900">
                Mẫu Đánh giá Thực tế đã Gắn nhãn AI/NLP ({filteredReviews.length})
              </h3>
              <p className="text-xs text-slate-500">
                Minh họa nội dung đánh giá khách hàng và từ khóa thuộc tính trích xuất
              </p>
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          {filteredReviews.map((rv) => {
            const country = COUNTRIES.find((c) => c.code === rv.countryCode);
            return (
              <div
                key={rv.id}
                className="flex flex-col justify-between rounded-xl border border-[#E2E8F0] bg-slate-50/40 p-4"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-900">
                      <CountryFlag code={rv.countryCode} size={16} />
                      <span>{country?.name}</span>
                      <span className="rounded bg-slate-200/70 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                        {rv.platform}
                      </span>
                    </span>
                    <span
                      className={`rounded-md px-2 py-0.5 text-[10px] font-semibold tabular-nums ${
                        rv.sentiment === 'positive'
                          ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200/70'
                          : rv.sentiment === 'negative'
                            ? 'bg-rose-50 text-rose-700 ring-1 ring-rose-200/70'
                            : 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {rv.sentiment === 'positive'
                        ? 'Tích cực'
                        : rv.sentiment === 'negative'
                          ? 'Tiêu cực'
                          : 'Trung lập'}{' '}
                      ({rv.confidencePct}%)
                    </span>
                  </div>

                  <p className="mt-2 text-xs font-bold text-slate-900">{rv.productName}</p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-700">"{rv.excerptVi}"</p>
                  <p className="mt-1 text-[11px] italic text-slate-400">"{rv.excerptOrig}"</p>
                </div>

                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200/70 pt-2.5">
                  <div className="flex flex-wrap gap-1">
                    {rv.aspectTags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <span className="text-[11px] font-medium text-slate-400 tabular-nums">
                    {rv.rating}★ • {rv.reviewDate}
                  </span>
                </div>
              </div>
            );
          })}

          {filteredReviews.length === 0 && (
            <p className="col-span-2 py-6 text-center text-xs text-slate-400">
              Không có mẫu đánh giá nào khớp bộ lọc hiện tại.
            </p>
          )}
        </div>
      </section>
    </div>
  );
};
