import type React from 'react';
import { useState } from 'react';
import { Bell, Trash2 } from 'lucide-react';
import { Badge, Button, Card, ConfirmDialog, EmptyState, Pagination, Select } from '../common';
import type { AlertRuleItem, AlertRuleParameters, AlertType } from '../../types/alerts';
import { formatDateTime } from '../../utils/format';

export type AlertRuleEnabledFilter = 'all' | 'enabled' | 'disabled';
export type AlertTypeFilter = 'all' | AlertType;
export type AlertRuleBusyAction = 'test' | 'toggle' | 'delete';

export interface AlertRuleBusyState {
  id: number;
  action: AlertRuleBusyAction;
}

const ENABLED_FILTER_OPTIONS = [
  { value: 'all', label: '전체 상태' },
  { value: 'enabled', label: '활성화됨' },
  { value: 'disabled', label: '비활성화됨' },
];

const ALERT_TYPE_FILTER_OPTIONS = [
  { value: 'all', label: '전체 유형' },
  { value: 'price_cross', label: '가격 돌파' },
  { value: 'price_change_percent', label: '등락률' },
  { value: 'volume_spike', label: '거래량 급증' },
  { value: 'ma_price_cross', label: '가격-이동평균 교차' },
  { value: 'rsi_threshold', label: 'RSI 임계값' },
  { value: 'macd_cross', label: 'MACD 교차' },
  { value: 'kdj_cross', label: 'KDJ 교차' },
  { value: 'cci_threshold', label: 'CCI 임계값' },
];

const typeLabel: Record<AlertType, string> = {
  price_cross: '가격 돌파',
  price_change_percent: '등락률',
  volume_spike: '거래량 급증',
  ma_price_cross: '가격-이동평균 교차',
  rsi_threshold: 'RSI 임계값',
  macd_cross: 'MACD 교차',
  kdj_cross: 'KDJ 교차',
  cci_threshold: 'CCI 임계값',
};

const severityLabel = {
  info: '정보',
  warning: '경고',
  critical: '긴급',
} as const;

function isCoolingDown(rule: AlertRuleItem): boolean {
  if (rule.cooldownActive != null) return rule.cooldownActive;
  return Boolean(rule.cooldownUntil && new Date(rule.cooldownUntil).getTime() > Date.now());
}

function formatDirection(value?: string): string {
  if (value === 'above') return '이상';
  if (value === 'below') return '이하';
  if (value === 'up') return '상승';
  if (value === 'down') return '하락';
  if (value === 'bullish_cross') return '골든크로스';
  if (value === 'bearish_cross') return '데드크로스';
  return value ?? '-';
}

function formatParameters(rule: AlertRuleItem): string {
  const p: AlertRuleParameters = rule.parameters ?? {};
  if (rule.alertType === 'price_cross') return `${formatDirection(p.direction)} ${p.price ?? '-'}`;
  if (rule.alertType === 'price_change_percent') return `${formatDirection(p.direction)} ${p.changePct ?? '-'}%`;
  if (rule.alertType === 'volume_spike') return `${p.multiplier ?? '-'}배`;
  if (rule.alertType === 'ma_price_cross') return `${p.window ?? '-'}일 이동평균 ${formatDirection(p.direction)}`;
  if (rule.alertType === 'rsi_threshold') return `RSI ${p.period ?? '-'}일 ${formatDirection(p.direction)} ${p.threshold ?? '-'}`;
  if (rule.alertType === 'macd_cross') return `${formatDirection(p.direction)} ${p.fastPeriod ?? '-'}/${p.slowPeriod ?? '-'}/${p.signalPeriod ?? '-'}`;
  if (rule.alertType === 'kdj_cross') return `${formatDirection(p.direction)} ${p.period ?? '-'}/${p.kPeriod ?? '-'}/${p.dPeriod ?? '-'}`;
  return `CCI ${p.period ?? '-'}일 ${formatDirection(p.direction)} ${p.threshold ?? '-'}`;
}

function formatTarget(rule: AlertRuleItem): string {
  if (rule.targetScope === 'watchlist') return 'default';
  if (rule.targetScope === 'portfolio_account' || rule.targetScope === 'portfolio_holdings') {
    return rule.target === 'all' ? '全部账户' : `账户 ${rule.target}`;
  }
  return rule.target;
}

function hasChildTargetCooldown(rule: AlertRuleItem): boolean {
  return rule.targetScope === 'watchlist' || rule.targetScope === 'portfolio_holdings';
}

interface AlertRuleListProps {
  rules: AlertRuleItem[];
  total: number;
  page: number;
  pageSize: number;
  isLoading?: boolean;
  enabledFilter: AlertRuleEnabledFilter;
  alertTypeFilter: AlertTypeFilter;
  onEnabledFilterChange: (value: AlertRuleEnabledFilter) => void;
  onAlertTypeFilterChange: (value: AlertTypeFilter) => void;
  onPageChange: (page: number) => void;
  onToggleEnabled: (rule: AlertRuleItem) => void;
  onDelete: (rule: AlertRuleItem) => void;
  onTest: (rule: AlertRuleItem) => void;
  busyRule?: AlertRuleBusyState | null;
  className?: string;
}

