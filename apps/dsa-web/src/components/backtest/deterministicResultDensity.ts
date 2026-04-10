import type { CSSProperties } from 'react';
import { useEffect, useState } from 'react';

export type DeterministicResultDensityMode = 'comfortable' | 'compact' | 'dense';

export type DeterministicResultDensityConfig = {
  mode: DeterministicResultDensityMode;
  buttonSize: 'sm' | 'md';
  pageGap: string;
  pagePaddingBottom: string;
  heroPaddingBlock: string;
  heroPaddingInline: string;
  heroGapRow: string;
  heroGapColumn: string;
  heroEyebrowSize: string;
  heroEyebrowTracking: string;
  heroTitleSize: string;
  heroMetaSize: string;
  heroActionGap: string;
  stageGap: string;
  workspaceGap: string;
  panelGap: string;
  panelSectionSpacing: string;
  panelHeaderGap: string;
  panelTitleSize: string;
  dashboardGap: string;
  dashboardPaddingBlock: string;
  dashboardPaddingInline: string;
  metricStageGap: string;
  metricHeaderGap: string;
  metricTitleSize: string;
  metricGridGap: string;
  metricCardPaddingBlock: string;
  metricCardPaddingInline: string;
  metricLabelSize: string;
  metricValueSize: string;
  chipGap: string;
  chipTightGap: string;
  chipMinHeight: string;
  chipPaddingBlock: string;
  chipPaddingInline: string;
  chipFontSize: string;
  toolbarGap: string;
  toolbarNoteSize: string;
  mainHeight: number;
  dailyHeight: number;
  positionHeight: number;
  brushHeight: number;
  brushOverviewHeight: string;
  brushSelectionInset: string;
  brushSliderGap: string;
  brushSliderLabelSize: string;
  axisFontSize: number;
  xTickMinGap: number;
  mainYTickCount: number;
  subYTickCount: number;
  markerLimit: number;
  legendGap: string;
  legendItemGap: string;
  legendFontSize: string;
  legendLetterSpacing: string;
  legendSwatchSize: string;
  tooltipMaxWidth: string;
  tooltipMaxHeight: string;
  tooltipPaddingBlock: string;
  tooltipPaddingInline: string;
  tooltipGap: string;
  tooltipHeaderGap: string;
  tooltipEyebrowSize: string;
  tooltipTitleSize: string;
  tooltipMetaSize: string;
  tooltipLabelWidth: string;
  tooltipLabelSize: string;
  tooltipValueSize: string;
  tooltipSectionGap: string;
  tooltipOffsetX: number;
  tooltipOffsetY: number;
  tooltipEdgePadding: number;
};

function resolveViewportWidth(): number {
  if (typeof window === 'undefined') return 1440;
  return Math.max(window.innerWidth || 1440, 0);
}

export function resolveDeterministicResultDensityMode(viewportWidth: number): DeterministicResultDensityMode {
  if (viewportWidth >= 1560) return 'comfortable';
  if (viewportWidth >= 1220) return 'compact';
  return 'dense';
}

