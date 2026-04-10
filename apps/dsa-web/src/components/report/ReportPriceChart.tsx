import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { stocksApi, type StockHistoryPoint, type StockIntradayPoint } from '../../api/stocks';
import { useI18n } from '../../contexts/UiLanguageContext';
import type {
  StandardReportDecisionPanel,
  StandardReportMarketBlock,
  StandardReportSummaryPanel,
} from '../../types/analysis';
import { SupportPanel } from '../common';
import { cn } from '../../utils/cn';
import { useElementSize } from '../../hooks/useElementSize';

export type ChartViewKey = 'minute1' | 'minute5' | 'daily' | 'weekly' | 'monthly' | 'yearly';

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
  labelKey: string;
  descriptionKey: string;
  request:
    | { kind: 'intraday'; interval: '1m' | '5m' | '15m' | '30m'; range: '1d' | '5d' | '1mo' }
    | { kind: 'history'; period: 'daily' | 'weekly' | 'monthly' | 'yearly'; days: number };
};

export type ReportPriceChartFixtureView = {
  source?: string;
  data: Array<StockIntradayPoint | StockHistoryPoint>;
};

export type ReportPriceChartFixtures = Partial<Record<ChartViewKey, ReportPriceChartFixtureView>>;

type AnnotationLine = {
  labelKey: string;
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
    key: 'minute1',
    labelKey: 'chart.minute1',
    descriptionKey: 'chart.minute1Desc',
    request: { kind: 'intraday', interval: '1m', range: '1d' },
  },
  {
    key: 'minute5',
    labelKey: 'chart.minute5',
    descriptionKey: 'chart.minute5Desc',
    request: { kind: 'intraday', interval: '5m', range: '5d' },
  },
  {
    key: 'daily',
    labelKey: 'chart.daily',
    descriptionKey: 'chart.dailyDesc',
    request: { kind: 'history', period: 'daily', days: 3650 },
  },
  {
    key: 'weekly',
    labelKey: 'chart.weekly',
    descriptionKey: 'chart.weeklyDesc',
    request: { kind: 'history', period: 'weekly', days: 3650 },
  },
  {
    key: 'monthly',
    labelKey: 'chart.monthly',
    descriptionKey: 'chart.monthlyDesc',
    request: { kind: 'history', period: 'monthly', days: 3650 },
  },
  {
    key: 'yearly',
    labelKey: 'chart.year',
    descriptionKey: 'chart.yearDesc',
    request: { kind: 'history', period: 'yearly', days: 3650 },
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

const formatSignedPrice = (value?: number | null): string => {
  if (!Number.isFinite(value ?? NaN)) {
    return '--';
  }
  const numeric = Number(value);
  return `${numeric > 0 ? '+' : ''}${formatAxisPrice(numeric)}`;
};

const formatSignedPercent = (value?: number | null): string => {
  if (!Number.isFinite(value ?? NaN)) {
    return '--';
  }
  const numeric = Number(value);
  return `${numeric > 0 ? '+' : ''}${numeric.toFixed(2)}%`;
};

const parseNumericText = (value?: string | null): number | null => {
  if (!value) {
    return null;
  }
  const normalized = String(value).replace(/[%,$,\s]/g, '');
  const numeric = Number(normalized);
  return Number.isFinite(numeric) ? numeric : null;
};

const formatShortLabel = (stamp: string, view: ChartViewKey, locale: string): string => {
  const date = new Date(stamp);
  if (Number.isNaN(date.getTime())) {
    return stamp;
  }
  if (view === 'minute1' || view === 'minute5') {
    return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false });
  }
  if (view === 'yearly') {
    return date.toLocaleDateString(locale, { year: '2-digit', month: 'short' });
  }
  return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
};

