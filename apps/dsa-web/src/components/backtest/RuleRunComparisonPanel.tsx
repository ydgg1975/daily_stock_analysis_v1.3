import type React from 'react';
import { Card } from '../../components/common';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import type { DeterministicBacktestNormalizedResult } from './normalizeDeterministicBacktestResult';
import { Banner, SummaryStrip, formatDateTime, formatNumber, pct } from './shared';
import {
  buildRuleRunComparisonWarnings,
  describeRuleRunNarrative,
  getRuleRunExecutionNotes,
  getRuleRunSetupHighlights,
} from './ruleBacktestP6';
import { getRuleStrategyTypeLabel } from './strategyInspectability';

export type RuleComparisonItem = {
  run: RuleBacktestRunResponse;
  normalized: DeterministicBacktestNormalizedResult;
  label?: string;
  badge?: string;
};

type MetricMode = 'higher' | 'lower' | 'neutral';

type MetricRow = {
  key: string;
  label: string;
  mode: MetricMode;
  values: Array<number | null>;
  renderValue: (value: number | null, item: RuleComparisonItem) => string;
};

function formatMetricValue(
  metric: MetricRow,
  value: number | null,
  item: RuleComparisonItem,
): string {
  return metric.renderValue(value, item);
}

function getMetricCellTone(metric: MetricRow, value: number | null): string {
  if (value == null || metric.mode === 'neutral') return 'default';
  const comparable = metric.values.filter((item): item is number => item != null && Number.isFinite(item));
  if (comparable.length <= 1) return 'default';
  const best = metric.mode === 'lower' ? Math.min(...comparable) : Math.max(...comparable);
  const worst = metric.mode === 'lower' ? Math.max(...comparable) : Math.min(...comparable);
  if (value === best && best !== worst) return 'best';
  if (value === worst && best !== worst) return 'worst';
  return 'default';
}

function buildProgressSeries(
  items: RuleComparisonItem[],
): Array<{
  key: string;
  label: string;
  colorClass: string;
  points: string;
}> {
  const colorClasses = [
    'comparison-chart__line--a',
    'comparison-chart__line--b',
    'comparison-chart__line--c',
    'comparison-chart__line--d',
  ];
  const allValues = items.flatMap((item) => item.normalized.rows.map((row) => row.strategyCumReturn).filter((value): value is number => value != null));
  const min = Math.min(...allValues, 0);
  const max = Math.max(...allValues, 0);
  const span = Math.max(8, max - min);
  const width = 880;
  const height = 220;
  const paddingLeft = 54;
  const paddingRight = 16;
  const paddingTop = 18;
  const paddingBottom = 30;
  const usableWidth = width - paddingLeft - paddingRight;
  const usableHeight = height - paddingTop - paddingBottom;
  const getY = (value: number) => paddingTop + usableHeight - ((value - min) / span) * usableHeight;

  return items.map((item, index) => {
    const rows = item.normalized.rows.filter((row) => row.strategyCumReturn != null);
    const points = rows.map((row, rowIndex) => {
      const x = paddingLeft + (usableWidth * rowIndex) / Math.max(1, rows.length - 1);
      const y = getY(row.strategyCumReturn ?? 0);
      return `${x},${y}`;
    }).join(' ');
    return {
      key: `${item.run.id}-${index}`,
      label: item.label || `#${item.run.id}`,
      colorClass: colorClasses[index % colorClasses.length],
      points,
    };
  });
}

