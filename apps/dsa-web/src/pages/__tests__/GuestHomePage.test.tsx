import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import GuestHomePage from '../GuestHomePage';

const { previewMock } = vi.hoisted(() => ({
  previewMock: vi.fn(),
}));

vi.mock('../../api/publicAnalysis', () => ({
  publicAnalysisApi: {
    preview: (...args: unknown[]) => previewMock(...args),
  },
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
  }),
}));

vi.mock('../../components/StockAutocomplete', () => ({
  StockAutocomplete: ({
    value,
    onChange,
    placeholder,
  }: {
    value: string;
    onChange: (value: string) => void;
    placeholder: string;
  }) => (
    <input
      aria-label="guest-stock-input"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
    />
  ),
}));

describe('GuestHomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders locked feature cards and generates a guest preview snapshot', async () => {
    previewMock.mockResolvedValue({
      queryId: 'preview-q1',
      stockCode: 'AAPL',
      stockName: 'Apple',
      previewScope: 'guest',
      report: {
        meta: {
          queryId: 'preview-q1',
          stockCode: 'AAPL',
          stockName: 'Apple',
          reportType: 'brief',
          createdAt: '2026-04-14T10:00:00Z',
        },
        summary: {
          analysisSummary: '趋势延续但需要等待更好的介入点。',
          operationAdvice: '等待回踩',
          trendPrediction: '偏强震荡',
          sentimentScore: 72,
        },
        strategy: {
          idealBuy: '184-186',
          stopLoss: '179',
          takeProfit: '196',
        },
      },
    });

    render(
      <MemoryRouter>
        <GuestHomePage />
      </MemoryRouter>,
    );

    expect(screen.getByText('完整研究报告')).toBeInTheDocument();
    expect(screen.getByText('问股追问')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '创建账户' })).toHaveAttribute('href', '/login?mode=create&redirect=%2F');

    fireEvent.change(screen.getByLabelText('guest-stock-input'), { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByRole('button', { name: '生成简版判断' }));

    await waitFor(() => {
      expect(previewMock).toHaveBeenCalledWith({
        stockCode: 'AAPL',
        stockName: undefined,
        reportType: 'brief',
      });
    });

    expect(await screen.findByText('趋势延续但需要等待更好的介入点。')).toBeInTheDocument();
    expect(screen.getByText('等待回踩')).toBeInTheDocument();
    expect(screen.getByText('偏强震荡')).toBeInTheDocument();
    expect(screen.getByText('184-186')).toBeInTheDocument();
  });
});
