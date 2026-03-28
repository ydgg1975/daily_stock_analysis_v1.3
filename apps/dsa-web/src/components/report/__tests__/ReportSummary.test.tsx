import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReportSummary } from '../ReportSummary';
import type { AnalysisReport } from '../../../types/analysis';

vi.mock('../StandardReportPanel', () => ({
  StandardReportPanel: () => <div data-testid="standard-report-panel">standard report panel</div>,
}));

vi.mock('../ReportNews', () => ({
  ReportNews: () => <div data-testid="legacy-report-news">legacy report news</div>,
}));

vi.mock('../ReportDetails', () => ({
  ReportDetails: () => <div data-testid="report-details">report details</div>,
}));

const report: AnalysisReport = {
  meta: {
    queryId: 'q2',
    stockCode: 'NVDA',
    stockName: 'NVIDIA',
    reportType: 'full',
    createdAt: '2026-03-28T21:35:00+08:00',
    id: 99,
  },
  summary: {
    analysisSummary: '等待确认',
    operationAdvice: '观望',
    trendPrediction: '看空',
    sentimentScore: 42,
  },
  strategy: {},
  details: {
    standardReport: {
      summaryPanel: {
        stock: 'NVIDIA (NVDA)',
        ticker: 'NVDA',
        score: 42,
        currentPrice: '167.52',
        changeAmount: '-4.76',
        changePct: '-2.76%',
        marketTime: '2026-03-27 16:00:00 EDT',
        marketSessionDate: '2026-03-27',
        sessionLabel: '上一已收盘交易日',
        operationAdvice: '观望',
        trendPrediction: '看空',
        oneSentence: '短线承压，等待趋势企稳',
      },
      market: { consistencyWarnings: [] },
      tableSections: {},
      visualBlocks: {},
      highlights: {},
      battlePlanCompact: { cards: [], notes: [], warnings: [] },
      checklistItems: [],
    },
  },
};

describe('ReportSummary', () => {
  it('suppresses legacy news block when standard report layout is active', () => {
    render(<ReportSummary data={report} isHistory />);

    expect(screen.getByTestId('standard-report-panel')).toBeInTheDocument();
    expect(screen.getByTestId('report-details')).toBeInTheDocument();
    expect(screen.queryByTestId('legacy-report-news')).not.toBeInTheDocument();
  });
});