function ComparisonCurveChart({ items }: { items: RuleComparisonItem[] }) {
  if (items.length <= 1) return null;

  const width = 880;
  const height = 220;
  const paddingLeft = 54;
  const paddingRight = 16;
  const paddingTop = 18;
  const paddingBottom = 30;
  const usableWidth = width - paddingLeft - paddingRight;
  const usableHeight = height - paddingTop - paddingBottom;
  const allValues = items.flatMap((item) => item.normalized.rows.map((row) => row.strategyCumReturn).filter((value): value is number => value != null));
  const min = Math.min(...allValues, 0);
  const max = Math.max(...allValues, 0);
  const span = Math.max(8, max - min);
  const getY = (value: number) => paddingTop + usableHeight - ((value - min) / span) * usableHeight;
  const lines = buildProgressSeries(items);
  const ticks = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    const value = max - ratio * span;
    return {
      y: getY(value),
      label: `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`,
    };
  });

  return (
    <div className="comparison-chart">
      <div className="comparison-chart__header">
        <div>
          <span className="product-kicker">对比曲线</span>
          <h3 className="backtest-unified-chart-viewer__panel-title">累计收益进度对比</h3>
        </div>
        <span className="product-inline-meta">按各自回测进度归一化对齐</span>
      </div>
      <div className="chart-card__legend">
        {lines.map((line) => (
          <span key={line.key} className="chart-card__legend-item">
            <span className={`chart-card__legend-swatch ${line.colorClass.replace('__line', '__swatch')}`} />
            {line.label}
          </span>
        ))}
      </div>
      <div className="chart-card__frame">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-card__svg" aria-label="回测比较收益进度图">
          {ticks.map((tick) => (
            <g key={tick.label}>
              <line x1={paddingLeft} y1={tick.y} x2={width - paddingRight} y2={tick.y} className="chart-card__grid" />
              <text x={paddingLeft - 10} y={tick.y + 4} textAnchor="end" className="chart-card__axis-label chart-card__axis-label--y">
                {tick.label}
              </text>
            </g>
          ))}
          <line x1={paddingLeft} y1={height - paddingBottom} x2={width - paddingRight} y2={height - paddingBottom} className="chart-card__grid chart-card__grid--vertical" />
          <text x={paddingLeft} y={height - 10} className="chart-card__axis-label">起点</text>
          <text x={paddingLeft + usableWidth / 2} y={height - 10} textAnchor="middle" className="chart-card__axis-label">中段</text>
          <text x={width - paddingRight} y={height - 10} textAnchor="end" className="chart-card__axis-label">结束</text>
          {lines.map((line) => (
            <polyline key={line.key} className={`comparison-chart__line ${line.colorClass}`} points={line.points} />
          ))}
        </svg>
      </div>
    </div>
  );
}

