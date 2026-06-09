import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SchedulerStatusCard } from '../SchedulerStatusCard';

const { getSchedulerStatus, runSchedulerNow } = vi.hoisted(() => ({
  getSchedulerStatus: vi.fn(),
  runSchedulerNow: vi.fn(),
}));

vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: { getSchedulerStatus, runSchedulerNow },
}));

const baseStatus = {
  available: true,
  enabled: true,
  schedulerRunning: true,
  taskRunning: false,
  scheduleTimes: ['09:20', '12:30'],
  nextRun: '2026-06-09 12:30:00',
  lastStartedAt: null,
  lastFinishedAt: null,
  lastSuccess: null,
  lastError: null,
  runCount: 0,
  skippedCount: 0,
  lastSkippedReason: null,
};

describe('SchedulerStatusCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders effective times and next run from status', async () => {
    getSchedulerStatus.mockResolvedValue(baseStatus);
    render(<SchedulerStatusCard />);

    expect(await screen.findByText('09:20, 12:30')).toBeInTheDocument();
    expect(screen.getByText('2026-06-09 12:30:00')).toBeInTheDocument();
  });

  it('triggers run-now and shows a success notice', async () => {
    getSchedulerStatus.mockResolvedValue(baseStatus);
    runSchedulerNow.mockResolvedValue({ triggered: true, message: 'ok' });
    render(<SchedulerStatusCard />);

    fireEvent.click(await screen.findByRole('button', { name: '立即执行一次' }));

    await waitFor(() => expect(runSchedulerNow).toHaveBeenCalled());
    expect(await screen.findByText('已触发一次定时分析。')).toBeInTheDocument();
  });

  it('shows a skipped notice when a run is already in progress', async () => {
    getSchedulerStatus.mockResolvedValue(baseStatus);
    runSchedulerNow.mockResolvedValue({ triggered: false, message: 'busy' });
    render(<SchedulerStatusCard />);

    fireEvent.click(await screen.findByRole('button', { name: '立即执行一次' }));

    expect(await screen.findByText('已有任务在执行，已跳过本次触发。')).toBeInTheDocument();
  });

  it('disables manual run and shows a note when scheduler service is unavailable', async () => {
    getSchedulerStatus.mockResolvedValue({ ...baseStatus, available: false });
    render(<SchedulerStatusCard />);

    expect(await screen.findByText(/未运行调度服务/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '立即执行一次' })).toBeDisabled();
  });
});
