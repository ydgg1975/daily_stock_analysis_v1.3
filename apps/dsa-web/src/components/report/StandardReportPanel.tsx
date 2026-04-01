import React from 'react';
import { translateForCurrentLanguage } from '../../i18n/core';
import type {
  AnalysisReport,
  StandardReportDecisionPanel,
  StandardReport,
  StandardReportBattlePlanCompact,
  StandardReportBattlePlanItem,
  StandardReportChecklistItem,
  StandardReportDecisionContext,
  StandardReportField,
  StandardReportHighlights,
  StandardReportReasonLayer,
  StandardReportScoreBreakdownItem,
  StandardReportTableSection,
} from '../../types/analysis';
import { Badge } from '../common';
import { cn } from '../../utils/cn';
import { ReportPriceChart, type ReportPriceChartFixtures } from './ReportPriceChart';
import { useElementSize } from '../../hooks/useElementSize';

interface StandardReportPanelProps {
  report: AnalysisReport;
  chartFixtures?: ReportPriceChartFixtures;
}

const solidCardClass =
  'theme-panel-solid rounded-[1.45rem] px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6';
const glassCardClass =
  'theme-panel-glass rounded-[1.55rem] px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6';
const subtlePanelClass = 'theme-panel-subtle rounded-[1rem] px-3.5 py-3';
const rowGridClass =
  'grid gap-4 lg:grid-cols-2';
const middleSectionGridClass =
  'grid gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(340px,0.88fr)]';
const denseTableColumns =
  'md:grid-cols-[minmax(0,1.1fr)_minmax(0,1.25fr)_minmax(0,0.9fr)_minmax(0,0.8fr)]';
const WIDE_DESKTOP_HERO_MIN = 1100;
const ui = translateForCurrentLanguage;

const parseNumericValue = (value?: string | number): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const normalized = value.replace(/,/g, '').replace('%', '').trim();
    const parsed = Number(normalized);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const isMeaningfulText = (value?: string | null): value is string => {
  if (!value) {
    return false;
  }
  const text = value.trim();
  return Boolean(text);
};

const extractMissingReason = (value?: string | null): string | undefined => {
  const text = String(value || '').trim();
  if (text.startsWith('NA（') && text.endsWith('）')) {
    return text.slice(3, -1).trim();
  }
  return undefined;
};

const isMissingDisplayText = (value?: string | null): boolean => Boolean(extractMissingReason(value));

const softenMissingValue = (value?: string | null): string => {
  const reason = extractMissingReason(value);
  if (!reason) {
    return String(value || '').trim();
  }
  if (reason.includes('冲突')) {
    return ui('report.conflicts');
  }
  if (reason.includes('样本不足')) {
    return ui('report.noFields');
  }
  if (reason.includes('会话')) {
    return `${ui('report.noFields')}（${ui('report.session')}）`;
  }
  if (reason.includes('市场暂不支持')) {
    return `${ui('report.noFields')}（${ui('report.coverageGaps')}）`;
  }
  return ui('report.noFields');
};

const isMeaningfulMetaText = (value?: string | null): boolean => {
  const text = String(value || '').trim();
  return Boolean(text) && !isMissingDisplayText(text) && text !== '已就绪' && text !== 'ready';
};

const isPresentValue = (value?: string | null): boolean => {
  const text = String(value || '').trim();
  return Boolean(text) && !isMissingDisplayText(text);
};

const lowerText = (value?: string | null): string => String(value || '').trim().toLowerCase();

const uniqueMeaningfulItems = (
  items: Array<string | null | undefined>,
  limit: number,
): string[] => {
  const seen = new Set<string>();
  const normalized: string[] = [];

  items.forEach((item) => {
    const text = String(item || '').trim();
    if (!text || seen.has(text)) {
      return;
    }
    seen.add(text);
    normalized.push(text);
  });

  return normalized.slice(0, limit);
};

const buildSection = (
  section?: StandardReportTableSection,
  fallbackTitle?: string,
  fallbackFields?: StandardReportField[],
): StandardReportTableSection => ({
  title: section?.title || fallbackTitle || ui('report.evidence'),
  fields: section?.fields || fallbackFields || [],
  note: section?.note,
});

const badgeTone = (
  tone?: string,
): 'default' | 'success' | 'warning' | 'danger' | 'info' | 'history' => {
  if (!tone) {
    return 'default';
  }
  if (['success', 'positive', 'buy', 'pass'].includes(tone)) {
    return 'success';
  }
  if (['warning', 'warn', 'caution'].includes(tone)) {
    return 'warning';
  }
  if (['danger', 'negative', 'risk', 'fail', 'target'].includes(tone)) {
    return 'danger';
  }
  if (['info', 'position', 'note'].includes(tone)) {
    return 'info';
  }
  if (['history'].includes(tone)) {
    return 'history';
  }
  return 'default';
};

const checklistBadgeTone = (
  status: string,
): 'default' | 'success' | 'warning' | 'danger' | 'info' | 'history' => {
  if (status === 'pass') {
    return 'success';
  }
  if (status === 'warn') {
    return 'warning';
  }
  if (status === 'fail') {
    return 'danger';
  }
  if (status === 'info') {
    return 'info';
  }
  return 'default';
};

const checklistLabel = (status: string): string => {
  if (status === 'pass') {
    return ui('tasks.completed');
  }
  if (status === 'warn') {
    return ui('report.risk');
  }
  if (status === 'fail') {
    return ui('tasks.failed');
  }
  if (status === 'na') {
    return 'NA';
  }
  return ui('report.note');
};

const scoreToneClass = (score?: number): string => {
  if (score === undefined) {
    return 'text-foreground';
  }
  if (score >= 70) {
    return 'text-[var(--accent-positive)]';
  }
  if (score >= 45) {
    return 'text-[var(--accent-warning)]';
  }
  return 'text-[var(--accent-danger)]';
};

