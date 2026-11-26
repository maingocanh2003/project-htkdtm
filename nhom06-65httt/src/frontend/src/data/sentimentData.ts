import { ProductCategoryId } from './marketOverviewData';

export type SentimentLabel = 'positive' | 'neutral' | 'negative';

export interface CountrySentimentMetric {
  countryCode: string;
  totalReviews: number;
  avgRating: number; // 1 - 5
  positivePct: number;
  neutralPct: number;
  negativePct: number;
  ratingDistribution: { stars: number; pct: number }[];
}

export interface AspectSentimentItem {
  aspect: string;
  praiseCount: number;
  complaintCount: number;
  praiseExample: string;
  complaintExample: string;
}

export interface CustomerReviewSample {
  id: string;
  countryCode: string;
  categoryId: Exclude<ProductCategoryId, 'all'>;
  platform: 'Amazon' | 'Etsy';
  productName: string;
  rating: number;
  sentiment: SentimentLabel;
  confidencePct: number;
  aspectTags: string[];
  reviewDate: string;
  excerptVi: string;
  excerptOrig: string;
}

export interface NlpModelEvalMetric {
  modelName: string;
  datasetSplit: string;
  accuracyPct: number;
  macroF1Pct: number;
  precisionPct: number;
  recallPct: number;
  perClass: {
    label: string;
    precision: number;
    recall: number;
    f1: number;
    support: number;
  }[];
}

export const NLP_MODEL_EVALUATION: NlpModelEvalMetric = {
  modelName: 'RoBERTa + Aspect-Extraction Pipeline',
  datasetSplit: 'Tập kiểm thử (2,840 đánh giá TMĐT)',
  accuracyPct: 92.1,
  macroF1Pct: 91.4,
  precisionPct: 91.8,
  recallPct: 91.1,
  perClass: [
    { label: 'Tích cực', precision: 94.6, recall: 95.2, f1: 94.9, support: 1960 },
    { label: 'Trung lập', precision: 88.2, recall: 86.5, f1: 87.3, support: 495 },
    { label: 'Tiêu cực', precision: 92.6, recall: 91.5, f1: 92.0, support: 385 },
  ],
};

export const COUNTRY_SENTIMENTS: CountrySentimentMetric[] = [
  {
    countryCode: 'US',
    totalReviews: 4820,
    avgRating: 4.56,
    positivePct: 74.2,
    neutralPct: 14.8,
    negativePct: 11.0,
    ratingDistribution: [
      { stars: 5, pct: 68 },
      { stars: 4, pct: 16 },
      { stars: 3, pct: 7 },
      { stars: 2, pct: 4 },
      { stars: 1, pct: 5 },
    ],
  },
  {
    countryCode: 'JP',
    totalReviews: 3190,
    avgRating: 4.71,
    positivePct: 80.5,
    neutralPct: 12.1,
    negativePct: 7.4,
    ratingDistribution: [
      { stars: 5, pct: 75 },
      { stars: 4, pct: 14 },
      { stars: 3, pct: 6 },
      { stars: 2, pct: 3 },
      { stars: 1, pct: 2 },
    ],
  },
  {
    countryCode: 'DE',
    totalReviews: 2640,
    avgRating: 4.52,
    positivePct: 72.4,
    neutralPct: 16.2,
    negativePct: 11.4,
    ratingDistribution: [
      { stars: 5, pct: 66 },
      { stars: 4, pct: 17 },
      { stars: 3, pct: 8 },
      { stars: 2, pct: 5 },
      { stars: 1, pct: 4 },
    ],
  },
  {
    countryCode: 'FR',
    totalReviews: 1980,
    avgRating: 4.62,
    positivePct: 76.8,
    neutralPct: 14.0,
    negativePct: 9.2,
    ratingDistribution: [
      { stars: 5, pct: 71 },
      { stars: 4, pct: 15 },
      { stars: 3, pct: 7 },
      { stars: 2, pct: 4 },
      { stars: 1, pct: 3 },
    ],
  },
  {
    countryCode: 'GB',
    totalReviews: 2150,
    avgRating: 4.49,
    positivePct: 71.1,
    neutralPct: 17.3,
    negativePct: 11.6,
    ratingDistribution: [
      { stars: 5, pct: 64 },
      { stars: 4, pct: 18 },
      { stars: 3, pct: 8 },
      { stars: 2, pct: 5 },
      { stars: 1, pct: 5 },
    ],
  },
  {
    countryCode: 'KR',
    totalReviews: 2410,
    avgRating: 4.67,
    positivePct: 78.6,
    neutralPct: 13.4,
    negativePct: 8.0,
    ratingDistribution: [
      { stars: 5, pct: 74 },
      { stars: 4, pct: 15 },
      { stars: 3, pct: 5 },
      { stars: 2, pct: 3 },
      { stars: 1, pct: 3 },
    ],
  },
  {
    countryCode: 'AU',
    totalReviews: 1470,
    avgRating: 4.58,
    positivePct: 75.0,
    neutralPct: 15.2,
    negativePct: 9.8,
    ratingDistribution: [
      { stars: 5, pct: 69 },
      { stars: 4, pct: 16 },
      { stars: 3, pct: 7 },
      { stars: 2, pct: 4 },
      { stars: 1, pct: 4 },
    ],
  },
  {
    countryCode: 'CA',
    totalReviews: 1320,
    avgRating: 4.54,
    positivePct: 73.5,
    neutralPct: 15.9,
    negativePct: 10.6,
    ratingDistribution: [
      { stars: 5, pct: 67 },
      { stars: 4, pct: 17 },
      { stars: 3, pct: 7 },
      { stars: 2, pct: 5 },
      { stars: 1, pct: 4 },
    ],
  },
];

