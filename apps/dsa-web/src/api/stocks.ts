import apiClient from './index';
import { toCamelCase } from './utils';

export type ExtractItem = {
  code?: string | null;
  name?: string | null;
  confidence: string;
};

export type ExtractFromImageResponse = {
  codes: string[];
  items?: ExtractItem[];
  rawText?: string;
};

export type ChartAnalysisMetadata = {
  version?: number;
  latestClose?: number;
  support?: number;
  resistance?: number;
  pattern?: {
    name?: string;
    confidence?: number;
  };
  visualSignal?: string;
  indicatorSignal?: string;
  displayLabels?: {
    pattern?: string;
    visualSignal?: string;
    indicatorSignal?: string;
  };
  conflicts?: Array<{
    type?: string;
    visualSignal?: string;
    indicatorSignal?: string;
    message?: string;
  }>;
};

export type StockChartAnalysisResponse = {
  stockCode: string;
  source?: string | null;
  requestedDays: number;
  status: string;
  imageFormat: string;
  svg?: string | null;
  svgOmitted: boolean;
  svgLength: number;
  metadata: ChartAnalysisMetadata;
  reason?: string | null;
};

export const stocksApi = {
  async extractFromImage(file: File): Promise<ExtractFromImageResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
    const response = await apiClient.post(
      '/api/v1/stocks/extract-from-image',
      formData,
      {
        headers,
        timeout: 60000, // Vision API can be slow; 60s
      },
    );

    const data = response.data as { codes?: string[]; items?: ExtractItem[]; raw_text?: string };
    return {
      codes: data.codes ?? [],
      items: data.items,
      rawText: data.raw_text,
    };
  },

  async parseImport(file?: File, text?: string): Promise<ExtractFromImageResponse> {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
      const response = await apiClient.post('/api/v1/stocks/parse-import', formData, { headers });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    if (text) {
      const response = await apiClient.post('/api/v1/stocks/parse-import', { text });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    throw new Error('파일을 선택하거나 텍스트를 붙여넣어 주세요');
  },

  async getChartAnalysis(stockCode: string, days = 90, includeSvg = true): Promise<StockChartAnalysisResponse> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/chart-analysis`, {
      params: {
        days,
        include_svg: includeSvg,
      },
    });
    return toCamelCase<StockChartAnalysisResponse>(response.data);
  },
};