const changeToneClass = (changePct?: string): string => {
  const numeric = parseNumericValue(changePct);
  if (numeric === undefined) {
    return 'text-secondary-text';
  }
  if (numeric > 0) {
    return 'text-[var(--accent-positive)]';
  }
  if (numeric < 0) {
    return 'text-[var(--accent-danger)]';
  }
  return 'text-secondary-text';
};

const progressToneClass = (score?: number): string => {
  if (score === undefined) {
    return 'theme-progress-fill';
  }
  if (score >= 70) {
    return 'theme-progress-fill theme-progress-fill--positive';
  }
  if (score >= 45) {
    return 'theme-progress-fill theme-progress-fill--warning';
  }
  return 'theme-progress-fill theme-progress-fill--danger';
};

const clampPercent = (value?: number): number => {
  if (value === undefined || Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
};

const SectionHeader: React.FC<{ title: string; description?: string }> = ({ title, description }) => (
  <div className="mb-4 flex items-start justify-between gap-3">
    <div>
      <h3 className="text-lg font-semibold tracking-tight text-foreground">{title}</h3>
    </div>
    {isMeaningfulText(description) ? (
      <p className="max-w-xs text-right text-xs leading-5 text-muted-text">{description}</p>
    ) : null}
  </div>
);

const HeroMetaRow: React.FC<{
  items: Array<{ label: string; value?: string }>;
}> = ({ items }) => (
  <div className="report-hero-meta-grid">
    {items
      .filter((item) => isMeaningfulText(item.value))
      .map((item) => (
        <div key={`${item.label}-${item.value}`} className="report-hero-meta-item">
          <span className="report-hero-meta-label">{item.label}</span>
          <span className="report-hero-meta-value">{softenMissingValue(item.value)}</span>
        </div>
      ))}
  </div>
);

const compactSessionLabel = (summary: StandardReport['summaryPanel'] | undefined): string => {
  const sessionText = summary?.marketSessionDate
    ? `${summary.marketSessionDate} ${ui('report.sessionSuffix')}`
    : summary?.referenceSession;
  const snapshotText = summary?.snapshotTime ? `${ui('report.updatedShort')} ${summary.snapshotTime}` : undefined;
  return uniqueMeaningfulItems(
    [summary?.priceBasis, sessionText, snapshotText],
    3,
  ).join(' · ');
};

const CompactSummaryBlock: React.FC<{
  label: string;
  value?: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'history';
}> = ({ label, value, tone = 'default' }) => (
  <div className="theme-panel-subtle rounded-[1rem] px-3.5 py-3.5">
    <div className="flex items-center justify-between gap-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{label}</p>
      <Badge variant={tone}>{label === ui('report.setup') ? ui('report.plan') : tone === 'danger' ? ui('report.risk') : tone === 'success' ? ui('report.bull') : tone === 'info' ? ui('report.mixed') : ui('report.note')}</Badge>
    </div>
    <p className={cn('mt-2.5 text-sm leading-6', isMissingDisplayText(value) ? 'text-muted-text' : 'text-secondary-text')}>
      {softenMissingValue(value)}
    </p>
  </div>
);

const HeroStat: React.FC<{ label: string; value?: string | number; accent?: 'score' | 'advice' | 'trend' }> = ({
  label,
  value,
  accent = 'advice',
}) => {
  const wrapperClass = 'theme-panel-subtle border border-[var(--theme-panel-subtle-border)]';
  const accentClass = accent === 'score'
    ? 'text-[var(--accent-primary)]'
    : accent === 'trend'
      ? 'text-secondary-text'
      : 'text-foreground';
  const valueClass =
    accent === 'score'
      ? 'text-[2.5rem] leading-none md:text-[2.9rem]'
      : 'text-[1.2rem] leading-7 md:text-[1.35rem]';
  return (
    <div className={cn('rounded-[1rem] px-4 py-3.5', wrapperClass)}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{label}</p>
      <p className={cn('mt-2 font-semibold tracking-tight', accentClass, valueClass)}>
        {softenMissingValue(typeof value === 'number' ? String(value) : value)}
      </p>
    </div>
  );
};

const ExecutionMetricCard: React.FC<{
  label: string;
  value?: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}> = ({ label, value, tone = 'default' }) => (
  <div className="theme-panel-subtle rounded-[1rem] px-3.5 py-3.5">
    <div className="flex items-center justify-between gap-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{label}</p>
      <Badge variant={tone} className="min-w-[3.75rem]">
        {tone === 'danger' ? ui('report.riskControl') : tone === 'success' ? ui('report.targetOne') : tone === 'info' ? ui('report.positionSizing') : ui('report.execution')}
      </Badge>
    </div>
    <p className={cn('mt-3 text-base font-semibold leading-7 break-words', isMissingDisplayText(value) ? 'text-muted-text' : 'text-foreground')}>
      {softenMissingValue(value)}
    </p>
  </div>
);

const NarrativeBucketCard: React.FC<{
  label: string;
  items: string[];
  emptyText: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  footer?: React.ReactNode;
}> = ({
  label,
  items,
  emptyText,
  tone = 'default',
  footer,
}) => (
  <div className={subtlePanelClass}>
    <div className="flex items-center justify-between gap-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{label}</p>
      <Badge variant={tone} className="min-w-[4rem]">
        {tone === 'success'
          ? ui('report.bull')
          : tone === 'danger'
            ? ui('report.risk')
            : tone === 'info'
              ? ui('report.mixed')
              : ui('report.latestUpdate')}
      </Badge>
    </div>
    {items.length > 0 ? (
      <ul className="mt-3 space-y-2 text-sm leading-5 text-secondary-text">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="border-b border-[var(--theme-panel-subtle-border)] pb-2 last:border-b-0 last:pb-0">
            {item}
          </li>
        ))}
      </ul>
    ) : (
      <p className="mt-3 text-sm leading-6 text-muted-text">{emptyText}</p>
    )}
    {footer ? <div className="mt-3 border-t border-[var(--theme-panel-subtle-border)] pt-3">{footer}</div> : null}
  </div>
);

