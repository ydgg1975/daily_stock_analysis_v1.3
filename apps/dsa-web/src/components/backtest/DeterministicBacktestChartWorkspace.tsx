import type React from 'react';
import { useMemo, useRef, useState } from 'react';
import { useElementSize } from '../../hooks/useElementSize';
import { formatNumber, pct } from './shared';
import type { DeterministicResultDensityConfig, DeterministicResultDensityMode } from './deterministicResultDensity';
import type {
  DeterministicBacktestBenchmarkMeta,
  DeterministicBacktestNormalizedResult,
  DeterministicBacktestNormalizedRow,
} from './normalizeDeterministicBacktestResult';
import { formatDeterministicActionLabel } from './normalizeDeterministicBacktestResult';

type PanelLayout = {
  width: number;
  density: DeterministicResultDensityMode;
  config: DeterministicResultDensityConfig;
};

type SharedPanelProps = {
  visibleRows: DeterministicBacktestNormalizedRow[];
  hoveredIndex: number;
  onHoverIndexChange: (index: number, geometry?: { clientX: number; clientY: number }) => void;
  onHoverLeave: () => void;
  benchmarkMeta: DeterministicBacktestBenchmarkMeta;
  layout: PanelLayout;
  surfaceTestId: string;
};

const CHART_BASE_WIDTH = 1180;
const RANGE_BRUSH_WIDTH = 1000;
const RANGE_BRUSH_PADDING = 8;

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function buildTickIndices(count: number, targetTickCount: number): number[] {
  if (count <= 0) return [];
  if (count <= targetTickCount) return Array.from({ length: count }, (_, index) => index);

  const indexes = new Set<number>([0, count - 1]);
  const step = (count - 1) / Math.max(1, targetTickCount - 1);
  for (let index = 1; index < targetTickCount - 1; index += 1) {
    indexes.add(Math.round(step * index));
  }
  return Array.from(indexes).sort((left, right) => left - right);
}

function formatChartDateLabel(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value || '--';
  return `${match[2]}-${match[3]}`;
}

function formatSignedPercent(value: number, digits = 1): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}%`;
}

function formatCompactPnl(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '-' : '';
  const abs = Math.abs(value);
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(abs >= 100000 ? 0 : 1)}万`;
  if (abs >= 1000) return `${sign}${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}k`;
  return `${sign}${abs.toFixed(abs >= 100 ? 0 : 1)}`;
}

function formatPosition(value: number | null | undefined): string | null {
  if (value == null) return null;
  return pct(value * 100);
}

function createPanelLayout(config: DeterministicResultDensityConfig): PanelLayout {
  return {
    width: CHART_BASE_WIDTH,
    density: config.mode,
    config,
  };
}

function ChartSurface({
  rows,
  hoveredIndex,
  onHoverIndexChange,
  onHoverLeave,
  testId,
  x,
  y,
  width,
  height,
}: {
  rows: DeterministicBacktestNormalizedRow[];
  hoveredIndex: number;
  onHoverIndexChange: (index: number, geometry?: { clientX: number; clientY: number }) => void;
  onHoverLeave: () => void;
  testId: string;
  x: number;
  y: number;
  width: number;
  height: number;
}) {
  return (
    <rect
      data-testid={testId}
      x={x}
      y={y}
      width={width}
      height={height}
      fill="transparent"
      pointerEvents="all"
      onMouseMove={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        if (!rect.width || rows.length <= 1) return;
        const ratio = clampNumber((event.clientX - rect.left) / rect.width, 0, 1);
        onHoverIndexChange(Math.round(ratio * (rows.length - 1)), {
          clientX: event.clientX,
          clientY: event.clientY,
        });
      }}
      onFocus={() => {
        if (rows.length > 0) onHoverIndexChange(hoveredIndex);
      }}
      onMouseLeave={onHoverLeave}
    />
  );
}

function buildVisibleTickCount(rowCount: number, width: number, minGap: number, cap: number): number {
  const widthBudget = Math.max(width - 120, minGap * 1.4);
  const widthLimited = Math.max(2, Math.floor(widthBudget / Math.max(minGap, 1)));
  return Math.max(2, Math.min(rowCount, cap, widthLimited));
}

