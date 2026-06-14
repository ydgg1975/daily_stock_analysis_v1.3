import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, Clock3, Cpu, Database, Gauge, RefreshCw } from 'lucide-react';
import { usageApi, type UsageDashboard, type UsageModelBreakdown, type UsagePeriod } from '../api/usage';
import type { ParsedApiError } from '../api/error';
import { ApiErrorAlert, AppPage, Card, EmptyState, PageHeader, StatCard } from '../components/common';
import { cn } from '../utils/cn';

const PERIOD_OPTIONS: Array<{ value: UsagePeriod; label: string }> = [
  { value: 'today', label: '今日' },
  { value: 'month', label: '本月' },
  { value: 'all', label: '全部' },
];

const CALL_TYPE_LABELS: Record<string, string> = {
  analysis: '个股分析',
  agent: '问股 Agent',
  market_review: '大盘复盘',
};

function formatNumber(value: number | null | undefined): string {
  return new Intl.NumberFormat('zh-CN').format(value ?? 0);
}

function formatDateTime(value: string): string {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function getCallTypeLabel(callType: string): string {
  return CALL_TYPE_LABELS[callType] ?? callType;
}

function buildParsedError(error: unknown): ParsedApiError {
  if (error && typeof error === 'object' && 'parsedError' in error) {
    const parsedError = (error as { parsedError?: ParsedApiError }).parsedError;
    if (parsedError) {
      return parsedError;
    }
  }

  const message = error instanceof Error ? error.message : 'Token 用量数据加载失败';
  return {
    title: 'Token 用量加载失败',
    message,
    rawMessage: message,
    category: 'http_error',
  };
}

const ModelUsageCard: React.FC<{ model: UsageModelBreakdown }> = ({ model }) => {
  return (
    <Card padding="sm" className="rounded-lg">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-foreground">{model.model}</h3>
          <p className="mt-1 text-xs text-secondary-text">{formatNumber(model.calls)} 次调用</p>
        </div>
        <span className="rounded-full border border-cyan/20 bg-cyan/10 px-2 py-1 text-xs text-cyan">
          {formatNumber(model.totalTokens)} tokens
        </span>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-xs text-secondary-text">Prompt</p>
          <p className="mt-1 font-medium text-foreground">{formatNumber(model.promptTokens)}</p>
        </div>
        <div>
          <p className="text-xs text-secondary-text">Completion</p>
          <p className="mt-1 font-medium text-foreground">{formatNumber(model.completionTokens)}</p>
        </div>
        <div>
          <p className="text-xs text-secondary-text">单次峰值</p>
          <p className="mt-1 font-medium text-foreground">{formatNumber(model.maxTotalTokens)}</p>
        </div>
      </div>
    </Card>
  );
};

const TokenUsagePage: React.FC = () => {
  const [period, setPeriod] = useState<UsagePeriod>('month');
  const [dashboard, setDashboard] = useState<UsageDashboard | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await usageApi.getDashboard({ period, limit: 50 });
      setDashboard(data);
    } catch (err) {
      setError(buildParsedError(err));
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const largestCallTypeTotal = useMemo(() => {
    return Math.max(...(dashboard?.byCallType.map((item) => item.totalTokens) ?? [0]), 1);
  }, [dashboard]);

  return (
    <AppPage>
      <div className="space-y-5">
        <PageHeader
          eyebrow="Usage"
          title="Token 用量监控"
          description="查看 LLM 调用次数、Prompt/Completion Token 消耗、模型用量和最近调用明细。"
          actions={(
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-xl border border-border/70 bg-card/70 p-1">
                {PERIOD_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setPeriod(option.value)}
                    className={cn(
                      'rounded-lg px-3 py-1.5 text-sm transition-colors',
                      period === option.value
                        ? 'bg-cyan text-background shadow-soft-card'
                        : 'text-secondary-text hover:bg-hover hover:text-foreground'
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="btn-secondary inline-flex items-center gap-2"
                onClick={() => void loadDashboard()}
                disabled={loading}
              >
                <RefreshCw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} />
                刷新
              </button>
            </div>
          )}
        />

        {error ? <ApiErrorAlert error={error} actionLabel="重试" onAction={() => void loadDashboard()} /> : null}

        {loading && !dashboard ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-28 animate-pulse rounded-2xl border border-border/70 bg-card/60" />
            ))}
          </div>
        ) : null}

        {dashboard ? (
          <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard label="总 tokens" value={formatNumber(dashboard.totalTokens)} hint={`${dashboard.fromDate} 至 ${dashboard.toDate}`} icon={<Database className="h-5 w-5" />} tone="primary" />
              <StatCard label="调用次数" value={formatNumber(dashboard.totalCalls)} hint="已记录的 LLM 调用" icon={<Activity className="h-5 w-5" />} />
              <StatCard label="Prompt tokens" value={formatNumber(dashboard.totalPromptTokens)} hint="输入上下文消耗" icon={<Cpu className="h-5 w-5" />} />
              <StatCard label="Completion tokens" value={formatNumber(dashboard.totalCompletionTokens)} hint="模型输出消耗" icon={<Gauge className="h-5 w-5" />} />
            </div>

            {dashboard.totalCalls === 0 ? (
              <EmptyState title="暂无 Token 用量记录" description="完成一次分析、大盘复盘或问股调用后，这里会显示模型用量。" />
            ) : (
              <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
                <section className="space-y-4">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">模型用量</h2>
                    <p className="mt-1 text-sm text-secondary-text">按模型聚合 Token 消耗、调用次数和单次峰值。</p>
                  </div>
                  <div className="grid gap-4">
                    {dashboard.byModel.map((model) => (
                      <ModelUsageCard key={model.model} model={model} />
                    ))}
                  </div>
                </section>

                <section className="space-y-4">
                  <Card title="调用类型" subtitle="Breakdown" className="rounded-lg">
                    <div className="space-y-4">
                      {dashboard.byCallType.map((item) => (
                        <div key={item.callType}>
                          <div className="flex items-center justify-between gap-3 text-sm">
                            <span className="font-medium text-foreground">{getCallTypeLabel(item.callType)}</span>
                            <span className="text-secondary-text">{formatNumber(item.totalTokens)} tokens</span>
                          </div>
                          <div className="mt-2 h-2 overflow-hidden rounded-full bg-border/70">
                            <div
                              className="h-full rounded-full bg-cyan"
                              style={{ width: `${Math.max(4, (item.totalTokens / largestCallTypeTotal) * 100)}%` }}
                            />
                          </div>
                          <p className="mt-1 text-xs text-secondary-text">
                            {formatNumber(item.calls)} 次 · Prompt {formatNumber(item.promptTokens)} · Completion {formatNumber(item.completionTokens)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </Card>
                </section>
              </div>
            )}

            <section className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">最近调用</h2>
                  <p className="mt-1 text-sm text-secondary-text">最近 50 条 LLM token 审计记录。</p>
                </div>
                <Clock3 className="h-5 w-5 text-secondary-text" />
              </div>
              <div className="overflow-hidden rounded-2xl border border-border/70 bg-card/75 shadow-soft-card">
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-border/70 text-sm">
                    <thead className="bg-surface-2/70 text-left text-xs uppercase tracking-[0.16em] text-secondary-text">
                      <tr>
                        <th className="px-4 py-3 font-medium">时间</th>
                        <th className="px-4 py-3 font-medium">类型</th>
                        <th className="px-4 py-3 font-medium">模型</th>
                        <th className="px-4 py-3 text-right font-medium">Prompt</th>
                        <th className="px-4 py-3 text-right font-medium">Completion</th>
                        <th className="px-4 py-3 text-right font-medium">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {dashboard.recentCalls.length ? dashboard.recentCalls.map((item) => (
                        <tr key={item.id} className="hover:bg-hover/60">
                          <td className="whitespace-nowrap px-4 py-3 text-secondary-text">{formatDateTime(item.calledAt)}</td>
                          <td className="whitespace-nowrap px-4 py-3 text-foreground">{getCallTypeLabel(item.callType)}</td>
                          <td className="min-w-56 px-4 py-3">
                            <div className="max-w-[18rem] truncate font-medium text-foreground">{item.model}</div>
                            {item.stockCode ? <div className="text-xs text-secondary-text">{item.stockCode}</div> : null}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-right text-secondary-text">{formatNumber(item.promptTokens)}</td>
                          <td className="whitespace-nowrap px-4 py-3 text-right text-secondary-text">{formatNumber(item.completionTokens)}</td>
                          <td className="whitespace-nowrap px-4 py-3 text-right font-medium text-foreground">{formatNumber(item.totalTokens)}</td>
                        </tr>
                      )) : (
                        <tr>
                          <td colSpan={6} className="px-4 py-8 text-center text-secondary-text">暂无最近调用记录</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          </>
        ) : null}
      </div>
    </AppPage>
  );
};

export default TokenUsagePage;