const BulletSummaryCard: React.FC<{
  title: string;
  items: string[];
  reminders?: string[];
}> = ({ title, items, reminders = [] }) => (
  <div className="theme-panel-subtle flex h-full flex-col rounded-[1rem] px-5 py-5">
    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{title}</p>
    <ul className="mt-3.5 space-y-3.5 text-[15.5px] leading-7 text-secondary-text">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="flex items-start gap-3">
          <span className="mt-2.5 inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-primary)]" />
          <span className="min-w-0 flex-1">
            {item.includes('：') || item.includes(':') ? (
              <>
                <span className="mr-1.5 text-[12px] uppercase tracking-[0.14em] text-muted-text">
                  {item.split(/[：:]/)[0]}
                </span>
                <span className="font-semibold text-foreground">
                  {item.split(/[：:]/).slice(1).join('：').trim()}
                </span>
              </>
            ) : (
              <span className="font-semibold text-foreground">{item}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
    {reminders.length > 0 ? (
      <div className="mt-auto border-t border-[var(--theme-panel-subtle-border)] pt-4">
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.reminders')}</p>
        <ul className="mt-2.5 space-y-2 text-[13px] leading-6 text-secondary-text">
          {reminders.slice(0, 3).map((item, index) => (
            <li key={`${item}-${index}`} className="flex items-start gap-2.5">
              <span className="mt-2 inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-warning)]" />
              <span className="min-w-0 flex-1">{item}</span>
            </li>
          ))}
        </ul>
      </div>
    ) : null}
  </div>
);

const DenseTable: React.FC<{
  section: StandardReportTableSection;
  description?: string;
  footer?: React.ReactNode;
}> = ({ section, description, footer }) => {
  const fields = section.fields || [];
  const showSource = fields.some((field) => isMeaningfulMetaText(field.source));
  const showStatus = fields.some((field) => isMeaningfulMetaText(field.status));
  const columnClass = showSource && showStatus
    ? denseTableColumns
    : showSource || showStatus
      ? 'md:grid-cols-[minmax(0,1.15fr)_minmax(0,1.35fr)_minmax(0,0.9fr)]'
      : 'md:grid-cols-[minmax(0,1.2fr)_minmax(0,1.5fr)]';

  return (
    <div className={solidCardClass}>
      <SectionHeader title={section.title} description={description || section.note} />

      {fields.length > 0 ? (
        <div className="theme-panel-table overflow-hidden rounded-[1rem] border">
          <div
            className={cn(
              'hidden items-center gap-3 border-b border-white/7 px-3 py-2.5 text-[11px] uppercase tracking-[0.16em] text-muted-text md:grid',
              columnClass,
            )}
          >
            <span>{ui('report.field')}</span>
            <span>{ui('report.value')}</span>
            {showSource ? <span>{ui('report.source')}</span> : null}
            {showStatus ? <span>{ui('report.status')}</span> : null}
          </div>

          <div className="divide-y divide-white/6">
            {fields.map((field, index) => (
              <div
                key={`${field.label}-${index}`}
                className={cn(
                  'grid gap-3 px-3 py-3.5',
                  columnClass,
                )}
              >
                <div className="space-y-1">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-muted-text md:hidden">{ui('report.field')}</p>
                  <p className="text-sm font-medium leading-6 text-foreground break-words">{field.label}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-muted-text md:hidden">{ui('report.value')}</p>
                  <p className={cn('text-sm leading-6 break-words', isMissingDisplayText(field.value) ? 'text-muted-text' : 'text-secondary-text')}>
                    {softenMissingValue(field.value)}
                  </p>
                </div>
                {showSource ? (
                  <div className="space-y-1">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-muted-text md:hidden">{ui('report.source')}</p>
                    <p className="text-xs leading-5 text-muted-text break-words">{isMeaningfulMetaText(field.source) ? field.source : '—'}</p>
                  </div>
                ) : null}
                {showStatus ? (
                  <div className="space-y-1">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-muted-text md:hidden">{ui('report.status')}</p>
                    <p className="text-xs leading-5 text-muted-text break-words">{isMeaningfulMetaText(field.status) ? field.status : '—'}</p>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-[1rem] border border-dashed border-[var(--border-muted)] bg-[hsl(var(--bg-card-elevated-hsl)/0.72)] px-4 py-6 text-sm text-muted-text">
          {ui('report.noFields')}
        </div>
      )}

      {footer ? <div className="mt-3">{footer}</div> : null}
    </div>
  );
};

const DecisionExecutionPanel: React.FC<{
  decisionPanel?: StandardReportDecisionPanel;
}> = ({ decisionPanel }) => (
  <section className={cn(solidCardClass, 'animate-in slide-in-from-bottom-2 duration-300')} data-testid="decision-execution-panel">
    <SectionHeader title={ui('report.tradeExecution')} />

    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
      <div className="theme-panel-subtle rounded-[1rem] px-4 py-4">
        <div className="flex flex-wrap items-center gap-2.5">
          <Badge variant="info">{softenMissingValue(decisionPanel?.setupType)}</Badge>
          <Badge variant="history">{ui('report.confidenceLabel')} {softenMissingValue(decisionPanel?.confidence)}</Badge>
        </div>
        <p className="mt-3 text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.executionSummary')}</p>
        <p className="mt-2 text-base font-semibold leading-7 text-foreground">
          {softenMissingValue(decisionPanel?.keyAction || decisionPanel?.noPositionAdvice)}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <CompactDecisionMetric label={ui('report.keySupport')} value={decisionPanel?.support} />
          <CompactDecisionMetric label={ui('report.keyResistance')} value={decisionPanel?.resistance} />
          <CompactDecisionMetric label={ui('report.stopReason')} value={decisionPanel?.stopReason} />
          <CompactDecisionMetric label={ui('report.targetReason')} value={decisionPanel?.targetReason} />
        </div>
      </div>

      <div className="theme-panel-subtle rounded-[1rem] px-4 py-4">
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.structureSnapshot')}</p>
        <p className="mt-2 text-sm leading-6 text-secondary-text">
          {softenMissingValue(decisionPanel?.marketStructure)}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <CompactDecisionMetric label={ui('report.positionSizing')} value={decisionPanel?.positionSizing} />
          <CompactDecisionMetric label={ui('report.targetZone')} value={decisionPanel?.targetZone || decisionPanel?.target} />
        </div>
      </div>
    </div>

    <div className="mt-4 grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
      <ExecutionMetricCard label={ui('report.idealEntry')} value={decisionPanel?.idealEntry} />
      <ExecutionMetricCard label={ui('report.backupEntry')} value={decisionPanel?.backupEntry} />
      <ExecutionMetricCard label={ui('report.stopLoss')} value={decisionPanel?.stopLoss} tone="danger" />
      <ExecutionMetricCard label={ui('report.targetOne')} value={decisionPanel?.targetOne || decisionPanel?.target} tone="success" />
      <ExecutionMetricCard label={ui('report.targetTwo')} value={decisionPanel?.targetTwo} tone="success" />
      <ExecutionMetricCard label={ui('report.targetZone')} value={decisionPanel?.targetZone || decisionPanel?.target} tone="info" />
    </div>

    <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <div className="grid gap-3">
        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.positionSizing')}</p>
          <p className="mt-3 text-sm leading-6 text-secondary-text">{softenMissingValue(decisionPanel?.positionSizing)}</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className={subtlePanelClass}>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.buildStrategy')}</p>
            <p className="mt-3 text-sm leading-6 text-secondary-text">{softenMissingValue(decisionPanel?.buildStrategy)}</p>
          </div>
          <div className={subtlePanelClass}>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.riskControl')}</p>
            <p className="mt-3 text-sm leading-6 text-secondary-text">{softenMissingValue(decisionPanel?.riskControlStrategy)}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-3">
        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.noPositionAdvice')}</p>
          <p className="mt-3 text-sm leading-6 text-secondary-text">{softenMissingValue(decisionPanel?.noPositionAdvice)}</p>
        </div>
        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.holderAdvice')}</p>
          <p className="mt-3 text-sm leading-6 text-secondary-text">{softenMissingValue(decisionPanel?.holderAdvice)}</p>
        </div>
      </div>
    </div>
  </section>
);

const SummaryHero: React.FC<{
  standardReport: StandardReport;
  report: AnalysisReport;
  chartFixtures?: ReportPriceChartFixtures;
}> = ({ standardReport, report, chartFixtures }) => {
  const { ref: heroRef, size: heroSize } = useElementSize<HTMLElement>();
  const summary = standardReport.summaryPanel || {};
  const visualBlocks = standardReport.visualBlocks || {};
  const decisionPanel = standardReport.decisionPanel || {};
  const reasonLayer = standardReport.reasonLayer || {};
  const highlights = standardReport.highlights || {};
  const score = summary.score ?? visualBlocks.score?.value;
  const trendStrength = visualBlocks.trendStrength;
  const scorePercent = clampPercent(visualBlocks.score?.max ? ((score || 0) / visualBlocks.score.max) * 100 : score);
  const trendPercent = clampPercent(
    trendStrength?.max ? ((trendStrength.value || 0) / trendStrength.max) * 100 : trendStrength?.value,
  );
  const topAction = decisionPanel.keyAction || decisionPanel.noPositionAdvice;
  const topRisk = reasonLayer.topRisk || highlights.riskAlerts?.[0];
  const topCatalyst = reasonLayer.topCatalyst || highlights.positiveCatalysts?.[0];
  const latestUpdate = reasonLayer.latestKeyUpdate || highlights.latestNews?.[0];
  const heroMetaItems = [
    { label: ui('report.priceBasis'), value: summary.priceBasis },
    { label: ui('report.session'), value: summary.referenceSession || summary.marketSessionDate },
    { label: ui('report.updated'), value: summary.snapshotTime || summary.marketTime },
  ];
  const companyTitle = report.meta.stockName || summary.stock || report.meta.stockCode;
  const tickerLabel = summary.ticker || report.meta.stockCode;
  const priceLabel = ui('report.analysisPrice');
  const compactMetaLine = compactSessionLabel(summary);
  const mobileHeroChips = [
    { label: `${ui('report.score')} ${score ?? 'NA'}`, tone: 'history' as const },
    { label: softenMissingValue(summary.operationAdvice || report.summary.operationAdvice), tone: 'info' as const },
    { label: softenMissingValue(summary.trendPrediction || report.summary.trendPrediction), tone: 'warning' as const },
  ];
  const desktopHighlightRows = uniqueMeaningfulItems([latestUpdate, topCatalyst, topRisk], 3);
  const actionItems = uniqueMeaningfulItems([
    topAction,
    isPresentValue(decisionPanel?.idealEntry) ? `${ui('report.idealEntry')}：${softenMissingValue(decisionPanel?.idealEntry)}` : undefined,
    isPresentValue(decisionPanel?.backupEntry) ? `${ui('report.backupEntry')}：${softenMissingValue(decisionPanel?.backupEntry)}` : undefined,
    isPresentValue(decisionPanel?.stopLoss) ? `${ui('report.stopLoss')}：${softenMissingValue(decisionPanel?.stopLoss)}` : undefined,
    isPresentValue(decisionPanel?.targetOne || decisionPanel?.target) ? `${ui('report.targetOne')}：${softenMissingValue(decisionPanel?.targetOne || decisionPanel?.target)}` : undefined,
  ], 5);
  const catalystItems = uniqueMeaningfulItems([topCatalyst, ...(highlights.positiveCatalysts || [])], 3);
  const riskItems = uniqueMeaningfulItems([topRisk, ...(highlights.riskAlerts || [])], 3);
  const executionReminders = uniqueMeaningfulItems(decisionPanel.executionReminders || [], 3);
  const useWideDesktopHero = heroSize.width >= WIDE_DESKTOP_HERO_MIN;

  return (
    <section ref={heroRef} className={cn(glassCardClass, 'animate-in slide-in-from-bottom-2 duration-300')} data-testid="hero-summary-card">
      {useWideDesktopHero ? (
      <div className="grid gap-7 2xl:gap-8 [grid-template-columns:minmax(0,1.9fr)_minmax(19.5rem,0.82fr)]">
        <div className="report-hero-primary-column min-w-0">
          <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
            <h2 className="min-w-0 text-[2.1rem] font-semibold tracking-tight text-foreground 2xl:text-[2.55rem]">
              {companyTitle}
            </h2>
            <span className="theme-inline-chip rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-muted-text">
              {tickerLabel}
            </span>
          </div>

          <div className="report-hero-desktop-priceband mt-5">
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{priceLabel}</p>
              <div className="mt-2 flex flex-wrap items-end gap-x-4 gap-y-2">
                <p className="text-[3rem] font-semibold tracking-tight text-foreground 2xl:text-[3.35rem]">
                  {softenMissingValue(summary.currentPrice)}
                </p>
                <p className={cn('pb-1 text-lg font-semibold 2xl:text-xl', changeToneClass(summary.changePct))}>
                  {softenMissingValue(summary.changeAmount)} / {softenMissingValue(summary.changePct)}
                </p>
              </div>
            </div>

            <div className="report-hero-desktop-meta">
              <HeroMetaRow items={heroMetaItems} />
              <p className="mt-3 text-xs leading-5 text-muted-text">
                {ui('report.reportTime')} {softenMissingValue(summary.reportGeneratedAt)}
              </p>
            </div>
          </div>

          <p className="mt-5 max-w-5xl text-[15px] leading-7 text-secondary-text 2xl:text-base">
            {summary.oneSentence || report.summary.analysisSummary || ui('report.oneLineFallback')}
          </p>

          <div className="mt-5 grid gap-3 2xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
            <BulletSummaryCard
              title={ui('report.keyAction')}
              items={actionItems.length > 0 ? actionItems : [softenMissingValue(topAction)]}
              reminders={executionReminders}
            />
            <div className="grid gap-3">
              <NarrativeBucketCard
                label={ui('report.keyCatalyst')}
                items={catalystItems}
                emptyText={ui('report.oneLineFallback')}
                tone="success"
              />
              <NarrativeBucketCard
                label={ui('report.keyRisk')}
                items={riskItems}
                emptyText={ui('report.noFields')}
                tone="danger"
              />
            </div>
          </div>
        </div>

        <aside className="report-hero-status-column grid gap-3">
          <div className="grid gap-2.5 sm:grid-cols-[minmax(170px,0.9fr)_1fr_1fr] xl:grid-cols-1 2xl:grid-cols-[minmax(170px,0.9fr)_1fr_1fr]">
            <HeroStat label={ui('report.score')} value={score !== undefined ? `${score}` : 'NA'} accent="score" />
            <HeroStat label={ui('report.actionAdvice')} value={summary.operationAdvice || report.summary.operationAdvice} accent="advice" />
            <HeroStat label={ui('report.trend')} value={summary.trendPrediction || report.summary.trendPrediction} accent="trend" />
          </div>

          <div className={cn(subtlePanelClass, 'grid gap-3')}>
            <div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-text">{ui('report.scoreStrength')}</span>
                <span className={cn('text-sm font-semibold', scoreToneClass(score))}>{score ?? 'NA'}/100</span>
              </div>
              <div className="theme-progress-track mt-2.5 h-2 overflow-hidden rounded-full">
                <div className={cn('h-full rounded-full transition-all duration-300', progressToneClass(score))} style={{ width: `${scorePercent}%` }} />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-text">{ui('report.trendStrength')}</span>
                <span className="text-sm font-semibold text-foreground">
                  {trendStrength?.value ?? 'NA'}
                  {trendStrength?.max ? `/${trendStrength.max}` : ''}
                </span>
              </div>
              <div className="theme-progress-track mt-2.5 h-2 overflow-hidden rounded-full">
                <div className="theme-progress-fill theme-progress-fill--warning h-full rounded-full transition-all duration-300" style={{ width: `${trendPercent}%` }} />
              </div>
            </div>
            {isMeaningfulText(trendStrength?.label) || isMeaningfulText(summary.timeSensitivity) ? (
              <p className="text-sm leading-6 text-secondary-text">
                {trendStrength?.label}
                {isMeaningfulText(trendStrength?.label) && isMeaningfulText(summary.timeSensitivity) ? ' · ' : ''}
                {isMeaningfulText(summary.timeSensitivity) ? `${ui('report.timeHorizon')} ${summary.timeSensitivity}` : ''}
              </p>
            ) : null}
          </div>

          <div className="theme-panel-subtle rounded-[1rem] px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.statusBoard')}</p>
              <Badge variant="info">{ui('report.desktop')}</Badge>
            </div>
            <div className="mt-3 space-y-3">
              <CompactDecisionMetric label={ui('report.setup')} value={`${softenMissingValue(decisionPanel.setupType)} · ${ui('report.confidence')} ${softenMissingValue(decisionPanel.confidence)}`} />
              {desktopHighlightRows.map((item, index) => (
                <div key={`${item}-${index}`} className="border-t border-[var(--theme-panel-subtle-border)] pt-3 first:border-t-0 first:pt-0">
                  <p className="text-sm leading-6 text-secondary-text">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
      ) : (
      <div>
        <div className="report-hero-mobile-top">
          <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
            <h2 className="min-w-0 text-[1.42rem] font-semibold tracking-tight text-foreground sm:text-[1.64rem]">
              {companyTitle}
            </h2>
            <span className="theme-inline-chip rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-muted-text">
              {tickerLabel}
            </span>
          </div>

          <div className="mt-4">
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{priceLabel}</p>
            <div className="mt-2 flex flex-wrap items-end gap-x-3 gap-y-2">
              <p className="text-[2.02rem] font-semibold tracking-tight text-foreground sm:text-[2.28rem]">
                {softenMissingValue(summary.currentPrice)}
              </p>
              <p className={cn('pb-1 text-[0.95rem] font-semibold sm:text-base', changeToneClass(summary.changePct))}>
                {softenMissingValue(summary.changeAmount)} / {softenMissingValue(summary.changePct)}
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {mobileHeroChips.map((chip) => (
              <Badge key={`${chip.label}-${chip.tone}`} variant={chip.tone}>
                {chip.label}
              </Badge>
            ))}
          </div>

          <p className="mt-3 text-[13px] leading-6 text-secondary-text sm:text-[14px]">
            {summary.oneSentence || report.summary.analysisSummary || ui('report.oneLineFallback')}
          </p>

          {isMeaningfulText(compactMetaLine) ? (
            <div className="mt-3 rounded-[1rem] border border-[var(--theme-panel-subtle-border)] bg-[var(--theme-panel-subtle-bg)] px-3 py-2.5 text-[12px] leading-5 text-secondary-text">
              {compactMetaLine}
            </div>
          ) : null}

          <div className="mt-3 theme-panel-subtle rounded-[1rem] px-3.5 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.keyAction')}</p>
            <ul className="mt-2.5 space-y-1.5 text-[13px] leading-5 text-secondary-text">
              {(actionItems.length > 0 ? actionItems.slice(0, 3) : [softenMissingValue(topAction)]).map((item, index) => (
                <li key={`${item}-${index}`} className="flex items-start gap-2">
                  <span className="mt-2 inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-primary)]" />
                  <span className="min-w-0 flex-1 font-medium text-foreground">{item}</span>
                </li>
              ))}
            </ul>
            {executionReminders.length > 0 ? (
              <div className="mt-2.5 border-t border-[var(--theme-panel-subtle-border)] pt-2.5">
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.reminders')}</p>
                <ul className="mt-1.5 space-y-1 text-[11px] leading-5 text-secondary-text">
                  {executionReminders.map((item, index) => (
                    <li key={`${item}-${index}`} className="flex items-start gap-2">
                      <span className="mt-1.5 inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-warning)]" />
                      <span className="min-w-0 flex-1">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          <details className="report-hero-disclosure mt-3">
            <summary>{ui('report.moreQuoteContext')}</summary>
            <div className="report-hero-disclosure-body">
              <HeroMetaRow items={heroMetaItems} />
              <p className="mt-3 text-xs leading-5 text-muted-text">
                {ui('report.reportTime')} {softenMissingValue(summary.reportGeneratedAt)}
              </p>
            </div>
          </details>
        </div>
      </div>
      )}

      <div className="mt-6 border-t border-[var(--theme-panel-subtle-border)] pt-5">
        <ReportPriceChart
          stockCode={report.meta.stockCode}
          stockName={report.meta.stockName}
          summary={standardReport.summaryPanel}
          market={standardReport.market}
          decisionPanel={standardReport.decisionPanel}
          integrated
          fixtures={chartFixtures}
        />
      </div>

      {!useWideDesktopHero ? (
      <div className="mt-4 grid gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <CompactSummaryBlock label={ui('report.keyCatalyst')} value={topCatalyst} tone="success" />
          <CompactSummaryBlock label={ui('report.keyRisk')} value={topRisk} tone="danger" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <CompactSummaryBlock label={ui('report.latestUpdate')} value={latestUpdate} tone="history" />
          <CompactSummaryBlock label={ui('report.setup')} value={`${softenMissingValue(decisionPanel.setupType)} · ${ui('report.confidence')} ${softenMissingValue(decisionPanel.confidence)}`} tone="info" />
        </div>
      </div>
      ) : null}
    </section>
  );
};

const NewsRiskPanel: React.FC<{
  highlights?: StandardReportHighlights;
  reasonLayer?: StandardReportReasonLayer;
}> = ({ highlights, reasonLayer }) => {
  const latestNews = highlights?.latestNews || [];
  const bullishFactors = highlights?.bullishFactors || highlights?.positiveCatalysts || [];
  const bearishFactors = highlights?.bearishFactors || highlights?.riskAlerts || [];
  const neutralFactors = highlights?.neutralFactors || [];
  const latestUpdates = uniqueMeaningfulItems(
    [reasonLayer?.latestKeyUpdate, ...latestNews],
    3,
  );
  const seenAcrossBuckets = new Set(latestUpdates.map((item) => item.toLowerCase()));
  const pullUniqueBucket = (items: Array<string | null | undefined>, limit: number): string[] => {
    const bucket = uniqueMeaningfulItems(items, limit * 2).filter((item) => {
      const normalized = item.toLowerCase();
      if (seenAcrossBuckets.has(normalized)) {
        return false;
      }
      seenAcrossBuckets.add(normalized);
      return true;
    });
    return bucket.slice(0, limit);
  };
  const bullish = pullUniqueBucket([reasonLayer?.topCatalyst, ...bullishFactors], 4);
  const bearish = pullUniqueBucket([reasonLayer?.topRisk, ...bearishFactors], 4);
  const neutral = pullUniqueBucket(neutralFactors, 4);
  const socialSources = uniqueMeaningfulItems(highlights?.socialSources || [], 3);

  return (
    <div className={cn(solidCardClass, 'animate-in slide-in-from-bottom-2 duration-300')} data-testid="risk-catalyst-panel">
      <SectionHeader title={ui('report.riskCatalystSentiment')} />

      <div className="grid gap-3 xl:grid-cols-2">
        <NarrativeBucketCard
          label={ui('report.latestUpdate')}
          items={latestUpdates}
          emptyText={ui('report.oneLineFallback')}
          footer={isMeaningfulText(highlights?.newsValueGrade) ? (
            <p className="text-xs leading-5 text-muted-text">{ui('report.note')}: {highlights?.newsValueGrade}</p>
          ) : null}
        />
        <NarrativeBucketCard
          label={ui('report.bullishFactors')}
          items={bullish}
          emptyText={ui('report.oneLineFallback')}
          tone="success"
        />
        <NarrativeBucketCard
          label={ui('report.bearishFactors')}
          items={bearish}
          emptyText={ui('report.noFields')}
          tone="danger"
        />
        <NarrativeBucketCard
          label={ui('report.neutralFactors')}
          items={neutral}
          emptyText={ui('report.noFields')}
          tone="info"
          footer={
            <>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.mixed')}</p>
              <p className="mt-2 text-sm leading-5 text-secondary-text">
                {softenMissingValue(reasonLayer?.sentimentSummary || highlights?.sentimentSummary)}
              </p>
              <div className="mt-3 rounded-[0.95rem] border border-[var(--theme-panel-subtle-border)] bg-[var(--theme-panel-subtle-bg)] px-3 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="info">{ui('report.synthesized')}</Badge>
                  <Badge variant="history">{ui('report.retailTone')} {softenMissingValue(highlights?.socialTone)}</Badge>
                  <Badge variant="default">{softenMissingValue(highlights?.socialAttention)}</Badge>
                </div>
                <p className="mt-3 text-sm leading-5 text-secondary-text">
                  {softenMissingValue(highlights?.socialSynthesis)}
                </p>
                <p className="mt-3 text-xs leading-5 text-muted-text">
                  {ui('report.narrativeFocus')}: {softenMissingValue(highlights?.socialNarrativeFocus)}
                </p>
                {socialSources.length > 0 ? (
                  <p className="mt-2 text-xs leading-5 text-muted-text">
                    {ui('report.socialSources')}: {socialSources.join(' / ')}
                  </p>
                ) : null}
              </div>
              {isMeaningfulText(highlights?.earningsOutlook) ? (
                <>
                  <p className="mt-3 text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.earningsOutlook')}</p>
                  <p className="mt-2 text-sm leading-5 text-secondary-text">{softenMissingValue(highlights?.earningsOutlook)}</p>
                </>
              ) : null}
            </>
          }
        />
      </div>
    </div>
  );
};

const BattlePlanPanel: React.FC<{
  battlePlan?: StandardReportBattlePlanCompact;
}> = ({ battlePlan }) => {
  const cardItems = battlePlan?.cards || [];
  const noteItems = battlePlan?.notes || [];
  const topGridItems: StandardReportBattlePlanItem[] = [];
  const lowerNotes: StandardReportBattlePlanItem[] = [];

  [...cardItems, ...noteItems].forEach((item) => {
    const label = lowerText(item.label);
    const isTopMetric = (
      label.includes('交易场景') ||
      label.includes('关键动作') ||
      label.includes('理想买入') ||
      label.includes('次优买入') ||
      label.includes('止损') ||
      label.includes('目标')
    );
    if (isTopMetric && topGridItems.length < 4) {
      topGridItems.push(item);
      return;
    }
    lowerNotes.push(item);
  });

  return (
    <div className={cn(solidCardClass, 'animate-in slide-in-from-bottom-2 duration-300')} data-testid="battle-plan-panel">
      <SectionHeader title={ui('report.battlePlan')} />

      {topGridItems.length > 0 || lowerNotes.length > 0 ? (
        <div className="space-y-4">
          {topGridItems.length > 0 ? (
            <div
              data-testid="battle-plan-grid"
              className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-4"
            >
              {topGridItems.map((item, index) => (
                <div key={`${item.label}-${index}`} className="theme-panel-subtle rounded-[1rem] px-3.5 py-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{item.label}</p>
                    <Badge variant={badgeTone(item.tone)} className="min-w-[3.75rem]">
                      {item.tone === 'buy'
                        ? ui('report.planBuy')
                        : item.tone === 'risk'
                          ? ui('report.planRisk')
                          : item.tone === 'target'
                            ? ui('report.planTarget')
                            : ui('report.planDefault')}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-foreground break-words">{item.value}</p>
                </div>
              ))}
            </div>
          ) : null}

          {lowerNotes.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {lowerNotes.map((item, index) => (
                <div key={`${item.label}-${index}`} className="theme-panel-subtle rounded-[1rem] px-4 py-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{item.label}</p>
                    <Badge variant={badgeTone(item.tone)} className="min-w-[3.75rem]">
                      {item.tone === 'position'
                        ? ui('report.planPosition')
                        : item.tone === 'risk'
                          ? ui('report.planRisk')
                          : ui('report.planDefault')}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-secondary-text break-words">{item.value}</p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="rounded-[1rem] border border-dashed border-[var(--border-muted)] bg-[hsl(var(--bg-card-elevated-hsl)/0.72)] px-4 py-6 text-sm text-muted-text">
          {ui('report.noBattlePlan')}
        </div>
      )}

      {battlePlan?.warnings?.length ? (
        <div
          className="mt-4 rounded-[1rem] border border-[hsl(var(--accent-danger-hsl)/0.24)] bg-[hsl(var(--accent-danger-hsl)/0.12)] px-4 py-3"
        >
          <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--accent-danger)]">{ui('report.reminders')}</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-[hsl(var(--accent-danger-hsl)/0.9)]">
            {battlePlan.warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
};

const ScoreBreakdownList: React.FC<{ items: StandardReportScoreBreakdownItem[] }> = ({ items }) => {
  if (items.length === 0) {
    return <p className="text-sm text-muted-text">{ui('report.noScoreBreakdown')}</p>;
  }

  const compactGrid = items.length <= 4;

  return (
    <div className={cn(compactGrid ? 'grid gap-2 sm:grid-cols-2' : 'space-y-2.5')}>
      {items.map((item, index) => (
        <div key={`${item.label}-${index}`} className="theme-panel-subtle rounded-[0.95rem] px-3 py-2.5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium text-foreground">{item.label}</p>
            <Badge variant={badgeTone(item.tone)} className="min-w-[3.5rem]">
              {item.score ?? 'NA'}
            </Badge>
          </div>
          {isMeaningfulText(item.note) ? (
            <p className="mt-1.5 text-xs leading-5 text-secondary-text">{item.note}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
};

const ChecklistPanel: React.FC<{ items: StandardReportChecklistItem[] }> = ({ items }) => {
  if (items.length === 0) {
    return <p className="text-sm text-muted-text">{ui('report.noChecklist')}</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={`${item.text}-${index}`} className="theme-panel-subtle flex items-start gap-2.5 rounded-[0.95rem] px-3 py-2.5">
          <Badge variant={checklistBadgeTone(item.status)} className="min-w-[4.75rem]">
            <span className="inline-flex items-center gap-1.5">
              <span className="text-[11px]">{item.icon}</span>
              <span>{checklistLabel(item.status)}</span>
            </span>
          </Badge>
          <p className="min-w-0 flex-1 text-sm leading-5 text-secondary-text">{item.text}</p>
        </div>
      ))}
    </div>
  );
};

const CompactDecisionMetric: React.FC<{ label: string; value?: string | null }> = ({ label, value }) => (
  <div className="space-y-1">
    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{label}</p>
    <p className="text-sm leading-5 text-secondary-text">{softenMissingValue(value)}</p>
  </div>
);

const DecisionBoardPanel: React.FC<{
  decisionContext?: StandardReportDecisionContext;
  checklistItems: StandardReportChecklistItem[];
  reasonLayer?: StandardReportReasonLayer;
}> = ({ decisionContext, checklistItems, reasonLayer }) => (
  <div className={cn(solidCardClass, 'animate-in slide-in-from-bottom-2 duration-300')} data-testid="decision-board-panel">
    <SectionHeader title={ui('report.checklistAndScore')} />

    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
      <div className="grid gap-4">
        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.topReasons')}</p>
          {reasonLayer?.coreReasons?.length ? (
            <ul className="mt-3 space-y-2 text-sm leading-5 text-secondary-text">
              {reasonLayer.coreReasons.slice(0, 3).map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-muted-text">{ui('report.noReasons')}</p>
          )}
        </div>

        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.checklistState')}</p>
          <div className="mt-2.5">
            <ChecklistPanel items={checklistItems} />
          </div>
        </div>
      </div>

      <div className="grid gap-4">
        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.scoreBreakdown')}</p>
          <div className="mt-2.5">
            <ScoreBreakdownList items={decisionContext?.scoreBreakdown || []} />
          </div>
        </div>

        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.scoreNotes')}</p>
          <div className="mt-2.5 grid gap-x-4 gap-y-3 sm:grid-cols-2">
            <CompactDecisionMetric label={ui('report.shortTermView')} value={decisionContext?.shortTermView || ui('report.noFields')} />
            <CompactDecisionMetric label={ui('report.compositeView')} value={decisionContext?.compositeView || ui('report.noFields')} />
            <CompactDecisionMetric label={ui('report.checklistSummary')} value={reasonLayer?.checklistSummary || ui('report.noFields')} />
            <CompactDecisionMetric label={ui('report.changeReason')} value={decisionContext?.changeReason || decisionContext?.adjustmentReason || ui('report.noFields')} />
            {isMeaningfulText(decisionContext?.adjustmentReason) ? (
              <CompactDecisionMetric label={ui('report.adjustmentReason')} value={decisionContext?.adjustmentReason} />
            ) : null}
            {decisionContext?.previousScore ? (
              <CompactDecisionMetric label={ui('report.previousScore')} value={decisionContext?.previousScore} />
            ) : null}
            {decisionContext?.scoreChange ? (
              <CompactDecisionMetric label={ui('report.scoreChange')} value={decisionContext?.scoreChange} />
            ) : null}
          </div>
          {isMeaningfulText(reasonLayer?.checklistSummary) ? (
            <div className="mt-3 border-t border-white/6 pt-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{ui('report.reminders')}</p>
              <p className="mt-2 text-sm leading-5 text-secondary-text">{reasonLayer?.checklistSummary}</p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  </div>
);

const MarketWarnings: React.FC<{ warnings: string[] }> = ({ warnings }) => {
  if (warnings.length === 0) {
    return null;
  }
  return (
    <div className="rounded-[1rem] border border-[hsl(var(--accent-warning-hsl)/0.46)] bg-[hsl(var(--accent-warning-hsl)/0.14)] px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--accent-warning)]">{ui('report.basisNotes')}</p>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-[hsl(var(--accent-warning-hsl)/0.9)]">
        {warnings.map((warning, index) => (
          <li key={`${warning}-${index}`}>{warning}</li>
        ))}
      </ul>
    </div>
  );
};

export const StandardReportPanel: React.FC<StandardReportPanelProps> = ({ report, chartFixtures }) => {
  const standardReport = report.details?.standardReport;

  if (!standardReport) {
    return null;
  }

  const marketSection = buildSection(
    standardReport.tableSections?.market,
    ui('report.evidence'),
    standardReport.market?.displayFields || standardReport.market?.regularFields,
  );
  const technicalSection = buildSection(standardReport.tableSections?.technical, ui('report.signals'), standardReport.technicalFields);
  const fundamentalSection = buildSection(standardReport.tableSections?.fundamental, ui('report.evidence'), standardReport.fundamentalFields);
  const earningsSection = buildSection(standardReport.tableSections?.earnings, ui('report.sourceNotes'), standardReport.earningsFields);
  const warnings = standardReport.market?.consistencyWarnings || [];

  return (
    <div className="space-y-5 text-left md:space-y-6 xl:space-y-7" data-testid="standard-report-panel">
      <SummaryHero standardReport={standardReport} report={report} chartFixtures={chartFixtures} />

      <DecisionExecutionPanel decisionPanel={standardReport.decisionPanel} />

      <div className={middleSectionGridClass}>
        <NewsRiskPanel highlights={standardReport.highlights} reasonLayer={standardReport.reasonLayer} />
        <DecisionBoardPanel
          decisionContext={standardReport.decisionContext}
          checklistItems={standardReport.checklistItems || []}
          reasonLayer={standardReport.reasonLayer}
        />
      </div>

      <div className={rowGridClass}>
        <DenseTable
          section={marketSection}
          footer={<MarketWarnings warnings={warnings} />}
        />
        <DenseTable
          section={technicalSection}
        />
      </div>

      <div className={rowGridClass}>
        <DenseTable
          section={fundamentalSection}
        />
        <DenseTable
          section={earningsSection}
        />
      </div>

      <BattlePlanPanel battlePlan={standardReport.battlePlanCompact} />
    </div>
  );
};
