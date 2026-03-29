import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { stocksApi, type StockHistoryPoint, type StockIntradayPoint } from '../../api/stocks';
import type {
  StandardReportDecisionPanel,
  StandardReportMarketBlock,
  StandardReportSummaryPanel,
} from '../../types/analysis';
import { cn } from '../../utils/cn';
import { useElementSize } from '../../hooks/useElementSize';

export type ChartViewKey = 'intraday' | 'month' | 'quarter' | 'year' | 'weekly' | 'monthly';

type ChartDatum = {
  stamp: string;
  label: string;
  shortLabel: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
};

type ChartViewConfig = {
  key: ChartViewKey;
  label: string;
  description: string;
  request:
    | { kind: 'intraday'; interval: '5m' | '15m' | '30m'; range: '1d' | '5d' | '1mo' }
    | { kind: 'history'; period: 'daily' | 'weekly' | 'monthly'; days: number };
};

export type ReportPriceChartFixtureView = {
  source?: string;
  data: Array<StockIntradayPoint | StockHistoryPoint>;
};

export type ReportPriceChartFixtures = Partial<Record<ChartViewKey, ReportPriceChartFixtureView>>;

type AnnotationLine = {
  label: string;
  value: number;
  stroke: string;
};

type ChartGeometry = {
  width: number;
  height: number;
  plotLeft: number;
  plotRight: number;
  plotWidth: number;
  priceTop: number;
  priceBottom: number;
  priceHeight: number;
  volumeTop: number;
  volumeBottom: number;
  volumeHeight: number;
  candleWidth: number;
  step: number;
};

const VIEW_CONFIGS: ChartViewConfig[] = [
  {
    key: 'intraday',
    label: '1D',
    description: '5m intraday',
    request: { kind: 'intraday', interval: '5m', range: '1d' },
  },
  {
    key: 'month',
    label: '1M',
    description: 'Daily candles',
    request: { kind: 'history', period: 'daily', days: 30 },
  },
  {
    key: 'quarter',
    label: '3M',
    description: 'Daily candles',
    request: { kind: 'history', period: 'daily', days: 90 },
  },
  {
    key: 'year',
    label: '1Y',
    description: 'Daily context',
    request: { kind: 'history', period: 'daily', days: 365 },
  },
  {
    key: 'weekly',
    label: 'W',
    description: 'Weekly K-line',
    request: { kind: 'history', period: 'weekly', days: 365 },
  },
  {
    key: 'monthly',
    label: 'M',
    description: 'Monthly K-line',
    request: { kind: 'history', period: 'monthly', days: 730 },
  },
];

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

const clamp = (value: number, min: number, max: number): number => Math.max(min, Math.min(max, value));

const formatAxisPrice = (value: number): string => {
  if (!Number.isFinite(value)) {
    return '--';
  }
  if (Math.abs(value) >= 1000) {
    return value.toFixed(0);
  }
  return value.toFixed(2);
};

const formatVolume = (value?: number | null): string => {
  if (!Number.isFinite(value ?? NaN)) {
    return '--';
  }
  const numeric = Number(value);
  if (numeric >= 1_000_000_000) {
    return `${(numeric / 1_000_000_000).toFixed(2)}B`;
  }
  if (numeric >= 1_000_000) {
    return `${(numeric / 1_000_000).toFixed(2)}M`;
  }
  if (numeric >= 1_000) {
    return `${(numeric / 1_000).toFixed(1)}K`;
  }
  return numeric.toFixed(0);
};