const formatLongLabel = (stamp: string, view: ChartViewKey, locale: string): string => {
  const date = new Date(stamp);
  if (Number.isNaN(date.getTime())) {
    return stamp;
  }
  if (view === 'minute1' || view === 'minute5') {
    return date.toLocaleString(locale, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }
  return date.toLocaleDateString(locale, {
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
  locale: string,
): ChartDatum[] => {
  const closes = items.map((item) => item.close);
  return items.map((item, index) => {
    const stamp = 'time' in item ? item.time : item.date;
    return {
      stamp,
      label: formatLongLabel(stamp, view, locale),
      shortLabel: formatShortLabel(stamp, view, locale),
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

const resolveAnnotationLines = (decisionPanel?: StandardReportDecisionPanel): AnnotationLine[] => {
  const items: AnnotationLine[] = [
    { labelKey: 'chart.support', value: decisionPanel?.supportLevel ?? NaN, stroke: 'var(--theme-chart-support)' },
    { labelKey: 'chart.resistance', value: decisionPanel?.resistanceLevel ?? NaN, stroke: 'var(--theme-chart-resistance)' },
    { labelKey: 'chart.entry', value: decisionPanel?.idealEntryCenter ?? NaN, stroke: 'var(--theme-chart-entry)' },
    { labelKey: 'chart.stop', value: decisionPanel?.stopLossLevel ?? NaN, stroke: 'var(--theme-chart-stop)' },
    { labelKey: 'chart.targetOne', value: decisionPanel?.targetOneLevel ?? NaN, stroke: 'var(--theme-chart-target)' },
    { labelKey: 'chart.targetTwo', value: decisionPanel?.targetTwoLevel ?? NaN, stroke: 'var(--theme-chart-target-strong)' },
  ];
  return items.filter((item) => isFiniteNumber(item.value));
};

const createDefaultViewWindow = (view: ChartViewKey, count: number): ViewWindow => {
  if (count <= 0) {
    return { start: 0, end: 0 };
  }
  const isMinuteView = view === 'minute1' || view === 'minute5';
  const preferredSize = isMinuteView ? Math.min(count, 96) : count;
  const size = Math.min(count, Math.max(preferredSize, Math.min(count, 24)));
  return {
    start: Math.max(0, count - size),
    end: count - 1,
  };
};

const normalizeViewWindow = (window: ViewWindow, count: number): ViewWindow => {
  if (count <= 0) {
    return { start: 0, end: 0 };
  }
  const safeStart = clamp(window.start, 0, count - 1);
  const safeEnd = clamp(window.end, safeStart, count - 1);
  return { start: safeStart, end: safeEnd };
};

type IndicatorKey =
  | 'candles'
  | 'volume'
  | 'ma5'
  | 'ma10'
  | 'ma20'
  | 'support'
  | 'resistance'
  | 'entry'
  | 'targets';

type ViewWindow = {
  start: number;
  end: number;
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
  const { language, t } = useI18n();
  const locale = language === 'zh' ? 'zh-CN' : 'en-US';
  const [activeView, setActiveView] = useState<ChartViewKey>('minute1');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<Record<ChartViewKey, ChartDatum[]>>({
    minute1: [],
    minute5: [],
    daily: [],
    weekly: [],
    monthly: [],
    yearly: [],
  });
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [indicatorVisibility, setIndicatorVisibility] = useState<Record<IndicatorKey, boolean>>({
    candles: true,
    volume: true,
    ma5: false,
    ma10: false,
    ma20: false,
    support: false,
    resistance: false,
    entry: false,
    targets: false,
  });
  const [viewWindowByView, setViewWindowByView] = useState<Record<ChartViewKey, ViewWindow | null>>({
    minute1: null,
    minute5: null,
    daily: null,
    weekly: null,
    monthly: null,
    yearly: null,
  });
  const dragStateRef = useRef<{ pointerX: number; window: ViewWindow } | null>(null);
  const chartStageRef = useRef<HTMLDivElement | null>(null);
  const activeTouchPointerIdRef = useRef<number | null>(null);
  const pageScrollLockStateRef = useRef<{
    bodyOverflow: string;
    htmlOverflow: string;
    bodyTouchAction: string;
  } | null>(null);
  const { ref: chartRef, size } = useElementSize<HTMLDivElement>();

  const lockPageScroll = useCallback(() => {
    if (typeof document === 'undefined') {
      return;
    }
    if (pageScrollLockStateRef.current != null) {
      return;
    }
    pageScrollLockStateRef.current = {
      bodyOverflow: document.body.style.overflow,
      htmlOverflow: document.documentElement.style.overflow,
      bodyTouchAction: document.body.style.touchAction,
    };
    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
    document.body.style.touchAction = 'none';
  }, []);

  const unlockPageScroll = useCallback(() => {
    if (typeof document === 'undefined') {
      return;
    }
    if (pageScrollLockStateRef.current == null) {
      return;
    }
    document.body.style.overflow = pageScrollLockStateRef.current.bodyOverflow;
    document.documentElement.style.overflow = pageScrollLockStateRef.current.htmlOverflow;
    document.body.style.touchAction = pageScrollLockStateRef.current.bodyTouchAction;
    pageScrollLockStateRef.current = null;
  }, []);

  useEffect(() => {
    setActiveView('minute1');
    setHoveredIndex(null);
    setError(null);
    setChartData({
      minute1: [],
      minute5: [],
      daily: [],
      weekly: [],
      monthly: [],
      yearly: [],
    });
    setViewWindowByView({
      minute1: null,
      minute5: null,
      daily: null,
      weekly: null,
      monthly: null,
      yearly: null,
    });
  }, [stockCode]);

  useEffect(() => () => {
    unlockPageScroll();
  }, [unlockPageScroll]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const viewConfig = VIEW_CONFIGS.find((item) => item.key === activeView);
        if (!viewConfig) {
          throw new Error(t('chart.noData'));
        }

        const fixture = fixtures?.[activeView];
        if (fixture) {
          if (cancelled) {
            return;
          }
          setChartData((current) => ({
            ...current,
            [activeView]: buildChartData(fixture.data || [], activeView, locale),
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
            [activeView]: buildChartData(response.data || [], activeView, locale),
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
          [activeView]: buildChartData(response.data || [], activeView, locale),
        }));
      } catch (fetchError) {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : t('chart.noData'));
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
  }, [activeView, fixtures, locale, stockCode, t]);

  const activeData = chartData[activeView];
  const activeWindow = useMemo(() => {
    const existing = viewWindowByView[activeView];
    if (!existing) {
      return createDefaultViewWindow(activeView, activeData.length);
    }
    return normalizeViewWindow(existing, activeData.length);
  }, [activeData.length, activeView, viewWindowByView]);
  const visibleData = useMemo(
    () => activeData.slice(activeWindow.start, activeWindow.end + 1),
    [activeData, activeWindow.end, activeWindow.start],
  );
  const activeIndex = hoveredIndex != null
    ? clamp(hoveredIndex, 0, Math.max(visibleData.length - 1, 0))
    : Math.max(visibleData.length - 1, 0);
  const activeBar = visibleData[activeIndex];

  useEffect(() => {
    if (activeData.length === 0) {
      return;
    }
    const existing = viewWindowByView[activeView];
    if (
      !existing
      || existing.start >= activeData.length
      || existing.end >= activeData.length
      || existing.end <= existing.start
    ) {
      setViewWindowByView((current) => ({
        ...current,
        [activeView]: createDefaultViewWindow(activeView, activeData.length),
      }));
    }
  }, [activeData.length, activeView, viewWindowByView]);

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
    const step = visibleData.length > 1 ? plotWidth / (visibleData.length - 1) : plotWidth;
    const isMinuteView = activeView === 'minute1' || activeView === 'minute5';
    const candleWidth = clamp(step * 0.68, isMinuteView ? 2.8 : 1.6, isMinuteView ? 7.5 : 9.5);

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
  }, [activeView, size.height, size.width, visibleData.length]);

  const priceDomain = useMemo(() => {
    const values = visibleData.flatMap((item) => [item.low, item.high]);
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
  }, [annotationLines, decisionPanel?.analysisPrice, visibleData]);

  const volumeMax = useMemo(
    () => Math.max(...visibleData.map((item) => item.volume || 0), 1),
    [visibleData],
  );

  const xAt = useCallback((index: number): number => {
    if (!chartGeometry) {
      return 0;
    }
    if (visibleData.length <= 1) {
      return chartGeometry.plotLeft + chartGeometry.plotWidth / 2;
    }
    return chartGeometry.plotLeft + chartGeometry.step * index;
  }, [chartGeometry, visibleData.length]);

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

  const xTickIndices = useMemo(() => buildTickIndices(visibleData.length, 6), [visibleData.length]);

  const ma5Path = useMemo(
    () => buildPath(visibleData.map((item, index) => ({ x: xAt(index), y: item.ma5 != null ? priceY(item.ma5) : undefined }))),
    [priceY, visibleData, xAt],
  );
  const ma10Path = useMemo(
    () => buildPath(visibleData.map((item, index) => ({ x: xAt(index), y: item.ma10 != null ? priceY(item.ma10) : undefined }))),
    [priceY, visibleData, xAt],
  );
  const ma20Path = useMemo(
    () => buildPath(visibleData.map((item, index) => ({ x: xAt(index), y: item.ma20 != null ? priceY(item.ma20) : undefined }))),
    [priceY, visibleData, xAt],
  );

  const resolveHoverIndex = (clientX: number): number | null => {
    if (!chartGeometry || !chartRef.current || visibleData.length === 0) {
      return null;
    }
    const rect = chartRef.current.getBoundingClientRect();
    const localX = clamp(clientX - rect.left, chartGeometry.plotLeft, chartGeometry.plotRight);
    if (visibleData.length <= 1) {
      return 0;
    }
    return clamp(Math.round((localX - chartGeometry.plotLeft) / chartGeometry.step), 0, visibleData.length - 1);
  };

  const setViewWindow = useCallback((nextWindow: ViewWindow) => {
    setViewWindowByView((current) => ({
      ...current,
      [activeView]: normalizeViewWindow(nextWindow, activeData.length),
    }));
  }, [activeData.length, activeView]);

  const zoomWindow = useCallback((direction: 'in' | 'out') => {
    if (activeData.length <= 8) {
      return;
    }
    const currentWindow = activeWindow;
    const currentCount = Math.max(currentWindow.end - currentWindow.start + 1, 1);
    const nextCount = direction === 'in'
      ? Math.max(8, Math.round(currentCount * 0.8))
      : Math.min(activeData.length, Math.round(currentCount * 1.25));
    const anchorIndex = hoveredIndex != null ? currentWindow.start + hoveredIndex : currentWindow.start + Math.floor(currentCount / 2);
    const nextStart = clamp(anchorIndex - Math.floor(nextCount / 2), 0, Math.max(activeData.length - nextCount, 0));
    setViewWindow({ start: nextStart, end: nextStart + nextCount - 1 });
  }, [activeData.length, activeWindow, hoveredIndex, setViewWindow]);

  const resetViewWindow = useCallback(() => {
    setViewWindow(createDefaultViewWindow(activeView, activeData.length));
  }, [activeData.length, activeView, setViewWindow]);

  const visibleAnnotationLines = useMemo(() => annotationLines.filter((line) => {
    if (line.labelKey === 'chart.support') {
      return indicatorVisibility.support;
    }
    if (line.labelKey === 'chart.resistance') {
      return indicatorVisibility.resistance;
    }
    if (line.labelKey === 'chart.entry') {
      return indicatorVisibility.entry;
    }
    return indicatorVisibility.targets;
  }), [annotationLines, indicatorVisibility.entry, indicatorVisibility.resistance, indicatorVisibility.support, indicatorVisibility.targets]);

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragStateRef.current && chartGeometry) {
      if (event.pointerType === 'touch') {
        event.preventDefault();
        event.stopPropagation();
      }
      const currentWindow = dragStateRef.current.window;
      const currentCount = currentWindow.end - currentWindow.start + 1;
      const deltaBars = Math.round(((event.clientX - dragStateRef.current.pointerX) / chartGeometry.plotWidth) * currentCount);
      const nextStart = clamp(currentWindow.start - deltaBars, 0, Math.max(activeData.length - currentCount, 0));
      setViewWindow({ start: nextStart, end: nextStart + currentCount - 1 });
      return;
    }
    const index = resolveHoverIndex(event.clientX);
    if (index != null) {
      setHoveredIndex(index);
    }
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!chartGeometry) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    if (event.pointerType === 'touch') {
      event.preventDefault();
      event.stopPropagation();
      activeTouchPointerIdRef.current = event.pointerId;
      lockPageScroll();
    }
    dragStateRef.current = {
      pointerX: event.clientX,
      window: activeWindow,
    };
    setHoveredIndex(resolveHoverIndex(event.clientX));
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    dragStateRef.current = null;
    if (event.pointerType === 'touch') {
      event.preventDefault();
      event.stopPropagation();
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (activeTouchPointerIdRef.current === event.pointerId) {
      activeTouchPointerIdRef.current = null;
      unlockPageScroll();
    }
  };

  const handlePointerLeave = () => {
    dragStateRef.current = null;
    setHoveredIndex(null);
    if (activeTouchPointerIdRef.current != null) {
      activeTouchPointerIdRef.current = null;
      unlockPageScroll();
    }
  };

  const handlePointerCancel = (event: React.PointerEvent<HTMLDivElement>) => {
    dragStateRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (activeTouchPointerIdRef.current === event.pointerId) {
      activeTouchPointerIdRef.current = null;
      unlockPageScroll();
    }
  };

  useEffect(() => {
    const stage = chartStageRef.current;
    if (!stage) {
      return;
    }

    const stopTouchPropagation = (event: TouchEvent) => {
      event.stopPropagation();
    };

    const preventTouchScroll = (event: TouchEvent) => {
      if (!event.cancelable) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
    };

    const handleWheel = (event: WheelEvent) => {
      if (!event.cancelable || event.deltaY === 0) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      zoomWindow(event.deltaY > 0 ? 'out' : 'in');
    };

    stage.addEventListener('wheel', handleWheel, { passive: false });
    stage.addEventListener('touchstart', stopTouchPropagation, { passive: true });
    stage.addEventListener('touchmove', preventTouchScroll, { passive: false });

    return () => {
      stage.removeEventListener('wheel', handleWheel);
      stage.removeEventListener('touchstart', stopTouchPropagation);
      stage.removeEventListener('touchmove', preventTouchScroll);
    };
  }, [zoomWindow]);

  const chartShellClass = integrated
    ? 'theme-chart-shell report-hero-chart'
    : 'theme-chart-shell theme-panel-solid';

  const legendItems = useMemo(() => {
    const items = [
      { label: t('chart.candles'), color: 'var(--theme-chart-bull)', key: 'candles' as IndicatorKey },
      { label: t('chart.volumeBars'), color: 'var(--theme-chart-volume)', key: 'volume' as IndicatorKey },
      { label: t('chart.ma5'), color: 'var(--theme-chart-ma5)', key: 'ma5' as IndicatorKey },
      { label: t('chart.ma10'), color: 'var(--theme-chart-ma10)', key: 'ma10' as IndicatorKey },
      { label: t('chart.ma20'), color: 'var(--theme-chart-ma20)', key: 'ma20' as IndicatorKey },
      { label: t('chart.support'), color: 'var(--theme-chart-support)', key: 'support' as IndicatorKey },
      { label: t('chart.resistance'), color: 'var(--theme-chart-resistance)', key: 'resistance' as IndicatorKey },
      { label: t('chart.entry'), color: 'var(--theme-chart-entry)', key: 'entry' as IndicatorKey },
      { label: t('chart.targetOne'), color: 'var(--theme-chart-target)', key: 'targets' as IndicatorKey },
    ];
    return items;
  }, [t]);

  const activeViewConfig = VIEW_CONFIGS.find((item) => item.key === activeView);
  const compactContextLine = useMemo(() => {
    const parts = [
      summary?.priceBasis,
      summary?.referenceSession,
      summary?.snapshotTime ? `${t('chart.updated')} ${summary.snapshotTime}` : undefined,
    ].filter(Boolean);
    return parts.join(' · ');
  }, [summary?.priceBasis, summary?.referenceSession, summary?.snapshotTime, t]);

  const inspectorRows = useMemo(() => {
    if (!activeBar) {
      return [];
    }
    return [
      { label: t('chart.open'), value: formatAxisPrice(activeBar.open) },
      { label: t('chart.high'), value: formatAxisPrice(activeBar.high) },
      { label: t('chart.low'), value: formatAxisPrice(activeBar.low) },
      { label: t('chart.close'), value: formatAxisPrice(activeBar.close) },
      { label: t('chart.volume'), value: formatVolume(activeBar.volume) },
      {
        label: t('chart.movingAverages'),
        value: [
          isFiniteNumber(activeBar.ma5) ? formatAxisPrice(activeBar.ma5) : '--',
          isFiniteNumber(activeBar.ma10) ? formatAxisPrice(activeBar.ma10) : '--',
          isFiniteNumber(activeBar.ma20) ? formatAxisPrice(activeBar.ma20) : '--',
        ].join(' / '),
      },
    ];
  }, [activeBar, t]);

  const sessionMetricRows = useMemo(() => {
    const metrics = market?.regularMetrics;
    const latestPrice = metrics?.price ?? parseNumericText(summary?.currentPrice);
    const prevClose = metrics?.prevClose;
    const open = metrics?.open;
    const high = metrics?.high;
    const low = metrics?.low;
    const volume = metrics?.volume;
    const turnover = metrics?.amount;
    const changeAmount = metrics?.changeAmount ?? parseNumericText(summary?.changeAmount);
    const changePct = metrics?.changePct ?? parseNumericText(summary?.changePct);
    const vwap = metrics?.vwap ?? metrics?.averagePrice;

    return [
      { label: t('chart.latest'), value: latestPrice != null ? formatAxisPrice(latestPrice) : (summary?.currentPrice || '--') },
      { label: t('chart.change'), value: `${formatSignedPrice(changeAmount)} / ${formatSignedPercent(changePct)}` },
      { label: t('chart.open'), value: formatAxisPrice(open ?? NaN) },
      { label: t('chart.high'), value: formatAxisPrice(high ?? NaN) },
      { label: t('chart.low'), value: formatAxisPrice(low ?? NaN) },
      { label: t('chart.prevClose'), value: formatAxisPrice(prevClose ?? NaN) },
      { label: t('chart.volume'), value: formatVolume(volume) },
      { label: t('chart.turnover'), value: formatVolume(turnover) },
      ...(isFiniteNumber(vwap) ? [{ label: t('chart.vwap'), value: formatAxisPrice(vwap) }] : []),
    ];
  }, [market?.regularMetrics, summary?.changeAmount, summary?.changePct, summary?.currentPrice, t]);

  return (
    <div className={chartShellClass} data-testid="report-price-chart" data-language={language}>
      <div className={cn('theme-chart-frame flex flex-col gap-3', integrated ? 'pt-1' : 'py-4 md:py-5')}>
        <div className="flex flex-col gap-2.5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{t('chart.title')}</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              <h3 className="text-base font-semibold tracking-tight text-foreground sm:text-lg">
                {stockName || stockCode}
              </h3>
              <span className="text-xs text-muted-text sm:text-sm">{activeViewConfig ? t(activeViewConfig.descriptionKey) : t('chart.title')}</span>
            </div>
            {compactContextLine ? <p className="mt-1.5 text-[11px] leading-5 text-muted-text sm:text-xs">{compactContextLine}</p> : null}
            <p className="mt-2 hidden text-xs leading-5 text-muted-text md:block">{t('chart.dragHint')}</p>
          </div>

          <div className="theme-chart-toolbar w-full lg:ml-auto lg:w-auto lg:max-w-full" data-language={language}>
            <div className="theme-chart-toolbar-track">
              <div className="theme-chart-toolbar-tabs">
                {VIEW_CONFIGS.map((view) => (
                  <button
                    key={view.key}
                    type="button"
                    onClick={() => setActiveView(view.key)}
                    className={cn('theme-chart-tab', activeView === view.key ? 'is-active' : '')}
                  >
                    <span className="theme-chart-tab__primary">{t(view.labelKey)}</span>
                    <span className="theme-chart-tab__secondary">{t(view.descriptionKey)}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="theme-chart-toolbar-actions flex flex-nowrap items-center gap-2">
              <button type="button" className="theme-chart-tab px-3" onClick={() => zoomWindow('in')} aria-label={t('chart.zoomIn')}>+</button>
              <button type="button" className="theme-chart-tab px-3" onClick={() => zoomWindow('out')} aria-label={t('chart.zoomOut')}>-</button>
              <button type="button" className="theme-chart-tab px-3.5" onClick={resetViewWindow}>{t('chart.resetView')}</button>
            </div>
          </div>
        </div>

        <div className="theme-chart-legend flex flex-wrap items-center gap-2.5">
          {legendItems.map((item) => (
            <button
              key={item.label}
              type="button"
              className={cn('theme-chart-legend-item', !indicatorVisibility[item.key] && 'opacity-45')}
              onClick={() => setIndicatorVisibility((current) => ({ ...current, [item.key]: !current[item.key] }))}
            >
              <span className="theme-chart-legend-swatch" style={{ background: item.color }} />
              <span>{item.label}</span>
            </button>
          ))}
        </div>
        <div className="theme-chart-canvas">
          {activeBar ? (
            <div className="mb-3 grid items-stretch gap-3.5 md:mb-3.5 md:grid-cols-2">
              <SupportPanel
                className="h-full px-3 py-2.5"
                title={hoveredIndex != null ? t('chart.inspectBar') : t('chart.currentBar')}
                titleClassName="text-[11px] uppercase tracking-[0.16em] text-muted-text"
              >
                <p className="text-xs font-medium text-foreground sm:text-sm">{activeBar.label}</p>
                <div className="mt-2.5 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {inspectorRows.map((row) => (
                    <div key={row.label} className="space-y-1.5">
                      <p className="text-[10px] uppercase tracking-[0.13em] text-muted-text">{row.label}</p>
                      <p className="text-[12px] font-medium text-secondary-text sm:text-sm">{row.value}</p>
                    </div>
                  ))}
                </div>
              </SupportPanel>
              <SupportPanel
                className="h-full px-3 py-2.5"
                title={t('chart.sessionMetrics')}
                titleClassName="text-[11px] uppercase tracking-[0.16em] text-muted-text"
                actions={(
                  <span className="text-[10px] text-muted-text sm:text-[11px]">
                    {summary?.snapshotTime || summary?.marketSessionDate || '--'}
                  </span>
                )}
                actionsClassName="mt-0 justify-end"
              >
                <div className="grid grid-cols-2 gap-x-3.5 gap-y-2.5 xl:grid-cols-3">
                  {sessionMetricRows.map((row) => (
                    <div key={row.label} className="min-w-0">
                      <p className="text-[10px] uppercase tracking-[0.12em] text-muted-text">{row.label}</p>
                      <p className="mt-0.5 truncate text-[12px] font-medium text-foreground sm:text-sm">{row.value}</p>
                    </div>
                  ))}
                </div>
              </SupportPanel>
            </div>
          ) : null}
          <div
            onTouchStartCapture={(event) => {
              event.stopPropagation();
            }}
            onTouchMoveCapture={(event) => {
              event.stopPropagation();
            }}
            className="theme-chart-stage relative h-[250px] w-full touch-none sm:h-[340px] md:h-[420px] xl:h-[460px]"
            onPointerCancel={handlePointerCancel}
            onPointerMove={handlePointerMove}
            onPointerDown={handlePointerDown}
            onPointerUp={handlePointerUp}
            onPointerLeave={handlePointerLeave}
            ref={(node) => {
              chartRef.current = node;
              chartStageRef.current = node;
            }}
          >
            {loading ? (
              <div className="flex h-full items-center justify-center text-sm text-secondary-text">{t('chart.loading')}</div>
            ) : error ? (
              <div className="flex h-full items-center justify-center text-sm text-secondary-text">{error}</div>
            ) : visibleData.length === 0 || !chartGeometry || !priceDomain ? (
              <div className="flex h-full items-center justify-center text-sm text-secondary-text">{t('chart.noData')}</div>
            ) : (
              <>
                <svg width={chartGeometry.width} height={chartGeometry.height} role="img" aria-label={t('chart.ariaLabel', { code: stockCode })}>
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

                  {visibleAnnotationLines.map((line, index) => {
                    const y = priceY(line.value);
                    return (
                      <g key={`${line.labelKey}-${line.value}-${index}`}>
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
                          {`${t(line.labelKey)} ${formatAxisPrice(line.value)}`}
                        </text>
                      </g>
                    );
                  })}

                  {indicatorVisibility.ma20 && ma20Path ? <path d={ma20Path} fill="none" stroke="var(--theme-chart-ma20)" strokeWidth={1.75} /> : null}
                  {indicatorVisibility.ma10 && ma10Path ? <path d={ma10Path} fill="none" stroke="var(--theme-chart-ma10)" strokeWidth={1.6} /> : null}
                  {indicatorVisibility.ma5 && ma5Path ? <path d={ma5Path} fill="none" stroke="var(--theme-chart-ma5)" strokeWidth={1.55} /> : null}

                  {visibleData.map((datum, index) => {
                    const x = xAt(index);
                    const wickTop = priceY(datum.high);
                    const wickBottom = priceY(datum.low);
                    const openY = priceY(datum.open);
                    const closeY = priceY(datum.close);
                    const candleTop = Math.min(openY, closeY);
                    const candleHeight = Math.max(Math.abs(closeY - openY), 1.8);
                    const bullish = datum.close >= datum.open;
                    const bodyFill = bullish ? 'var(--theme-chart-bull)' : 'var(--theme-chart-bear)';
                    const bodyStroke = bullish ? 'var(--theme-chart-bull)' : 'var(--theme-chart-bear)';
                    const volumeTop = volumeY(datum.volume || 0);
                    const active = index === activeIndex;

                    return (
                      <g key={`${datum.stamp}-${index}`}>
                        {indicatorVisibility.volume ? (
                          <rect
                            x={x - chartGeometry.candleWidth / 2}
                            y={volumeTop}
                            width={chartGeometry.candleWidth}
                            height={Math.max(chartGeometry.volumeBottom - volumeTop, 1)}
                            rx={Math.min(chartGeometry.candleWidth / 4, 2)}
                            fill="url(#chartVolumeFill)"
                            opacity={active ? 0.9 : 0.62}
                          />
                        ) : null}
                        {indicatorVisibility.candles ? (
                          <>
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
                          </>
                        ) : null}
                      </g>
                    );
                  })}

                  {hoveredIndex != null && activeBar ? (
                    <g>
                      <line
                        x1={xAt(activeIndex)}
                        x2={xAt(activeIndex)}
                        y1={chartGeometry.priceTop}
                        y2={chartGeometry.volumeBottom}
                        stroke="var(--theme-chart-crosshair)"
                        strokeDasharray="4 4"
                      />
                      <rect
                        x={chartGeometry.plotRight + 6}
                        y={priceY(activeBar.close) - 11}
                        width={62}
                        height={18}
                        rx={9}
                        fill="color-mix(in srgb, var(--theme-chart-tooltip-bg) 88%, transparent)"
                      />
                      <text
                        x={chartGeometry.plotRight + 12}
                        y={priceY(activeBar.close) + 2}
                        fontSize={10.5}
                        fill="var(--theme-chart-axis)"
                      >
                        {formatAxisPrice(activeBar.close)}
                      </text>
                      <rect
                        x={clamp(xAt(activeIndex) - 52, chartGeometry.plotLeft, chartGeometry.plotRight - 104)}
                        y={chartGeometry.height - 22}
                        width={104}
                        height={18}
                        rx={9}
                        fill="color-mix(in srgb, var(--theme-chart-tooltip-bg) 88%, transparent)"
                      />
                      <text
                        x={clamp(xAt(activeIndex), chartGeometry.plotLeft + 52, chartGeometry.plotRight - 52)}
                        y={chartGeometry.height - 9}
                        textAnchor="middle"
                        fontSize={10.5}
                        fill="var(--theme-chart-axis)"
                      >
                        {activeBar.shortLabel}
                      </text>
                    </g>
                  ) : null}

                  {xTickIndices.map((index) => {
                    const datum = visibleData[index];
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
                    {t('chart.priceAxis')}
                  </text>
                  <text x={chartGeometry.plotLeft} y={chartGeometry.volumeTop - 12} fontSize={11} fill="var(--theme-chart-axis)">
                    {t('chart.volumeAxis')}
                  </text>
                  <text x={chartGeometry.plotRight + 8} y={chartGeometry.volumeTop + 12} fontSize={11} fill="var(--theme-chart-axis)">
                    {formatVolume(volumeMax)}
                  </text>
                </svg>

              </>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
