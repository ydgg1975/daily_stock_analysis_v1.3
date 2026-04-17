import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminLogsPage from '../AdminLogsPage';

const { listSessions, getSessionDetail } = vi.hoisted(() => ({
  listSessions: vi.fn(),
  getSessionDetail: vi.fn(),
}));

vi.mock('../../api/adminLogs', () => ({
  adminLogsApi: {
    listSessions,
    getSessionDetail,
  },
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    t: (key: string, params?: Record<string, unknown>) =>
      key === 'adminLogs.filterHint'
        ? `count:${String(params?.count ?? '')}`
        : key,
  }),
}));

vi.mock('../../components/common', () => ({
  ApiErrorAlert: () => <div>api-error</div>,
}));

describe('AdminLogsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listSessions.mockResolvedValue({
      total: 2,
      items: [
        {
          sessionId: 'admin-action-1',
          name: 'Factory reset',
          overallStatus: 'completed',
          startedAt: '2026-04-15T10:00:00Z',
          readableSummary: {
            actorDisplay: 'Bootstrap Admin',
            actorRole: 'admin',
            sessionKind: 'admin_action',
            subsystem: 'system_control',
            actionName: 'factory_reset_system',
            destructive: true,
          },
        },
        {
          sessionId: 'scanner-run-1',
          name: 'Scanner run',
          overallStatus: 'completed',
          startedAt: '2026-04-15T08:40:00Z',
          readableSummary: {
            actorDisplay: 'Bootstrap Admin',
            actorRole: 'admin',
            sessionKind: 'admin_action',
            subsystem: 'scanner',
            actionName: 'scanner_run',
            destructive: false,
            scannerRunId: 88,
            scannerMarket: 'us',
            scannerShortlistCount: 5,
            scannerFallbackCount: 1,
            scannerProvidersUsed: ['alpaca', 'twelve_data'],
            scannerCoverageSummary: 'Scanned 180 symbols, shortlisted 5.',
          },
        },
        {
          sessionId: 'user-activity-1',
          name: 'AAPL analysis',
          overallStatus: 'completed',
          startedAt: '2026-04-15T09:00:00Z',
          readableSummary: {
            actorDisplay: 'Alice',
            actorRole: 'user',
            sessionKind: 'user_activity',
            subsystem: 'analysis',
            actionName: 'analyze_stock',
            destructive: false,
          },
        },
      ],
    });
    getSessionDetail.mockImplementation(async (sessionId: string) => ({
      sessionId,
      name: sessionId === 'admin-action-1' ? 'Factory reset' : sessionId === 'scanner-run-1' ? 'Scanner run' : 'AAPL analysis',
      overallStatus: 'completed',
      readableSummary: {
        actorDisplay: sessionId === 'admin-action-1' || sessionId === 'scanner-run-1' ? 'Bootstrap Admin' : 'Alice',
        actorRole: sessionId === 'admin-action-1' || sessionId === 'scanner-run-1' ? 'admin' : 'user',
        sessionKind: sessionId === 'admin-action-1' || sessionId === 'scanner-run-1' ? 'admin_action' : 'user_activity',
        subsystem: sessionId === 'admin-action-1' ? 'system_control' : sessionId === 'scanner-run-1' ? 'scanner' : 'analysis',
        actionName: sessionId === 'admin-action-1' ? 'factory_reset_system' : sessionId === 'scanner-run-1' ? 'scanner_run' : 'analyze_stock',
        destructive: sessionId === 'admin-action-1',
        scannerRunId: sessionId === 'scanner-run-1' ? 88 : undefined,
        scannerMarket: sessionId === 'scanner-run-1' ? 'us' : undefined,
        scannerShortlistCount: sessionId === 'scanner-run-1' ? 5 : undefined,
        scannerFallbackCount: sessionId === 'scanner-run-1' ? 1 : undefined,
        scannerProvidersUsed: sessionId === 'scanner-run-1' ? ['alpaca', 'twelve_data'] : undefined,
        scannerCoverageSummary: sessionId === 'scanner-run-1' ? 'Scanned 180 symbols, shortlisted 5.' : undefined,
      },
      events: [
        {
          id: 1,
          phase: sessionId === 'admin-action-1' ? 'system' : sessionId === 'scanner-run-1' ? 'scanner' : 'ai_model',
          status: 'completed',
          detail: {
            action: sessionId === 'admin-action-1' ? 'factory_reset_system' : sessionId === 'scanner-run-1' ? 'scanner_run' : 'analyze_stock',
          },
        },
      ],
    }));
  });

  it('renders global admin observability metadata for both admin actions and user activity', async () => {
    render(<AdminLogsPage />);

    expect(await screen.findByText('adminLogs.globalScopeTitle')).toBeInTheDocument();
    expect((await screen.findAllByText('Bootstrap Admin')).length).toBeGreaterThan(0);
    expect(screen.getByText('AAPL analysis')).toBeInTheDocument();
    expect(screen.getAllByText(/system_control|analysis/).length).toBeGreaterThan(0);
  });

  it('filters between admin/system actions and user activity', async () => {
    render(<AdminLogsPage />);

    expect((await screen.findAllByText('Factory reset')).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText('adminLogs.activityTypeFilter'), {
      target: { value: 'admin_action' },
    });

    await waitFor(() => {
      expect(screen.getAllByText('Factory reset').length).toBeGreaterThan(0);
    });
    expect(screen.queryByText('AAPL analysis')).not.toBeInTheDocument();
  });

  it('renders scanner observability metadata in admin logs', async () => {
    render(<AdminLogsPage />);

    expect(await screen.findByText('Scanner run')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Scanner run/ }));

    await waitFor(() => {
      expect(screen.getByText(/Scanned 180 symbols, shortlisted 5./)).toBeInTheDocument();
    });
    expect(screen.getByText(/alpaca/)).toBeInTheDocument();
    expect(screen.getByText(/twelve_data/)).toBeInTheDocument();
    expect(screen.getByText(/fallback/i)).toBeInTheDocument();
  });

  it('renders a visible empty timeline state instead of crashing when detail events are missing', async () => {
    getSessionDetail.mockResolvedValueOnce({
      sessionId: 'admin-action-1',
      name: 'Factory reset',
      overallStatus: 'completed',
      readableSummary: {
        actorDisplay: 'Bootstrap Admin',
        actorRole: 'admin',
        sessionKind: 'admin_action',
        subsystem: 'system_control',
        actionName: 'factory_reset_system',
      },
    });

    render(<AdminLogsPage />);

    expect(await screen.findByText('Factory reset')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Factory reset/ }));

    await waitFor(() => {
      expect(screen.getByText('adminLogs.emptyTimeline')).toBeInTheDocument();
    });
  });
});