export const AlertRuleList: React.FC<AlertRuleListProps> = ({
  rules,
  total,
  page,
  pageSize,
  isLoading = false,
  enabledFilter,
  alertTypeFilter,
  onEnabledFilterChange,
  onAlertTypeFilterChange,
  onPageChange,
  onToggleEnabled,
  onDelete,
  onTest,
  busyRule,
  className,
}) => {
  const [pendingDelete, setPendingDelete] = useState<AlertRuleItem | null>(null);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isRuleBusy = (rule: AlertRuleItem) => busyRule?.id === rule.id;
  const isRuleActionBusy = (rule: AlertRuleItem, action: AlertRuleBusyAction) => busyRule?.id === rule.id && busyRule.action === action;

  return (
    <Card title="알림 규칙" subtitle={`${total}개 규칙`} variant="bordered" padding="md" className={className}>
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        <Select label="활성 상태" value={enabledFilter} options={ENABLED_FILTER_OPTIONS} onChange={(value) => onEnabledFilterChange(value as AlertRuleEnabledFilter)} />
        <Select label="규칙 유형" value={alertTypeFilter} options={ALERT_TYPE_FILTER_OPTIONS} onChange={(value) => onAlertTypeFilterChange(value as AlertTypeFilter)} />
      </div>

      {rules.length === 0 ? (
        <div className="flex min-h-[220px] flex-1 items-center justify-center">
          <EmptyState
            icon={<Bell className="h-6 w-6" />}
            title={isLoading ? '규칙을 불러오는 중' : '알림 규칙 없음'}
            description="규칙을 만들면 백그라운드 평가 작업이 활성화된 알림을 주기적으로 처리합니다."
          />
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead className="border-b border-border/60 text-xs uppercase text-muted-text">
              <tr>
                <th className="px-3 py-2 font-medium">규칙</th>
                <th className="px-3 py-2 font-medium">종목</th>
                <th className="px-3 py-2 font-medium">유형</th>
                <th className="px-3 py-2 font-medium">조건</th>
                <th className="px-3 py-2 font-medium">상태</th>
                <th className="px-3 py-2 font-medium">쿨다운</th>
                <th className="px-3 py-2 font-medium">수정 시간</th>
                <th className="px-3 py-2 text-right font-medium">작업</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {rules.map((rule) => (
                <tr key={rule.id} className="align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium text-foreground">{rule.name}</div>
                    <div className="mt-1 text-xs text-muted-text">출처: {rule.source}</div>
                  </td>
                  <td className="px-3 py-3 text-secondary-text">
                    <div className="font-mono">{formatTarget(rule)}</div>
                    <div className="mt-1 text-xs">{scopeLabel[rule.targetScope] ?? rule.targetScope}</div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <Badge variant="info">{typeLabel[rule.alertType]}</Badge>
                      <Badge variant={rule.severity === 'critical' ? 'danger' : rule.severity === 'warning' ? 'warning' : 'default'}>
                        {severityLabel[rule.severity] ?? rule.severity}
                      </Badge>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-secondary-text">{formatParameters(rule)}</td>
                  <td className="px-3 py-3">
                    <Badge variant={rule.enabled ? 'success' : 'default'}>{rule.enabled ? '활성화됨' : '비활성화됨'}</Badge>
                  </td>
                  <td className="px-3 py-3 text-xs text-secondary-text">
                    <div>{isCoolingDown(rule) ? '쿨다운 중' : '대기 중'}</div>
                    <div className="mt-1">{formatDateTime(rule.cooldownUntil)}</div>
                    {hasChildTargetCooldown(rule) ? (
                      <div className="mt-1 text-muted-text">子目标见触发历史</div>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 text-xs text-secondary-text">{formatDateTime(rule.updatedAt ?? rule.createdAt)}</td>
                  <td className="px-3 py-3">
                    <div className="flex justify-end gap-2">
                      <Button size="xsm" variant="outline" onClick={() => onTest(rule)} isLoading={isRuleActionBusy(rule, 'test')} loadingText="테스트 중" disabled={isRuleBusy(rule) && !isRuleActionBusy(rule, 'test')}>
                        테스트
                      </Button>
                      <Button size="xsm" variant={rule.enabled ? 'secondary' : 'primary'} onClick={() => onToggleEnabled(rule)} isLoading={isRuleActionBusy(rule, 'toggle')} loadingText={rule.enabled ? '비활성화 중' : '활성화 중'} disabled={isRuleBusy(rule) && !isRuleActionBusy(rule, 'toggle')}>
                        {rule.enabled ? '비활성화' : '활성화'}
                      </Button>
                      <Button size="xsm" variant="danger-subtle" aria-label={`삭제 ${rule.name}`} onClick={() => setPendingDelete(rule)} disabled={isRuleBusy(rule)}>
                        <Trash2 className="h-3.5 w-3.5" />
                        삭제
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination currentPage={page} totalPages={totalPages} onPageChange={onPageChange} className="mt-5" />

      <ConfirmDialog
        isOpen={pendingDelete != null}
        title="알림 규칙 삭제"
        message={pendingDelete ? `「${pendingDelete.name}」 규칙을 삭제하시겠습니까? 기존 트리거 기록은 삭제되지 않습니다.` : ''}
        confirmText="삭제"
        cancelText="취소"
        isDanger
        onConfirm={() => {
          if (pendingDelete) onDelete(pendingDelete);
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </Card>
  );
};
