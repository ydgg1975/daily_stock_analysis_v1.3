import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { createParsedApiError } from '../../api/error';
import { historyApi } from '../../api/history';
import type { Message } from '../../stores/agentChatStore';
import ChatPage from '../ChatPage';

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const {
  mockGetSkills,
  mockDeleteChatSession,
  mockSendChat,
  mockDownloadSession,
  mockFormatSessionAsMarkdown,
} = vi.hoisted(() => ({
  mockGetSkills: vi.fn(),
  mockDeleteChatSession: vi.fn(),
  mockSendChat: vi.fn(),
  mockDownloadSession: vi.fn(),
  mockFormatSessionAsMarkdown: vi.fn(),
}));

const mockLoadSessions = vi.fn();
const mockLoadInitialSession = vi.fn();
const mockSwitchSession = vi.fn();
const mockStartStream = vi.fn();
const mockClearCompletionBadge = vi.fn();
const mockStartNewChat = vi.fn();

const mockStoreState = {
  messages: [] as Message[],
  loading: false,
  progressSteps: [],
  sessionId: 'session-1',
  sessions: [
    {
      session_id: 'session-1',
      title: '600519 간단히 분석해 주세요',
      message_count: 2,
      created_at: '2026-03-15T09:00:00Z',
      last_active: '2026-03-15T09:05:00Z',
    },
  ],
  sessionsLoading: false,
  chatError: null,
  loadSessions: mockLoadSessions,
  loadInitialSession: mockLoadInitialSession,
  switchSession: mockSwitchSession,
  startStream: mockStartStream,
  clearCompletionBadge: mockClearCompletionBadge,
};

vi.mock('../../api/agent', () => ({
  agentApi: {
    getSkills: mockGetSkills,
    deleteChatSession: mockDeleteChatSession,
    sendChat: mockSendChat,
  },
}));

vi.mock('../../utils/chatExport', () => ({
  downloadSession: mockDownloadSession,
  formatSessionAsMarkdown: mockFormatSessionAsMarkdown,
}));

vi.mock('../../api/history', () => ({
  historyApi: {
    getDetail: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('../../stores/agentChatStore', () => {
  const useAgentChatStore = (
    selector?: (state: typeof mockStoreState) => unknown
  ) => (typeof selector === 'function' ? selector(mockStoreState) : mockStoreState);

  useAgentChatStore.getState = () => ({
    startNewChat: mockStartNewChat,
  });

  return { useAgentChatStore };
});

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  Object.defineProperty(window, 'requestAnimationFrame', {
    writable: true,
    value: (callback: FrameRequestCallback) => window.setTimeout(() => callback(0), 0),
  });

  Object.defineProperty(window, 'cancelAnimationFrame', {
    writable: true,
    value: (handle: number) => window.clearTimeout(handle),
  });

  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    writable: true,
    value: vi.fn(),
  });
});

beforeEach(() => {
  vi.clearAllMocks();
  mockStoreState.messages = [];
  mockStoreState.loading = false;
  mockStoreState.progressSteps = [];
  mockStoreState.chatError = null;
  mockStoreState.sessionsLoading = false;
  mockStoreState.sessionId = 'session-1';
  mockStoreState.sessions = [
    {
      session_id: 'session-1',
      title: '600519 간단히 분석해 주세요',
      message_count: 2,
      created_at: '2026-03-15T09:00:00Z',
      last_active: '2026-03-15T09:05:00Z',
    },
  ];
  mockGetSkills.mockResolvedValue({
    skills: [
      { id: 'bull_trend', name: '추세 분석', description: '테스트 전략' },
    ],
    default_skill_id: 'bull_trend',
  });
  mockDeleteChatSession.mockResolvedValue(undefined);
  mockSendChat.mockResolvedValue({ success: true });
  mockDownloadSession.mockImplementation(() => {});
  mockFormatSessionAsMarkdown.mockReturnValue('# exported session');
});

