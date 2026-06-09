import type React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { Activity, Hash, Layers, Zap } from 'lucide-react';
import type { UsageSummary, UsagePeriod } from '../api/usage';
import { usageApi } from '../api/usage';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Card, PageHeader, StatCard, EmptyState } from '../components/common';

const PERIOD_OPTIONS: { value: UsagePeriod; label: string }[] = [
  { value: 'today', label: '今日' },
  { value: 'month', label: '本月' },
  { value: 'all', label: '全部' },
];

const CALL_TYPE_LABELS: Record<string, string> = {
  analysis: '个股分析',
  agent: 'Agent 问股',
  market_review: '大盘复盘',
  vision: '图片识别',
  system_test: '渠道测试',
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

const UsagePage: React.FC = () => {
  const [period, setPeriod] = useState<UsagePeriod>('month');
  const [data, setData] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const fetchData = useCallback(async (p: UsagePeriod) => {
    setLoading(true);
    setError(null);
    try {
      const res = await usageApi.getSummary(p);
      setData(res);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchData(period);
  }, [period, fetchData]);

  const handlePeriodChange = (p: UsagePeriod) => {
    setPeriod(p);
  };

  const periodSelector = (
    <div className="flex gap-1 rounded-xl border border-subtle bg-card/60 p-1">
      {PERIOD_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => handlePeriodChange(opt.value)}
          className={`rounded-lg px-3 py-1.5 text-sm transition-all ${
            period === opt.value
              ? 'bg-primary-gradient text-[hsl(var(--primary-foreground))] shadow-sm font-medium'
              : 'text-secondary-text hover:text-foreground hover:bg-hover'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4 md:p-6">
      <PageHeader
        title="Token 用量"
        description="LLM 调用次数与 Token 消耗统计"
        actions={periodSelector}
      />

      {error ? (
        <ApiErrorAlert error={error} />
      ) : loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan border-t-transparent" />
        </div>
      ) : !data || data.totalCalls === 0 ? (
        <EmptyState
          title="暂无用量数据"
          description="运行分析或 Agent 问股后，Token 消耗数据将在此显示"
        />
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="总调用次数"
              value={data.totalCalls.toLocaleString()}
              icon={<Hash className="h-5 w-5" />}
              tone="primary"
            />
            <StatCard
              label="总 Token 数"
              value={formatTokens(data.totalTokens)}
              hint={data.totalTokens.toLocaleString()}
              icon={<Zap className="h-5 w-5" />}
              tone="success"
            />
            <StatCard
              label="模型数"
              value={data.byModel.length}
              icon={<Layers className="h-5 w-5" />}
            />
            <StatCard
              label="统计周期"
              value={PERIOD_OPTIONS.find((o) => o.value === period)?.label ?? period}
              hint={`${data.fromDate} ~ ${data.toDate}`}
              icon={<Activity className="h-5 w-5" />}
            />
          </div>

          {/* By call type */}
          <Card title="按调用类型">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-subtle text-left text-xs uppercase tracking-wider text-secondary-text">
                    <th className="pb-3 pr-4 font-medium">类型</th>
                    <th className="pb-3 pr-4 text-right font-medium">调用次数</th>
                    <th className="pb-3 pr-4 text-right font-medium">Token 数</th>
                    <th className="pb-3 font-medium">占比</th>
                  </tr>
                </thead>
                <tbody>
                  {data.byCallType.map((row) => {
                    const pct = data.totalTokens > 0 ? (row.totalTokens / data.totalTokens) * 100 : 0;
                    return (
                      <tr key={row.callType} className="border-b border-subtle/50 last:border-0">
                        <td className="py-3 pr-4 font-medium text-foreground">
                          {CALL_TYPE_LABELS[row.callType] ?? row.callType}
                        </td>
                        <td className="py-3 pr-4 text-right tabular-nums text-secondary-text">
                          {row.calls.toLocaleString()}
                        </td>
                        <td className="py-3 pr-4 text-right tabular-nums text-foreground">
                          {formatTokens(row.totalTokens)}
                        </td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <div className="h-2 w-24 overflow-hidden rounded-full bg-hover">
                              <div
                                className="h-full rounded-full bg-primary-gradient transition-all"
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            </div>
                            <span className="text-xs tabular-nums text-secondary-text">{pct.toFixed(1)}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          {/* By model */}
          <Card title="按模型">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-subtle text-left text-xs uppercase tracking-wider text-secondary-text">
                    <th className="pb-3 pr-4 font-medium">模型</th>
                    <th className="pb-3 pr-4 text-right font-medium">调用次数</th>
                    <th className="pb-3 pr-4 text-right font-medium">Token 数</th>
                    <th className="pb-3 font-medium">占比</th>
                  </tr>
                </thead>
                <tbody>
                  {data.byModel
                    .sort((a, b) => b.totalTokens - a.totalTokens)
                    .map((row) => {
                      const pct = data.totalTokens > 0 ? (row.totalTokens / data.totalTokens) * 100 : 0;
                      return (
                        <tr key={row.model} className="border-b border-subtle/50 last:border-0">
                          <td className="py-3 pr-4 font-medium text-foreground">
                            <code className="rounded bg-hover px-1.5 py-0.5 text-xs">{row.model}</code>
                          </td>
                          <td className="py-3 pr-4 text-right tabular-nums text-secondary-text">
                            {row.calls.toLocaleString()}
                          </td>
                          <td className="py-3 pr-4 text-right tabular-nums text-foreground">
                            {formatTokens(row.totalTokens)}
                          </td>
                          <td className="py-3">
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-24 overflow-hidden rounded-full bg-hover">
                                <div
                                  className="h-full rounded-full bg-primary-gradient transition-all"
                                  style={{ width: `${Math.min(pct, 100)}%` }}
                                />
                              </div>
                              <span className="text-xs tabular-nums text-secondary-text">{pct.toFixed(1)}%</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
};

export default UsagePage;
