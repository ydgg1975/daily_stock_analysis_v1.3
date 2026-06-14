import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TokenUsagePage from '../TokenUsagePage';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../../api/index', () => ({
  default: { get },
}));

const dashboardResponse = {
  period: 'month',
  from_date: '2026-06-01',
  to_date: '2026-06-11',
  total_calls: 3,
  total_prompt_tokens: 120,
  total_completion_tokens: 280,
  total_tokens: 400,
  by_call_type: [
    {
      call_type: 'analysis',
      calls: 2,
      prompt_tokens: 100,
      completion_tokens: 200,
      total_tokens: 300,
    },
    {
      call_type: 'agent',
      calls: 1,
      prompt_tokens: 20,
      completion_tokens: 80,
      total_tokens: 100,
    },
  ],
  by_model: [
    {
      model: 'openai/gpt-test',
      calls: 2,
      prompt_tokens: 100,
      completion_tokens: 200,
      total_tokens: 300,
      max_total_tokens: 240,
    },
    {
      model: 'custom-router',
      calls: 1,
      prompt_tokens: 20,
      completion_tokens: 80,
      total_tokens: 100,
      max_total_tokens: 100,
    },
  ],
  recent_calls: [
    {
      id: 1,
      called_at: '2026-06-11T09:30:00',
      call_type: 'analysis',
      model: 'openai/gpt-test',
      stock_code: '600519',
      prompt_tokens: 40,
      completion_tokens: 200,
      total_tokens: 240,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  get.mockResolvedValue({ data: dashboardResponse });
});

describe('TokenUsagePage', () => {
  it('renders token summary, model breakdowns, and recent calls from the dashboard API shape', async () => {
    render(<TokenUsagePage />);

    expect(await screen.findByRole('heading', { name: 'Token 用量监控' })).toBeInTheDocument();
    expect(await screen.findByText('400')).toBeInTheDocument();
    expect(screen.getAllByText('openai/gpt-test')).toHaveLength(2);
    expect(screen.getAllByText('个股分析')).toHaveLength(2);
    expect(screen.getByText(/600519/)).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith('/api/v1/usage/dashboard', {
      params: { period: 'month', limit: 50 },
    });
  });

  it('reloads dashboard when period changes', async () => {
    render(<TokenUsagePage />);

    await screen.findByRole('heading', { name: 'Token 用量监控' });
    fireEvent.click(screen.getByRole('button', { name: '今日' }));

    await waitFor(() => {
      expect(get).toHaveBeenLastCalledWith('/api/v1/usage/dashboard', {
        params: { period: 'today', limit: 50 },
      });
    });
  });
});