function ReturnPanel({
  visibleRows,
  hoveredIndex,
  onHoverIndexChange,
  onHoverLeave,
  benchmarkMeta,
  layout,
  surfaceTestId,
}: SharedPanelProps) {
  const strategyRows = visibleRows.filter((row) => row.strategyCumReturn != null);
  const strategySeriesLength = strategyRows.length;
  if (!visibleRows.length || !strategySeriesLength) {
    return <div className="backtest-unified-chart-viewer__panel"><div className="product-empty-state product-empty-state--compact">暂无累计收益数据。</div></div>;
  }

  const { width, density, config } = layout;
  const height = config.mainHeight;
  const paddingLeft = density === 'dense' ? 56 : 64;
  const paddingRight = 22;
  const paddingTop = 18;
  const paddingBottom = density === 'dense' ? 34 : density === 'compact' ? 38 : 42;
  const plotRight = width - paddingRight;
  const plotBottom = height - paddingBottom;
  const usableWidth = plotRight - paddingLeft;
  const usableHeight = plotBottom - paddingTop;
  const values = visibleRows.flatMap((row) => [
    ...(row.strategyCumReturn != null ? [row.strategyCumReturn] : []),
    ...(benchmarkMeta.showBenchmark && row.benchmarkCumReturn != null ? [row.benchmarkCumReturn] : []),
    ...(benchmarkMeta.showBuyHold && row.buyHoldCumReturn != null ? [row.buyHoldCumReturn] : []),
  ]);
  const rawMin = Math.min(...values, 0);
  const rawMax = Math.max(...values, 0);
  const padding = Math.max((rawMax - rawMin) * 0.1, 2.5);
  const min = Math.floor((rawMin - padding) / 2) * 2;
  const max = Math.ceil((rawMax + padding) / 2) * 2;
  const span = Math.max(6, max - min);
  const getX = (index: number) => paddingLeft + (usableWidth * index) / Math.max(1, visibleRows.length - 1);
  const getY = (value: number) => paddingTop + usableHeight - ((value - min) / span) * usableHeight;
  const buildPolyline = (selector: (row: DeterministicBacktestNormalizedRow) => number | null) => visibleRows
    .map((row, index) => {
      const value = selector(row);
      return value != null ? `${getX(index)},${getY(value)}` : null;
    })
    .filter(Boolean)
    .join(' ');
  const xTicks = buildTickIndices(
    visibleRows.length,
    buildVisibleTickCount(visibleRows.length, width, config.xTickMinGap, 6),
  ).map((index) => ({
    x: getX(index),
    label: formatChartDateLabel(visibleRows[index]?.date || '--'),
  }));
  const yTicks = Array.from({ length: config.mainYTickCount }, (_, index) => {
    const ratio = config.mainYTickCount === 1 ? 0 : index / (config.mainYTickCount - 1);
    const value = max - ratio * span;
    return { value, y: getY(value), label: formatSignedPercent(value, density === 'dense' ? 0 : 1) };
  });
  const actionRows = visibleRows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => row.action != null);
  const markerIndexes = buildTickIndices(
    actionRows.length,
    Math.max(4, Math.min(config.markerLimit, Math.floor(width / 88))),
  );
  const markers = (actionRows.length > markerIndexes.length
    ? markerIndexes.map((index) => actionRows[index]).filter(Boolean)
    : actionRows)
    .map(({ row, index }) => ({
      key: `${row.date}:${row.action}:${index}`,
      x: getX(index),
      y: getY(row.strategyCumReturn ?? 0),
      action: row.action === 'sell' || row.action === 'forced_close' ? 'sell' : 'buy',
      label: `${formatDeterministicActionLabel(row.action)} · ${row.date}`,
    }));
  const safeHoverIndex = clampNumber(hoveredIndex, 0, visibleRows.length - 1);
  const hoveredRow = visibleRows[safeHoverIndex];
  const hoverX = getX(safeHoverIndex);
  const hoverY = getY(hoveredRow.strategyCumReturn ?? 0);

  return (
    <div className="backtest-unified-chart-viewer__panel backtest-linked-chart" data-density={density} data-series-length={strategySeriesLength}>
      <div className="backtest-unified-chart-viewer__panel-header">
        <div>
          <span className="product-kicker">主图</span>
          <h3 className="backtest-unified-chart-viewer__panel-title">累计收益率</h3>
        </div>
      </div>
      <div className="chart-card__legend">
        <span className="chart-card__legend-item"><span className="chart-card__legend-swatch chart-card__legend-swatch--strategy" />策略</span>
        {benchmarkMeta.showBenchmark ? (
          <span className="chart-card__legend-item"><span className="chart-card__legend-swatch chart-card__legend-swatch--benchmark" />{benchmarkMeta.benchmarkLabel}</span>
        ) : null}
        {benchmarkMeta.showBuyHold ? (
          <span className="chart-card__legend-item"><span className="chart-card__legend-swatch chart-card__legend-swatch--buy-hold" />{benchmarkMeta.buyHoldLabel}</span>
        ) : null}
        <span className="chart-card__legend-item"><span className="chart-card__legend-swatch chart-card__legend-swatch--trades" />买卖点</span>
      </div>
      <div className="chart-card__frame">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-card__svg" aria-label="累计收益率图">
          {yTicks.map((tick) => (
            <g key={`return-y-${tick.label}`}>
              <line x1={paddingLeft} y1={tick.y} x2={plotRight} y2={tick.y} className="chart-card__grid" />
              <text x={paddingLeft - 12} y={tick.y + 4} className="chart-card__axis-label chart-card__axis-label--y" fontSize={config.axisFontSize}>
                {tick.label}
              </text>
            </g>
          ))}
          {xTicks.map((tick) => (
            <g key={`return-x-${tick.label}`}>
              <line x1={tick.x} y1={paddingTop} x2={tick.x} y2={plotBottom} className="chart-card__grid chart-card__grid--vertical" />
              <text x={tick.x} y={height - 14} textAnchor="middle" className="chart-card__axis-label" fontSize={config.axisFontSize}>
                {tick.label}
              </text>
            </g>
          ))}
          <polyline className="chart-card__line chart-card__line--strategy" points={buildPolyline((row) => row.strategyCumReturn)} />
          {benchmarkMeta.showBenchmark ? <polyline className="chart-card__line chart-card__line--benchmark" points={buildPolyline((row) => row.benchmarkCumReturn)} /> : null}
          {benchmarkMeta.showBuyHold ? <polyline className="chart-card__line chart-card__line--buy-hold" points={buildPolyline((row) => row.buyHoldCumReturn)} /> : null}
          {markers.map((marker) => (
            <g key={marker.key} className={`chart-card__marker chart-card__marker--${marker.action}`}>
              {marker.action === 'buy' ? <circle cx={marker.x} cy={marker.y} r={3.2} /> : <rect x={marker.x - 2.8} y={marker.y - 2.8} width={5.6} height={5.6} rx="1.4" />}
              <title>{marker.label}</title>
            </g>
          ))}
          <line x1={hoverX} y1={paddingTop} x2={hoverX} y2={plotBottom} className="backtest-linked-chart__cursor" />
          <circle cx={hoverX} cy={hoverY} r={4.1} className="backtest-linked-chart__focus-dot" />
          <ChartSurface
            rows={visibleRows}
            hoveredIndex={hoveredIndex}
            onHoverIndexChange={onHoverIndexChange}
            onHoverLeave={onHoverLeave}
            testId={surfaceTestId}
            x={paddingLeft}
            y={paddingTop}
            width={usableWidth}
            height={usableHeight}
          />
        </svg>
      </div>
    </div>
  );
}

