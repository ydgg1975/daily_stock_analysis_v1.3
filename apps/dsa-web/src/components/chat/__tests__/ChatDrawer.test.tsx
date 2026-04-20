import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ChatDrawer } from '../ChatDrawer';
import { useAgentChatStore } from '../../../stores/agentChatStore';
import type { AnalysisReport } from '../../../types/analysis';
import type { ChatSessionMessage } from '../../../api/agent';

vi.mock('../../../api/agent', () => ({
  agentApi: {
    getChatSessions: vi.fn(async () => []),
    getChatSessionMessages: vi.fn(async () => [] as ChatSessionMessage[]),
    chatStream: vi.fn(),
  },
}));

const { agentApi } = await import('../../../api/agent');

function buildReport(overrides: Partial<AnalysisReport['meta']> = {}): AnalysisReport {
  return {
    meta: {
      id: 42,
      queryId: 'q1',
      stockCode: '600519',
      stockName: '贵州茅台',
      reportType: 'full',
      createdAt: '2026-04-20T00:00:00Z',
      currentPrice: 1680,
      changePct: 1.2,
      ...overrides,
    },
    summary: {
      analysisSummary: 'summary',
      operationAdvice: 'hold',
      trendPrediction: 'up',
      sentimentScore: 70,
    },
    strategy: {
      idealBuy: '1650',
      stopLoss: '1600',
      takeProfit: '1800',
    },
  };
}

describe('ChatDrawer', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([]);
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <ChatDrawer isOpen={false} onClose={() => {}} report={buildReport()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when report is null', () => {
    const { container } = render(
      <ChatDrawer isOpen={true} onClose={() => {}} report={null} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders the report title and preset prompts after hydration', async () => {
    render(<ChatDrawer isOpen={true} onClose={() => {}} report={buildReport()} />);

    expect(screen.getByText('贵州茅台(600519)')).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText('为什么把止损和买点定在这里？给我解释一下这个点位逻辑'),
      ).toBeInTheDocument();
    });
  });

  it('calls getChatSessionMessages with report-{id} session id', async () => {
    render(<ChatDrawer isOpen={true} onClose={() => {}} report={buildReport({ id: 99 })} />);

    await waitFor(() => {
      expect(agentApi.getChatSessionMessages).toHaveBeenCalledWith('report-99');
    });
  });

  it('falls back to report-{stockCode} session id when meta.id is missing', async () => {
    render(
      <ChatDrawer
        isOpen={true}
        onClose={() => {}}
        report={buildReport({ id: undefined })}
      />,
    );

    await waitFor(() => {
      expect(agentApi.getChatSessionMessages).toHaveBeenCalledWith('report-600519');
    });
  });

  it('does NOT mutate the global useAgentChatStore sessionId (no session stealing)', async () => {
    const originalGlobalSessionId = useAgentChatStore.getState().sessionId;

    render(
      <ChatDrawer isOpen={true} onClose={() => {}} report={buildReport({ id: 77 })} />,
    );

    await waitFor(() => {
      expect(agentApi.getChatSessionMessages).toHaveBeenCalledWith('report-77');
    });

    // 全局 /chat store 的 sessionId 不应被 drawer 动过
    expect(useAgentChatStore.getState().sessionId).toBe(originalGlobalSessionId);
    // localStorage 的 /chat 默认会话 key 不应被写入 report-*
    const stored = localStorage.getItem('dsa_chat_session_id');
    if (stored !== null) {
      expect(stored).not.toMatch(/^report-/);
    }
  });

  it('restores focus to the previously focused element on close', async () => {
    const { rerender } = render(
      <>
        <button data-testid="trigger">Trigger</button>
        <ChatDrawer isOpen={false} onClose={() => {}} report={buildReport()} />
      </>,
    );

    const trigger = screen.getByTestId('trigger');
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    rerender(
      <>
        <button data-testid="trigger">Trigger</button>
        <ChatDrawer isOpen={true} onClose={() => {}} report={buildReport()} />
      </>,
    );

    // drawer 打开期间焦点可能被移入；关闭时应恢复到 trigger
    rerender(
      <>
        <button data-testid="trigger">Trigger</button>
        <ChatDrawer isOpen={false} onClose={() => {}} report={buildReport()} />
      </>,
    );

    await waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });

  it('traps Tab within the drawer (focus does not leak behind overlay)', async () => {
    render(
      <>
        <button data-testid="outside">Outside</button>
        <ChatDrawer isOpen={true} onClose={() => {}} report={buildReport()} />
      </>,
    );

    await waitFor(() => {
      expect(
        screen.getByText('为什么把止损和买点定在这里？给我解释一下这个点位逻辑'),
      ).toBeInTheDocument();
    });

    // 输入框是 drawer 内在空输入下最后一个可聚焦元素（发送按钮 disabled）
    // 对它按 Tab 应该环绕到第一个（关闭按钮），绝不逃到页面的 outside 按钮
    const textarea = screen.getByRole('textbox');
    textarea.focus();
    expect(document.activeElement).toBe(textarea);

    const dialog = screen.getByRole('dialog');
    fireEvent.keyDown(dialog, { key: 'Tab' });

    const outside = screen.getByTestId('outside');
    expect(document.activeElement).not.toBe(outside);
  });
});
