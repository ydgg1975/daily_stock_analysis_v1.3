import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi, DuplicateTaskError } from '../../api/analysis';
import { agentApi } from '../../api/agent';
import { historyApi } from '../../api/history';
import { systemConfigApi } from '../../api/systemConfig';
import { useStockPoolStore } from '../../stores';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import HomePage from '../HomePage';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('../../api/history', () => ({
  historyApi: {
    getList: vi.fn(),
    getDetail: vi.fn(),
    deleteRecords: vi.fn(),
    getNews: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    getMarkdown: vi.fn().mockResolvedValue('# report'),
  },
}));

vi.mock('../../api/analysis', async () => {
  const actual = await vi.importActual<typeof import('../../api/analysis')>('../../api/analysis');
  return {
    ...actual,
    analysisApi: {
      analyzeAsync: vi.fn(),
      triggerMarketReview: vi.fn(),
      getStatus: vi.fn(),
    },
  };
});

vi.mock('../../api/systemConfig', () => ({
  systemConfigApi: {
    getSetupStatus: vi.fn(),
  },
}));

vi.mock('../../api/agent', () => ({
  agentApi: {
    getSkills: vi.fn(),
  },
}));

vi.mock('../../hooks/useTaskStream', () => ({
  useTaskStream: vi.fn(),
}));

const historyItem = {
  id: 1,
  queryId: 'q-1',
  stockCode: '600519',
  stockName: 'guizhoumaotai',
  sentimentScore: 82,
  operationAdvice: 'mairu',
  createdAt: '2026-03-18T08:00:00Z',
};

const historyReport = {
  meta: {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: 'guizhoumaotai',
    reportType: 'detailed' as const,
    reportLanguage: 'zh' as const,
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: 'qushiweichiqiangshi',
    operationAdvice: 'jixuguanchamaidian',
    trendPrediction: 'duanxianzhendangpianqiang',
    sentimentScore: 78,
  },
};

const marketReviewHistoryItem = {
  id: 2,
  queryId: 'market-review-q-1',
  stockCode: 'MARKET',
  stockName: '\uC2DC\uC7A5 \uB9AC\uBDF0',
  reportType: 'market_review' as const,
  createdAt: '2026-03-18T08:00:00Z',
};