function DailyPnlPanel({
  visibleRows,
  hoveredIndex,
  onHoverIndexChange,
  onHoverLeave,
  layout,
  surfaceTestId,
}: Omit<SharedPanelProps, 'benchmarkMeta'> & { benchmarkMeta?: DeterministicBacktestBenchmarkMeta }) {
  const seriesLength = visibleRows.filter((row) => row.dailyPnl != null).length;
  if (!visibleRows.length || !seriesLength) {
    return <div className="backtest-unified-chart-viewer__panel"><div className="product-empty-state product-empty-state--compact">暂无每日盈亏数据。</div></div>;
  }

  const { width, density, config } = layout;
  const height = config.dailyHeight;
  const paddingLeft = density === 'dense' ? 56 : 64;
  const paddingRight = 22;
  const paddingTop = 14;
  const paddingBottom = density === 'dense' ? 28 : 34;
  const plotRight = width - paddingRight;
  const plotBottom = height - paddingBottom;
  const usableWidth = plotRight - paddingLeft;
  const usableHeight = plotBottom - paddingTop;
  const values = visibleRows.map((row) => row.dailyPnl ?? 0);
  const amplitude = Math.max(Math.abs(Math.min(...values, 0)), Math.abs(Math.max(...values, 0)), 1);
  const zeroY = paddingTop + usableHeight / 2;
  const getX = (index: number) => paddingLeft + (usableWidth * index) / Math.max(1, visibleRows.length - 1);
  const getY = (value: number) => paddingTop + usableHeight - ((value + amplitude) / (amplitude * 2)) * usableHeight;
  const barWidth = Math.max(2, Math.min(density === 'comfortable' ? 9 : 7, usableWidth / Math.max(visibleRows.length, 1) - 2));
  const bars = visibleRows.map((row, index) => {
    const value = row.dailyPnl ?? 0;
    const y = Math.min(zeroY, getY(value));
    return {
      key: `${row.date}:${index}`,
      x: getX(index) - barWidth / 2,
      y,
      width: barWidth,
      height: Math.max(1.5, Math.abs(getY(value) - zeroY)),
      value,
    };
  });
  const xTicks = buildTickIndices(
    visibleRows.length,
    buildVisibleTickCount(visibleRows.length, width, config.xTickMinGap, 5),
  ).map((index) => ({
    x: getX(index),
    label: formatChartDateLabel(visibleRows[index]?.date || '--'),
  }));
  const yTicks = Array.from({ length: config.subYTickCount + 1 }, (_, index) => {
    const ratio = config.subYTickCount === 0 ? 0 : index / config.subYTickCount;
    const value = amplitude - ratio * amplitude * 2;
    return { value, y: getY(value), label: formatCompactPnl(value) };
  });
  const hoverX = getX(clampNumber(hoveredIndex, 0, visibleRows.length - 1));

  return (
    <div className="backtest-unified-chart-viewer__panel backtest-linked-chart" data-density={density} data-series-length={seriesLength}>
      <div className="backtest-unified-chart-viewer__panel-header">
        <div>
          <span className="product-kicker">子图</span>
          <h3 className="backtest-unified-chart-viewer__panel-title">每日盈亏</h3>
        </div>
      </div>
      <div className="chart-card__frame">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-card__svg" aria-label="每日盈亏图">
          {yTicks.map((tick) => (
            <g key={`daily-y-${tick.label}`}>
              <line x1={paddingLeft} y1={tick.y} x2={plotRight} y2={tick.y} className="chart-card__grid" />
              <text x={paddingLeft - 12} y={tick.y + 4} className="chart-card__axis-label chart-card__axis-label--y" fontSize={config.axisFontSize}>
                {tick.label}
              </text>
            </g>
          ))}
          {xTicks.map((tick) => (
            <text key={`daily-x-${tick.label}`} x={tick.x} y={height - 14} textAnchor="middle" className="chart-card__axis-label" fontSize={config.axisFontSize}>
              {tick.label}
            </text>
          ))}
          {bars.map((bar, index) => (
            <rect
              key={bar.key}
              x={bar.x}
              y={bar.y}
              width={bar.width}
              height={bar.height}
              rx="2"
              className={bar.value >= 0 ? 'chart-card__bar chart-card__bar--positive' : 'chart-card__bar chart-card__bar--negative'}
              opacity={index === hoveredIndex ? 1 : 0.82}
            />
          ))}
          <line x1={hoverX} y1={paddingTop} x2={hoverX} y2={plotBottom} className="backtest-linked-chart__cursor" />
          <ChartSurface
            rows={visibleRows}
            hoveredIndex={hoveredIndex}
            onHoverIndexChange={onHoverIndexChange}
            onHoverLeave={onHoverLeave}
            testId={surfaceTestId}
            x={paddingLeft}
            y={paddingTop}
            width={usableWidth}
            height={usableHeight}
          />
        </svg>
      </div>
    </div>
  );
}

