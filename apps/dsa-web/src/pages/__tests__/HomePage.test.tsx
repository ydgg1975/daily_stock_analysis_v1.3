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
      getTasks: vi.fn().mockResolvedValue({ total: 0, pending: 0, processing: 0, tasks: [] }),
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
    vi.mocked(analysisApi.getTasks).mockResolvedValue({ total: 0, pending: 0, processing: 0, tasks: [] });
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
    const workflowStrip = screen.getByTestId('home-workflow-strip');
    expect(workflowStrip).toBeInTheDocument();
    expect(within(workflowStrip).getByTestId('home-command-region')).toBeInTheDocument();
    expect(within(workflowStrip).getByTestId('home-status-region')).toBeInTheDocument();
    expect(within(workflowStrip).queryByTestId('home-decision-summary')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-history-column')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入股票代码或名称，如 600519、贵州茅台、AAPL')).toBeInTheDocument();
    expect(within(screen.getByTestId('analysis-status-strip')).getAllByRole('listitem')).toHaveLength(6);
    const decisionSummary = screen.getByTestId('home-decision-summary');
    expect(within(decisionSummary).getByText('趋势维持强势')).toBeInTheDocument();
    expect(workflowStrip.compareDocumentPosition(decisionSummary) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
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

  it('shows multiple active tasks in the queue below the decision summary', async () => {
    const tasks = [
      {
        taskId: 'task-processing',
        stockCode: 'NVDA',
        stockName: 'NVIDIA',
        status: 'processing' as const,
        progress: 62,
        reportType: 'full',
        createdAt: '2026-03-28T09:30:00Z',
        startedAt: '2026-03-28T09:31:00Z',
        updatedAt: '2026-03-28T09:34:00Z',
        message: '正在拉取行情',
      },
      {
        taskId: 'task-pending',
        stockCode: 'AAPL',
        stockName: 'Apple',
        status: 'pending' as const,
        progress: 14,
        reportType: 'full',
        createdAt: '2026-03-28T09:20:00Z',
        updatedAt: '2026-03-28T09:22:00Z',
        message: '等待队列空位',
      },
    ];
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 2,
      pending: 1,
      processing: 1,
      tasks: tasks as never,
    });

    render(
      <MemoryRouter>
        <ShellRailHarness>
          <HomePage />
        </ShellRailHarness>
      </MemoryRouter>,
    );

    const queue = await screen.findByTestId('home-task-queue');
    expect(queue).toBeInTheDocument();
    await waitFor(() => {
      expect(within(queue).getByText('NVIDIA')).toBeInTheDocument();
      expect(within(queue).getByText('Apple')).toBeInTheDocument();
    });
    expect(within(queue).getByText('当前聚焦')).toBeInTheDocument();
    expect(within(queue).getByLabelText('运行中')).toBeInTheDocument();
    expect(within(queue).getByLabelText('排队中')).toBeInTheDocument();
    expect(within(queue).getByText('行情')).toBeInTheDocument();
    expect(within(queue).getByText('排队')).toBeInTheDocument();
  });

  it('renders a compact localized task queue in English mode', async () => {
    window.localStorage.setItem('dsa-ui-language', 'en');
    const tasks = [
      {
        taskId: 'task-processing',
        stockCode: 'NVDA',
        stockName: 'NVIDIA',
        status: 'processing' as const,
        progress: 62,
        reportType: 'full',
        createdAt: '2026-03-28T09:30:00Z',
        startedAt: '2026-03-28T09:31:00Z',
        updatedAt: '2026-03-28T09:34:00Z',
      },
      {
        taskId: 'task-pending',
        stockCode: 'AAPL',
        stockName: 'Apple',
        status: 'pending' as const,
        progress: 14,
        reportType: 'full',
        createdAt: '2026-03-28T09:20:00Z',
        updatedAt: '2026-03-28T09:22:00Z',
      },
    ];
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 2,
      pending: 1,
      processing: 1,
      tasks: tasks as never,
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

    const queue = await screen.findByTestId('home-task-queue');
    expect(within(queue).getAllByText('Task queue').length).toBeGreaterThanOrEqual(2);
    expect(within(queue).getByText('NVIDIA')).toBeInTheDocument();
    expect(within(queue).getByText('Apple')).toBeInTheDocument();
    expect(within(queue).getByLabelText('Running')).toBeInTheDocument();
    expect(within(queue).getByLabelText('Queued')).toBeInTheDocument();
    expect(within(queue).getByText('Draft')).toBeInTheDocument();
    expect(within(queue).getByText('Queue')).toBeInTheDocument();
    expect(screen.queryByText('正在拉取行情')).not.toBeInTheDocument();
    expect(screen.queryByText('等待队列空位')).not.toBeInTheDocument();
  });

  it('shows an overflow summary when more tasks exist than the compact queue can display', async () => {
    const tasks = Array.from({ length: 7 }, (_, index) => ({
      taskId: `task-${index}`,
      stockCode: `STK${index}`,
      stockName: `Stock ${index}`,
      status: index === 0 ? 'processing' : index === 1 ? 'failed' : index === 2 ? 'completed' : 'pending',
      progress: 12 + index * 8,
      reportType: 'full',
      createdAt: `2026-03-28T09:${String(10 + index).padStart(2, '0')}:00Z`,
      updatedAt: `2026-03-28T09:${String(11 + index).padStart(2, '0')}:00Z`,
    }));
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 7,
      pending: 4,
      processing: 1,
      tasks: tasks as never,
    });

    render(
      <MemoryRouter>
        <ShellRailHarness>
          <HomePage />
        </ShellRailHarness>
      </MemoryRouter>,
    );

    const queue = await screen.findByTestId('home-task-queue');
    expect(within(queue).getByText('+1')).toBeInTheDocument();
    expect(within(queue).getByLabelText('更多 1')).toBeInTheDocument();
  });

  it('localizes controlled decision values and keeps the summary metrics dense in English mode', async () => {
    window.localStorage.setItem('dsa-ui-language', 'en');
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);

    render(
      <MemoryRouter>
        <UiLanguageProvider>
          <ShellRailHarness>
            <HomePage />
          </ShellRailHarness>
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    const decisionSummary = await screen.findByTestId('home-decision-summary');
    expect(within(decisionSummary).getByText('Watch')).toBeInTheDocument();
    expect(within(decisionSummary).getByText('Wait for confirmation')).toBeInTheDocument();
    expect(within(decisionSummary).getAllByText('Bullish')).toHaveLength(2);
    expect(within(decisionSummary).getByText('Trend strengthening')).toBeInTheDocument();
    expect(decisionSummary.querySelectorAll('.home-decision-summary__metric-meter')).toHaveLength(1);
    expect(screen.queryByText('观望')).not.toBeInTheDocument();
    expect(screen.queryByText('看空')).not.toBeInTheDocument();
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
      expect(screen.getAllByText(/正在分析中/).length).toBeGreaterThan(0);
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
    expect(screen.getByTestId('analysis-status-strip').querySelector('.workspace-statusboard__copy'))
      .toHaveTextContent('600519 已进入分析队列');
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