const marketReviewHistoryReport = {
  meta: {
    id: 2,
    queryId: 'market-review-q-1',
    stockCode: 'MARKET',
    stockName: '\uC2DC\uC7A5 \uB9AC\uBDF0',
    reportType: 'market_review' as const,
    reportLanguage: 'zh' as const,
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: '\uC2DC\uC7A5 \uB9AC\uBDF0 \uC694\uC57D',
    operationAdvice: 'chakanfupan',
    trendPrediction: '\uC2DC\uC7A5 \uB9AC\uBDF0',
    sentimentScore: 50,
  },
};

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    useStockPoolStore.getState().resetDashboardState();
    vi.mocked(agentApi.getSkills).mockResolvedValue({ skills: [], default_skill_id: '' });
    vi.mocked(systemConfigApi.getSetupStatus).mockResolvedValue({
      isComplete: true,
      readyForSmoke: true,
      requiredMissingKeys: [],
      nextStepKey: null,
      checks: [],
    });
  });

  it('renders the dashboard workspace and auto-loads the first report', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const dashboard = await screen.findByTestId('home-dashboard');
    expect(dashboard).toBeInTheDocument();
    expect(dashboard.className).toContain('h-[calc(100vh-5rem)]');
    expect(dashboard.className).toContain('lg:h-[calc(100vh-2rem)]');
    expect(dashboard.firstElementChild?.className).toContain('min-h-0');
    expect(dashboard.querySelector('.flex-1.flex.min-h-0.overflow-hidden')).toBeTruthy();
    expect(screen.getByTestId('home-dashboard-scroll')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('\uC885\uBAA9 \uCF54\uB4DC\uB098 \uC774\uB984\uC744 \uC785\uB825\uD558\uC138\uC694. \uC608: KR005930, AAPL')).toBeInTheDocument();
    expect(await screen.findByText('qushiweichiqiangshi')).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: getReportText(normalizeReportLanguage(historyReport.meta.reportLanguage)).fullReport,
      }),
    ).toBeInTheDocument();
  });

  it('shows the empty report workspace when history is empty', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('\uBD84\uC11D \uC2DC\uC791')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '\uBD84\uC11D \uC2DC\uC791', level: 3 })).toBeInTheDocument();
    expect(screen.getByText('\uC885\uBAA9 \uCF54\uB4DC\uB97C \uC785\uB825\uD574 \uBD84\uC11D\uD558\uAC70\uB098 \uC67C\uCABD\uC5D0\uC11C \uC774\uC804 \uB9AC\uD3EC\uD2B8\uB97C \uC120\uD0DD\uD558\uC138\uC694.')).toBeInTheDocument();
    expect(screen.getByText('\uC544\uC9C1 \uBD84\uC11D \uAE30\uB85D\uC774 \uC5C6\uC2B5\uB2C8\uB2E4')).toBeInTheDocument();
  });

  it('surfaces duplicate task warnings from dashboard submission', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(
      new DuplicateTaskError('600519', 'task-1', '\uC885\uBAA9 600519\uAC00 \uC774\uBBF8 \uBD84\uC11D \uC911\uC785\uB2C8\uB2E4'),
    );

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('\uC885\uBAA9 \uCF54\uB4DC\uB098 \uC774\uB984\uC744 \uC785\uB825\uD558\uC138\uC694. \uC608: KR005930, AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '\uBD84\uC11D' }));

    await waitFor(() => {
      expect(screen.getByText('\uC791\uC5C5\uC774 \uC774\uBBF8 \uC788\uC2B5\uB2C8\uB2E4')).toBeInTheDocument();
    });
    expect(screen.getByText('\uC791\uC5C5\uC774 \uC774\uBBF8 \uC788\uC2B5\uB2C8\uB2E4').closest('[role="alert"]')).toBeInTheDocument();
  });

  it('submits market review from the home toolbar', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '\uC2DC\uC7A5 \uB9AC\uBDF0 \uC791\uC5C5\uC774 \uC81C\uCD9C\uB418\uC5C8\uC2B5\uB2C8\uB2E4',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: 'shichangfupanbaogaoshiliwenben',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\uC2DC\uC7A5 \uB9AC\uBDF0' }));

    await waitFor(() => {
      expect(analysisApi.triggerMarketReview).toHaveBeenCalledWith({ sendNotification: true });
    });
    expect(await screen.findByText('\uC2DC\uC7A5 \uB9AC\uBDF0 \uC644\uB8CC')).toBeInTheDocument();
    expect(await screen.findByText('shichangfupanbaogaoshiliwenben')).toBeInTheDocument();
    expect(analysisApi.getStatus).toHaveBeenCalledWith('task-1');
  });

  it('scrolls the dashboard to market review feedback after toolbar clicks', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '\uC2DC\uC7A5 \uB9AC\uBDF0 \uC791\uC5C5\uC774 \uC81C\uCD9C\uB418\uC5C8\uC2B5\uB2C8\uB2E4',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: 'shichangfupanbaogaoshiliwenben',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByText('qushiweichiqiangshi');
    const dashboardScroll = screen.getByTestId('home-dashboard-scroll');
    const scrollToMock = vi.fn(function scrollTo(this: HTMLElement, options?: ScrollToOptions) {
      if (typeof options?.top === 'number') {
        this.scrollTop = options.top;
      }
    });
    Object.defineProperty(dashboardScroll, 'scrollTo', {
      configurable: true,
      value: scrollToMock,
    });
    dashboardScroll.scrollTop = 480;

    fireEvent.click(screen.getByRole('button', { name: '\uC2DC\uC7A5 \uB9AC\uBDF0' }));

    await waitFor(() => {
      expect(scrollToMock).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
    });
    expect(dashboardScroll.scrollTop).toBe(0);
    expect(await screen.findByText('\uC2DC\uC7A5 \uB9AC\uBDF0 \uC644\uB8CC')).toBeInTheDocument();
  });

  it('keeps market review results in the main dashboard scroll area', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.triggerMarketReview).mockResolvedValue({
      status: 'accepted',
      sendNotification: true,
      message: '\uC2DC\uC7A5 \uB9AC\uBDF0 \uC791\uC5C5\uC774 \uC81C\uCD9C\uB418\uC5C8\uC2B5\uB2C8\uB2E4',
      taskId: 'task-1',
    });
    vi.mocked(analysisApi.getStatus).mockResolvedValue({
      taskId: 'task-1',
      status: 'completed',
      marketReviewReport: Array.from({ length: 30 }, (_, index) => `di ${index + 1} xingfupanneirong`).join('\n'),
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\uC2DC\uC7A5 \uB9AC\uBDF0' }));

    const dashboardScroll = screen.getByTestId('home-dashboard-scroll');
    const marketReviewReport = await screen.findByTestId('market-review-report');
    expect(dashboardScroll).toContainElement(marketReviewReport);
    expect(marketReviewReport.className).not.toContain('max-h-64');
    expect(marketReviewReport.className).not.toContain('overflow-y-auto');
    expect(await screen.findByText('\uBD84\uC11D \uC2DC\uC791')).toBeInTheDocument();
  });

  it('shows first-run setup gaps and links to settings', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(systemConfigApi.getSetupStatus).mockResolvedValue({
      isComplete: false,
      readyForSmoke: false,
      requiredMissingKeys: ['llm_primary', 'stock_list'],
      nextStepKey: 'llm_primary',
      checks: [
        {
          key: 'llm_primary',
          title: 'LLM \uC8FC\uCC44\uB110',
          category: 'ai_model',
          required: true,
          status: 'needs_action',
          message: 'queshaozhumoxingpeizhi',
        },
        {
          key: 'stock_list',
          title: '\uAD00\uC2EC \uC885\uBAA9',
          category: 'base',
          required: true,
          status: 'needs_action',
          message: '\uAD00\uC2EC \uC885\uBAA9\uC774 \uBD80\uC871\uD569\uB2C8\uB2E4',
        },
      ],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('\uAE30\uBCF8 \uC124\uC815 \uBBF8\uC644\uB8CC')).toBeInTheDocument();
    expect(screen.getByText(/LLM \uC8FC\uCC44\uB110\u3001\uAD00\uC2EC \uC885\uBAA9/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\uC124\uC815\uC73C\uB85C \uC774\uB3D9' }));
    expect(navigateMock).toHaveBeenCalledWith('/settings');
  });

  it('navigates to chat with report context when asking a follow-up question', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const followUpButton = await screen.findByRole('button', { name: 'AI\uC5D0\uAC8C \uC774\uC5B4\uC11C \uC9C8\uBB38' });
    fireEvent.click(followUpButton);

    expect(navigateMock).toHaveBeenCalledWith(
      '/chat?stock=600519&name=guizhoumaotai&recordId=1',
    );
  });

  it('confirms and deletes selected history from the dashboard state flow', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(historyApi.deleteRecords).mockResolvedValue({ deleted: 1 });

    useStockPoolStore.setState({
      historyItems: [historyItem],
      selectedHistoryIds: [1],
      selectedReport: historyReport,
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\uC120\uD0DD \uC0AD\uC81C' }));

    expect(
      await screen.findByText('\uC774 \uBD84\uC11D \uAE30\uB85D\uC744 \uC0AD\uC81C\uD558\uC2DC\uACA0\uC2B5\uB2C8\uAE4C? \uC0AD\uC81C \uD6C4\uC5D0\uB294 \uBCF5\uAD6C\uD560 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4.'),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\uC0AD\uC81C' }));

    await waitFor(() => {
      expect(historyApi.deleteRecords).toHaveBeenCalledWith([1]);
    });
  });

  it('opens and closes the mobile history drawer without changing dashboard styles', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const trigger = await screen.findByRole('button', { name: '\uBD84\uC11D \uAE30\uB85D' });
    fireEvent.click(trigger);

    expect(container.querySelector('.page-drawer-overlay')).toBeTruthy();
    expect(container.querySelector('.dashboard-card')).toBeTruthy();

    fireEvent.click(container.querySelector('.fixed.inset-0.z-40') as HTMLElement);

    await waitFor(() => {
      expect(container.querySelector('.page-drawer-overlay')).toBeFalsy();
    });
  });

  it('renders active task panel content from dashboard state', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    useStockPoolStore.setState({
      activeTasks: [
        {
          taskId: 'task-1',
          stockCode: '600519',
          stockName: 'guizhoumaotai',
          status: 'processing',
          progress: 45,
          message: 'zhengzaizhuaquzuixinhangqing',
          reportType: 'detailed',
          createdAt: '2026-03-18T08:00:00Z',
        },
      ],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('\uBD84\uC11D \uC791\uC5C5')).toBeInTheDocument();
    expect(screen.getByText('zhengzaizhuaquzuixinhangqing')).toBeInTheDocument();
  });

  it('triggers reanalyze for the current report even if the search input has other text', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-re-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    // Wait for the report to load
    await screen.findByText('qushiweichiqiangshi');

    // Type something else in the search box
    const input = screen.getByPlaceholderText('\uC885\uBAA9 \uCF54\uB4DC\uB098 \uC774\uB984\uC744 \uC785\uB825\uD558\uC138\uC694. \uC608: KR005930, AAPL');
    fireEvent.change(input, { target: { value: 'AAPL' } });

    // Click "Reanalyze"
    const reanalyzeButton = screen.getByRole('button', { name: '\uB2E4\uC2DC \uBD84\uC11D' });
    fireEvent.click(reanalyzeButton);

    // Verify that analyzeAsync is called with the report's stock code, not the search box text
    expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
      stockCode: '600519',
      originalQuery: '600519',
      forceRefresh: true,
    }));
  });

  it('passes the selected strategy when submitting stock analysis', async () => {
    vi.mocked(agentApi.getSkills).mockResolvedValue({
      default_skill_id: 'bull_trend',
      skills: [
        { id: 'bull_trend', name: '\uAE30\uBCF8 \uB2E4\uC911 \uCD94\uC138', description: '\uCD94\uC138 \uBD84\uC11D' },
        { id: 'growth_quality', name: '\uC131\uC7A5 \uD488\uC9C8', description: '\uC131\uC7A5\uC8FC \uBD84\uC11D' },
      ],
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-strategy-1',
      status: 'pending',
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '\uC804\uB7B5' }));
    fireEvent.click(screen.getByRole('menuitemradio', { name: /\uC131\uC7A5 \uD488\uC9C8/ }));

    const input = screen.getByPlaceholderText('\uC885\uBAA9 \uCF54\uB4DC\uB098 \uC774\uB984\uC744 \uC785\uB825\uD558\uC138\uC694. \uC608: KR005930, AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '\uBD84\uC11D' }));

    await waitFor(() => {
      expect(analysisApi.analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: '600519',
        skills: ['growth_quality'],
      }));
    });
  });

  it('supports keyboard navigation in the strategy menu', async () => {
    vi.mocked(agentApi.getSkills).mockResolvedValue({
      default_skill_id: 'bull_trend',
      skills: [
        { id: 'bull_trend', name: '\uAE30\uBCF8 \uB2E4\uC911 \uCD94\uC138', description: '\uCD94\uC138 \uBD84\uC11D' },
        { id: 'growth_quality', name: '\uC131\uC7A5 \uD488\uC9C8', description: '\uC131\uC7A5\uC8FC \uBD84\uC11D' },
      ],
    });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    const trigger = await screen.findByRole('button', { name: '\uC804\uB7B5' });
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });

    const defaultOption = await screen.findByRole('menuitemradio', { name: /\uAE30\uBCF8 \uC804\uB7B5/ });
    await waitFor(() => {
      expect(defaultOption).toHaveFocus();
    });

    const menu = screen.getByRole('menu');
    fireEvent.keyDown(menu, { key: 'ArrowDown' });
    expect(screen.getByRole('menuitemradio', { name: /\uAE30\uBCF8 \uB2E4\uC911 \uCD94\uC138/ })).toHaveFocus();

    fireEvent.keyDown(menu, { key: 'End' });
    expect(screen.getByRole('menuitemradio', { name: /\uC131\uC7A5 \uD488\uC9C8/ })).toHaveFocus();

    fireEvent.keyDown(menu, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });
    expect(trigger).toHaveFocus();
  });

  it('disables stock reanalysis and follow-up for market review history reports', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [marketReviewHistoryItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(marketReviewHistoryReport);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await screen.findByText('\uC2DC\uC7A5 \uB9AC\uBDF0 \uC694\uC57D');
    const reanalyzeButton = screen.getByRole('button', { name: '\uB2E4\uC2DC \uBD84\uC11D' });
    const followUpButton = screen.getByRole('button', { name: 'AI\uC5D0\uAC8C \uC774\uC5B4\uC11C \uC9C8\uBB38' });

    expect(reanalyzeButton).toBeDisabled();
    expect(followUpButton).toBeDisabled();

    fireEvent.click(reanalyzeButton);
    fireEvent.click(followUpButton);

    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
