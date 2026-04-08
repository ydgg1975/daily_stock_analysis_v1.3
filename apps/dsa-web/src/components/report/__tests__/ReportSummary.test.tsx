import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ReportSummary } from '../ReportSummary';
import type { AnalysisReport } from '../../../types/analysis';

vi.mock('../StandardReportPanel', () => ({
  StandardReportPanel: ({ showLeadSummary }: { showLeadSummary?: boolean }) => (
    <div data-testid="standard-report-panel" data-show-lead-summary={String(showLeadSummary)}>
      standard report panel
    </div>
  ),
}));

vi.mock('../ReportOverview', () => ({
  ReportOverview: () => <div data-testid="legacy-report-overview">legacy report overview</div>,
}));

vi.mock('../ReportStrategy', () => ({
  ReportStrategy: () => <div data-testid="legacy-report-strategy">legacy report strategy</div>,
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

const legacyOnlyReport: AnalysisReport = {
  meta: {
    queryId: 'q-legacy-only',
    stockCode: 'AAPL',
    stockName: 'Apple',
    reportType: 'full',
    createdAt: '2026-03-28T21:35:00+08:00',
    id: 101,
  },
  summary: {
    analysisSummary: 'legacy summary',
    operationAdvice: '观望',
    trendPrediction: '震荡',
    sentimentScore: 55,
  },
  details: {
    rawResult: {
      signal: 'hold',
    },
  },
};

const legacyEmptyReport: AnalysisReport = {
  meta: {
    queryId: 'q-legacy-empty',
    stockCode: 'TSLA',
    stockName: 'Tesla',
    reportType: 'full',
    createdAt: '2026-03-28T21:35:00+08:00',
    id: 102,
  },
  summary: {
    analysisSummary: '',
    operationAdvice: '',
    trendPrediction: '',
    sentimentScore: 50,
  },
};

describe('ReportSummary', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubEnv('VITE_REPORT_LEGACY_FALLBACK', 'auto');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('suppresses legacy news block when standard report layout is active', () => {
    render(<ReportSummary data={report} />);

    expect(screen.getByTestId('standard-report-panel')).toBeInTheDocument();
    expect(screen.getByTestId('standard-report-panel')).toHaveAttribute('data-show-lead-summary', 'true');
    expect(screen.getByTestId('report-details')).toBeInTheDocument();
    expect(screen.queryByTestId('legacy-report-news')).not.toBeInTheDocument();
  });

  it('suppresses duplicated lead summaries in compact-home mode', () => {
    render(<ReportSummary data={report} leadSummaryMode="compact-home" />);

    expect(screen.getByTestId('standard-report-panel')).toHaveAttribute('data-show-lead-summary', 'false');
    expect(screen.queryByTestId('legacy-report-overview')).not.toBeInTheDocument();
  });

  it('uses guarded legacy fallback in auto mode for legacy_only payloads', () => {
    render(<ReportSummary data={legacyOnlyReport} />);

    expect(screen.queryByTestId('standard-report-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-overview')).toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-news')).toBeInTheDocument();
    expect(screen.getByTestId('report-details')).toBeInTheDocument();
  });

  it('uses guarded legacy fallback in auto mode for legacy_empty payloads', () => {
    render(<ReportSummary data={legacyEmptyReport} />);

    expect(screen.queryByTestId('standard-report-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-overview')).toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-news')).toBeInTheDocument();
    expect(screen.getByTestId('report-details')).toBeInTheDocument();
  });

  it('forces legacy fallback in on mode', () => {
    vi.stubEnv('VITE_REPORT_LEGACY_FALLBACK', 'on');
    render(<ReportSummary data={report} />);

    expect(screen.queryByTestId('standard-report-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-overview')).toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('legacy-report-news')).toBeInTheDocument();
  });

  it('disables fallback in off mode for legacy_only payloads', () => {
    vi.stubEnv('VITE_REPORT_LEGACY_FALLBACK', 'off');
    render(<ReportSummary data={legacyOnlyReport} />);

    expect(screen.getByTestId('report-standard-only-degraded')).toBeInTheDocument();
    expect(screen.getByText('当前模式：off')).toBeInTheDocument();
    expect(screen.queryByTestId('standard-report-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('legacy-report-overview')).not.toBeInTheDocument();
    expect(screen.queryByTestId('legacy-report-strategy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('legacy-report-news')).not.toBeInTheDocument();
    expect(screen.getByTestId('report-details')).toBeInTheDocument();
  });

  it('shows degraded compatibility panel in off mode for legacy_empty payloads', () => {
    vi.stubEnv('VITE_REPORT_LEGACY_FALLBACK', 'off');
    render(<ReportSummary data={legacyEmptyReport} />);

    expect(screen.getByTestId('report-standard-only-degraded')).toBeInTheDocument();
    expect(screen.getByText('当前模式：off')).toBeInTheDocument();
    expect(screen.queryByTestId('standard-report-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('legacy-report-overview')).not.toBeInTheDocument();
    expect(screen.queryByTestId('legacy-report-strategy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('legacy-report-news')).not.toBeInTheDocument();
    expect(screen.getByTestId('report-details')).toBeInTheDocument();
  });

  it('logs fallback observability in test mode when fallback is activated', () => {
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

    render(<ReportSummary data={legacyOnlyReport} />);

    expect(infoSpy).toHaveBeenCalledWith(
      '[report-legacy-fallback]',
      expect.objectContaining({
        payloadVariant: 'legacy_only',
        standardReportSource: 'none',
        fallbackMode: 'auto',
      }),
    );
  });
});
