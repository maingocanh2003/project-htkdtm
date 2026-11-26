import { ProductCategoryId } from './marketOverviewData';

export type CeramicPlatform = 'all' | 'Etsy' | 'Amazon';

export interface TasteAttributeScore {
  name: string;
  sharePct: number;
  growthPct: number;
  swatch?: string;
}

export interface CountryTasteProfile {
  countryCode: string;
  platformBias: { Etsy: number; Amazon: number };
  avgPriceUsd: number;
  topProductTypes: { name: string; sharePct: number; growthPct: number }[];
  colors: TasteAttributeScore[];
  shapes: TasteAttributeScore[];
  materials: TasteAttributeScore[];
  styles: TasteAttributeScore[];
  priceRanges: { label: string; sharePct: number }[];
  summaryNote: string;
}

export interface TrendingTasteCombo {
  id: string;
  countryCode: string;
  categoryId: Exclude<ProductCategoryId, 'all'>;
  productType: string;
  color: string;
  colorSwatch: string;
  shape: string;
  material: string;
  style: string;
  avgPriceUsd: number;
  demandGrowthPct: number;
  searchScore: number;
  status: 'rising' | 'steady' | 'cooling';
}

export const TASTE_PROFILES: CountryTasteProfile[] = [
  {
    countryCode: 'US',
    platformBias: { Etsy: 44, Amazon: 56 },
    avgPriceUsd: 38.5,
    topProductTypes: [
      { name: 'Bình hoa & Đồ trang trí', sharePct: 31, growthPct: 16.4 },
      { name: 'Bát & Đĩa ăn tối', sharePct: 27, growthPct: 12.1 },
      { name: 'Cốc & Ly cà phê', sharePct: 24, growthPct: 14.8 },
      { name: 'Bộ ấm trà', sharePct: 18, growthPct: 7.5 },
    ],
    colors: [
      { name: 'Trắng ngà / Kem', sharePct: 32, growthPct: 11.2, swatch: '#F5F5F0' },
      { name: 'Màu đa sắc / Họa tiết', sharePct: 26, growthPct: 15.8, swatch: '#4F46E5' },
      { name: 'Xanh Cobalt / Biển', sharePct: 20, growthPct: 13.4, swatch: '#1D4ED8' },
      { name: 'Nâu đất / Terracotta', sharePct: 14, growthPct: 18.1, swatch: '#C2410C' },
      { name: 'Màu tự nhiên / Men tro', sharePct: 8, growthPct: 9.2, swatch: '#A8A29E' },
    ],
    shapes: [
      { name: 'Tròn cổ điển', sharePct: 44, growthPct: 9.8 },
      { name: 'Hình dáng nghệ thuật', sharePct: 26, growthPct: 17.5 },
      { name: 'Oval / Bầu dục', sharePct: 17, growthPct: 11.2 },
      { name: 'Vuông / Góc cạnh', sharePct: 13, growthPct: 6.4 },
    ],
    materials: [
      { name: 'Stoneware (Gốm sành)', sharePct: 45, growthPct: 16.2 },
      { name: 'Sứ (Porcelain)', sharePct: 34, growthPct: 10.5 },
      { name: 'Gốm đất nung / Thủ công', sharePct: 21, growthPct: 13.8 },
    ],
    styles: [
      { name: 'Hiện đại', sharePct: 36, growthPct: 15.4 },
      { name: 'Tối giản', sharePct: 29, growthPct: 14.1 },
      { name: 'Thủ công (Handmade)', sharePct: 23, growthPct: 16.9 },
      { name: 'Truyền thống', sharePct: 12, growthPct: 4.8 },
    ],
    priceRanges: [
      { label: '$15 – $30', sharePct: 34 },
      { label: '$30 – $60', sharePct: 42 },
      { label: '$60 – $100', sharePct: 17 },
      { label: '> $100', sharePct: 7 },
    ],
    summaryNote:
      'Người tiêu dùng Mỹ ưa chuộng đồ trang trí và đồ gia dụng có màu sắc đa dạng, thiết kế hiện đại; chất liệu Stoneware tăng trưởng mạnh trên cả Amazon và Etsy.',
  },
  {
    countryCode: 'JP',
    platformBias: { Etsy: 31, Amazon: 69 },
    avgPriceUsd: 42.0,
    topProductTypes: [
      { name: 'Bộ ấm chén & Trà đạo', sharePct: 36, growthPct: 12.6 },
      { name: 'Bát & Đĩa ăn hằng ngày', sharePct: 34, growthPct: 10.9 },
      { name: 'Cốc gốm thủ công', sharePct: 19, growthPct: 8.4 },
      { name: 'Bình hoa Ikebana', sharePct: 11, growthPct: 6.7 },
    ],
    colors: [
      { name: 'Màu tự nhiên / Men tro', sharePct: 38, growthPct: 13.5, swatch: '#A8A29E' },
      { name: 'Trắng sứ thanh nhã', sharePct: 29, growthPct: 8.9, swatch: '#F8FAFC' },
      { name: 'Nâu đất / Men hỏa biến', sharePct: 19, growthPct: 11.4, swatch: '#78350F' },
      { name: 'Xanh lam nhạt / Rêu', sharePct: 10, growthPct: 7.2, swatch: '#0F766E' },
      { name: 'Màu đa sắc', sharePct: 4, growthPct: 2.1, swatch: '#4F46E5' },
    ],
    shapes: [
      { name: 'Tròn bất đối xứng nhẹ', sharePct: 48, growthPct: 11.8 },
      { name: 'Oval / Đĩa dài', sharePct: 24, growthPct: 9.5 },
      { name: 'Vuông khay Nhật', sharePct: 18, growthPct: 7.1 },
      { name: 'Hình dáng nghệ thuật', sharePct: 10, growthPct: 8.2 },
    ],
    materials: [
      { name: 'Sứ cao cấp (Porcelain)', sharePct: 46, growthPct: 10.1 },
      { name: 'Gốm mộc thủ công', sharePct: 32, growthPct: 11.7 },
      { name: 'Stoneware', sharePct: 22, growthPct: 9.4 },
    ],
    styles: [
      { name: 'Tối giản (Wabi-sabi)', sharePct: 44, growthPct: 13.2 },
      { name: 'Thủ công', sharePct: 27, growthPct: 10.6 },
      { name: 'Truyền thống', sharePct: 19, growthPct: 6.2 },
      { name: 'Hiện đại', sharePct: 10, growthPct: 7.5 },
    ],
    priceRanges: [
      { label: '$15 – $30', sharePct: 26 },
      { label: '$30 – $60', sharePct: 45 },
      { label: '$60 – $100', sharePct: 21 },
      { label: '> $100', sharePct: 8 },
    ],
    summaryNote:
      'Thị trường Nhật Bản ưu tiên bộ ấm chén và bát đĩa theo phong cách tối giản, màu tự nhiên, men tinh xảo và kích thước đồng bộ.',
  },
  {
    countryCode: 'DE',
    platformBias: { Etsy: 35, Amazon: 65 },
    avgPriceUsd: 35.8,
    topProductTypes: [
      { name: 'Bát & Đĩa gia dụng', sharePct: 38, growthPct: 11.2 },
      { name: 'Cốc & Ly chịu nhiệt', sharePct: 28, growthPct: 9.8 },
      { name: 'Đồ trang trí tối giản', sharePct: 21, growthPct: 8.9 },
      { name: 'Ấm trà & Bình nước', sharePct: 13, growthPct: 6.1 },
    ],
    colors: [
      { name: 'Trắng tinh / Xám đá', sharePct: 42, growthPct: 10.2, swatch: '#E2E8F0' },
      { name: 'Xanh dương nhạt / Slate', sharePct: 24, growthPct: 11.5, swatch: '#0284C7' },
      { name: 'Màu tự nhiên', sharePct: 18, growthPct: 9.4, swatch: '#A8A29E' },
      { name: 'Nâu đất', sharePct: 10, growthPct: 7.8, swatch: '#92400E' },
      { name: 'Màu đa sắc', sharePct: 6, growthPct: 3.4, swatch: '#4F46E5' },
    ],
    shapes: [
      { name: 'Tròn chuẩn công năng', sharePct: 52, growthPct: 9.7 },
      { name: 'Vuông / Chữ nhật xếp gọn', sharePct: 24, growthPct: 10.4 },
      { name: 'Oval', sharePct: 16, growthPct: 7.3 },
      { name: 'Hình dáng nghệ thuật', sharePct: 8, growthPct: 5.1 },
    ],
    materials: [
      { name: 'Sứ bền cao cấp', sharePct: 49, growthPct: 9.9 },
      { name: 'Stoneware (an toàn máy rửa bát)', sharePct: 38, growthPct: 12.8 },
      { name: 'Gốm đất nung', sharePct: 13, growthPct: 5.4 },
    ],
    styles: [
      { name: 'Tối giản & Ứng dụng cao', sharePct: 43, growthPct: 11.5 },
      { name: 'Hiện đại', sharePct: 34, growthPct: 10.2 },
      { name: 'Thủ công', sharePct: 14, growthPct: 8.6 },
      { name: 'Truyền thống', sharePct: 9, growthPct: 3.1 },
    ],
    priceRanges: [
      { label: '$15 – $30', sharePct: 38 },
      { label: '$30 – $60', sharePct: 41 },
      { label: '$60 – $100', sharePct: 15 },
      { label: '> $100', sharePct: 6 },
    ],
    summaryNote:
      'Khách hàng Đức đề cao thiết kế đơn giản, tính ứng dụng cao (dùng được với máy rửa bát, lò vi sóng) và màu trắng/xám thanh lịch.',
  },
  {
    countryCode: 'FR',
    platformBias: { Etsy: 52, Amazon: 48 },
    avgPriceUsd: 44.2,
    topProductTypes: [
      { name: 'Bình hoa & Đồ trang trí', sharePct: 36, growthPct: 13.7 },
      { name: 'Đĩa & Khay phục vụ', sharePct: 29, growthPct: 10.1 },
      { name: 'Đồ thủ công mỹ nghệ', sharePct: 21, growthPct: 14.2 },
      { name: 'Cốc & Ấm trà', sharePct: 14, growthPct: 7.8 },
    ],
    colors: [
      { name: 'Trắng kem / Men rạn', sharePct: 31, growthPct: 10.8, swatch: '#FEFCE8' },
      { name: 'Xanh Olive / Lam cổ', sharePct: 26, growthPct: 13.9, swatch: '#0D9488' },
      { name: 'Màu tự nhiên / Vàng đất', sharePct: 22, growthPct: 12.1, swatch: '#D97706' },
      { name: 'Màu đa sắc nghệ thuật', sharePct: 14, growthPct: 11.4, swatch: '#4F46E5' },
      { name: 'Nâu trầm', sharePct: 7, growthPct: 5.5, swatch: '#78350F' },
    ],
    shapes: [
      { name: 'Hình dáng nghệ thuật', sharePct: 35, growthPct: 14.9 },
      { name: 'Tròn mềm mại', sharePct: 34, growthPct: 8.6 },
      { name: 'Oval cổ điển', sharePct: 22, growthPct: 10.2 },
      { name: 'Vuông', sharePct: 9, growthPct: 4.5 },
    ],
    materials: [
      { name: 'Gốm men thủ công', sharePct: 41, growthPct: 13.4 },
      { name: 'Sứ nghệ thuật', sharePct: 34, growthPct: 9.8 },
      { name: 'Stoneware', sharePct: 25, growthPct: 11.2 },
    ],
    styles: [
      { name: 'Thủ công (Artisan)', sharePct: 39, growthPct: 14.5 },
      { name: 'Truyền thống châu Âu', sharePct: 26, growthPct: 8.1 },
      { name: 'Hiện đại', sharePct: 20, growthPct: 10.4 },
      { name: 'Tối giản', sharePct: 15, growthPct: 9.7 },
    ],
    priceRanges: [
      { label: '$15 – $30', sharePct: 24 },
      { label: '$30 – $60', sharePct: 40 },
      { label: '$60 – $100', sharePct: 26 },
      { label: '> $100', sharePct: 10 },
    ],
    summaryNote:
      'Người tiêu dùng Pháp có xu hướng chi trả cao hơn cho dòng bình hoa, đồ trang trí thủ công giàu tính nghệ thuật trên Etsy.',
  },
  {
    countryCode: 'GB',
    platformBias: { Etsy: 41, Amazon: 59 },
    avgPriceUsd: 36.4,
    topProductTypes: [
      { name: 'Bộ ấm trà & Tách trà', sharePct: 35, growthPct: 10.4 },
      { name: 'Bát đĩa bàn ăn', sharePct: 31, growthPct: 8.7 },
      { name: 'Chậu gốm & Đồ trang trí', sharePct: 22, growthPct: 11.2 },
      { name: 'Cốc sứ in họa tiết', sharePct: 12, growthPct: 6.9 },
    ],
    colors: [
      { name: 'Trắng sứ', sharePct: 34, growthPct: 8.4, swatch: '#F8FAFC' },
      { name: 'Xanh lam cổ điển', sharePct: 28, growthPct: 11.1, swatch: '#1D4ED8' },
      { name: 'Pastel / Kem', sharePct: 20, growthPct: 10.5, swatch: '#E0E7FF' },
      { name: 'Màu tự nhiên', sharePct: 12, growthPct: 7.9, swatch: '#A8A29E' },
      { name: 'Nâu', sharePct: 6, growthPct: 4.8, swatch: '#92400E' },
    ],
    shapes: [
      { name: 'Tròn truyền thống', sharePct: 49, growthPct: 8.9 },
      { name: 'Oval', sharePct: 22, growthPct: 8.1 },
      { name: 'Hình dáng nghệ thuật', sharePct: 17, growthPct: 10.8 },
      { name: 'Vuông', sharePct: 12, growthPct: 5.4 },
    ],
    materials: [
      { name: 'Sứ (Bone China / Porcelain)', sharePct: 52, growthPct: 9.6 },
      { name: 'Stoneware', sharePct: 31, growthPct: 11.4 },
      { name: 'Gốm đất nung', sharePct: 17, growthPct: 7.2 },
    ],
    styles: [
      { name: 'Truyền thống pha hiện đại', sharePct: 36, growthPct: 9.2 },
      { name: 'Hiện đại', sharePct: 27, growthPct: 10.3 },
      { name: 'Thủ công', sharePct: 22, growthPct: 10.9 },
      { name: 'Tối giản', sharePct: 15, growthPct: 7.6 },
    ],
    priceRanges: [
      { label: '$15 – $30', sharePct: 35 },
      { label: '$30 – $60', sharePct: 43 },
      { label: '$60 – $100', sharePct: 16 },
      { label: '> $100', sharePct: 6 },
    ],
    summaryNote:
      'Thị trường Anh duy trì nhu cầu ổn định đối với bộ ấm chén trà chiều chất liệu sứ trắng và họa tiết xanh lam cổ điển.',
  },
  {
    countryCode: 'KR',
    platformBias: { Etsy: 29, Amazon: 71 },
    avgPriceUsd: 33.9,
    topProductTypes: [
      { name: 'Bát đĩa bàn ăn tối giản', sharePct: 36, growthPct: 18.9 },
      { name: 'Cốc cà phê decor tại gia', sharePct: 30, growthPct: 19.6 },
      { name: 'Bình hoa dáng lạ', sharePct: 23, growthPct: 17.2 },
      { name: 'Bộ ấm trà', sharePct: 11, growthPct: 11.4 },
    ],
    colors: [
      { name: 'Trắng sữa / Be mờ', sharePct: 43, growthPct: 20.1, swatch: '#F5F5DC' },
      { name: 'Pastel / Xanh mint', sharePct: 24, growthPct: 18.4, swatch: '#99F6E4' },
      { name: 'Màu tự nhiên / Chấm đá', sharePct: 19, growthPct: 17.6, swatch: '#CBD5E1' },
      { name: 'Nâu ấm', sharePct: 9, growthPct: 12.2, swatch: '#9A3412' },
      { name: 'Màu đa sắc', sharePct: 5, growthPct: 9.8, swatch: '#4F46E5' },
    ],
    shapes: [
      { name: 'Tròn viền lượn / Bất đối xứng', sharePct: 41, growthPct: 19.2 },
      { name: 'Oval mềm', sharePct: 27, growthPct: 17.8 },
      { name: 'Hình dáng nghệ thuật', sharePct: 21, growthPct: 18.5 },
      { name: 'Vuông bo góc', sharePct: 11, growthPct: 12.1 },
    ],
    materials: [
      { name: 'Stoneware men mờ', sharePct: 47, growthPct: 19.4 },
      { name: 'Sứ trắng nhẹ', sharePct: 36, growthPct: 15.8 },
      { name: 'Gốm thủ công', sharePct: 17, growthPct: 14.3 },
    ],
    styles: [
      { name: 'Tối giản trẻ trung', sharePct: 46, growthPct: 20.4 },
      { name: 'Hiện đại', sharePct: 32, growthPct: 17.2 },
      { name: 'Thủ công', sharePct: 16, growthPct: 15.1 },
      { name: 'Truyền thống', sharePct: 6, growthPct: 6.4 },
    ],
    priceRanges: [
      { label: '$15 – $30', sharePct: 45 },
      { label: '$30 – $60', sharePct: 39 },
      { label: '$60 – $100', sharePct: 12 },
      { label: '> $100', sharePct: 4 },
    ],
    summaryNote:
      'Hàn Quốc tăng trưởng nhanh nhất ở phân khúc cốc và bát đĩa men mờ tone be/pastel phục vụ xu hướng Home Café.',
  },
  {
    countryCode: 'AU',
    platformBias: { Etsy: 46, Amazon: 54 },
    avgPriceUsd: 37.2,
    topProductTypes: [
      { name: 'Chậu gốm & Đồ trang trí', sharePct: 35, growthPct: 16.5 },
      { name: 'Bát & Đĩa Stoneware', sharePct: 32, growthPct: 14.8 },
      { name: 'Cốc & Ly gốm', sharePct: 21, growthPct: 13.9 },
      { name: 'Thủ công mỹ nghệ', sharePct: 12, growthPct: 11.5 },
    ],
    colors: [
      { name: 'Nâu đất / Terracotta', sharePct: 31, growthPct: 16.8, swatch: '#C2410C' },
      { name: 'Màu tự nhiên / Cát biển', sharePct: 28, growthPct: 15.4, swatch: '#D6D3D1' },
      { name: 'Xanh biển / Teal', sharePct: 21, growthPct: 14.9, swatch: '#0D9488' },
      { name: 'Trắng kem', sharePct: 14, growthPct: 11.2, swatch: '#F8FAFC' },
      { name: 'Màu đa sắc', sharePct: 6, growthPct: 8.7, swatch: '#4F46E5' },
    ],
    shapes: [
      { name: 'Tròn tự nhiên', sharePct: 45, growthPct: 14.6 },
      { name: 'Hình dáng nghệ thuật', sharePct: 26, growthPct: 16.1 },
      { name: 'Oval', sharePct: 18, growthPct: 12.8 },
      { name: 'Vuông', sharePct: 11, growthPct: 9.2 },
    ],
    materials: [
      { name: 'Stoneware bền thời tiết', sharePct: 44, growthPct: 16.3 },
      { name: 'Gốm đất nung', sharePct: 33, growthPct: 15.2 },
      { name: 'Sứ', sharePct: 23, growthPct: 11.4 },
    ],
    styles: [
      { name: 'Thủ công & Bền vững', sharePct: 35, growthPct: 16.4 },
      { name: 'Hiện đại', sharePct: 31, growthPct: 14.7 },
      { name: 'Tối giản', sharePct: 24, growthPct: 13.9 },
      { name: 'Truyền thống', sharePct: 10, growthPct: 6.8 },
    ],
    priceRanges: [
      { label: '$15 – $30', sharePct: 33 },
      { label: '$30 – $60', sharePct: 43 },
      { label: '$60 – $100', sharePct: 18 },
      { label: '> $100', sharePct: 6 },
    ],
    summaryNote:
      'Người tiêu dùng Úc chuộng chất liệu tự nhiên, gam màu đất nung/xanh biển cho đồ trang trí sân vườn và bàn ăn gia đình.',
  },
  {
    countryCode: 'CA',
    platformBias: { Etsy: 43, Amazon: 57 },
    avgPriceUsd: 35.1,
    topProductTypes: [
      { name: 'Bát đĩa sử dụng hằng ngày', sharePct: 37, growthPct: 12.2 },
      { name: 'Cốc gốm giữ nhiệt', sharePct: 27, growthPct: 11.6 },
      { name: 'Đồ trang trí nội thất', sharePct: 23, growthPct: 12.8 },
      { name: 'Sản phẩm thủ công', sharePct: 13, growthPct: 9.9 },
    ],
    colors: [
      { name: 'Trắng / Kem ấm', sharePct: 35, growthPct: 10.9, swatch: '#F5F5F0' },
      { name: 'Xanh rừng / Teal', sharePct: 23, growthPct: 12.7, swatch: '#0F766E' },
      { name: 'Nâu gỗ / Đất', sharePct: 21, growthPct: 11.8, swatch: '#78350F' },
      { name: 'Màu tự nhiên', sharePct: 14, growthPct: 10.1, swatch: '#A8A29E' },
      { name: 'Màu đa sắc', sharePct: 7, growthPct: 6.5, swatch: '#4F46E5' },
    ],
    shapes: [
      { name: 'Tròn cổ điển', sharePct: 48, growthPct: 11.2 },
      { name: 'Oval', sharePct: 21, growthPct: 10.4 },
      { name: 'Hình dáng nghệ thuật', sharePct: 18, growthPct: 12.9 },
      { name: 'Vuông', sharePct: 13, growthPct: 8.1 },
    ],
    materials: [
      { name: 'Stoneware', sharePct: 46, growthPct: 12.9 },
      { name: 'Sứ', sharePct: 34, growthPct: 10.3 },
      { name: 'Gốm thủ công', sharePct: 20, growthPct: 11.1 },
    ],
    styles: [
      { name: 'Hiện đại ấm cúng', sharePct: 34, growthPct: 12.1 },
      { name: 'Tối giản', sharePct: 29, growthPct: 11.5 },
      { name: 'Thủ công', sharePct: 25, growthPct: 12.4 },
      { name: 'Truyền thống', sharePct: 12, growthPct: 6.2 },
    ],
    priceRanges: [
      { label: '$15 – $30', sharePct: 37 },
      { label: '$30 – $60', sharePct: 42 },
      { label: '$60 – $100', sharePct: 15 },
      { label: '> $100', sharePct: 6 },
    ],
    summaryNote:
      'Canada chuộng sản phẩm gốm sứ đa năng dùng hằng ngày, chất liệu Stoneware giữ nhiệt tốt với tông màu ấm.',
  },
];

