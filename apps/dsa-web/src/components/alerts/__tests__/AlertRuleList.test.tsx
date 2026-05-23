import { fireEvent, render, screen } from '@testing-library/react';
import type React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AlertRuleList } from '../AlertRuleList';
import type { AlertRuleItem } from '../../../types/alerts';

const rules: AlertRuleItem[] = [
  {
    id: 1,
    name: '茅台가격 돌파',
    targetScope: 'single_symbol',
    target: '600519',
    alertType: 'price_cross',
    parameters: { direction: 'above', price: 1800 },
    severity: 'warning',
    enabled: true,
    source: 'api',
    cooldownUntil: '2099-05-18T10:30:00',
    cooldownActive: true,
    createdAt: '2026-05-18T09:00:00',
    updatedAt: '2026-05-18T09:30:00',
  },
  {
    id: 2,
    name: 'MACD 골든크로스',
    targetScope: 'single_symbol',
    target: '300750',
    alertType: 'macd_cross',
    parameters: { direction: 'bullish_cross', fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
    severity: 'info',
    enabled: true,
    source: 'api',
    cooldownActive: false,
    createdAt: '2026-05-18T09:00:00',
    updatedAt: '2026-05-18T09:30:00',
  },
  {
    id: 3,
    name: 'KDJ 데드크로스',
    targetScope: 'single_symbol',
    target: '000001',
    alertType: 'kdj_cross',
    parameters: { direction: 'bearish_cross', period: 9, kPeriod: 3, dPeriod: 3 },
    severity: 'warning',
    enabled: true,
    source: 'api',
    cooldownActive: false,
    createdAt: '2026-05-18T09:00:00',
    updatedAt: '2026-05-18T09:30:00',
  },
];

describe('AlertRuleList', () => {
  const onEnabledFilterChange = vi.fn();
  const onAlertTypeFilterChange = vi.fn();
  const onPageChange = vi.fn();
  const onToggleEnabled = vi.fn();
  const onDelete = vi.fn();
  const onTest = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderList(overrides: Partial<React.ComponentProps<typeof AlertRuleList>> = {}) {
    render(
      <AlertRuleList
        rules={rules}
        total={40}
        page={1}
        pageSize={20}
        enabledFilter="all"
        alertTypeFilter="all"
        onEnabledFilterChange={onEnabledFilterChange}
        onAlertTypeFilterChange={onAlertTypeFilterChange}
        onPageChange={onPageChange}
        onToggleEnabled={onToggleEnabled}
        onDelete={onDelete}
        onTest={onTest}
        {...overrides}
      />,
    );
  }

  it('renders rules, filters, and pagination', () => {
    renderList();

    expect(screen.getByText('茅台가격 돌파')).toBeInTheDocument();
    expect(screen.getByText('600519')).toBeInTheDocument();
    expect(screen.getAllByText('가격 돌파').length).toBeGreaterThan(0);
    expect(screen.getByText('이상 1800')).toBeInTheDocument();
    expect(screen.getAllByText('MACD 교차').length).toBeGreaterThan(0);
    expect(screen.getByText('골든크로스 12/26/9')).toBeInTheDocument();
    expect(screen.getByText('데드크로스 9/3/3')).toBeInTheDocument();
    expect(screen.getByText('쿨다운 중')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('활성 상태'), { target: { value: 'enabled' } });
    fireEvent.change(screen.getByLabelText('규칙 유형'), { target: { value: 'price_cross' } });
    fireEvent.click(screen.getByRole('button', { name: '2' }));

    expect(onEnabledFilterChange).toHaveBeenCalledWith('enabled');
    expect(onAlertTypeFilterChange).toHaveBeenCalledWith('price_cross');
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('uses backend cooldownActive instead of parsing cooldownUntil locally', () => {
    renderList({
      rules: [
        {
          ...rules[0],
          cooldownUntil: '2099-05-18T10:30:00',
          cooldownActive: false,
        },
      ],
    });

    expect(screen.getByText('대기 중')).toBeInTheDocument();
  });

  it('renders portfolio scope labels and child-target cooldown hint', () => {
    renderList({
      rules: [
        {
          id: 4,
          name: '持仓 RSI',
          targetScope: 'portfolio_holdings',
          target: 'all',
          alertType: 'rsi_threshold',
          parameters: { direction: 'below', period: 12, threshold: 30 },
          severity: 'warning',
          enabled: true,
          source: 'api',
          cooldownActive: false,
        },
        {
          id: 5,
          name: '组合止损',
          targetScope: 'portfolio_account',
          target: '9',
          alertType: 'portfolio_stop_loss',
          parameters: { mode: 'breach' },
          severity: 'critical',
          enabled: true,
          source: 'api',
          cooldownActive: false,
        },
      ],
    });

    expect(screen.getByText('持仓标的')).toBeInTheDocument();
    expect(screen.getByText('子目标见触发历史')).toBeInTheDocument();
    expect(screen.getByText('账户 9')).toBeInTheDocument();
    expect(screen.getAllByText('组合止损').length).toBeGreaterThan(0);
    expect(screen.getByText('已触发止损')).toBeInTheDocument();
  });

  it('runs test and toggles enabled state', () => {
    renderList();

    fireEvent.click(screen.getAllByRole('button', { name: '테스트' })[0]);
    fireEvent.click(screen.getAllByRole('button', { name: '비활성화' })[0]);

    expect(onTest).toHaveBeenCalledWith(rules[0]);
    expect(onToggleEnabled).toHaveBeenCalledWith(rules[0]);
  });

  it('shows loading text only for the active rule operation', () => {
    renderList({ busyRule: { id: 1, action: 'toggle' } });

    expect(screen.getAllByRole('button', { name: '테스트' })[0]).toBeDisabled();
    expect(screen.getByRole('button', { name: '비활성화 중' })).toHaveAttribute('aria-busy', 'true');
    expect(screen.queryByRole('button', { name: '테스트 중' })).not.toBeInTheDocument();
  });

  it('confirms deletion before calling onDelete', async () => {
    renderList();

    fireEvent.click(screen.getByLabelText('삭제 茅台가격 돌파'));
    expect(await screen.findByRole('heading', { name: '알림 규칙 삭제' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '삭제' }));

    expect(onDelete).toHaveBeenCalledWith(rules[0]);
  });

  it('shows an empty state for no rules', () => {
    renderList({ rules: [], total: 0 });

    expect(screen.getByText('알림 규칙 없음')).toBeInTheDocument();
  });
});
