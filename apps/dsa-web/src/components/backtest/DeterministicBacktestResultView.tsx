import type React from 'react';
import { useMemo } from 'react';
import { Button, Card } from '../../components/common';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import { DeterministicBacktestChartWorkspace } from './DeterministicBacktestChartWorkspace';
import {
  getDeterministicResultDensityCssVars,
  type DeterministicResultDensityConfig,
  useDeterministicResultDensity,
} from './deterministicResultDensity';
import {
  MetricCard,
  formatNumber,
  pct,
} from './shared';
import {
  formatDeterministicActionLabel,
  normalizeDeterministicBacktestResult,
  type DeterministicBacktestNormalizedResult,
  type DeterministicBacktestNormalizedRow,
  type DeterministicBacktestTradeEvent,
} from './normalizeDeterministicBacktestResult';

function downloadAuditCsv(run: RuleBacktestRunResponse, rows: DeterministicBacktestNormalizedRow[]): void {
  const header = [
    '日期',
    '标的收盘价',
    '基准收盘价',
    '信号摘要',
    '动作',
    '成交价',
    '持股数',
    '现金',
    '持仓市值',
    '总资产',
    '当日盈亏',
    '当日收益率',
    '策略累计收益率',
    '基准累计收益率',
    '买入持有累计收益率',
    '仓位',
    '手续费',
    '滑点',
    '备注',
    '不可用说明',
  ];
  const lines = rows.map((row) => [
    row.date,
    row.symbolClose ?? '',
    row.benchmarkClose ?? '',
    row.signalSummary ?? '',
    formatDeterministicActionLabel(row.action),
    row.fillPrice ?? '',
    row.shares ?? '',
    row.cash ?? '',
    row.holdingsValue ?? '',
    row.totalValue ?? '',
    row.dailyPnl ?? '',
    row.dailyReturn ?? '',
    row.strategyCumReturn ?? '',
    row.benchmarkCumReturn ?? '',
    row.buyHoldCumReturn ?? '',
    row.position ?? '',
    row.fees ?? '',
    row.slippage ?? '',
    row.notes ?? '',
    row.unavailableReason ?? '',
  ]);
  const content = [header, ...lines]
    .map((row) => row.map((cell) => `"${String(cell ?? '').replaceAll('"', '""')}"`).join(','))
    .join('\n');
  const blob = new Blob([`\uFEFF${content}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `backtest-audit-${run.code}-${run.id}.csv`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function DeterministicAuditTable({
  run,
  rows,
}: {
  run: RuleBacktestRunResponse;
  rows: DeterministicBacktestNormalizedRow[];
}) {
  return (
    <Card
      title="日级审计 / 对账"
      subtitle="KPI 与联动图表共用同一份 normalized rows"
      className="product-section-card product-section-card--backtest-standard"
    >
      <div className="backtest-audit-table__header">
        <p className="product-section-copy">每一行审计记录都直接来自 normalized rows，不再由表格自行重建业务数据。</p>
        <Button variant="secondary" onClick={() => downloadAuditCsv(run, rows)}>导出 CSV</Button>
      </div>
      {rows.length === 0 ? (
        <div className="product-empty-state product-empty-state--compact">暂无可导出的日级审计数据。</div>
      ) : (
        <div className="product-table-shell">
          <table className="product-table product-table--audit">
            <thead>
              <tr>
                <th>日期</th>
                <th>动作</th>
                <th className="product-table__align-right">标的收盘</th>
                <th className="product-table__align-right">基准收盘</th>
                <th className="product-table__align-right">成交价</th>
                <th className="product-table__align-right">持股数</th>
                <th className="product-table__align-right">现金</th>
                <th className="product-table__align-right">总资产</th>
                <th className="product-table__align-right">当日盈亏</th>
                <th className="product-table__align-right">当日收益</th>
                <th className="product-table__align-right">策略累计</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`audit-${row.date}`}>
                  <td>{row.date}</td>
                  <td>{formatDeterministicActionLabel(row.action)}</td>
                  <td className="product-table__align-right">{formatNumber(row.symbolClose)}</td>
                  <td className="product-table__align-right">{formatNumber(row.benchmarkClose)}</td>
                  <td className="product-table__align-right">{formatNumber(row.fillPrice)}</td>
                  <td className="product-table__align-right">{formatNumber(row.shares, 4)}</td>
                  <td className="product-table__align-right">{formatNumber(row.cash)}</td>
                  <td className="product-table__align-right">{formatNumber(row.totalValue)}</td>
                  <td className="product-table__align-right">{formatNumber(row.dailyPnl)}</td>
                  <td className="product-table__align-right">{pct(row.dailyReturn)}</td>
                  <td className="product-table__align-right">{pct(row.strategyCumReturn)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function DeterministicTradeEventTable({ events }: { events: DeterministicBacktestTradeEvent[] }) {
  return (
    <Card title="交易 / 事件日志" subtitle="交易表同样只读 normalized tradeEvents" className="product-section-card product-section-card--backtest-standard">
      {events.length === 0 ? (
        <div className="product-empty-state product-empty-state--compact">暂无交易或执行事件。</div>
      ) : (
        <div className="product-table-shell">
          <table className="product-table product-table--audit">
            <thead>
              <tr>
                <th>日期</th>
                <th>动作</th>
                <th className="product-table__align-right">成交价</th>
                <th className="product-table__align-right">持股数</th>
                <th className="product-table__align-right">现金</th>
                <th className="product-table__align-right">总资产</th>
                <th>信号 / 触发</th>
                <th className="product-table__align-right">收益</th>
                <th>来源</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.key}>
                  <td>{event.date}</td>
                  <td>{formatDeterministicActionLabel(event.action)}</td>
                  <td className="product-table__align-right">{formatNumber(event.fillPrice)}</td>
                  <td className="product-table__align-right">{formatNumber(event.shares, 4)}</td>
                  <td className="product-table__align-right">{formatNumber(event.cash)}</td>
                  <td className="product-table__align-right">{formatNumber(event.totalValue)}</td>
                  <td>{event.signalSummary || event.trigger || '--'}</td>
                  <td className="product-table__align-right">{pct(event.returnPct)}</td>
                  <td>{event.source === 'row' ? 'audit row' : 'trade log'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export const DeterministicBacktestResultView: React.FC<{
  run: RuleBacktestRunResponse;
  normalized?: DeterministicBacktestNormalizedResult;
  densityConfig?: DeterministicResultDensityConfig;
}> = ({ run, normalized: providedNormalized, densityConfig }) => {
  const fallbackDensityConfig = useDeterministicResultDensity();
  const resolvedDensity = densityConfig ?? fallbackDensityConfig;
  const normalized = useMemo(
    () => providedNormalized ?? normalizeDeterministicBacktestResult(run),
    [providedNormalized, run],
  );
  const { metrics, benchmarkMeta, viewerMeta } = normalized;
  const annualizedReturn = metrics.annualizedReturnPct != null ? pct(metrics.annualizedReturnPct) : '--';
  const sharpeRatio = metrics.sharpeRatio != null ? formatNumber(metrics.sharpeRatio, 2) : '--';
  const workspaceKey = `${viewerMeta.runId}:${viewerMeta.rowCount}:${viewerMeta.firstDate ?? 'empty'}:${viewerMeta.lastDate ?? 'empty'}`;

  return (
    <div
      className="backtest-result-viewer"
      data-testid="deterministic-backtest-result-view"
      data-run-id={run.id}
      data-row-count={viewerMeta.rowCount}
      data-main-series-length={viewerMeta.strategySeriesLength}
      data-daily-pnl-series-length={viewerMeta.dailyPnlSeriesLength}
      data-position-series-length={viewerMeta.positionSeriesLength}
      data-kpi-count={6}
      data-density={resolvedDensity.mode}
      style={getDeterministicResultDensityCssVars(resolvedDensity)}
    >
      <section className="backtest-display-section" data-testid="backtest-display-section-dashboard">
        <div data-testid="deterministic-result-dashboard">
          <Card
            className="product-section-card product-section-card--backtest-result backtest-result-viewer__dashboard"
            padding="none"
          >
            <div className="backtest-result-viewer__metric-stage" data-testid="deterministic-result-kpi-row">
              <div className="backtest-result-viewer__metric-stage-header">
                <div>
                  <span className="product-kicker">Dashboard</span>
                  <h2 className="backtest-result-viewer__metric-stage-title">关键指标</h2>
                </div>
                <div className="product-chip-list product-chip-list--tight">
                  <span className="product-chip">样本 {viewerMeta.rowCount} 天</span>
                  <span className="product-chip">交易 {metrics.tradeCount}</span>
                  <span className="product-chip">权益 {formatNumber(metrics.finalEquity)}</span>
                </div>
              </div>
              <div className="metric-grid backtest-result-viewer__metric-grid">
                <MetricCard label="总收益" value={pct(metrics.totalReturnPct)} tone="accent" />
                <MetricCard label="年化收益" value={annualizedReturn} />
                <MetricCard label="最大回撤" value={pct(metrics.maxDrawdownPct)} tone="negative" />
                <MetricCard label="夏普" value={sharpeRatio} />
                <MetricCard
                  label={benchmarkMeta.showBenchmark ? benchmarkMeta.benchmarkLabel : '基准收益'}
                  value={benchmarkMeta.showBenchmark ? pct(metrics.benchmarkReturnPct) : '--'}
                />
                <MetricCard
                  label="超额收益"
                  value={benchmarkMeta.showBenchmark ? pct(metrics.excessReturnVsBenchmarkPct) : '--'}
                  tone={benchmarkMeta.showBenchmark
                    ? (metrics.excessReturnVsBenchmarkPct ?? 0) >= 0 ? 'positive' : 'negative'
                    : 'default'}
                />
              </div>
            </div>
            <div className="backtest-result-viewer__chart-stage">
              <DeterministicBacktestChartWorkspace key={workspaceKey} normalized={normalized} densityConfig={resolvedDensity} />
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
};