export const TRENDING_TASTE_COMBOS: TrendingTasteCombo[] = [
  {
    id: 'tc-1',
    countryCode: 'US',
    categoryId: 'decor',
    productType: 'Bình hoa gốm dáng hữu cơ',
    color: 'Trắng ngà / Men mờ',
    colorSwatch: '#F5F5F0',
    shape: 'Hình dáng nghệ thuật',
    material: 'Stoneware',
    style: 'Hiện đại',
    avgPriceUsd: 42.5,
    demandGrowthPct: 19.4,
    searchScore: 91,
    status: 'rising',
  },
  {
    id: 'tc-2',
    countryCode: 'JP',
    categoryId: 'tableware',
    productType: 'Bộ ấm chén men tro tự nhiên',
    color: 'Màu tự nhiên / Men tro',
    colorSwatch: '#A8A29E',
    shape: 'Tròn thủ công',
    material: 'Gốm mộc / Sứ',
    style: 'Tối giản',
    avgPriceUsd: 54.0,
    demandGrowthPct: 14.8,
    searchScore: 86,
    status: 'rising',
  },
  {
    id: 'tc-3',
    countryCode: 'KR',
    categoryId: 'household',
    productType: 'Set cốc & đĩa tráng miệng Home Café',
    color: 'Be mờ / Pastel',
    colorSwatch: '#F5F5DC',
    shape: 'Oval viền lượn',
    material: 'Stoneware',
    style: 'Tối giản',
    avgPriceUsd: 28.9,
    demandGrowthPct: 22.1,
    searchScore: 94,
    status: 'rising',
  },
  {
    id: 'tc-4',
    countryCode: 'DE',
    categoryId: 'household',
    productType: 'Bộ bát đĩa xếp gọn chịu nhiệt',
    color: 'Trắng tinh / Xám đá',
    colorSwatch: '#E2E8F0',
    shape: 'Tròn chuẩn',
    material: 'Sứ cao cấp',
    style: 'Tối giản',
    avgPriceUsd: 46.0,
    demandGrowthPct: 11.7,
    searchScore: 79,
    status: 'steady',
  },
  {
    id: 'tc-5',
    countryCode: 'FR',
    categoryId: 'artisan',
    productType: 'Đĩa trang trí vẽ tay Địa Trung Hải',
    color: 'Xanh Olive / Men rạn',
    colorSwatch: '#0D9488',
    shape: 'Hình dáng nghệ thuật',
    material: 'Gốm thủ công',
    style: 'Thủ công',
    avgPriceUsd: 58.0,
    demandGrowthPct: 16.2,
    searchScore: 83,
    status: 'rising',
  },
  {
    id: 'tc-6',
    countryCode: 'AU',
    categoryId: 'decor',
    productType: 'Chậu gốm Terracotta sân vườn',
    color: 'Nâu đất nung',
    colorSwatch: '#C2410C',
    shape: 'Tròn cổ điển',
    material: 'Gốm đất nung',
    style: 'Thủ công',
    avgPriceUsd: 39.0,
    demandGrowthPct: 17.5,
    searchScore: 84,
    status: 'rising',
  },
  {
    id: 'tc-7',
    countryCode: 'GB',
    categoryId: 'tableware',
    productType: 'Bộ ấm tách trà hoa lam cổ điển',
    color: 'Xanh lam / Trắng sứ',
    colorSwatch: '#1D4ED8',
    shape: 'Tròn truyền thống',
    material: 'Sứ',
    style: 'Truyền thống',
    avgPriceUsd: 49.5,
    demandGrowthPct: 9.2,
    searchScore: 75,
    status: 'steady',
  },
  {
    id: 'tc-8',
    countryCode: 'CA',
    categoryId: 'household',
    productType: 'Cốc gốm giữ nhiệt tay cầm rộng',
    color: 'Xanh rừng / Nâu ấm',
    colorSwatch: '#0F766E',
    shape: 'Tròn cổ điển',
    material: 'Stoneware',
    style: 'Hiện đại',
    avgPriceUsd: 26.5,
    demandGrowthPct: 13.1,
    searchScore: 78,
    status: 'steady',
  },
  {
    id: 'tc-9',
    countryCode: 'US',
    categoryId: 'household',
    productType: 'Bộ đĩa vuông họa tiết men bóng dày',
    color: 'Màu đa sắc cổ',
    colorSwatch: '#64748B',
    shape: 'Vuông',
    material: 'Sứ nặng',
    style: 'Truyền thống',
    avgPriceUsd: 34.0,
    demandGrowthPct: -3.8,
    searchScore: 54,
    status: 'cooling',
  },
];
