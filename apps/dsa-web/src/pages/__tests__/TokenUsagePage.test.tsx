import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TokenUsagePage from '../TokenUsagePage';

const { getDashboard } = vi.hoisted(() => ({
  getDashboard: vi.fn(),
}));

vi.mock('../../api/usage', () => ({
  usageApi: { getDashboard },
}));

const dashboard = {
  period: 'month' as const,
  fromDate: '2026-06-01',
  toDate: '2026-06-11',
  totalCalls: 3,
  totalPromptTokens: 120,
  totalCompletionTokens: 280,
  totalTokens: 400,
  byCallType: [
    {
      callType: 'analysis',
      calls: 2,
      promptTokens: 100,
      completionTokens: 200,
      totalTokens: 300,
    },
    {
      callType: 'agent',
      calls: 1,
      promptTokens: 20,
      completionTokens: 80,
      totalTokens: 100,
    },
  ],
  byModel: [
    {
      model: 'openai/gpt-test',
      provider: 'openai',
      calls: 2,
      promptTokens: 100,
      completionTokens: 200,
      totalTokens: 300,
      maxTotalTokens: 240,
      contextWindow: 1000,
      contextUsageRatio: 0.24,
    },
    {
      model: 'custom-router',
      provider: null,
      calls: 1,
      promptTokens: 20,
      completionTokens: 80,
      totalTokens: 100,
      maxTotalTokens: 100,
      contextWindow: null,
      contextUsageRatio: null,
    },
  ],
  recentCalls: [
    {
      id: 1,
      calledAt: '2026-06-11T09:30:00',
      callType: 'analysis',
      model: 'openai/gpt-test',
      provider: 'openai',
      stockCode: '600519',
      promptTokens: 40,
      completionTokens: 200,
      totalTokens: 240,
      contextWindow: 1000,
      contextUsageRatio: 0.24,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  getDashboard.mockResolvedValue(dashboard);
});

describe('TokenUsagePage', () => {
  it('renders token summary, model rings, breakdowns, and recent calls', async () => {
    render(<TokenUsagePage />);

    expect(await screen.findByRole('heading', { name: 'Token 用量监控' })).toBeInTheDocument();
    expect(await screen.findByText('400')).toBeInTheDocument();
    expect(screen.getAllByText('openai/gpt-test')).toHaveLength(2);
    expect(screen.getByLabelText(/openai\/gpt-test context usage 24%/)).toBeInTheDocument();
    expect(screen.getByText('部分模型缺少上下文窗口')).toBeInTheDocument();
    expect(screen.getAllByText('个股分析')).toHaveLength(2);
    expect(screen.getByText(/600519/)).toBeInTheDocument();
    expect(getDashboard).toHaveBeenCalledWith({ period: 'month', limit: 50 });
  });

  it('reloads dashboard when period changes', async () => {
    render(<TokenUsagePage />);

    await screen.findByRole('heading', { name: 'Token 用量监控' });
    fireEvent.click(screen.getByRole('button', { name: '今日' }));

    await waitFor(() => {
      expect(getDashboard).toHaveBeenLastCalledWith({ period: 'today', limit: 50 });
    });
  });
});