export const DETERMINISTIC_RESULT_DENSITY: Record<DeterministicResultDensityMode, DeterministicResultDensityConfig> = {
  comfortable: {
    mode: 'comfortable',
    buttonSize: 'md',
    pageGap: '0.5rem',
    pagePaddingBottom: '1.8rem',
    heroPaddingBlock: '0.52rem',
    heroPaddingInline: '0.7rem',
    heroGapRow: '0.3rem',
    heroGapColumn: '0.72rem',
    heroEyebrowSize: '0.58rem',
    heroEyebrowTracking: '0.09em',
    heroTitleSize: '1.16rem',
    heroMetaSize: '0.72rem',
    heroActionGap: '0.28rem',
    stageGap: '0.38rem',
    workspaceGap: '0.38rem',
    panelGap: '0.34rem',
    panelSectionSpacing: '0.32rem',
    panelHeaderGap: '0.3rem',
    panelTitleSize: '0.76rem',
    dashboardGap: '0.38rem',
    dashboardPaddingBlock: '0.48rem',
    dashboardPaddingInline: '0.6rem',
    metricStageGap: '0.3rem',
    metricHeaderGap: '0.28rem',
    metricTitleSize: '0.74rem',
    metricGridGap: '0.3rem',
    metricCardPaddingBlock: '0.36rem',
    metricCardPaddingInline: '0.44rem',
    metricLabelSize: '0.48rem',
    metricValueSize: '0.8rem',
    chipGap: '0.34rem',
    chipTightGap: '0.28rem',
    chipMinHeight: '1.84rem',
    chipPaddingBlock: '0.32rem',
    chipPaddingInline: '0.62rem',
    chipFontSize: '0.76rem',
    toolbarGap: '0.18rem',
    toolbarNoteSize: '0.58rem',
    mainHeight: 248,
    dailyHeight: 88,
    positionHeight: 72,
    brushHeight: 44,
    brushOverviewHeight: '2.08rem',
    brushSelectionInset: '0.46rem',
    brushSliderGap: '0.42rem',
    brushSliderLabelSize: '0.64rem',
    axisFontSize: 8.6,
    xTickMinGap: 208,
    mainYTickCount: 4,
    subYTickCount: 2,
    markerLimit: 10,
    legendGap: '0.52rem',
    legendItemGap: '0.32rem',
    legendFontSize: '0.6rem',
    legendLetterSpacing: '0.12em',
    legendSwatchSize: '0.56rem',
    tooltipMaxWidth: '18rem',
    tooltipMaxHeight: '15rem',
    tooltipPaddingBlock: '0.52rem',
    tooltipPaddingInline: '0.58rem',
    tooltipGap: '0.42rem',
    tooltipHeaderGap: '0.28rem',
    tooltipEyebrowSize: '0.52rem',
    tooltipTitleSize: '0.74rem',
    tooltipMetaSize: '0.64rem',
    tooltipLabelWidth: '5.4rem',
    tooltipLabelSize: '0.56rem',
    tooltipValueSize: '0.66rem',
    tooltipSectionGap: '0.32rem',
    tooltipOffsetX: 14,
    tooltipOffsetY: 12,
    tooltipEdgePadding: 10,
  },
  compact: {
    mode: 'compact',
    buttonSize: 'sm',
    pageGap: '0.42rem',
    pagePaddingBottom: '1.55rem',
    heroPaddingBlock: '0.44rem',
    heroPaddingInline: '0.6rem',
    heroGapRow: '0.24rem',
    heroGapColumn: '0.58rem',
    heroEyebrowSize: '0.55rem',
    heroEyebrowTracking: '0.085em',
    heroTitleSize: '1.06rem',
    heroMetaSize: '0.67rem',
    heroActionGap: '0.24rem',
    stageGap: '0.34rem',
    workspaceGap: '0.32rem',
    panelGap: '0.28rem',
    panelSectionSpacing: '0.26rem',
    panelHeaderGap: '0.26rem',
    panelTitleSize: '0.72rem',
    dashboardGap: '0.32rem',
    dashboardPaddingBlock: '0.42rem',
    dashboardPaddingInline: '0.52rem',
    metricStageGap: '0.26rem',
    metricHeaderGap: '0.24rem',
    metricTitleSize: '0.7rem',
    metricGridGap: '0.24rem',
    metricCardPaddingBlock: '0.3rem',
    metricCardPaddingInline: '0.38rem',
    metricLabelSize: '0.45rem',
    metricValueSize: '0.76rem',
    chipGap: '0.3rem',
    chipTightGap: '0.24rem',
    chipMinHeight: '1.72rem',
    chipPaddingBlock: '0.28rem',
    chipPaddingInline: '0.56rem',
    chipFontSize: '0.72rem',
    toolbarGap: '0.16rem',
    toolbarNoteSize: '0.55rem',
    mainHeight: 236,
    dailyHeight: 80,
    positionHeight: 64,
    brushHeight: 40,
    brushOverviewHeight: '1.92rem',
    brushSelectionInset: '0.4rem',
    brushSliderGap: '0.36rem',
    brushSliderLabelSize: '0.6rem',
    axisFontSize: 8,
    xTickMinGap: 236,
    mainYTickCount: 4,
    subYTickCount: 2,
    markerLimit: 8,
    legendGap: '0.42rem',
    legendItemGap: '0.28rem',
    legendFontSize: '0.58rem',
    legendLetterSpacing: '0.105em',
    legendSwatchSize: '0.5rem',
    tooltipMaxWidth: '16rem',
    tooltipMaxHeight: '13.5rem',
    tooltipPaddingBlock: '0.46rem',
    tooltipPaddingInline: '0.52rem',
    tooltipGap: '0.36rem',
    tooltipHeaderGap: '0.24rem',
    tooltipEyebrowSize: '0.48rem',
    tooltipTitleSize: '0.7rem',
    tooltipMetaSize: '0.6rem',
    tooltipLabelWidth: '4.8rem',
    tooltipLabelSize: '0.54rem',
    tooltipValueSize: '0.64rem',
    tooltipSectionGap: '0.28rem',
    tooltipOffsetX: 12,
    tooltipOffsetY: 10,
    tooltipEdgePadding: 8,
  },
  dense: {
    mode: 'dense',
    buttonSize: 'sm',
    pageGap: '0.32rem',
    pagePaddingBottom: '1.2rem',
    heroPaddingBlock: '0.32rem',
    heroPaddingInline: '0.46rem',
    heroGapRow: '0.16rem',
    heroGapColumn: '0.44rem',
    heroEyebrowSize: '0.53rem',
    heroEyebrowTracking: '0.08em',
    heroTitleSize: '1rem',
    heroMetaSize: '0.66rem',
    heroActionGap: '0.18rem',
    stageGap: '0.24rem',
    workspaceGap: '0.22rem',
    panelGap: '0.2rem',
    panelSectionSpacing: '0.18rem',
    panelHeaderGap: '0.18rem',
    panelTitleSize: '0.7rem',
    dashboardGap: '0.24rem',
    dashboardPaddingBlock: '0.3rem',
    dashboardPaddingInline: '0.4rem',
    metricStageGap: '0.18rem',
    metricHeaderGap: '0.18rem',
    metricTitleSize: '0.68rem',
    metricGridGap: '0.18rem',
    metricCardPaddingBlock: '0.22rem',
    metricCardPaddingInline: '0.28rem',
    metricLabelSize: '0.43rem',
    metricValueSize: '0.74rem',
    chipGap: '0.2rem',
    chipTightGap: '0.18rem',
    chipMinHeight: '1.48rem',
    chipPaddingBlock: '0.22rem',
    chipPaddingInline: '0.44rem',
    chipFontSize: '0.69rem',
    toolbarGap: '0.14rem',
    toolbarNoteSize: '0.54rem',
    mainHeight: 208,
    dailyHeight: 66,
    positionHeight: 50,
    brushHeight: 34,
    brushOverviewHeight: '1.58rem',
    brushSelectionInset: '0.3rem',
    brushSliderGap: '0.28rem',
    brushSliderLabelSize: '0.54rem',
    axisFontSize: 7.55,
    xTickMinGap: 312,
    mainYTickCount: 3,
    subYTickCount: 2,
    markerLimit: 7,
    legendGap: '0.28rem',
    legendItemGap: '0.2rem',
    legendFontSize: '0.56rem',
    legendLetterSpacing: '0.09em',
    legendSwatchSize: '0.44rem',
    tooltipMaxWidth: '13.6rem',
    tooltipMaxHeight: '12rem',
    tooltipPaddingBlock: '0.36rem',
    tooltipPaddingInline: '0.42rem',
    tooltipGap: '0.24rem',
    tooltipHeaderGap: '0.18rem',
    tooltipEyebrowSize: '0.46rem',
    tooltipTitleSize: '0.68rem',
    tooltipMetaSize: '0.58rem',
    tooltipLabelWidth: '4rem',
    tooltipLabelSize: '0.52rem',
    tooltipValueSize: '0.62rem',
    tooltipSectionGap: '0.2rem',
    tooltipOffsetX: 10,
    tooltipOffsetY: 8,
    tooltipEdgePadding: 8,
  },
};

