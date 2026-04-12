import type React from 'react';
import { useMemo, useState } from 'react';
import { Button, Card } from '../../components/common';
import type { RuleBacktestExecutionTraceRowItem, RuleBacktestRunResponse } from '../../types/backtest';
import { formatDeterministicActionLabel } from './normalizeDeterministicBacktestResult';
import {
  Banner,
  Disclosure,
  SummaryStrip,
  formatNumber,
  pct,
} from './shared';
import {
  downloadExecutionTraceCsv,
  downloadExecutionTraceJson,
  getExecutionTracePayload,
  getExecutionTraceRows,
  getExecutionTraceSourceLabel,
} from './executionTraceUtils';

const TRACE_PREVIEW_LIMIT = 18;

type TraceViewMode = 'highlights' | 'all';

function getTraceExplanation(row: RuleBacktestExecutionTraceRowItem): string {
  const parts = [row.fallback, row.notes, row.unavailableReason]
    .map((value) => String(value || '').trim())
    .filter(Boolean);
  return parts.length > 0 ? parts.join('；') : '--';
}

function isHighlightTraceRow(row: RuleBacktestExecutionTraceRowItem): boolean {
  const action = String(row.action || row.eventType || '').trim().toLowerCase();
  return action !== '' && action !== 'hold'
    || getTraceExplanation(row) !== '--';
}

const ExecutionTracePanel: React.FC<{ run: RuleBacktestRunResponse }> = ({ run }) => {
  const [viewMode, setViewMode] = useState<TraceViewMode>('highlights');
  const trace = getExecutionTracePayload(run);
  const rows = useMemo(() => getExecutionTraceRows(run), [run]);
  const highlightRows = useMemo(
    () => rows.filter((row) => isHighlightTraceRow(row)),
    [rows],
  );
  const previewRows = useMemo(() => {
    const sourceRows = viewMode === 'highlights' ? highlightRows : rows;
    return [...sourceRows].reverse().slice(0, TRACE_PREVIEW_LIMIT);
  }, [highlightRows, rows, viewMode]);
  const fallbackNote = String(trace?.fallback?.note || '').trim();
  const assumptionsSummary = String(trace?.assumptionsDefaults?.summaryText || '').trim();
  const activeRowCount = viewMode === 'highlights' ? highlightRows.length : rows.length;

  return (
    <Card
      title="执行轨迹"
      subtitle="默认先看关键节点，完整轨迹按需展开"
      className="product-section-card product-section-card--backtest-secondary"
    >
      <SummaryStrip
        items={[
          { label: '轨迹来源', value: getExecutionTraceSourceLabel(trace?.source) },
          { label: '轨迹总行数', value: String(rows.length) },
          { label: '关键节点', value: String(highlightRows.length), note: '买卖动作 / 回退 / 异常说明' },
          {
            label: '回退提示',
            value: trace?.fallback?.runFallback ? '存在回退' : trace?.fallback?.traceRebuilt ? '已回补' : '标准路径',
            note: fallbackNote || '无额外说明',
          },
        ]}
      />

      {fallbackNote ? (
        <Banner
          tone={trace?.fallback?.runFallback ? 'warning' : 'info'}
          className="mt-4"
          title="轨迹诊断"
          body={fallbackNote}
        />
      ) : null}

      <div className="summary-block mt-4">
        <div className="summary-block__header">
          <div>
            <h3 className="summary-block__title">关键节点预览</h3>
            <p className="product-section-copy">默认只显示最近的关键节点，避免首屏被逐日持有记录淹没；完整轨迹仍可切换和导出。</p>
          </div>
          <div className="product-action-row">
            <Button variant="secondary" onClick={() => downloadExecutionTraceCsv(run)} disabled={rows.length === 0}>
              导出 CSV
            </Button>
            <Button variant="ghost" onClick={() => downloadExecutionTraceJson(run)} disabled={rows.length === 0}>
              导出 JSON
            </Button>
          </div>
        </div>

        <div className="backtest-mode-toggle mt-4" role="tablist" aria-label="执行轨迹视图">
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'highlights'}
            className={`backtest-mode-toggle__button${viewMode === 'highlights' ? ' is-active' : ''}`}
            onClick={() => setViewMode('highlights')}
          >
            关键节点
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'all'}
            className={`backtest-mode-toggle__button${viewMode === 'all' ? ' is-active' : ''}`}
            onClick={() => setViewMode('all')}
          >
            全部轨迹
          </button>
        </div>

        {previewRows.length === 0 ? (
          <div className="product-empty-state product-empty-state--compact mt-4">暂无可展示的执行轨迹。</div>
        ) : (
          <>
            <div className="product-table-shell mt-4">
              <table className="product-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>动作</th>
                    <th>信号 / 说明</th>
                    <th className="product-table__align-right">策略累计</th>
                    <th className="product-table__align-right">总资产</th>
                    <th>备注</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, index) => (
                    <tr key={`${row.date || 'trace'}-${row.action || row.eventType || 'hold'}-${index}`}>
                      <td>{row.date || '--'}</td>
                      <td>
                        <div className="product-table__stack">
                          <span>{row.actionDisplay || formatDeterministicActionLabel(row.action)}</span>
                          <span>{row.fillPrice != null ? `成交 ${formatNumber(row.fillPrice)}` : '无成交价'}</span>
                        </div>
                      </td>
                      <td>{row.signalSummary || '--'}</td>
                      <td className="product-table__align-right">{pct(row.cumulativeReturn)}</td>
                      <td className="product-table__align-right">{formatNumber(row.totalPortfolioValue)}</td>
                      <td>{getTraceExplanation(row)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="product-footnote mt-4">
              当前显示 {previewRows.length} / {activeRowCount} 行{viewMode === 'highlights' ? '关键节点' : '轨迹'}。导出会包含完整数据。
            </p>
          </>
        )}
      </div>

      {(assumptionsSummary || trace?.executionAssumptions || trace?.executionModel) ? (
        <Disclosure summary="查看执行轨迹高级说明">
          <div className="backtest-result-page__tab-stack">
            {assumptionsSummary ? <p className="product-section-copy">{assumptionsSummary}</p> : null}
            <div className="preview-grid">
              <div className="preview-card">
                <p className="metric-card__label">轨迹来源</p>
                <p className="preview-card__text">{getExecutionTraceSourceLabel(trace?.source)}</p>
              </div>
              <div className="preview-card">
                <p className="metric-card__label">回退标记</p>
                <p className="preview-card__text">{fallbackNote || '标准执行路径'}</p>
              </div>
            </div>
          </div>
        </Disclosure>
      ) : null}
    </Card>
  );
};

export default ExecutionTracePanel;