function PositionPanel({
  visibleRows,
  hoveredIndex,
  onHoverIndexChange,
  onHoverLeave,
  layout,
  surfaceTestId,
}: Omit<SharedPanelProps, 'benchmarkMeta'> & { benchmarkMeta?: DeterministicBacktestBenchmarkMeta }) {
  const seriesLength = visibleRows.filter((row) => row.position != null).length;
  if (!visibleRows.length || !seriesLength) {
    return <div className="backtest-unified-chart-viewer__panel"><div className="product-empty-state product-empty-state--compact">暂无仓位数据。</div></div>;
  }

  const { width, density, config } = layout;
  const height = config.positionHeight;
  const paddingLeft = density === 'dense' ? 56 : 64;
  const paddingRight = 22;
  const paddingTop = 14;
  const paddingBottom = density === 'dense' ? 24 : 30;
  const plotRight = width - paddingRight;
  const plotBottom = height - paddingBottom;
  const usableWidth = plotRight - paddingLeft;
  const usableHeight = plotBottom - paddingTop;
  const getX = (index: number) => paddingLeft + (usableWidth * index) / Math.max(1, visibleRows.length - 1);
  const getY = (value: number) => paddingTop + usableHeight - value * usableHeight;
  const line = visibleRows.map((row, index) => `${getX(index)},${getY(clampNumber(row.position ?? 0, 0, 1))}`).join(' ');
  const area = `${paddingLeft},${getY(0)} ${line} ${plotRight},${getY(0)}`;
  const xTicks = buildTickIndices(
    visibleRows.length,
    buildVisibleTickCount(visibleRows.length, width, config.xTickMinGap, 5),
  ).map((index) => ({
    x: getX(index),
    label: formatChartDateLabel(visibleRows[index]?.date || '--'),
  }));
  const markerRows = visibleRows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => row.action != null);
  const markerIndexes = buildTickIndices(
    markerRows.length,
    Math.max(4, Math.min(config.markerLimit, Math.floor(width / 96))),
  );
  const markers = (markerRows.length > markerIndexes.length
    ? markerIndexes.map((index) => markerRows[index]).filter(Boolean)
    : markerRows)
    .map(({ row, index }) => ({
      key: `${row.date}:${row.action}:${index}`,
      x: getX(index),
      y: getY(row.action === 'sell' || row.action === 'forced_close' ? 0.12 : Math.max(0.2, row.position ?? 0.88)),
      action: row.action === 'sell' || row.action === 'forced_close' ? 'sell' : 'buy',
    }));
  const hoverX = getX(clampNumber(hoveredIndex, 0, visibleRows.length - 1));

  return (
    <div className="backtest-unified-chart-viewer__panel backtest-linked-chart" data-density={density} data-series-length={seriesLength}>
      <div className="backtest-unified-chart-viewer__panel-header">
        <div>
          <span className="product-kicker">子图</span>
          <h3 className="backtest-unified-chart-viewer__panel-title">仓位 / 买卖行为</h3>
        </div>
      </div>
      <div className="chart-card__frame">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-card__svg" aria-label="仓位/买卖行为图">
          <line x1={paddingLeft} y1={getY(0)} x2={plotRight} y2={getY(0)} className="chart-card__grid" />
          <line x1={paddingLeft} y1={getY(1)} x2={plotRight} y2={getY(1)} className="chart-card__grid" />
          <text x={paddingLeft - 12} y={getY(1) + 4} className="chart-card__axis-label chart-card__axis-label--y" fontSize={config.axisFontSize}>持仓</text>
          <text x={paddingLeft - 12} y={getY(0) + 4} className="chart-card__axis-label chart-card__axis-label--y" fontSize={config.axisFontSize}>空仓</text>
          <polyline className="chart-card__area-line" points={area} />
          <polyline className="chart-card__line chart-card__line--exposure" points={line} />
          {markers.map((marker) => (
            <g key={marker.key} className={`chart-card__marker chart-card__marker--${marker.action} chart-card__marker--exposure`}>
              {marker.action === 'buy' ? <circle cx={marker.x} cy={marker.y} r={2.8} /> : <rect x={marker.x - 2.6} y={marker.y - 2.6} width={5.2} height={5.2} rx="1.2" />}
            </g>
          ))}
          {xTicks.map((tick) => (
            <text key={`position-x-${tick.label}`} x={tick.x} y={height - 12} textAnchor="middle" className="chart-card__axis-label" fontSize={config.axisFontSize}>
              {tick.label}
            </text>
          ))}
          <line x1={hoverX} y1={paddingTop} x2={hoverX} y2={plotBottom} className="backtest-linked-chart__cursor" />
          <ChartSurface
            rows={visibleRows}
            hoveredIndex={hoveredIndex}
            onHoverIndexChange={onHoverIndexChange}
            onHoverLeave={onHoverLeave}
            testId={surfaceTestId}
            x={paddingLeft}
            y={paddingTop}
            width={usableWidth}
            height={usableHeight}
          />
        </svg>
      </div>
    </div>
  );
}