export function getDeterministicResultDensity(viewportWidth: number): DeterministicResultDensityConfig {
  return DETERMINISTIC_RESULT_DENSITY[resolveDeterministicResultDensityMode(viewportWidth)];
}

export function useDeterministicResultDensity(): DeterministicResultDensityConfig {
  const [viewportWidth, setViewportWidth] = useState(resolveViewportWidth);

  useEffect(() => {
    const handleResize = () => setViewportWidth(resolveViewportWidth());
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return getDeterministicResultDensity(viewportWidth);
}

export function getDeterministicResultDensityCssVars(
  density: DeterministicResultDensityConfig,
): CSSProperties {
  return {
    '--backtest-page-gap': density.pageGap,
    '--backtest-page-padding-bottom': density.pagePaddingBottom,
    '--backtest-hero-padding-block': density.heroPaddingBlock,
    '--backtest-hero-padding-inline': density.heroPaddingInline,
    '--backtest-hero-gap-row': density.heroGapRow,
    '--backtest-hero-gap-column': density.heroGapColumn,
    '--backtest-hero-eyebrow-size': density.heroEyebrowSize,
    '--backtest-hero-eyebrow-tracking': density.heroEyebrowTracking,
    '--backtest-hero-title-size': density.heroTitleSize,
    '--backtest-hero-meta-size': density.heroMetaSize,
    '--backtest-hero-action-gap': density.heroActionGap,
    '--backtest-stage-gap': density.stageGap,
    '--backtest-workspace-gap': density.workspaceGap,
    '--backtest-panel-gap': density.panelGap,
    '--backtest-panel-section-spacing': density.panelSectionSpacing,
    '--backtest-panel-header-gap': density.panelHeaderGap,
    '--backtest-panel-title-size': density.panelTitleSize,
    '--backtest-dashboard-gap': density.dashboardGap,
    '--backtest-dashboard-padding-block': density.dashboardPaddingBlock,
    '--backtest-dashboard-padding-inline': density.dashboardPaddingInline,
    '--backtest-metric-stage-gap': density.metricStageGap,
    '--backtest-metric-header-gap': density.metricHeaderGap,
    '--backtest-metric-title-size': density.metricTitleSize,
    '--backtest-metric-grid-gap': density.metricGridGap,
    '--backtest-metric-card-padding-block': density.metricCardPaddingBlock,
    '--backtest-metric-card-padding-inline': density.metricCardPaddingInline,
    '--backtest-metric-label-size': density.metricLabelSize,
    '--backtest-metric-value-size': density.metricValueSize,
    '--backtest-chip-gap': density.chipGap,
    '--backtest-chip-tight-gap': density.chipTightGap,
    '--backtest-chip-min-height': density.chipMinHeight,
    '--backtest-chip-padding-block': density.chipPaddingBlock,
    '--backtest-chip-padding-inline': density.chipPaddingInline,
    '--backtest-chip-font-size': density.chipFontSize,
    '--backtest-toolbar-gap': density.toolbarGap,
    '--backtest-toolbar-note-size': density.toolbarNoteSize,
    '--backtest-legend-gap': density.legendGap,
    '--backtest-legend-item-gap': density.legendItemGap,
    '--backtest-legend-font-size': density.legendFontSize,
    '--backtest-legend-letter-spacing': density.legendLetterSpacing,
    '--backtest-legend-swatch-size': density.legendSwatchSize,
    '--backtest-tooltip-max-width': density.tooltipMaxWidth,
    '--backtest-tooltip-max-height': density.tooltipMaxHeight,
    '--backtest-tooltip-padding-block': density.tooltipPaddingBlock,
    '--backtest-tooltip-padding-inline': density.tooltipPaddingInline,
    '--backtest-tooltip-gap': density.tooltipGap,
    '--backtest-tooltip-header-gap': density.tooltipHeaderGap,
    '--backtest-tooltip-eyebrow-size': density.tooltipEyebrowSize,
    '--backtest-tooltip-title-size': density.tooltipTitleSize,
    '--backtest-tooltip-meta-size': density.tooltipMetaSize,
    '--backtest-tooltip-label-width': density.tooltipLabelWidth,
    '--backtest-tooltip-label-size': density.tooltipLabelSize,
    '--backtest-tooltip-value-size': density.tooltipValueSize,
    '--backtest-tooltip-section-gap': density.tooltipSectionGap,
    '--backtest-brush-overview-height': density.brushOverviewHeight,
    '--backtest-brush-selection-inset': density.brushSelectionInset,
    '--backtest-brush-slider-gap': density.brushSliderGap,
    '--backtest-brush-slider-label-size': density.brushSliderLabelSize,
  } as CSSProperties;
}