const formatShortLabel = (stamp: string, view: ChartViewKey): string => {
  const date = new Date(stamp);
  if (Number.isNaN(date.getTime())) {
    return stamp;
  }
  if (view === 'intraday') {
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  }
  if (view === 'monthly') {
    return date.toLocaleDateString('en-US', { year: '2-digit', month: 'short' });
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const formatLongLabel = (stamp: string, view: ChartViewKey): string => {
  const date = new Date(stamp);
  if (Number.isNaN(date.getTime())) {
    return stamp;
  }
  if (view === 'intraday') {
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

const computeMovingAverage = (values: number[], index: number, length: number): number | undefined => {
  if (index < 0) {
    return undefined;
  }
  const start = Math.max(0, index - length + 1);
  const slice = values.slice(start, index + 1);
  if (slice.length === 0) {
    return undefined;
  }
  const total = slice.reduce((sum, item) => sum + item, 0);
  return Number((total / slice.length).toFixed(2));
};

const buildChartData = (
  items: Array<StockIntradayPoint | StockHistoryPoint>,
  view: ChartViewKey,
): ChartDatum[] => {
  const closes = items.map((item) => item.close);
  return items.map((item, index) => {
    const stamp = 'time' in item ? item.time : item.date;
    return {
      stamp,
      label: formatLongLabel(stamp, view),
      shortLabel: formatShortLabel(stamp, view),
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: Number(item.volume || 0),
      ma5: computeMovingAverage(closes, index, 5),
      ma10: computeMovingAverage(closes, index, 10),
      ma20: computeMovingAverage(closes, index, 20),
    };
  });
};

const buildTickIndices = (count: number, maxTicks = 6): number[] => {
  if (count <= 0) {
    return [];
  }
  if (count <= maxTicks) {
    return Array.from({ length: count }, (_, index) => index);
  }
  const step = Math.max(1, Math.floor((count - 1) / (maxTicks - 1)));
  const values: number[] = [];
  for (let index = 0; index < count; index += step) {
    values.push(index);
  }
  if (values[values.length - 1] !== count - 1) {
    values[values.length - 1] = count - 1;
  }
  return [...new Set(values)];
};

const buildPath = (points: Array<{ x: number; y?: number }>): string => {
  let path = '';
  let started = false;
  points.forEach((point) => {
    if (!isFiniteNumber(point.y)) {
      started = false;
      return;
    }
    if (!started) {
      path += `M ${point.x.toFixed(2)} ${point.y.toFixed(2)} `;
      started = true;
      return;
    }
    path += `L ${point.x.toFixed(2)} ${point.y.toFixed(2)} `;
  });
  return path.trim();
};

const resolveViewSourceLabel = (view: ChartViewKey, responseSource?: string): string => {
  if (responseSource && responseSource.trim()) {
    if (view === 'intraday') {
      return `${responseSource} intraday`;
    }
    return responseSource;
  }
  if (view === 'weekly') {
    return 'Weekly aggregate';
  }
  if (view === 'monthly') {
    return 'Monthly aggregate';
  }
  if (view === 'intraday') {
    return 'Intraday snapshot';
  }
  return 'Daily history';
};

const resolveAnnotationLines = (decisionPanel?: StandardReportDecisionPanel): AnnotationLine[] => {
  const items: AnnotationLine[] = [
    { label: 'Support', value: decisionPanel?.supportLevel ?? NaN, stroke: 'var(--theme-chart-support)' },
    { label: 'Resistance', value: decisionPanel?.resistanceLevel ?? NaN, stroke: 'var(--theme-chart-resistance)' },
    { label: 'Entry', value: decisionPanel?.idealEntryCenter ?? NaN, stroke: 'var(--theme-chart-entry)' },
    { label: 'Stop', value: decisionPanel?.stopLossLevel ?? NaN, stroke: 'var(--theme-chart-stop)' },
    { label: 'Target 1', value: decisionPanel?.targetOneLevel ?? NaN, stroke: 'var(--theme-chart-target)' },
    { label: 'Target 2', value: decisionPanel?.targetTwoLevel ?? NaN, stroke: 'var(--theme-chart-target-strong)' },
  ];
  return items.filter((item) => isFiniteNumber(item.value));
};

const normalizeFieldLabel = (value: string): string => value.trim().toLowerCase();

const pickMarketFieldValue = (
  market: StandardReportMarketBlock | undefined,
  labels: string[],
): string | undefined => {
  const wanted = new Set(labels.map(normalizeFieldLabel));
  const match = (market?.displayFields || market?.regularFields || []).find((field) =>
    wanted.has(normalizeFieldLabel(field.label)),
  );
  const value = String(match?.value || '').trim();
  return value || undefined;
};

type ChartStat = {
  label: string;
  value?: string;
  emphasis?: 'primary' | 'default';
};

interface ReportPriceChartProps {
  stockCode: string;
  stockName?: string;
  summary?: StandardReportSummaryPanel;
  market?: StandardReportMarketBlock;
  decisionPanel?: StandardReportDecisionPanel;
  integrated?: boolean;
  fixtures?: ReportPriceChartFixtures;
}

export const ReportPriceChart: React.FC<ReportPriceChartProps> = ({
  stockCode,
  stockName,
  summary,
  market,
  decisionPanel,
  integrated = false,
  fixtures,
}) => {
  const [activeView, setActiveView] = useState<ChartViewKey>('intraday');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<Record<ChartViewKey, ChartDatum[]>>({
    intraday: [],
    month: [],
    quarter: [],
    year: [],
    weekly: [],
    monthly: [],
  });
  const [sourceByView, setSourceByView] = useState<Record<ChartViewKey, string>>({
    intraday: '',
    month: '',
    quarter: '',
    year: '',
    weekly: '',
    monthly: '',
  });
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const { ref: chartRef, size } = useElementSize<HTMLDivElement>();

  useEffect(() => {
    setActiveView('intraday');
    setHoveredIndex(null);
    setError(null);
    setChartData({
      intraday: [],
      month: [],
      quarter: [],
      year: [],
      weekly: [],
      monthly: [],
    });
    setSourceByView({
      intraday: '',
      month: '',
      quarter: '',
      year: '',
      weekly: '',
      monthly: '',
    });
  }, [stockCode]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const viewConfig = VIEW_CONFIGS.find((item) => item.key === activeView);
        if (!viewConfig) {
          throw new Error('Unknown chart view');
        }

        const fixture = fixtures?.[activeView];
        if (fixture) {
          if (cancelled) {
            return;
          }
          setChartData((current) => ({
            ...current,
            [activeView]: buildChartData(fixture.data || [], activeView),
          }));
          setSourceByView((current) => ({
            ...current,
            [activeView]: resolveViewSourceLabel(activeView, fixture.source || viewConfig.description),
          }));
          return;
        }

        if (viewConfig.request.kind === 'intraday') {
          const response = await stocksApi.getIntraday(stockCode, {
            interval: viewConfig.request.interval,
            range: viewConfig.request.range,
          });
          if (cancelled) {
            return;
          }
          setChartData((current) => ({
            ...current,
            [activeView]: buildChartData(response.data || [], activeView),
          }));
          setSourceByView((current) => ({
            ...current,
            [activeView]: resolveViewSourceLabel(activeView, response.source ?? undefined),
          }));
          return;
        }

        const response = await stocksApi.getHistory(stockCode, {
          period: viewConfig.request.period,
          days: viewConfig.request.days,
        });
        if (cancelled) {
          return;
        }
        setChartData((current) => ({
          ...current,
          [activeView]: buildChartData(response.data || [], activeView),
        }));
        setSourceByView((current) => ({
          ...current,
          [activeView]: resolveViewSourceLabel(activeView, viewConfig.description),
        }));
      } catch (fetchError) {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : 'Chart data failed to load');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [activeView, fixtures, stockCode]);

  const activeData = chartData[activeView];
  const latestBar = activeData[activeData.length - 1];
  const activeIndex = hoveredIndex != null
    ? clamp(hoveredIndex, 0, Math.max(activeData.length - 1, 0))
    : Math.max(activeData.length - 1, 0);
  const activeBar = activeData[activeIndex];

  const annotationLines = useMemo(
    () => resolveAnnotationLines(decisionPanel),
    [decisionPanel],
  );

  const chartGeometry = useMemo<ChartGeometry | null>(() => {
    if (size.width <= 0 || size.height <= 0) {
      return null;
    }
    const width = size.width;
    const height = size.height;
    const plotLeft = 10;
    const plotRight = Math.max(width - 72, plotLeft + 80);
    const plotWidth = Math.max(plotRight - plotLeft, 120);
    const bottomPadding = 24;
    const priceTop = 14;
    const volumeHeight = Math.max(64, height * 0.2);
    const gap = 20;
    const priceHeight = Math.max(height - priceTop - bottomPadding - volumeHeight - gap, 180);
    const priceBottom = priceTop + priceHeight;
    const volumeTop = priceBottom + gap;
    const volumeBottom = volumeTop + volumeHeight;
    const step = activeData.length > 1 ? plotWidth / (activeData.length - 1) : plotWidth;
    const candleWidth = clamp(step * 0.56, 3.5, activeView === 'intraday' ? 7.5 : 12);

    return {
      width,
      height,
      plotLeft,
      plotRight,
      plotWidth,
      priceTop,
      priceBottom,
      priceHeight,
      volumeTop,
      volumeBottom,
      volumeHeight,
      candleWidth,
      step,
    };
  }, [activeData.length, activeView, size.height, size.width]);

  const priceDomain = useMemo(() => {
    const values = activeData.flatMap((item) => [item.low, item.high]);
    annotationLines.forEach((item) => values.push(item.value));
    if (isFiniteNumber(decisionPanel?.analysisPrice)) {
      values.push(decisionPanel.analysisPrice);
    }
    if (values.length === 0) {
      return null;
    }
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const range = Math.max(maxValue - minValue, Math.max(Math.abs(maxValue) * 0.02, 1));
    const padding = Math.max(range * 0.08, Math.abs(maxValue) * 0.006, 0.5);
    return {
      min: minValue - padding,
      max: maxValue + padding,
    };
  }, [activeData, annotationLines, decisionPanel?.analysisPrice]);

  const volumeMax = useMemo(
    () => Math.max(...activeData.map((item) => item.volume || 0), 1),
    [activeData],
  );

  const xAt = useCallback((index: number): number => {
    if (!chartGeometry) {
      return 0;
    }
    if (activeData.length <= 1) {
      return chartGeometry.plotLeft + chartGeometry.plotWidth / 2;
    }
    return chartGeometry.plotLeft + chartGeometry.step * index;
  }, [activeData.length, chartGeometry]);

  const priceY = useCallback((value: number): number => {
    if (!chartGeometry || !priceDomain) {
      return 0;
    }
    const denominator = Math.max(priceDomain.max - priceDomain.min, 0.0001);
    return chartGeometry.priceTop + ((priceDomain.max - value) / denominator) * chartGeometry.priceHeight;
  }, [chartGeometry, priceDomain]);

  const volumeY = useCallback((value: number): number => {
    if (!chartGeometry) {
      return 0;
    }
    const ratio = value <= 0 ? 0 : value / volumeMax;
    return chartGeometry.volumeBottom - ratio * chartGeometry.volumeHeight;
  }, [chartGeometry, volumeMax]);

  const priceTicks = useMemo(() => {
    if (!priceDomain) {
      return [];
    }
    return Array.from({ length: 5 }, (_, index) => {
      const ratio = index / 4;
      return priceDomain.max - (priceDomain.max - priceDomain.min) * ratio;
    });
  }, [priceDomain]);

  const xTickIndices = useMemo(() => buildTickIndices(activeData.length, 6), [activeData.length]);

  const ma5Path = useMemo(
    () => buildPath(activeData.map((item, index) => ({ x: xAt(index), y: item.ma5 != null ? priceY(item.ma5) : undefined }))),
    [activeData, priceY, xAt],
  );
  const ma10Path = useMemo(
    () => buildPath(activeData.map((item, index) => ({ x: xAt(index), y: item.ma10 != null ? priceY(item.ma10) : undefined }))),
    [activeData, priceY, xAt],
  );
  const ma20Path = useMemo(
    () => buildPath(activeData.map((item, index) => ({ x: xAt(index), y: item.ma20 != null ? priceY(item.ma20) : undefined }))),
    [activeData, priceY, xAt],
  );

  const resolveHoverIndex = (clientX: number): number | null => {
    if (!chartGeometry || !chartRef.current || activeData.length === 0) {
      return null;
    }
    const rect = chartRef.current.getBoundingClientRect();
    const localX = clamp(clientX - rect.left, chartGeometry.plotLeft, chartGeometry.plotRight);
    if (activeData.length <= 1) {
      return 0;
    }
    return clamp(Math.round((localX - chartGeometry.plotLeft) / chartGeometry.step), 0, activeData.length - 1);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const index = resolveHoverIndex(event.clientX);
    if (index != null) {
      setHoveredIndex(index);
    }
  };

  const handlePointerLeave = () => {
    setHoveredIndex(null);
  };

  const chartShellClass = integrated
    ? 'theme-chart-shell report-hero-chart'
    : 'theme-chart-shell theme-panel-solid px-4 py-4 md:px-5 md:py-5';

  const tooltipLeft = useMemo(() => {
    if (!chartGeometry || hoveredIndex == null) {
      return 16;
    }
    const x = xAt(hoveredIndex);
    const preferred = x > chartGeometry.width * 0.62 ? x - 212 : x + 14;
    return clamp(preferred, 12, Math.max(chartGeometry.width - 220, 12));
  }, [chartGeometry, hoveredIndex, xAt]);

  const legendItems = useMemo(() => {
    const items = [
      { label: 'Candles', color: 'var(--theme-chart-bull)' },
      { label: 'Volume', color: 'var(--theme-chart-volume)' },
      { label: 'MA5', color: 'var(--theme-chart-ma5)' },
      { label: 'MA10', color: 'var(--theme-chart-ma10)' },
      { label: 'MA20', color: 'var(--theme-chart-ma20)' },
    ];
    annotationLines.slice(0, 3).forEach((item) => {
      items.push({ label: item.label, color: item.stroke });
    });
    return items;
  }, [annotationLines]);

  const priceContextNote = summary?.priceContextNote || summary?.priceBasisDetail || 'This chart uses the same reference price basis as the report.';
  const activeViewConfig = VIEW_CONFIGS.find((item) => item.key === activeView);
  const marketStats = useMemo(() => {
    const analysisPrice = String(summary?.currentPrice || '').trim()
      || pickMarketFieldValue(market, ['Analysis Price', 'Reference Price', 'Current Price']);
    const previousClose = pickMarketFieldValue(market, ['Prev Close']);
    const open = pickMarketFieldValue(market, ['Session Open', 'Regular Open', 'Open']);
    const high = pickMarketFieldValue(market, ['Session High', 'Regular High', 'High']);
    const low = pickMarketFieldValue(market, ['Session Low', 'Regular Low', 'Low']);
    const volume = pickMarketFieldValue(market, ['Volume']);
    const turnover = pickMarketFieldValue(market, ['Turnover', 'Amount']);

    const desktop: ChartStat[] = [
      { label: 'Analysis', value: analysisPrice, emphasis: 'primary' as const },
      { label: 'Prev close', value: previousClose },
      { label: 'Open', value: open },
      { label: 'High', value: high },
      { label: 'Low', value: low },
      { label: 'Volume', value: volume },
      { label: 'Turnover', value: turnover },
    ].filter((item) => Boolean(item.value));

    const mobile: ChartStat[] = [
      { label: 'Analysis', value: analysisPrice, emphasis: 'primary' as const },
      { label: 'Open', value: open },
      { label: 'High', value: high },
      { label: 'Low', value: low },
      { label: 'Prev close', value: previousClose },
      { label: 'Volume', value: volume },
    ].filter((item) => Boolean(item.value));

    return { desktop, mobile };
  }, [market, summary?.currentPrice]);
  const compactContextLine = useMemo(() => {
    const parts = [
      summary?.priceBasis,
      summary?.snapshotTime ? `Updated ${summary.snapshotTime}` : undefined,
      sourceByView[activeView] ? `Feed ${sourceByView[activeView]}` : undefined,
    ].filter(Boolean);
    return parts.join(' · ');
  }, [activeView, sourceByView, summary?.priceBasis, summary?.snapshotTime]);

  return (
    <div className={chartShellClass} data-testid="report-price-chart">
      <div className={cn('flex flex-col gap-4', integrated ? 'pt-1' : '')}>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">Market chart</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              <h3 className="text-lg font-semibold tracking-tight text-foreground">
                {stockName || stockCode}
              </h3>
              <span className="text-sm text-muted-text">{activeViewConfig?.description || 'Market chart'}</span>
            </div>
            <p className="mt-2 hidden max-w-4xl text-sm leading-6 text-secondary-text md:block">
              Candles, volume and trade-plan markers all use the same price basis as the report so the chart and execution levels stay in sync.
            </p>
            <p className="mt-2 text-xs leading-5 text-muted-text md:hidden">{compactContextLine || priceContextNote}</p>
          </div>

          <div className="theme-chart-toolbar flex flex-nowrap items-center gap-2 overflow-x-auto pb-1">
            {VIEW_CONFIGS.map((view) => (
              <button
                key={view.key}
                type="button"
                onClick={() => setActiveView(view.key)}
                className={cn('theme-chart-tab', activeView === view.key ? 'is-active' : '')}
              >
                <span className="font-medium">{view.label}</span>
                <span className="text-[10px] uppercase tracking-[0.16em] text-muted-text">{view.description}</span>
              </button>
            ))}
          </div>
        </div>

        {marketStats.mobile.length > 0 ? (
          <div className="theme-chart-kpi-grid md:hidden">
            {marketStats.mobile.map((item) => (
              <div key={`${item.label}-${item.value}`} className={cn('theme-chart-kpi', item.emphasis === 'primary' && 'theme-chart-kpi--primary')}>
                <span className="theme-chart-kpi-label">{item.label}</span>
                <span className="theme-chart-kpi-value">{item.value}</span>
              </div>
            ))}
          </div>
        ) : null}

        {marketStats.desktop.length > 0 ? (
          <div className="theme-chart-kpi-grid hidden md:grid">
            {marketStats.desktop.map((item) => (
              <div key={`${item.label}-${item.value}`} className={cn('theme-chart-kpi', item.emphasis === 'primary' && 'theme-chart-kpi--primary')}>
                <span className="theme-chart-kpi-label">{item.label}</span>
                <span className="theme-chart-kpi-value">{item.value}</span>
              </div>
            ))}
          </div>
        ) : null}

        <div className="theme-chart-legend hidden flex-wrap items-center gap-2.5 md:flex">
          {legendItems.map((item) => (
            <span key={item.label} className="theme-chart-legend-item">
              <span className="theme-chart-legend-swatch" style={{ background: item.color }} />
              <span>{item.label}</span>
            </span>
          ))}
        </div>

        <div className="theme-chart-canvas">
          <div
            ref={chartRef}
            className="theme-chart-stage relative h-[300px] w-full sm:h-[340px] md:h-[420px] xl:h-[460px]"
            onPointerMove={handlePointerMove}
            onPointerDown={handlePointerMove}
            onPointerLeave={handlePointerLeave}
          >
            {loading ? (
              <div className="flex h-full items-center justify-center text-sm text-secondary-text">Loading market chart…</div>
            ) : error ? (
              <div className="flex h-full items-center justify-center text-sm text-secondary-text">{error}</div>
            ) : activeData.length === 0 || !chartGeometry || !priceDomain ? (
              <div className="flex h-full items-center justify-center text-sm text-secondary-text">No chart data available for this view.</div>
            ) : (
              <>
                <svg width={chartGeometry.width} height={chartGeometry.height} role="img" aria-label={`${stockCode} market chart`}>
                  <defs>
                    <linearGradient id="chartVolumeFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="var(--theme-chart-volume)" stopOpacity="0.52" />
                      <stop offset="100%" stopColor="var(--theme-chart-volume)" stopOpacity="0.14" />
                    </linearGradient>
                  </defs>

                  <rect x={0} y={0} width={chartGeometry.width} height={chartGeometry.height} fill="transparent" />

                  {priceTicks.map((tick) => {
                    const y = priceY(tick);
                    return (
                      <g key={`tick-${tick.toFixed(4)}`}>
                        <line
                          x1={chartGeometry.plotLeft}
                          x2={chartGeometry.plotRight}
                          y1={y}
                          y2={y}
                          stroke="var(--theme-chart-grid)"
                          strokeDasharray="3 4"
                        />
                        <text
                          x={chartGeometry.plotRight + 8}
                          y={y + 4}
                          fontSize={11}
                          fill="var(--theme-chart-axis)"
                        >
                          {formatAxisPrice(tick)}
                        </text>
                      </g>
                    );
                  })}

                  <line
                    x1={chartGeometry.plotLeft}
                    x2={chartGeometry.plotRight}
                    y1={chartGeometry.volumeTop - 8}
                    y2={chartGeometry.volumeTop - 8}
                    stroke="var(--theme-chart-grid)"
                  />

                  {annotationLines.map((line, index) => {
                    const y = priceY(line.value);
                    return (
                      <g key={`${line.label}-${line.value}-${index}`}>
                        <line
                          x1={chartGeometry.plotLeft}
                          x2={chartGeometry.plotRight}
                          y1={y}
                          y2={y}
                          stroke={line.stroke}
                          strokeDasharray="5 5"
                          strokeWidth={1.1}
                          opacity={0.9}
                        />
                        <rect
                          x={chartGeometry.plotRight - 110}
                          y={y - 11}
                          width={102}
                          height={18}
                          rx={9}
                          fill="color-mix(in srgb, var(--theme-chart-tooltip-bg) 88%, transparent)"
                          opacity={0.92}
                        />
                        <text
                          x={chartGeometry.plotRight - 104}
                          y={y + 2}
                          fontSize={10.5}
                          fill={line.stroke}
                        >
                          {`${line.label} ${formatAxisPrice(line.value)}`}
                        </text>
                      </g>
                    );
                  })}

                  {ma20Path ? <path d={ma20Path} fill="none" stroke="var(--theme-chart-ma20)" strokeWidth={1.75} /> : null}
                  {ma10Path ? <path d={ma10Path} fill="none" stroke="var(--theme-chart-ma10)" strokeWidth={1.6} /> : null}
                  {ma5Path ? <path d={ma5Path} fill="none" stroke="var(--theme-chart-ma5)" strokeWidth={1.55} /> : null}

                  {activeData.map((datum, index) => {
                    const x = xAt(index);
                    const wickTop = priceY(datum.high);
                    const wickBottom = priceY(datum.low);
                    const openY = priceY(datum.open);
                    const closeY = priceY(datum.close);
                    const candleTop = Math.min(openY, closeY);
                    const candleHeight = Math.max(Math.abs(closeY - openY), 1.8);
                    const bullish = datum.close >= datum.open;
                    const bodyFill = bullish ? 'var(--theme-chart-bull-fill)' : 'var(--theme-chart-bear-fill)';
                    const bodyStroke = bullish ? 'var(--theme-chart-bull)' : 'var(--theme-chart-bear)';
                    const volumeTop = volumeY(datum.volume || 0);
                    const active = index === activeIndex;

                    return (
                      <g key={`${datum.stamp}-${index}`}>
                        <rect
                          x={x - chartGeometry.candleWidth / 2}
                          y={volumeTop}
                          width={chartGeometry.candleWidth}
                          height={Math.max(chartGeometry.volumeBottom - volumeTop, 1)}
                          rx={Math.min(chartGeometry.candleWidth / 4, 2)}
                          fill="url(#chartVolumeFill)"
                          opacity={active ? 0.9 : 0.62}
                        />
                        <line
                          x1={x}
                          x2={x}
                          y1={wickTop}
                          y2={wickBottom}
                          stroke={bodyStroke}
                          strokeWidth={active ? 1.7 : 1.3}
                        />
                        <rect
                          x={x - chartGeometry.candleWidth / 2}
                          y={candleTop}
                          width={chartGeometry.candleWidth}
                          height={candleHeight}
                          rx={Math.min(chartGeometry.candleWidth / 4, 2)}
                          fill={bodyFill}
                          stroke={bodyStroke}
                          strokeWidth={active ? 1.5 : 1.1}
                        />
                      </g>
                    );
                  })}

                  {hoveredIndex != null && activeBar ? (
                    <line
                      x1={xAt(activeIndex)}
                      x2={xAt(activeIndex)}
                      y1={chartGeometry.priceTop}
                      y2={chartGeometry.volumeBottom}
                      stroke="var(--theme-chart-crosshair)"
                      strokeDasharray="4 4"
                    />
                  ) : null}

                  {xTickIndices.map((index) => {
                    const datum = activeData[index];
                    if (!datum) {
                      return null;
                    }
                    return (
                      <g key={`x-tick-${datum.stamp}`}>
                        <text
                          x={xAt(index)}
                          y={chartGeometry.height - 4}
                          textAnchor="middle"
                          fontSize={11}
                          fill="var(--theme-chart-axis)"
                        >
                          {datum.shortLabel}
                        </text>
                      </g>
                    );
                  })}

                  <text x={chartGeometry.plotLeft} y={chartGeometry.priceTop - 2} fontSize={11} fill="var(--theme-chart-axis)">
                    Price
                  </text>
                  <text x={chartGeometry.plotLeft} y={chartGeometry.volumeTop - 12} fontSize={11} fill="var(--theme-chart-axis)">
                    Volume
                  </text>
                  <text x={chartGeometry.plotRight + 8} y={chartGeometry.volumeTop + 12} fontSize={11} fill="var(--theme-chart-axis)">
                    {formatVolume(volumeMax)}
                  </text>
                </svg>

                {activeBar ? (
                  <div className="theme-chart-tooltip absolute top-3 z-[1] min-w-[13.5rem] rounded-[1rem] px-3.5 py-3 text-sm" style={{ left: tooltipLeft }}>
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{activeBar.label}</p>
                    <div className="mt-2 grid gap-1.5">
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-muted-text">Open</span>
                        <span className="font-medium text-foreground">{formatAxisPrice(activeBar.open)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-muted-text">High</span>
                        <span className="font-medium text-foreground">{formatAxisPrice(activeBar.high)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-muted-text">Low</span>
                        <span className="font-medium text-foreground">{formatAxisPrice(activeBar.low)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-muted-text">Close</span>
                        <span className="font-medium text-foreground">{formatAxisPrice(activeBar.close)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-muted-text">Volume</span>
                        <span className="font-medium text-secondary-text">{formatVolume(activeBar.volume)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-muted-text">MA5 / MA10 / MA20</span>
                        <span className="font-medium text-secondary-text">
                          {isFiniteNumber(activeBar.ma5) ? formatAxisPrice(activeBar.ma5) : '--'}
                          {' / '}
                          {isFiniteNumber(activeBar.ma10) ? formatAxisPrice(activeBar.ma10) : '--'}
                          {' / '}
                          {isFiniteNumber(activeBar.ma20) ? formatAxisPrice(activeBar.ma20) : '--'}
                        </span>
                      </div>
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>

        <div className="grid gap-2.5 md:hidden">
          <div className="theme-chart-footnote">
            <span className="theme-chart-footnote-label">Data</span>
            <span className="theme-chart-footnote-value">
              {activeData.length || 0} bars · {sourceByView[activeView] || '--'}
            </span>
          </div>
        </div>

        <div className="hidden gap-2.5 md:grid md:grid-cols-3">
          <div className="theme-chart-footnote">
            <span className="theme-chart-footnote-label">Latest bar close</span>
            <span className="theme-chart-footnote-value">{latestBar ? formatAxisPrice(latestBar.close) : '--'}</span>
          </div>
          <div className="theme-chart-footnote">
            <span className="theme-chart-footnote-label">Bars / source</span>
            <span className="theme-chart-footnote-value">
              {activeData.length || 0} bars · {sourceByView[activeView] || '--'}
            </span>
          </div>
          <div className="theme-chart-footnote">
            <span className="theme-chart-footnote-label">Price basis</span>
            <span className="theme-chart-footnote-value">{summary?.priceBasis || priceContextNote}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