function RangeBrushPanel({
  allRows,
  visibleStartIndex,
  visibleEndIndex,
  onChange,
  height,
}: {
  allRows: DeterministicBacktestNormalizedRow[];
  visibleStartIndex: number;
  visibleEndIndex: number;
  onChange: (start: number, end: number) => void;
  height: number;
}) {
  if (!allRows.length) return null;

  const width = RANGE_BRUSH_WIDTH;
  const padding = RANGE_BRUSH_PADDING;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const values = allRows.map((row) => row.strategyCumReturn ?? 0);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = Math.max(1, max - min);
  const getX = (index: number) => padding + (plotWidth * index) / Math.max(1, allRows.length - 1);
  const getY = (value: number) => padding + plotHeight - ((value - min) / span) * plotHeight;
  const points = allRows.map((row, index) => `${getX(index)},${getY(row.strategyCumReturn ?? 0)}`).join(' ');
  const leftPct = allRows.length <= 1 ? 0 : (visibleStartIndex / (allRows.length - 1)) * 100;
  const rightPct = allRows.length <= 1 ? 100 : (visibleEndIndex / (allRows.length - 1)) * 100;

  return (
    <div className="backtest-range-brush backtest-unified-chart-viewer__panel backtest-unified-chart-viewer__panel--brush">
      <div className="backtest-unified-chart-viewer__panel-header">
        <div>
          <span className="product-kicker">范围选择</span>
          <h3 className="backtest-unified-chart-viewer__panel-title">联动时间窗口</h3>
        </div>
        <span className="product-inline-meta">{allRows[visibleStartIndex]?.date} {'->'} {allRows[visibleEndIndex]?.date}</span>
      </div>
      <div className="backtest-range-brush__overview">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-card__svg" aria-label="回测范围选择器">
          <polyline className="chart-card__line chart-card__line--strategy backtest-range-brush__line" points={points} />
        </svg>
        <div className="backtest-range-brush__selection" style={{ left: `${leftPct}%`, width: `${Math.max(rightPct - leftPct, 1)}%` }} />
      </div>
      <div className="backtest-range-brush__controls">
        <label className="backtest-range-brush__slider">
          <span>开始</span>
          <input
            aria-label="开始"
            type="range"
            min={0}
            max={Math.max(allRows.length - 1, 0)}
            value={visibleStartIndex}
            onChange={(event) => onChange(Math.min(Number(event.target.value), visibleEndIndex), visibleEndIndex)}
          />
        </label>
        <label className="backtest-range-brush__slider">
          <span>结束</span>
          <input
            aria-label="结束"
            type="range"
            min={0}
            max={Math.max(allRows.length - 1, 0)}
            value={visibleEndIndex}
            onChange={(event) => onChange(visibleStartIndex, Math.max(Number(event.target.value), visibleStartIndex))}
          />
        </label>
      </div>
    </div>
  );
}