describe('ChatPage', () => {
  it('renders a fixed workspace shell with independent session and message viewports', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('chat-session-list-scroll')).toBeInTheDocument();
    expect(screen.getByTestId('chat-message-scroll')).toBeInTheDocument();
    expect(mockLoadInitialSession).toHaveBeenCalled();
    expect(mockClearCompletionBadge).toHaveBeenCalled();
  });

  it('switches session when clicking anywhere on the session card', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const sessionCard = await screen.findByRole('button', {
      name: /\uB300\uD654 600519 간단히 분석해 주세요\uB85C \uC804\uD658/,
    });

    fireEvent.click(sessionCard);
    expect(mockSwitchSession).toHaveBeenCalledWith('session-1');
    expect(sessionCard).toHaveAttribute('aria-current', 'page');
  });

  it('renders a separate delete button for each session and opens confirmation without switching', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const deleteButton = await screen.findByRole('button', {
      name: /\uB300\uD654 600519 간단히 분석해 주세요 \uC0AD\uC81C/,
    });

    fireEvent.click(deleteButton);

    expect(mockSwitchSession).not.toHaveBeenCalled();
    expect(await screen.findByText('\uC0AD\uC81C \uD6C4\uC5D0\uB294 \uC774 \uB300\uD654\uB97C \uBCF5\uAD6C\uD560 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4. \uC0AD\uC81C\uD558\uC2DC\uACA0\uC2B5\uB2C8\uAE4C?')).toBeInTheDocument();
  });

  it('hides header actions when there are no messages', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: '\uC0C1\uB2F4 \uC2DC\uC791' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\uB300\uD654 \uB0B4\uBCF4\uB0B4\uAE30' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\uC124\uC815\uB41C \uC54C\uB9BC \uBD07/\uC774\uBA54\uC77C\uB85C \uBCF4\uB0B4\uAE30' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\uB300\uD654 \uAE30\uB85D' })).toBeInTheDocument();
  });

  it('exports the current session from the header action', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: '600519 분석해 주세요' },
      { id: 'assistant-1', role: 'assistant', content: '추세가 강합니다', skillName: '추세 분석' },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: '\uB300\uD654\uB97C Markdown \uD30C\uC77C\uB85C \uB0B4\uBCF4\uB0B4\uAE30' }));

    expect(mockDownloadSession).toHaveBeenCalledWith(mockStoreState.messages);
    expect(mockFormatSessionAsMarkdown).not.toHaveBeenCalled();
  });

  it('renders assistant skill labels with shared badge semantics', async () => {
    mockStoreState.messages = [
      { id: 'assistant-1', role: 'assistant', content: '추세가 강합니다', skillName: '추세 분석' },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const skillBadge = await screen.findByLabelText('\uC804\uB7B5 추세 분석');
    expect(skillBadge).toBeInTheDocument();
    expect(skillBadge).toHaveTextContent('추세 분석');
  });

  it('renders assistant multi-skill labels with shared badge semantics', async () => {
    mockStoreState.messages = [
      {
        id: 'assistant-1',
        role: 'assistant',
        content: '추세가 강합니다',
        skills: ['bull_trend', 'ma_golden_cross'],
        skillNames: ['추세 분석', '이동평균 골든크로스'],
      },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const skillBadge = await screen.findByLabelText('\uC804\uB7B5 추세 분석, 이동평균 골든크로스');
    expect(skillBadge).toBeInTheDocument();
    expect(skillBadge).toHaveTextContent('추세 분석, 이동평균 골든크로스');
  });

  it('selects the default skill after loading skills', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByRole('checkbox', { name: '추세 분석' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: '\uC77C\uBC18 \uBD84\uC11D' })).not.toBeChecked();
  });

  it('sends multiple selected skills in order', async () => {
    mockGetSkills.mockResolvedValue({
      skills: [
        { id: 'bull_trend', name: '추세 분석', description: '기본 추세' },
        { id: 'ma_golden_cross', name: '이동평균 골든크로스', description: '이동평균 교차' },
      ],
      default_skill_id: 'bull_trend',
    });

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('checkbox', { name: '이동평균 골든크로스' }));
    fireEvent.change(screen.getByPlaceholderText(/\uBD84\uC11D 600519/), {
      target: { value: '600519 분석' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\uBCF4\uB0B4\uAE30' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '600519 분석',
          skills: ['bull_trend', 'ma_golden_cross'],
        }),
        expect.objectContaining({
          skillNames: ['추세 분석', '이동평균 골든크로스'],
          skillName: '추세 분석, 이동평균 골든크로스',
        }),
      );
    });
  });

  it('omits skills when all concrete skills are cleared', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('checkbox', { name: '추세 분석' }));
    expect(screen.getByRole('checkbox', { name: '\uC77C\uBC18 \uBD84\uC11D' })).toBeChecked();

    fireEvent.change(screen.getByPlaceholderText(/\uBD84\uC11D 600519/), {
      target: { value: 'AAPL 분석' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\uBCF4\uB0B4\uAE30' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalled();
    });
    const lastCall = mockStartStream.mock.calls[mockStartStream.mock.calls.length - 1];
    expect(lastCall[0]).toEqual(expect.objectContaining({ message: 'AAPL 분석' }));
    expect(lastCall[0]).not.toHaveProperty('skills');
    expect(lastCall[1]).toEqual(expect.objectContaining({
      skillNames: ['\uC77C\uBC18'],
      skillName: '\uC77C\uBC18',
    }));
  });

  it('caps concrete skill selection at three and re-enables choices after unselecting', async () => {
    mockGetSkills.mockResolvedValue({
      skills: [
        { id: 'bull_trend', name: '추세 분석', description: '기본 추세' },
        { id: 'ma_golden_cross', name: '이동평균 골든크로스', description: '이동평균 교차' },
        { id: 'chan_theory', name: '찬 이론', description: '구조 분석' },
        { id: 'wave_theory', name: '파동 이론', description: '파동 분석' },
      ],
      default_skill_id: 'bull_trend',
    });

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('checkbox', { name: '이동평균 골든크로스' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '찬 이론' }));

    const wave = screen.getByRole('checkbox', { name: '파동 이론' });
    expect(wave).toBeDisabled();

    fireEvent.click(screen.getByRole('checkbox', { name: '이동평균 골든크로스' }));
    expect(wave).not.toBeDisabled();
  });

  it('quick questions override the current multi-skill selection', async () => {
    mockGetSkills.mockResolvedValue({
      skills: [
        { id: 'bull_trend', name: '추세 분석', description: '기본 추세' },
        { id: 'ma_golden_cross', name: '이동평균 골든크로스', description: '이동평균 교차' },
        { id: 'chan_theory', name: '찬 이론', description: '구조 분석' },
      ],
      default_skill_id: 'bull_trend',
    });

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('checkbox', { name: '이동평균 골든크로스' }));
    fireEvent.click(screen.getByRole('button', { name: '\uCC2C \uC774\uB860\uC73C\uB85C 600519 \uBD84\uC11D' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\uCC2C \uC774\uB860\uC73C\uB85C 600519 \uBD84\uC11D',
          skills: ['chan_theory'],
        }),
        expect.objectContaining({
          skillNames: ['찬 이론'],
          skillName: '찬 이론',
        }),
      );
    });
  });

  it('keeps assistant message actions directly activatable in the DOM', async () => {
    mockStoreState.messages = [
      { id: 'assistant-1', role: 'assistant', content: '추세가 강합니다', skillName: '추세 분석' },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const exportButton = await screen.findByRole('button', { name: '\uC774 \uBA54\uC2DC\uC9C0\uB97C Markdown\uC73C\uB85C \uB0B4\uBCF4\uB0B4\uAE30' });
    const actionGroup = exportButton.parentElement;

    expect(actionGroup).toHaveClass('chat-message-actions');
    expect(actionGroup?.className).not.toMatch(/pointer-events-none|opacity-0/);
  });

  it('sends exported markdown to notification channel and shows success feedback', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: '600519 분석해 주세요' },
      { id: 'assistant-1', role: 'assistant', content: '추세가 강합니다', skillName: '추세 분석' },
    ];
    mockFormatSessionAsMarkdown.mockReturnValue('# exported markdown');

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: '\uC124\uC815\uB41C \uC54C\uB9BC \uBD07/\uC774\uBA54\uC77C\uB85C \uBCF4\uB0B4\uAE30' }));

    await waitFor(() => {
      expect(mockFormatSessionAsMarkdown).toHaveBeenCalledWith(mockStoreState.messages);
      expect(mockSendChat).toHaveBeenCalledWith('# exported markdown');
    });

    expect(await screen.findByText('\uC54C\uB9BC \uCC44\uB110\uB85C \uC804\uC1A1\uD588\uC2B5\uB2C8\uB2E4')).toBeInTheDocument();
  });

  it('shows parsed error feedback when notification delivery fails', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: 'AAPL 분석해 주세요' },
      { id: 'assistant-1', role: 'assistant', content: '단기 박스권입니다', skillName: '추세 분석' },
    ];
    mockSendChat.mockRejectedValue(
      createParsedApiError({
        title: '전송 실패',
        message: 'tongzhiqudaobukeyong',
        category: 'unknown',
      }),
    );

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: '\uC124\uC815\uB41C \uC54C\uB9BC \uBD07/\uC774\uBA54\uC77C\uB85C \uBCF4\uB0B4\uAE30' }));

    expect(await screen.findByText('tongzhiqudaobukeyong')).toBeInTheDocument();
  });

  it('prevents duplicate notification sends while the request is in flight', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: 'TSLA 분석해 주세요' },
      { id: 'assistant-1', role: 'assistant', content: '변동성이 큽니다', skillName: '추세 분석' },
    ];
    const deferred = createDeferred<{ success: boolean }>();
    mockSendChat.mockImplementation(() => deferred.promise);

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const sendButton = await screen.findByRole('button', { name: '\uC124\uC815\uB41C \uC54C\uB9BC \uBD07/\uC774\uBA54\uC77C\uB85C \uBCF4\uB0B4\uAE30' });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockSendChat).toHaveBeenCalledTimes(1);
      expect(sendButton).toBeDisabled();
    });

    fireEvent.click(sendButton);
    expect(mockSendChat).toHaveBeenCalledTimes(1);

    deferred.resolve({ success: true });

    await waitFor(() => {
      expect(sendButton).not.toBeDisabled();
    });
  });

  it('allows sending with base follow-up context before report hydration completes', async () => {
    const deferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();

    vi.mocked(historyApi.getDetail).mockImplementation(() => deferred.promise);

    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: \u8D35\u5DDE\u8305\u53F0(600519)')).toBeInTheDocument();

    const sendButton = screen.getByRole('button', { name: /\uBCF4\uB0B4\uAE30|\uCC98\uB9AC \uC911\.\.\./ });
    expect(sendButton).not.toBeDisabled();
    expect(screen.getByText('\uC774\uC804 \uBD84\uC11D \uCEE8\uD14D\uC2A4\uD2B8\uB97C \uBD88\uB7EC\uC624\uB294 \uC911\uC785\uB2C8\uB2E4. \uC9C0\uAE08 \uBC14\uB85C \uC774\uC5B4\uC11C \uC9C8\uBB38\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.')).toBeInTheDocument();

    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: \u8D35\u5DDE\u8305\u53F0(600519)',
          context: {
            stock_code: '600519',
            stock_name: '\u8D35\u5DDE\u8305\u53F0',
          },
        }),
        expect.objectContaining({
          skillName: '추세 분석',
        }),
      );
    });

    deferred.resolve({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '구이저우마오타이',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '추세가 이어집니다',
        operationAdvice: '계속 관찰',
        trendPrediction: 'gaoweizhendang',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    await waitFor(() => {
      expect(screen.queryByText('\uC774\uC804 \uBD84\uC11D \uCEE8\uD14D\uC2A4\uD2B8\uB97C \uBD88\uB7EC\uC624\uB294 \uC911\uC785\uB2C8\uB2E4. \uC9C0\uAE08 \uBC14\uB85C \uC774\uC5B4\uC11C \uC9C8\uBB38\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.')).not.toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/\uBD84\uC11D 600519/), {
      target: { value: '거래량을 이어서 분석해 주세요' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\uBCF4\uB0B4\uAE30' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '거래량을 이어서 분석해 주세요',
          context: undefined,
        }),
        expect.objectContaining({
          skillName: '추세 분석',
        }),
      );
    });
  });

  it('uses hydrated report context when it finishes before sending', async () => {
    vi.mocked(historyApi.getDetail).mockResolvedValue({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '구이저우마오타이',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '추세가 이어집니다',
        operationAdvice: '계속 관찰',
        trendPrediction: 'gaoweizhendang',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: \u8D35\u5DDE\u8305\u53F0(600519)')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText('이전 분석 컨텍스트를 불러오는 중입니다. 지금 바로 이어서 질문할 수 있습니다.')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '\uBCF4\uB0B4\uAE30' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: \u8D35\u5DDE\u8305\u53F0(600519)',
          context: expect.objectContaining({
            stock_code: '600519',
            stock_name: '\u8D35\u5DDE\u8305\u53F0',
            previous_price: 1523.6,
            previous_change_pct: 1.8,
            previous_strategy: expect.objectContaining({
              stopLoss: '1450',
            }),
          }),
        }),
        expect.objectContaining({
          skillName: '추세 분석',
        }),
      );
    });
  });

  it('falls back to base stock context when recordId is missing', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=AAPL']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: AAPL')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\uBCF4\uB0B4\uAE30' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: AAPL',
          context: {
            stock_code: 'AAPL',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '추세 분석',
        }),
      );
    });
    expect(historyApi.getDetail).not.toHaveBeenCalled();
  });

  it('ignores malformed follow-up query params', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=%3Cscript%3E&name=Bad%0AName&recordId=abc']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: '\uC0C1\uB2F4 \uC2DC\uC791' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/\uBD84\uC11D 600519/)).toHaveValue('');
    expect(historyApi.getDetail).not.toHaveBeenCalled();
  });

  it('reprocesses follow-up query params when navigating to the same chat route again', async () => {
    const firstDeferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();
    const secondDeferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();

    vi.mocked(historyApi.getDetail)
      .mockImplementationOnce(() => firstDeferred.promise)
      .mockImplementationOnce(() => secondDeferred.promise);

    const router = createMemoryRouter(
      [{ path: '/chat', element: <ChatPage /> }],
      {
        initialEntries: ['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1'],
      },
    );

    render(<RouterProvider router={router} />);

    expect(await screen.findByDisplayValue('\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: \u8D35\u5DDE\u8305\u53F0(600519)')).toBeInTheDocument();
    expect(screen.getByText('\uC774\uC804 \uBD84\uC11D \uCEE8\uD14D\uC2A4\uD2B8\uB97C \uBD88\uB7EC\uC624\uB294 \uC911\uC785\uB2C8\uB2E4. \uC9C0\uAE08 \uBC14\uB85C \uC774\uC5B4\uC11C \uC9C8\uBB38\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.')).toBeInTheDocument();

    await router.navigate('/chat?stock=AAPL&name=Apple&recordId=2');

    expect(await screen.findByDisplayValue('\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: Apple(AAPL)')).toBeInTheDocument();

    firstDeferred.resolve({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '구이저우마오타이',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '추세가 이어집니다',
        operationAdvice: '계속 관찰',
        trendPrediction: 'gaoweizhendang',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    secondDeferred.resolve({
      meta: {
        id: 2,
        queryId: 'q-2',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'detailed',
        createdAt: '2026-03-18T09:00:00Z',
        currentPrice: 211.5,
        changePct: 2.4,
      },
      summary: {
        analysisSummary: '추세 강화',
        operationAdvice: '계속 보유',
        trendPrediction: '단기 강세',
        sentimentScore: 81,
      },
      strategy: {
        stopLoss: '205',
      },
    });

    await waitFor(() => {
      expect(screen.queryByText('\uC774\uC804 \uBD84\uC11D \uCEE8\uD14D\uC2A4\uD2B8\uB97C \uBD88\uB7EC\uC624\uB294 \uC911\uC785\uB2C8\uB2E4. \uC9C0\uAE08 \uBC14\uB85C \uC774\uC5B4\uC11C \uC9C8\uBB38\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '\uBCF4\uB0B4\uAE30' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\uC2EC\uCE35 \uBD84\uC11D\uD574 \uC8FC\uC138\uC694: Apple(AAPL)',
          context: expect.objectContaining({
            stock_code: 'AAPL',
            stock_name: 'Apple',
            previous_price: 211.5,
            previous_change_pct: 2.4,
            previous_strategy: expect.objectContaining({
              stopLoss: '205',
            }),
          }),
        }),
        expect.objectContaining({
          skillName: '추세 분석',
        }),
      );
    });
  });

  it('shows a jump-to-latest action when new content arrives while the user is away from bottom', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: '600519 분석해 주세요' },
      { id: 'assistant-1', role: 'assistant', content: '추세가 강합니다', skillName: '추세 분석' },
    ];

    const { rerender } = render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const viewport = await screen.findByTestId('chat-message-scroll');
    Object.defineProperty(viewport, 'scrollTop', { configurable: true, value: 0 });
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 400 });
    Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 1200 });

    fireEvent.scroll(viewport);

    mockStoreState.messages = [
      ...mockStoreState.messages,
      { id: 'assistant-2', role: 'assistant', content: '새로운 보충 분석', skillName: '추세 분석' },
    ];

    rerender(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const jumpButton = await screen.findByRole('button', { name: '\uCD5C\uC2E0 \uBA54\uC2DC\uC9C0 \uBCF4\uAE30' });
    expect(jumpButton).toBeInTheDocument();

    fireEvent.click(jumpButton);

    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });
});
