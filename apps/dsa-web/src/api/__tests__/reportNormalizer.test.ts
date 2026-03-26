import { describe, expect, it } from 'vitest';
import type { AnalysisReport } from '../../types/analysis';
import { normalizeAnalysisReport } from '../reportNormalizer';

describe('normalizeAnalysisReport', () => {
  it('fills required summary fields and defaults sentiment score when missing', () => {
    const report = {
      meta: {
        queryId: 'q1',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'detailed',
        createdAt: '2026-03-26T00:00:00Z',
      },
      summary: {
        analysisSummary: undefined,
        operationAdvice: undefined,
        trendPrediction: undefined,
        sentimentScore: undefined,
      },
    } as unknown as AnalysisReport;

    const normalized = normalizeAnalysisReport(report);

    expect(normalized.summary.analysisSummary).toBe('');
    expect(normalized.summary.operationAdvice).toBe('');
    expect(normalized.summary.trendPrediction).toBe('');
    expect(normalized.summary.sentimentScore).toBe(50);
  });

  it('uses top-level fallback metadata when report.meta fields are missing', () => {
    const report = {
      meta: {
        queryId: '',
        stockCode: '',
        stockName: '',
        reportType: undefined,
        createdAt: '',
      },
      summary: {
        analysisSummary: 'ok',
        operationAdvice: 'hold',
        trendPrediction: 'up',
        sentimentScore: 62,
      },
    } as unknown as AnalysisReport;

    const normalized = normalizeAnalysisReport(report, {
      queryId: 'q-fallback',
      stockCode: 'MSFT',
      stockName: 'Microsoft',
      createdAt: '2026-03-26T08:00:00+08:00',
    });

    expect(normalized.meta.queryId).toBe('q-fallback');
    expect(normalized.meta.stockCode).toBe('MSFT');
    expect(normalized.meta.stockName).toBe('Microsoft');
    expect(normalized.meta.reportType).toBe('detailed');
    expect(normalized.meta.createdAt).toBe('2026-03-26T08:00:00+08:00');
  });
});