export const ASPECT_SENTIMENTS: AspectSentimentItem[] = [
  {
    aspect: 'Chất lượng men & Hoàn thiện',
    praiseCount: 4120,
    complaintCount: 420,
    praiseExample: 'Men mịn đều, không bọt khí, dễ vệ sinh',
    complaintExample: 'Một vài vết rỗ nhỏ dưới đáy sản phẩm',
  },
  {
    aspect: 'Thiết kế & Kiểu dáng',
    praiseCount: 3890,
    complaintCount: 290,
    praiseExample: 'Kiểu dáng tinh tế, hợp trang trí bàn ăn hiện đại',
    complaintExample: 'Tay cầm cốc hơi nhỏ so với ngón tay lớn',
  },
  {
    aspect: 'Màu sắc thực tế',
    praiseCount: 2940,
    complaintCount: 680,
    praiseExample: 'Màu men hỏa biến tự nhiên sang trọng',
    complaintExample: 'Tông màu đậm hơn nhẹ so với ảnh quảng cáo',
  },
  {
    aspect: 'Đóng gói & Vận chuyển',
    praiseCount: 2210,
    complaintCount: 1180,
    praiseExample: 'Bọc xốp định hình 2 lớp rất chắc chắn',
    complaintExample: 'Bị sứt mẻ viền đĩa khi giao chặng dài',
  },
  {
    aspect: 'Kích thước & Dung tích',
    praiseCount: 1840,
    complaintCount: 540,
    praiseExample: 'Dung tích chuẩn cho trà và cà phê sáng',
    complaintExample: 'Bát nhỏ hơn kỳ vọng so với ảnh phối cảnh',
  },
  {
    aspect: 'Giá trị tương xứng giá',
    praiseCount: 2760,
    complaintCount: 310,
    praiseExample: 'Chất lượng thủ công vượt trội trong tầm giá',
    complaintExample: 'Phí vận chuyển quốc tế làm tổng đơn cao',
  },
];

