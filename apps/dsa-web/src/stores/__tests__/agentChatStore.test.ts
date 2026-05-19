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
        'data: {"type":"thinking","step":1,"message":"fenxizhong"}',
        'data: {"type":"tool_done","tool":"quote","display_name":"hangqing","success":true,"duration":0.3}',
        'data: {"type":"done","success":true,"content":"zuizhongfenxijieguo"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: 'fenximaotai', session_id: 'session-test' }, { skillName: 'qushijineng' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.chatError).toBeNull();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({
      role: 'user',
      content: 'fenximaotai',
      skillName: 'qushijineng',
    });
    expect(state.messages[1]).toMatchObject({
      role: 'assistant',
      content: 'zuizhongfenxijieguo',
      skillName: 'qushijineng',
    });
    expect(state.messages[1].thinkingSteps).toHaveLength(2);
    expect(state.progressSteps).toEqual([]);
  });

  it('preserves multiple selected skills on streamed user and assistant messages', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"done","success":true,"content":"duocelvefenxijieguo"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream(
        {
          message: 'fenximaotai',
          session_id: 'session-test',
          skills: ['bull_trend', 'ma_golden_cross'],
        },
        {
          skillNames: ['qushifenxi', 'junxianjincha'],
        },
      );

    const state = useAgentChatStore.getState();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({
      role: 'user',
      skills: ['bull_trend', 'ma_golden_cross'],
      skill: 'bull_trend',
      skillNames: ['qushifenxi', 'junxianjincha'],
      skillName: 'qushifenxi、junxianjincha',
    });
    expect(state.messages[1]).toMatchObject({
      role: 'assistant',
      content: 'duocelvefenxijieguo',
      skills: ['bull_trend', 'ma_golden_cross'],
      skill: 'bull_trend',
      skillNames: ['qushifenxi', 'junxianjincha'],
      skillName: 'qushifenxi、junxianjincha',
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
      .startStream({ message: 'fenximaotai', session_id: 'session-test' }, { skillName: 'qushijineng' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: 'xitongmeiyoupeizhikeyongde LLM moxing',
      message: 'qingxianzaixitongshezhizhongpeizhizhumoxing、keyongqudaohuoxiangguan API Key houzaizhongshi。',
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
      .startStream({ message: 'fenximaotai', session_id: 'session-test' }, { skillName: 'qushijineng' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: 'lianjieshangyoufuwuchaoshi',
      message: 'fuwuduanfangwenwaibuyilaishichaoshi，qingshaohouzhongshi，huojianchadangqianwangluoyudailishezhi。',
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
      .startStream({ message: 'fenximaotai', session_id: 'session-test' }, { skillName: 'qushijineng' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: 'qingqiushibai',
      message: 'fenxichucuo',
      category: 'unknown',
      rawMessage: 'fenxichucuo',
    });
  });
});
