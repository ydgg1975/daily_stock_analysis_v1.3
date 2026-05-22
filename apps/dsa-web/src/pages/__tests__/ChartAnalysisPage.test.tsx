import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChartAnalysisPage from '../ChartAnalysisPage';

const { mockGetChartAnalysis } = vi.hoisted(() => ({
  mockGetChartAnalysis: vi.fn(),
}));

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getChartAnalysis: mockGetChartAnalysis,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockGetChartAnalysis.mockResolvedValue({
    stockCode: 'AAPL',
    source: 'test',
    requestedDays: 60,
    status: 'ok',
    imageFormat: 'svg',
    svg: '<svg data-testid="inner-chart-svg"></svg>',
    svgOmitted: false,
    svgLength: 39,
    metadata: {
      latestClose: 304.99,
      support: 264.82,
      resistance: 305.54,
      pattern: { name: 'five_bar_breakout', confidence: 0.72 },
      visualSignal: 'bullish',
      indicatorSignal: 'bullish_overextended',
      conflicts: [
        {
          type: 'signal_conflict',
          visualSignal: 'bullish',
          indicatorSignal: 'bullish_overextended',
          message: 'Chart and indicator conflict.',
        },
      ],
    },
  });
});

describe('ChartAnalysisPage', () => {
  it('loads and renders chart analysis preview', async () => {
    render(<ChartAnalysisPage />);

    expect(await screen.findByText('AAPL 차트')).toBeInTheDocument();
    expect(screen.getByText('차트 상승')).toBeInTheDocument();
    expect(screen.getByText('지표 상승 과열')).toBeInTheDocument();
    expect(screen.getByText('5봉 돌파')).toBeInTheDocument();
    expect(screen.getByTestId('chart-svg-preview').innerHTML).toContain('<svg');
  });

  it('runs analysis for submitted stock code', async () => {
    render(<ChartAnalysisPage />);
    await screen.findByText('AAPL 차트');

    fireEvent.change(screen.getByPlaceholderText('AAPL'), { target: { value: 'MSFT' } });
    fireEvent.click(screen.getByRole('button', { name: '차트 분석' }));

    await waitFor(() => {
      expect(mockGetChartAnalysis).toHaveBeenLastCalledWith('MSFT', 60, true);
    });
  });
});
