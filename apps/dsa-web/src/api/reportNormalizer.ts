import type { AnalysisReport, ReportMeta, ReportSummary } from '../types/analysis';

interface ReportMetaFallback extends Partial<ReportMeta> {
  queryId?: string;
  stockCode?: string;
  stockName?: string;
  createdAt?: string;
}

const DEFAULT_SENTIMENT_SCORE = 50;

const toFiniteNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

export const normalizeAnalysisReport = (
  report: AnalysisReport,
  fallbackMeta: ReportMetaFallback = {},
): AnalysisReport => {
  const meta = report.meta || ({} as ReportMeta);
  const summary = report.summary || ({} as ReportSummary);

  const sentimentScore = toFiniteNumber(summary.sentimentScore) ?? DEFAULT_SENTIMENT_SCORE;

  return {
    ...report,
    meta: {
      ...meta,
      queryId: meta.queryId || fallbackMeta.queryId || '',
      stockCode: meta.stockCode || fallbackMeta.stockCode || '',
      stockName: meta.stockName || fallbackMeta.stockName || meta.stockCode || fallbackMeta.stockCode || '',
      reportType: meta.reportType || 'detailed',
      createdAt: meta.createdAt || fallbackMeta.createdAt || '',
    },
    summary: {
      ...summary,
      analysisSummary: summary.analysisSummary || '',
      operationAdvice: summary.operationAdvice || '',
      trendPrediction: summary.trendPrediction || '',
      sentimentScore,
    },
  };
};
