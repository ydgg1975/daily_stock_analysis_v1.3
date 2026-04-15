import type { ReportMeta, ReportStrategy, ReportSummary } from './analysis';

export interface PublicAnalysisPreviewReport {
  meta: ReportMeta;
  summary: ReportSummary;
  strategy?: ReportStrategy | null;
  details?: null;
}

export interface PublicAnalysisPreviewResponse {
  queryId: string;
  stockCode: string;
  stockName?: string | null;
  previewScope: 'guest' | string;
  report: PublicAnalysisPreviewReport;
}