export const RuleRunComparisonPanel: React.FC<{
  title: string;
  subtitle: string;
  items: RuleComparisonItem[];
  emptyText?: string;
}> = ({ title, subtitle, items, emptyText = '至少选择两条已完成运行后，这里会显示 side-by-side comparison。' }) => {
  if (items.length <= 1) {
    return (
      <Card title={title} subtitle={subtitle} className="product-section-card product-section-card--backtest-secondary">
        <div className="product-empty-state product-empty-state--compact">{emptyText}</div>
      </Card>
    );
  }

  const warnings = buildRuleRunComparisonWarnings(items.map((item) => item.run));
  const rankedByReturn = [...items].sort((left, right) => (right.run.totalReturnPct ?? Number.NEGATIVE_INFINITY) - (left.run.totalReturnPct ?? Number.NEGATIVE_INFINITY));
  const rankedByDrawdown = [...items].sort((left, right) => Math.abs(left.run.maxDrawdownPct ?? Number.POSITIVE_INFINITY) - Math.abs(right.run.maxDrawdownPct ?? Number.POSITIVE_INFINITY));
  const rankedByExcess = [...items].sort((left, right) => ((right.run.excessReturnVsBenchmarkPct ?? right.run.excessReturnVsBuyAndHoldPct) ?? Number.NEGATIVE_INFINITY) - ((left.run.excessReturnVsBenchmarkPct ?? left.run.excessReturnVsBuyAndHoldPct) ?? Number.NEGATIVE_INFINITY));

  const metrics: MetricRow[] = [
    {
      key: 'totalReturn',
      label: '总收益',
      mode: 'higher',
      values: items.map((item) => item.run.totalReturnPct ?? null),
      renderValue: (value) => pct(value),
    },
    {
      key: 'excess',
      label: '相对基准',
      mode: 'higher',
      values: items.map((item) => item.run.excessReturnVsBenchmarkPct ?? item.run.excessReturnVsBuyAndHoldPct ?? null),
      renderValue: (_value, item) => pct(item.run.excessReturnVsBenchmarkPct ?? item.run.excessReturnVsBuyAndHoldPct ?? null),
    },
    {
      key: 'drawdown',
      label: '最大回撤',
      mode: 'lower',
      values: items.map((item) => Math.abs(item.run.maxDrawdownPct ?? 0)),
      renderValue: (_value, item) => pct(item.run.maxDrawdownPct),
    },
    {
      key: 'tradeCount',
      label: '交易次数',
      mode: 'neutral',
      values: items.map((item) => item.run.tradeCount ?? null),
      renderValue: (value) => String(value ?? '--'),
    },
    {
      key: 'winRate',
      label: '胜率',
      mode: 'higher',
      values: items.map((item) => item.run.winRatePct ?? null),
      renderValue: (value) => pct(value),
    },
    {
      key: 'endingEquity',
      label: '期末权益',
      mode: 'higher',
      values: items.map((item) => item.run.finalEquity ?? null),
      renderValue: (value) => formatNumber(value),
    },
  ];

  return (
    <Card title={title} subtitle={subtitle} className="product-section-card product-section-card--backtest-secondary">
      <SummaryStrip
        items={[
          {
            label: '收益最佳',
            value: rankedByReturn[0]?.label || `#${rankedByReturn[0]?.run.id ?? '--'}`,
            note: pct(rankedByReturn[0]?.run.totalReturnPct ?? null),
          },
          {
            label: '超额最佳',
            value: rankedByExcess[0]?.label || `#${rankedByExcess[0]?.run.id ?? '--'}`,
            note: pct(rankedByExcess[0]?.run.excessReturnVsBenchmarkPct ?? rankedByExcess[0]?.run.excessReturnVsBuyAndHoldPct ?? null),
          },
          {
            label: '回撤最轻',
            value: rankedByDrawdown[0]?.label || `#${rankedByDrawdown[0]?.run.id ?? '--'}`,
            note: pct(rankedByDrawdown[0]?.run.maxDrawdownPct ?? null),
          },
        ]}
      />

      {warnings.length > 0 ? (
        <div className="mt-4">
          <Banner
            tone="warning"
            title="比较提醒"
            body={(
              <ul className="backtest-result-page__list">
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
          />
        </div>
      ) : null}

      <div className="comparison-card-grid mt-4">
        {items.map((item) => {
          const narrative = describeRuleRunNarrative(item.run);
          const executionNotes = getRuleRunExecutionNotes(item.run);
          return (
            <article key={item.run.id} className="comparison-card">
              <div className="comparison-card__header">
                <div>
                  <p className="metric-card__label">{item.label || `运行 #${item.run.id}`}</p>
                  <h3 className="comparison-card__title">{getRuleStrategyTypeLabel(item.run.parsedStrategy)}</h3>
                </div>
                {item.badge ? <span className="product-chip">{item.badge}</span> : null}
              </div>
              <p className="comparison-card__meta">
                #{item.run.id} · {item.run.code} · {formatDateTime(item.run.completedAt || item.run.runAt)}
              </p>
              <p className="comparison-card__narrative">{narrative.headline}</p>
              <div className="product-chip-list product-chip-list--tight">
                {getRuleRunSetupHighlights(item.run).map((highlight) => (
                  <span key={`${item.run.id}-${highlight}`} className="product-chip">{highlight}</span>
                ))}
              </div>
              {executionNotes.length > 0 ? (
                <p className="product-footnote comparison-card__footnote">{executionNotes[0]}</p>
              ) : null}
            </article>
          );
        })}
      </div>

      <div className="product-table-shell mt-4">
        <table className="product-table comparison-table">
          <thead>
            <tr>
              <th>指标</th>
              {items.map((item) => (
                <th key={item.run.id}>
                  <div className="product-table__stack">
                    <span>{item.label || `运行 #${item.run.id}`}</span>
                    <span className="product-table__mono">#{item.run.id}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={metric.key}>
                <th>{metric.label}</th>
                {items.map((item) => {
                  const rawValue = metric.key === 'excess'
                    ? item.run.excessReturnVsBenchmarkPct ?? item.run.excessReturnVsBuyAndHoldPct ?? null
                    : metric.key === 'drawdown'
                      ? Math.abs(item.run.maxDrawdownPct ?? 0)
                      : metric.key === 'endingEquity'
                        ? item.run.finalEquity ?? null
                        : metric.key === 'tradeCount'
                          ? item.run.tradeCount ?? null
                          : metric.key === 'winRate'
                            ? item.run.winRatePct ?? null
                            : item.run.totalReturnPct ?? null;
                  const tone = getMetricCellTone(metric, rawValue);
                  return (
                    <td key={`${metric.key}-${item.run.id}`} data-tone={tone}>
                      {formatMetricValue(metric, rawValue, item)}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr>
              <th>策略 / 设置</th>
              {items.map((item) => (
                <td key={`setup-${item.run.id}`}>
                  <div className="product-table__stack">
                    <span>{getRuleStrategyTypeLabel(item.run.parsedStrategy)}</span>
                    <span>{getRuleRunSetupHighlights(item.run).join(' · ')}</span>
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <div className="mt-4">
        <ComparisonCurveChart items={items} />
      </div>
    </Card>
  );
};