export const REVIEW_SAMPLES: CustomerReviewSample[] = [
  {
    id: 'rv-101',
    countryCode: 'US',
    categoryId: 'decor',
    platform: 'Etsy',
    productName: 'Bình gốm Stoneware dáng hữu cơ trắng ngà',
    rating: 5,
    sentiment: 'positive',
    confidencePct: 97,
    aspectTags: ['Chất lượng men', 'Thiết kế', 'Đóng gói'],
    reviewDate: '2025-11-12',
    excerptVi:
      'Bề mặt men mờ cực kỳ sang trọng, đóng gói xốp dày nên giao đến Texas nguyên vẹn 100%.',
    excerptOrig:
      'Gorgeous matte glaze and sculptural silhouette. Double-boxed foam kept it completely safe.',
  },
  {
    id: 'rv-102',
    countryCode: 'JP',
    categoryId: 'tableware',
    platform: 'Amazon',
    productName: 'Bộ ấm chén gốm men tro phong cách Wabi-sabi',
    rating: 5,
    sentiment: 'positive',
    confidencePct: 96,
    aspectTags: ['Chất lượng men', 'Màu sắc thực tế'],
    reviewDate: '2025-11-08',
    excerptVi:
      'Độ hoàn thiện tinh xảo, rót trà không nhỏ giọt, màu men tro rất hài hòa trên bàn gỗ.',
    excerptOrig:
      'Clean spout pour with zero drip. Natural ash glaze matches minimalist wooden tables beautifully.',
  },
  {
    id: 'rv-103',
    countryCode: 'DE',
    categoryId: 'household',
    platform: 'Amazon',
    productName: 'Bộ 6 đĩa sứ trắng chịu nhiệt cao cấp',
    rating: 2,
    sentiment: 'negative',
    confidencePct: 93,
    aspectTags: ['Đóng gói & Vận chuyển'],
    reviewDate: '2025-11-04',
    excerptVi:
      'Chất sứ đẹp nhưng 1 chiếc đĩa bị mẻ viền do thiếu vách ngăn carton giữa các đĩa.',
    excerptOrig:
      'Porcelain quality is solid, however one plate arrived chipped due to thin dividers between plates.',
  },
  {
    id: 'rv-104',
    countryCode: 'KR',
    categoryId: 'household',
    platform: 'Amazon',
    productName: 'Set cốc & đĩa tráng miệng be mờ Home Café',
    rating: 5,
    sentiment: 'positive',
    confidencePct: 95,
    aspectTags: ['Thiết kế', 'Màu sắc thực tế', 'Giá trị'],
    reviewDate: '2025-10-29',
    excerptVi:
      'Màu be chuẩn ảnh, viền đĩa lượn sóng rất xinh khi chụp ảnh đồ uống tại nhà.',
    excerptOrig:
      'Exact creamy beige tone as pictured. Love the subtle wavy rim for morning coffee.',
  },
  {
    id: 'rv-105',
    countryCode: 'FR',
    categoryId: 'artisan',
    platform: 'Etsy',
    productName: 'Đĩa gốm vẽ tay họa tiết xanh Olive',
    rating: 3,
    sentiment: 'neutral',
    confidencePct: 89,
    aspectTags: ['Thiết kế', 'Màu sắc thực tế', 'Kích thước'],
    reviewDate: '2025-10-21',
    excerptVi:
      'Họa tiết vẽ tay rất có hồn nhưng đường kính thực tế nhỏ hơn khoảng 1.5cm so với hình dung.',
    excerptOrig:
      'Lovely hand-painted brushwork, though slightly smaller than it appeared in lifestyle photos.',
  },
  {
    id: 'rv-106',
    countryCode: 'GB',
    categoryId: 'tableware',
    platform: 'Amazon',
    productName: 'Bộ ấm tách trà sứ xanh lam cổ điển',
    rating: 5,
    sentiment: 'positive',
    confidencePct: 94,
    aspectTags: ['Chất lượng men', 'Giá trị'],
    reviewDate: '2025-10-18',
    excerptVi:
      'Sứ nhẹ, giữ nhiệt trà lâu, họa tiết lam sắc nét vượt mong đợi so với mức giá.',
    excerptOrig:
      'Lightweight porcelain retains heat well. Crisp cobalt pattern feels much pricier than it cost.',
  },
  {
    id: 'rv-107',
    countryCode: 'US',
    categoryId: 'household',
    platform: 'Amazon',
    productName: 'Bộ bát ăn cơm Stoneware men nâu đất',
    rating: 2,
    sentiment: 'negative',
    confidencePct: 91,
    aspectTags: ['Màu sắc thực tế', 'Kích thước'],
    reviewDate: '2025-10-14',
    excerptVi:
      'Màu nâu ngoài đời tối hơn ảnh mẫu và miệng bát hơi nông nếu dùng đựng súp.',
    excerptOrig:
      'Glaze arrived noticeably darker than the product photo and bowls feel a bit shallow for soup.',
  },
  {
    id: 'rv-108',
    countryCode: 'AU',
    categoryId: 'decor',
    platform: 'Etsy',
    productName: 'Chậu gốm Terracotta chống thấm ngoài trời',
    rating: 5,
    sentiment: 'positive',
    confidencePct: 96,
    aspectTags: ['Chất lượng men', 'Thiết kế'],
    reviewDate: '2025-10-09',
    excerptVi:
      'Thành chậu dày dặn, lỗ thoát nước chuẩn và giữ màu đất nung rất đẹp dưới nắng.',
    excerptOrig:
      'Thick-walled stoneware with clean drainage hole. Warm terracotta finish holds up great outdoors.',
  },
];
