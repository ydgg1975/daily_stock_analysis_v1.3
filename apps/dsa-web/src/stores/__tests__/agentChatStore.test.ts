import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAgentChatStore } from '../agentChatStore';

vi.mock('../../api/agent', () => ({
  agentApi: {
    getChatSessions: vi.fn(async () => []),
    getChatSessionMessages: vi.fn(async () => []),
    chatStream: vi.fn(),
  },
}));

const { agentApi } = await import('../../api/agent');

const encoder = new TextEncoder();

function createStreamResponse(lines: string[]) {
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(lines.join('\n')));
        controller.close();
      },
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    },
  );
}

describe('agentChatStore.startStream', () => {
  beforeEach(() => {
    localStorage.clear();
    useAgentChatStore.setState({
      messages: [],
      loading: false,
      progressSteps: [],
      sessionId: 'session-test',
      sessions: [],
      sessionsLoading: false,
      chatError: null,
      currentRoute: '/chat',
      completionBadge: false,
      hasInitialLoad: true,
      abortController: null,
    });
    vi.clearAllMocks();
  });

  it('appends the user message and final assistant message from the SSE stream', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"thinking","step":1,"message":"분석 중"}',
        'data: {"type":"tool_done","tool":"quote","display_name":"시세","success":true,"duration":0.3}',
        'data: {"type":"done","success":true,"content":"최종 분석 결과"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '마오타이 분석', session_id: 'session-test' }, { skillName: '추세 전략' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.chatError).toBeNull();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({
      role: 'user',
      content: '마오타이 분석',
      skillName: '추세 전략',
    });
    expect(state.messages[1]).toMatchObject({
      role: 'assistant',
      content: '최종 분석 결과',
      skillName: '추세 전략',
    });
    expect(state.messages[1].thinkingSteps).toHaveLength(2);
    expect(state.progressSteps).toEqual([]);
  });

  it('preserves multiple selected skills on streamed user and assistant messages', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"done","success":true,"content":"다중 전략 분석 결과"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream(
        {
          message: '마오타이 분석',
          session_id: 'session-test',
          skills: ['bull_trend', 'ma_golden_cross'],
        },
        {
          skillNames: ['추세 분석', '이동평균 골든크로스'],
        },
      );

    const state = useAgentChatStore.getState();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({
      role: 'user',
      skills: ['bull_trend', 'ma_golden_cross'],
      skill: 'bull_trend',
      skillNames: ['추세 분석', '이동평균 골든크로스'],
      skillName: '추세 분석、이동평균 골든크로스',
    });
    expect(state.messages[1]).toMatchObject({
      role: 'assistant',
      content: '다중 전략 분석 결과',
      skills: ['bull_trend', 'ma_golden_cross'],
      skill: 'bull_trend',
      skillNames: ['추세 분석', '이동평균 골든크로스'],
      skillName: '추세 분석、이동평균 골든크로스',
    });
  });

  it('preserves parsed error details when done.success is false', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"done","success":false,"error":"Agent LLM: no effective primary model configured"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '마오타이 분석', session_id: 'session-test' }, { skillName: '추세 전략' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: '사용 가능한 LLM 모델이 설정되어 있지 않습니다',
      message: '시스템 설정에서 기본 모델, 사용 가능한 채널 또는 관련 API Key를 설정한 뒤 다시 시도하세요.',
      category: 'llm_not_configured',
      rawMessage: 'Agent LLM: no effective primary model configured',
    });
  });

  it('uses the same parser for SSE error events', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"error","message":"connect timeout while calling upstream provider"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '마오타이 분석', session_id: 'session-test' }, { skillName: '추세 전략' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: '상위 서비스 연결 시간이 초과되었습니다',
      message: '서버가 외부 의존성에 접근하는 중 시간이 초과되었습니다. 잠시 후 다시 시도하거나 네트워크와 프록시 설정을 확인하세요.',
      category: 'upstream_timeout',
      rawMessage: 'connect timeout while calling upstream provider',
    });
  });

  it('falls back when SSE error fields are empty strings', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"error","error":"","message":"   ","content":""}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '마오타이 분석', session_id: 'session-test' }, { skillName: '추세 전략' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: '요청 실패',
      message: '분석 오류',
      category: 'unknown',
      rawMessage: '분석 오류',
    });
  });
});
