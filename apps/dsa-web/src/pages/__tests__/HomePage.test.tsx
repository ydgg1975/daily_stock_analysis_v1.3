import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi, DuplicateTaskError } from '../../api/analysis';
import { historyApi } from '../../api/history';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { ShellRailHarness } from '../../test-utils/ShellRailHarness';
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
    },
  };
});

vi.mock('../../hooks/useTaskStream', () => ({
  useTaskStream: vi.fn(),
}));

const historyItem = {
  id: 1,
  queryId: 'q-1',
  stockCode: '600519',
  stockName: '贵州茅台',
  sentimentScore: 82,
  operationAdvice: '买入',
  createdAt: '2026-03-18T08:00:00Z',
};

const historyReport = {
  meta: {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: '贵州茅台',
    reportType: 'detailed' as const,
    reportLanguage: 'zh' as const,
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: '趋势维持强势',
    operationAdvice: '继续观察买点',
    trendPrediction: '短线震荡偏强',
    sentimentScore: 78,
  },
};

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigateMock.mockReset();
    window.localStorage.clear();
    useStockPoolStore.getState().resetDashboardState();
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
        <ShellRailHarness>
          <HomePage />
        </ShellRailHarness>
      </MemoryRouter>,
    );

    const dashboard = await screen.findByTestId('home-dashboard');
    expect(dashboard).toBeInTheDocument();
    expect(dashboard.className).toContain('workspace-page');
    expect(dashboard.className).toContain('workspace-page--home');
    expect(screen.getByTestId('home-dashboard-layout')).toBeInTheDocument();
    expect(screen.getByTestId('home-workflow-strip')).toBeInTheDocument();
    expect(screen.getByTestId('home-history-column')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL')).toBeInTheDocument();
    const decisionSummary = screen.getByTestId('home-decision-summary');
    expect(within(decisionSummary).getByText('趋势维持强势')).toBeInTheDocument();
    expect(
      screen.getAllByRole('button', {
        name: getReportText(normalizeReportLanguage(historyReport.meta.reportLanguage)).fullReport,
      }).length,
    ).toBeGreaterThan(0);
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
        <ShellRailHarness>
          <HomePage />
        </ShellRailHarness>
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('开始分析')).length).toBeGreaterThan(0);
    expect(screen.getByTestId('home-decision-summary')).toBeInTheDocument();
    expect(await screen.findByText('暂无历史分析记录')).toBeInTheDocument();
  });

  it('renders the shared English workspace copy when the UI language is English', async () => {
    window.localStorage.setItem('dsa-ui-language', 'en');
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <ShellRailHarness>
            <HomePage />
          </ShellRailHarness>
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Decision Brief')).toBeInTheDocument();
    expect(screen.getByText('Research Status')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter a stock code or company name, for example 600519, Kweichow Moutai, AAPL')).toBeInTheDocument();
    expect(screen.getByText('No analysis history yet')).toBeInTheDocument();
  });

  it('surfaces duplicate task warnings from dashboard submission', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(
      new DuplicateTaskError('600519', 'task-1', '股票 600519 正在分析中'),
    );

    render(
      <MemoryRouter>
        <ShellRailHarness>
          <HomePage />
        </ShellRailHarness>
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '分析' }));

    await waitFor(() => {
      expect(screen.getAllByText(/股票 600519 正在分析中/).length).toBeGreaterThan(0);
    });
  });

  it('shows a visible analysis status strip as soon as async analysis is accepted', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-accepted',
      status: 'pending',
      message: '任务已加入队列',
    });

    render(
      <MemoryRouter>
        <ShellRailHarness>
          <HomePage />
        </ShellRailHarness>
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '分析' }));

    expect(await screen.findByTestId('analysis-status-strip')).toBeInTheDocument();
    expect(screen.getAllByText('排队中').length).toBeGreaterThan(0);
    expect(screen.getByText(/600519 已进入分析队列/)).toBeInTheDocument();
  });

  it('shows a progressive research draft scaffold immediately after analysis starts', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-streaming',
      status: 'pending',
      message: '任务已加入队列',
    });

    render(
      <MemoryRouter>
        <ShellRailHarness>
          <HomePage />
        </ShellRailHarness>
      </MemoryRouter>,
    );

    const input = await screen.findByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL');
    fireEvent.change(input, { target: { value: '600519' } });
    fireEvent.click(screen.getByRole('button', { name: '分析' }));

    expect(await screen.findByTestId('report-generation-preview')).toBeInTheDocument();
    expect(screen.getByText('研究报告草稿')).toBeInTheDocument();
    expect(screen.getAllByText('决策摘要').length).toBeGreaterThan(0);
    expect(screen.getByText('市场上下文')).toBeInTheDocument();
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
        <ShellRailHarness>
          <HomePage />
        </ShellRailHarness>
      </MemoryRouter>,
    );

    const followUpButton = await screen.findByRole('button', { name: '追问 AI' });
    fireEvent.click(followUpButton);

    expect(navigateMock).toHaveBeenCalledWith(
      '/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1',
    );
  });
});
