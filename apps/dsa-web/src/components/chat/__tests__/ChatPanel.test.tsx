import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { ChatPanel } from '../ChatPanel';
import { createScopedChatStore } from '../../../stores/scopedChatStore';
import type { ChatFollowUpContext } from '../../../utils/chatFollowUp';
import type { ChatSessionMessage, ChatStreamRequest } from '../../../api/agent';
import type { StreamMeta } from '../../../stores/agentChatStore';

vi.mock('../../../api/agent', () => ({
  agentApi: {
    getChatSessions: vi.fn(async () => []),
    getChatSessionMessages: vi.fn(async () => [] as ChatSessionMessage[]),
    chatStream: vi.fn(),
  },
}));

const { agentApi } = await import('../../../api/agent');

const TEST_CONTEXT: ChatFollowUpContext = {
  stock_code: '600519',
  stock_name: '贵州茅台',
  previous_price: 1680,
  previous_change_pct: 1.2,
};

const PRESETS = ['为什么是这个止损？', '和我持仓冲突吗？', '已经更高位买了怎么办？'];

describe('ChatPanel', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([]);
  });

  it('shows hydrating state before initial history fetch resolves', async () => {
    let resolveFetch: (msgs: ChatSessionMessage[]) => void = () => {};
    vi.mocked(agentApi.getChatSessionMessages).mockImplementation(
      () =>
        new Promise<ChatSessionMessage[]>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const store = createScopedChatStore('report-42');
    render(
      <ChatPanel store={store} context={TEST_CONTEXT} presetPrompts={PRESETS} />,
    );

    // 加载占位态出现，presets 与输入框尚未展示
    expect(screen.getByText('加载历史追问...')).toBeInTheDocument();
    expect(screen.queryByText(PRESETS[0])).not.toBeInTheDocument();
    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeDisabled();

    // 解放 fetch 后，空态 + presets 出现
    await act(async () => {
      resolveFetch([]);
    });
    await waitFor(() => {
      expect(screen.getByText(PRESETS[0])).toBeInTheDocument();
    });
    expect(screen.getByRole('textbox')).not.toBeDisabled();
  });

  it('does not flash stale messages from another session before hydration', async () => {
    // 模拟一种场景：如果 store 不做 hydration gating，首帧会看到旧消息
    // 我们的 ChatPanel 应该在 hydrated=false 时完全不渲染 messages 列表
    let resolveFetch: (msgs: ChatSessionMessage[]) => void = () => {};
    vi.mocked(agentApi.getChatSessionMessages).mockImplementation(
      () =>
        new Promise<ChatSessionMessage[]>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const store = createScopedChatStore('report-42');
    // 为了模拟"别处遗留"的消息，直接注入到 store（实际架构下 scoped store 是隔离的，
    // 但这个保护是正确性守卫，任何未来污染都应被挡掉）
    store.setState({
      messages: [
        { id: 'stale', role: 'user', content: '上一份报告的遗留消息' },
      ],
    });

    render(
      <ChatPanel store={store} context={TEST_CONTEXT} presetPrompts={PRESETS} />,
    );

    // hydrated=false 期间不展示残留消息
    expect(screen.queryByText('上一份报告的遗留消息')).not.toBeInTheDocument();
    expect(screen.getByText('加载历史追问...')).toBeInTheDocument();

    await act(async () => {
      resolveFetch([]);
    });
    await waitFor(() => {
      // hydrate 后 store 的守卫会保留已有消息（不覆盖），因为 messages.length > 0
      // 对用户可见：hydrate 之后消息列表才展示
      expect(screen.getByText('上一份报告的遗留消息')).toBeInTheDocument();
    });
  });

  it('renders preset prompts in empty state after hydration', async () => {
    const store = createScopedChatStore('report-42');
    render(
      <ChatPanel store={store} context={TEST_CONTEXT} presetPrompts={PRESETS} />,
    );

    await waitFor(() => {
      PRESETS.forEach((p) => {
        expect(screen.getByText(p)).toBeInTheDocument();
      });
    });
  });

  it('blocks send button and preset click while still hydrating', async () => {
    let resolveFetch: (msgs: ChatSessionMessage[]) => void = () => {};
    vi.mocked(agentApi.getChatSessionMessages).mockImplementation(
      () =>
        new Promise<ChatSessionMessage[]>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const store = createScopedChatStore('report-42');
    const startStreamSpy = vi.spyOn(store.getState(), 'startStream');

    render(
      <ChatPanel store={store} context={TEST_CONTEXT} presetPrompts={PRESETS} />,
    );

    // hydrate 未完成时即使 presets 也未渲染出来 — 无法点击
    expect(screen.queryByText(PRESETS[0])).not.toBeInTheDocument();

    await act(async () => {
      resolveFetch([]);
    });
    await waitFor(() => {
      expect(screen.getByText(PRESETS[0])).toBeInTheDocument();
    });
    expect(startStreamSpy).not.toHaveBeenCalled();
  });

  it('clicking a preset after hydration calls startStream with context', async () => {
    const store = createScopedChatStore('report-42');
    const startStream = vi.fn<(payload: ChatStreamRequest, meta?: StreamMeta) => Promise<void>>(
      async () => {},
    );
    store.setState({ startStream });

    render(
      <ChatPanel store={store} context={TEST_CONTEXT} presetPrompts={PRESETS} />,
    );

    await waitFor(() => {
      expect(screen.getByText(PRESETS[0])).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(PRESETS[0]));

    await waitFor(() => {
      expect(startStream).toHaveBeenCalledTimes(1);
    });
    const [payload, meta] = startStream.mock.calls[0];
    expect(payload).toMatchObject({
      message: PRESETS[0],
      session_id: 'report-42',
      context: TEST_CONTEXT,
    });
    expect(meta).toMatchObject({ skillName: '追问' });
  });

  it('hydrate does not overwrite messages sent while fetching', async () => {
    // hydration 完成返回历史消息；但在 hydrate 完成前，store 里已有从别处流入的消息
    // → store 的守卫应保证不覆盖（belt-and-suspenders）
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([
      { id: 'srv1', role: 'user', content: '服务端历史', created_at: null },
    ]);

    const store = createScopedChatStore('report-42');
    // 模拟：hydrate 触发但还没 resolve，用户已经产生了一条消息
    store.setState({
      messages: [{ id: 'usr1', role: 'user', content: '用户刚发的' }],
    });

    await act(async () => {
      await store.getState().hydrate();
    });

    const finalMessages = store.getState().messages;
    expect(finalMessages).toHaveLength(1);
    expect(finalMessages[0].content).toBe('用户刚发的');
    expect(store.getState().hydrated).toBe(true);
  });
});