function HoverDetail({
  row,
  benchmarkMeta,
  position,
  tooltipRef,
  density,
}: {
  row: DeterministicBacktestNormalizedRow | null;
  benchmarkMeta: DeterministicBacktestBenchmarkMeta;
  position: { left: number; top: number } | null;
  tooltipRef: React.RefObject<HTMLDivElement | null>;
  density: DeterministicResultDensityMode;
}) {
  const positionLabel = formatPosition(row?.position);
  const primaryFields = row ? [
    { label: '日期', value: row.date },
    { label: '策略累计收益', value: pct(row.strategyCumReturn) },
    ...(benchmarkMeta.showBenchmark && row.benchmarkCumReturn != null
      ? [{ label: benchmarkMeta.benchmarkLabel, value: pct(row.benchmarkCumReturn) }]
      : []),
    ...(benchmarkMeta.showBuyHold && row.buyHoldCumReturn != null
      ? [{ label: benchmarkMeta.buyHoldLabel, value: pct(row.buyHoldCumReturn) }]
      : []),
    ...(row.dailyPnl != null ? [{ label: '当日盈亏', value: formatNumber(row.dailyPnl) }] : []),
    ...(row.dailyReturn != null ? [{ label: '当日收益率', value: pct(row.dailyReturn) }] : []),
    ...(positionLabel ? [{ label: '仓位', value: positionLabel }] : []),
    ...(row.action != null ? [{ label: '动作', value: formatDeterministicActionLabel(row.action) }] : []),
    ...(row.fillPrice != null ? [{ label: '成交价', value: formatNumber(row.fillPrice) }] : []),
    ...(row.shares != null ? [{ label: '持仓股数', value: formatNumber(row.shares, 4) }] : []),
    ...(row.cash != null ? [{ label: '现金', value: formatNumber(row.cash) }] : []),
    ...(row.totalValue != null ? [{ label: '总资产', value: formatNumber(row.totalValue) }] : []),
  ] : [];
  const detailBlocks = row ? [
    { label: '信号摘要', value: row.signalSummary || '--' },
    ...(row.notes ? [{ label: '备注', value: row.notes }] : []),
    ...(row.unavailableReason ? [{ label: '不可用说明', value: row.unavailableReason }] : []),
  ] : [];

  return (
    <div
      ref={tooltipRef}
      className="backtest-unified-chart-viewer__hover backtest-unified-chart-viewer__hover--floating"
      data-testid="deterministic-chart-hover-card"
      data-density={density}
      data-visible={position && row ? 'true' : 'false'}
      data-tooltip-left={position ? Math.round(position.left) : ''}
      data-tooltip-top={position ? Math.round(position.top) : ''}
      style={position && row
        ? {
          left: `${position.left}px`,
          top: `${position.top}px`,
        }
        : {
          left: '0px',
          top: '0px',
          opacity: 0,
          visibility: 'hidden',
        }}
    >
      <div className="backtest-unified-chart-viewer__hover-header">
        <div>
          <span className="product-kicker">联动悬停</span>
          <h3 className="backtest-unified-chart-viewer__panel-title">当日详情</h3>
        </div>
        {row ? <span className="product-inline-meta">{row.date}</span> : null}
      </div>
      {!row ? (
        <p className="product-empty-note">将鼠标移到图表上即可查看某一交易日的审计详情。</p>
      ) : (
        <div className="backtest-tooltip">
          <dl className="backtest-tooltip__grid">
          {primaryFields.map((field) => (
            <div key={field.label} className="backtest-tooltip__row">
              <dt className="backtest-tooltip__label" title={field.label}>{field.label}</dt>
              <dd className="backtest-tooltip__value" title={field.value}>{field.value}</dd>
            </div>
          ))}
          </dl>
          <dl className="backtest-tooltip__stack">
            {detailBlocks.map((field) => (
              <div key={field.label} className="backtest-tooltip__section">
                <dt className="backtest-tooltip__label" title={field.label}>{field.label}</dt>
                <dd className="backtest-tooltip__text" title={field.value}>{field.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

function ChartHeader({
  totalRows,
  visibleRowsLength,
  onApplyQuickRange,
}: {
  totalRows: number;
  visibleRowsLength: number;
  onApplyQuickRange: (bars: number | 'all') => void;
}) {
  return (
      <div className="backtest-result-viewer__toolbar">
        <div className="product-chip-list">
          <button type="button" className="product-chip product-chip--interactive" onClick={() => onApplyQuickRange('all')}>全部</button>
          <button type="button" className="product-chip product-chip--interactive" onClick={() => onApplyQuickRange(63)}>近3个月</button>
          <button type="button" className="product-chip product-chip--interactive" onClick={() => onApplyQuickRange(21)}>近1个月</button>
          <span className="product-chip">当前窗口: {visibleRowsLength} 天</span>
          <span className="product-chip">全部区间: {totalRows} 天</span>
        </div>
      <p className="backtest-result-viewer__toolbar-note">brush 控制联动窗口，hover 浮层跟随同一个 hoveredRow。</p>
    </div>
  );
}

export const DeterministicBacktestChartWorkspace: React.FC<{
  normalized: DeterministicBacktestNormalizedResult;
  densityConfig: DeterministicResultDensityConfig;
}> = ({ normalized, densityConfig }) => {
  const layout = useMemo(() => createPanelLayout(densityConfig), [densityConfig]);
  const shellRef = useRef<HTMLDivElement | null>(null);
  const { ref: tooltipRef, size: tooltipSize } = useElementSize<HTMLDivElement>();
  const allRows = normalized.rows;
  const totalRows = allRows.length;
  const [visibleStartIndex, setVisibleStartIndex] = useState(0);
  const [visibleEndIndex, setVisibleEndIndex] = useState(Math.max(totalRows - 1, 0));
  const [hoverIndex, setHoverIndex] = useState(Math.max(totalRows - 1, 0));
  const [hoverAnchor, setHoverAnchor] = useState<{
    x: number;
    y: number;
    shellWidth: number;
    shellHeight: number;
  } | null>(null);

  const safeVisibleStartIndex = totalRows > 0 ? clampNumber(visibleStartIndex, 0, totalRows - 1) : 0;
  const safeVisibleEndIndex = totalRows > 0
    ? clampNumber(Math.max(visibleEndIndex, safeVisibleStartIndex), safeVisibleStartIndex, totalRows - 1)
    : 0;

  const visibleRows = useMemo(
    () => (totalRows > 0 ? allRows.slice(safeVisibleStartIndex, safeVisibleEndIndex + 1) : []),
    [allRows, safeVisibleEndIndex, safeVisibleStartIndex, totalRows],
  );

  const safeHoverIndex = visibleRows.length > 0 ? clampNumber(hoverIndex, 0, visibleRows.length - 1) : 0;
  const hoveredRow = visibleRows[safeHoverIndex] ?? null;
  const tooltipPosition = useMemo(() => {
    if (!hoverAnchor || !hoveredRow) return null;
    const fallbackTooltipWidth = densityConfig.mode === 'comfortable'
      ? 288
      : densityConfig.mode === 'compact'
        ? 256
        : 224;
    const fallbackTooltipHeight = densityConfig.mode === 'comfortable'
      ? 220
      : densityConfig.mode === 'compact'
        ? 200
        : 180;
    const tooltipWidth = tooltipSize.width > 0 ? tooltipSize.width : fallbackTooltipWidth;
    const tooltipHeight = tooltipSize.height > 0 ? tooltipSize.height : fallbackTooltipHeight;
    const offsetX = densityConfig.tooltipOffsetX;
    const offsetY = densityConfig.tooltipOffsetY;
    const minEdge = densityConfig.tooltipEdgePadding;
    let left = hoverAnchor.x + offsetX;
    if (left + tooltipWidth > hoverAnchor.shellWidth - minEdge) {
      left = hoverAnchor.x - tooltipWidth - offsetX;
    }
    left = clampNumber(left, minEdge, Math.max(minEdge, hoverAnchor.shellWidth - tooltipWidth - minEdge));

    let top = hoverAnchor.y + offsetY;
    if (top + tooltipHeight > hoverAnchor.shellHeight - minEdge) {
      top = hoverAnchor.y - tooltipHeight - offsetY;
    }
    top = clampNumber(top, minEdge, Math.max(minEdge, hoverAnchor.shellHeight - tooltipHeight - minEdge));

    return { left, top };
  }, [densityConfig.mode, densityConfig.tooltipEdgePadding, densityConfig.tooltipOffsetX, densityConfig.tooltipOffsetY, hoverAnchor, hoveredRow, tooltipSize.height, tooltipSize.width]);

  const applyVisibleRange = (start: number, end: number) => {
    if (!totalRows) {
      setVisibleStartIndex(0);
      setVisibleEndIndex(0);
      setHoverIndex(0);
      setHoverAnchor(null);
      return;
    }
    const nextStart = clampNumber(start, 0, totalRows - 1);
    const nextEnd = clampNumber(Math.max(end, nextStart), nextStart, totalRows - 1);
    setVisibleStartIndex(nextStart);
    setVisibleEndIndex(nextEnd);
    setHoverIndex((previousHoverIndex) => clampNumber(previousHoverIndex, 0, Math.max(nextEnd - nextStart, 0)));
  };

  const applyQuickRange = (bars: number | 'all') => {
    if (!totalRows) return;
    if (bars === 'all') {
      applyVisibleRange(0, totalRows - 1);
      return;
    }
    const nextEnd = totalRows - 1;
    const nextStart = Math.max(0, nextEnd - bars + 1);
    applyVisibleRange(nextStart, nextEnd);
  };

  const handleHoverIndexChange = (index: number, geometry?: { clientX: number; clientY: number }) => {
    setHoverIndex(index);
    if (!geometry || !shellRef.current) return;
    const shellRect = shellRef.current.getBoundingClientRect();
    setHoverAnchor({
      x: geometry.clientX - shellRect.left,
      y: geometry.clientY - shellRect.top,
      shellWidth: shellRect.width,
      shellHeight: shellRect.height,
    });
  };

  const handleHoverLeave = () => {
    setHoverAnchor(null);
  };

  return (
    <div
      className="backtest-unified-chart-viewer"
      data-testid="deterministic-backtest-chart-workspace"
      data-density={layout.density}
      data-run-id={normalized.viewerMeta.runId}
      data-row-count={normalized.viewerMeta.rowCount}
      data-visible-start-index={safeVisibleStartIndex}
      data-visible-end-index={safeVisibleEndIndex}
      data-visible-rows={visibleRows.length}
      data-hover-index={safeHoverIndex}
      data-hovered-date={hoveredRow?.date ?? ''}
      data-main-series-length={normalized.viewerMeta.strategySeriesLength}
      data-daily-pnl-series-length={normalized.viewerMeta.dailyPnlSeriesLength}
      data-position-series-length={normalized.viewerMeta.positionSeriesLength}
      data-main-panel-height={layout.config.mainHeight}
      data-daily-panel-height={layout.config.dailyHeight}
      data-position-panel-height={layout.config.positionHeight}
      data-brush-height={layout.config.brushHeight}
      data-tooltip-visible={tooltipPosition && hoveredRow ? 'true' : 'false'}
    >
      <ChartHeader totalRows={totalRows} visibleRowsLength={visibleRows.length} onApplyQuickRange={applyQuickRange} />
      <div
        ref={(node) => {
          shellRef.current = node;
        }}
        className="backtest-unified-chart-viewer__workspace-shell"
      >
        <HoverDetail
          row={hoveredRow}
          benchmarkMeta={normalized.benchmarkMeta}
          position={tooltipPosition}
          tooltipRef={tooltipRef}
          density={layout.density}
        />
        <div className="backtest-unified-chart-viewer__panels">
          <ReturnPanel
            visibleRows={visibleRows}
            hoveredIndex={safeHoverIndex}
            onHoverIndexChange={handleHoverIndexChange}
            onHoverLeave={handleHoverLeave}
            benchmarkMeta={normalized.benchmarkMeta}
            layout={layout}
            surfaceTestId="deterministic-chart-surface-return"
          />
          <DailyPnlPanel
            visibleRows={visibleRows}
            hoveredIndex={safeHoverIndex}
            onHoverIndexChange={handleHoverIndexChange}
            onHoverLeave={handleHoverLeave}
            benchmarkMeta={normalized.benchmarkMeta}
            layout={layout}
            surfaceTestId="deterministic-chart-surface-daily-pnl"
          />
          <PositionPanel
            visibleRows={visibleRows}
            hoveredIndex={safeHoverIndex}
            onHoverIndexChange={handleHoverIndexChange}
            onHoverLeave={handleHoverLeave}
            benchmarkMeta={normalized.benchmarkMeta}
            layout={layout}
            surfaceTestId="deterministic-chart-surface-position"
          />
        </div>
      </div>
      <RangeBrushPanel
        allRows={allRows}
        visibleStartIndex={safeVisibleStartIndex}
        visibleEndIndex={safeVisibleEndIndex}
        onChange={applyVisibleRange}
        height={layout.config.brushHeight}
      />
    </div>
  );
};
