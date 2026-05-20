import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import BacktestPage from '../BacktestPage';



const {

  mockGetResults,

  mockGetOverallPerformance,

  mockGetStockPerformance,

  mockRun,

} = vi.hoisted(() => ({

  mockGetResults: vi.fn(),

  mockGetOverallPerformance: vi.fn(),

  mockGetStockPerformance: vi.fn(),

  mockRun: vi.fn(),

}));



vi.mock('../../api/backtest', () => ({

  backtestApi: {

    getResults: mockGetResults,

    getOverallPerformance: mockGetOverallPerformance,

    getStockPerformance: mockGetStockPerformance,

    run: mockRun,

  },

}));



const basePerformance = {

  scope: 'overall',

  evalWindowDays: 10,

  engineVersion: 'test-engine',

  totalEvaluations: 3,

  completedCount: 2,

  insufficientCount: 1,

  longCount: 2,

  cashCount: 1,

  winCount: 1,

  lossCount: 1,

  neutralCount: 0,

  directionAccuracyPct: 66.7,

  winRatePct: 50,

  neutralRatePct: 0,

  avgStockReturnPct: 2.4,

  avgSimulatedReturnPct: 1.2,

  stopLossTriggerRate: 10,

  takeProfitTriggerRate: 20,

  ambiguousRate: 0,

  avgDaysToFirstHit: 3.5,

  adviceBreakdown: {},

  diagnostics: {},

};



beforeEach(() => {

  vi.clearAllMocks();

  mockGetOverallPerformance.mockResolvedValue(basePerformance);

  mockGetStockPerformance.mockResolvedValue(null);

  mockGetResults.mockResolvedValue({

    total: 1,

    page: 1,

    limit: 20,

    items: [

      {

        analysisHistoryId: 101,

        code: '600519',

        stockName: '구이저우마오타이',

        analysisDate: '2026-03-20',

        evalWindowDays: 10,

        engineVersion: 'test-engine',

        evalStatus: 'completed',

        operationAdvice: '계속 보유',

        trendPrediction: '박스권 우상향',

        actualMovement: 'up',

        actualReturnPct: 3.8,

        directionExpected: 'long',

        directionCorrect: true,

        outcome: 'win',

        simulatedReturnPct: 3.8,

      },

    ],

  });

  mockRun.mockResolvedValue({

    processed: 1,

    saved: 1,

    completed: 1,

    insufficient: 0,

    errors: 0,

  });

});



describe('BacktestPage', () => {

  it('renders shared surface inputs and prediction tracking outputs', async () => {

    render(<BacktestPage />);



    const filterInput = await screen.findByPlaceholderText('종목 코드 필터 (비우면 전체)');

    const windowInput = screen.getByPlaceholderText('10');



    expect(filterInput).toHaveClass('input-surface');

    expect(filterInput).toHaveClass('input-focus-glow');

    expect(windowInput).toHaveClass('input-surface');

    expect(windowInput).toHaveClass('input-focus-glow');



    expect(await screen.findByText('WIN')).toBeInTheDocument();

    expect(screen.getByText('completed')).toBeInTheDocument();

    expect(screen.getByText('600519')).toBeInTheDocument();

    expect(screen.getByText('구이저우마오타이')).toBeInTheDocument();

    expect(screen.getByText('박스권 우상향')).toBeInTheDocument();

    expect(screen.getByText('UP')).toBeInTheDocument();

    expect(screen.getByText('Window Return')).toBeInTheDocument();

    expect(screen.getByText('Direction Match')).toBeInTheDocument();

    expect(screen.getAllByLabelText('yes').length).toBeGreaterThan(0);

  });



  it('filters results with stock code, window, and analysis date range when clicking Filter', async () => {

    render(<BacktestPage />);



    const filterInput = await screen.findByPlaceholderText('종목 코드 필터 (비우면 전체)');

    const windowInput = screen.getByPlaceholderText('10');

    const fromInput = screen.getByLabelText('분석 시작일');

    const toInput = screen.getByLabelText('분석 종료일');



    fireEvent.change(filterInput, { target: { value: 'aapl' } });

    fireEvent.change(windowInput, { target: { value: '20' } });

    fireEvent.change(fromInput, { target: { value: '2026-03-01' } });

    fireEvent.change(toInput, { target: { value: '2026-03-31' } });

    fireEvent.click(screen.getByRole('button', { name: '필터' }));



    await waitFor(() => {

      expect(mockGetResults).toHaveBeenLastCalledWith({

        code: 'AAPL',

        evalWindowDays: 20,

        analysisDateFrom: '2026-03-01',

        analysisDateTo: '2026-03-31',

        page: 1,

        limit: 20,

      });

      expect(mockGetStockPerformance).toHaveBeenLastCalledWith('AAPL', {

        evalWindowDays: 20,

        analysisDateFrom: '2026-03-01',

        analysisDateTo: '2026-03-31',

      });

    });

  });



  it('runs a backtest and refreshes results using the shared filter values', async () => {

    render(<BacktestPage />);



    const filterInput = await screen.findByPlaceholderText('종목 코드 필터 (비우면 전체)');

    const windowInput = screen.getByPlaceholderText('10');



    fireEvent.change(filterInput, { target: { value: 'tsla' } });

    fireEvent.change(windowInput, { target: { value: '15' } });

    fireEvent.click(screen.getByRole('button', { name: '백테스트 실행' }));



    await waitFor(() => {

      expect(mockRun).toHaveBeenCalledWith({

        code: 'TSLA',

        force: undefined,

        minAgeDays: undefined,

        evalWindowDays: 15,

      });

    });



    await waitFor(() => {

      expect(mockGetResults).toHaveBeenLastCalledWith({

        code: 'TSLA',

        evalWindowDays: 15,

        analysisDateFrom: undefined,

        analysisDateTo: undefined,

        page: 1,

        limit: 20,

      });

      expect(mockGetStockPerformance).toHaveBeenLastCalledWith('TSLA', {

        evalWindowDays: 15,

        analysisDateFrom: undefined,

        analysisDateTo: undefined,

      });

    });



    expect(await screen.findByText('Processed:')).toBeInTheDocument();

    expect(screen.getByText('Saved:')).toBeInTheDocument();

  });



  it('switches to next-day validation with the 1D shortcut', async () => {

    render(<BacktestPage />);



    await screen.findByPlaceholderText('종목 코드 필터 (비우면 전체)');

    fireEvent.click(screen.getByRole('button', { name: '1일 검증' }));



    await waitFor(() => {

      expect(mockGetResults).toHaveBeenLastCalledWith({

        code: undefined,

        evalWindowDays: 1,

        analysisDateFrom: undefined,

        analysisDateTo: undefined,

        page: 1,

        limit: 20,

      });

      expect(mockGetOverallPerformance).toHaveBeenLastCalledWith({

        evalWindowDays: 1,

        analysisDateFrom: undefined,

        analysisDateTo: undefined,

      });

    });



    expect(screen.getByText('Actual')).toBeInTheDocument();

    expect(screen.getByText('Accuracy')).toBeInTheDocument();

    expect(screen.getByText('다음 거래일 검증 모드는 AI 예측과 다음 거래일 종가를 비교합니다.')).toBeInTheDocument();

  });

});
