/**
 * SpaceX live refinement: preserves the standard-report IA and chart/execution/detail
 * modules while allowing the homepage to suppress the duplicated hero decision summary
 * so the chart becomes the first lower full-width module beneath the top workspace.
 */
import React from 'react';
import { translateForCurrentLanguage } from '../../i18n/core';
import type {
  AnalysisReport,
  StandardReport,
  StandardReportBattlePlanCompact,
  StandardReportBattlePlanItem,
  StandardReportChecklistItem,
  StandardReportDecisionContext,
  StandardReportDecisionPanel,
  StandardReportField,
  StandardReportHighlights,
  StandardReportReasonLayer,
  StandardReportScoreBreakdownItem,
  StandardReportTableSection,
} from '../../types/analysis';
import { getSentimentColor, getSentimentLabel } from '../../types/analysis';
import { Badge } from '../common';
import { cn } from '../../utils/cn';
import { ReportPriceChart, type ReportPriceChartFixtures } from './ReportPriceChart';
import {
  getReportControlledValueProfile,
  localizeReportHeadingLabel,
  localizeReportTermLabel,
  localizeReportControlledValue,
} from '../../utils/reportTerminology';
import {
  buildMissingFieldAudit,
  collectMissingFieldEntriesFromStandardReport,
  extractMissingReason,
  normalizeMissingFieldSemanticKey,
  type MissingFieldAuditSummary,
  type MissingFieldCategory,
} from './missingFieldAudit';

interface StandardReportPanelProps {
  report: AnalysisReport;
  chartFixtures?: ReportPriceChartFixtures;
  showLeadSummary?: boolean;
}

const solidCardClass =
  'theme-panel-solid rounded-[var(--cohere-radius-signature)] px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6';
const chartLayerCardClass =
  'theme-panel-solid rounded-[var(--cohere-radius-signature)] py-4 md:py-5 xl:py-6';
const glassCardClass =
  'theme-panel-glass rounded-[var(--cohere-radius-signature)] px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6';
const subtlePanelClass = 'theme-panel-subtle rounded-[var(--cohere-radius-medium)] px-3.5 py-3';
const rowGridClass = 'grid gap-4 lg:grid-cols-2';

const ui = translateForCurrentLanguage;
const isEnglishUi = (): boolean => /^[A-Za-z]/.test(ui('report.score'));
const reportLanguage = (): 'en' | 'zh' => (isEnglishUi() ? 'en' : 'zh');
const localeColon = (): string => (isEnglishUi() ? ': ' : '：');
const joinLabelValue = (label: string, value: string): string => {
  return `${label}${localeColon()}${value}`;
};
const renderGroupLabelClass = (): string => (
  isEnglishUi()
    ? 'text-[11px] font-normal uppercase tracking-[0.12em] text-muted-text'
    : 'text-[12px] font-normal tracking-[0.08em] text-muted-text'
);
const groupHeadingClass = 'text-[1.02rem] font-normal leading-6 tracking-[-0.02em] text-foreground md:text-[1.06rem]';

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

const isMissingDisplayText = (value?: string | null): boolean => Boolean(extractMissingReason(value));

const softenMissingValue = (value?: string | null): string => {
  const reason = extractMissingReason(value);
  if (!reason) {
    return String(value || '').trim() || '--';
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

const localizeControlledValue = (value?: string | null): string => localizeReportControlledValue(value, reportLanguage());

const softenControlledValue = (value?: string | null): string => softenMissingValue(localizeControlledValue(value));

const lowerText = (value?: string | null): string => String(value || '').trim().toLowerCase();

const uniqueMeaningfulItems = (
  items: Array<string | null | undefined>,
  limit: number,
): string[] => {
  const seen = new Set<string>();
  const normalized: string[] = [];

  items.forEach((item) => {
    const text = String(item || '').trim();
    if (!text || isMissingDisplayText(text)) {
      return;
    }
    const normalizedKey = text
      .toLowerCase()
      .replace(/[\s.,，。!！?？:：;；、()（）【】'"“”‘’`]/g, '')
      .replace(/[[\]]/g, '')
      .trim();
    if (!normalizedKey || seen.has(normalizedKey)) {
      return;
    }
    seen.add(normalizedKey);
    normalized.push(text);
  });

  return normalized.slice(0, limit);
};

const normalizeComparableText = (value: string): string => value
  .toLowerCase()
  .replace(/[\s.,，。!！?？:：;；、()（）【】'"“”‘’`/|_-]/g, '')
  .replace(/[[\]]/g, '')
  .trim();

const extractLeadingLabel = (value: string): string | null => {
  const normalized = value.trim();
  const match = normalized.match(/^([^:：]{1,24})[:：]/);
  if (!match?.[1]) {
    return null;
  }
  const label = normalizeComparableText(match[1]);
  return label || null;
};

const hasNearDuplicateText = (left: string, right: string): boolean => {
  if (!left || !right) {
    return false;
  }
  if (left === right) {
    return true;
  }
  const minLength = Math.min(left.length, right.length);
  if (minLength < 8) {
    return false;
  }
  return left.includes(right) || right.includes(left);
};

const executionSemanticKey = (text: string): string => {
  const normalized = normalizeComparableText(text);
  const label = extractLeadingLabel(text);
  if (label) {
    return `label:${label}`;
  }
  if (/(等待|观望|回踩|确认|wait|watch|confirm|pullback)/i.test(text)) {
    return 'intent:wait_confirmation';
  }
  if (/(持仓|holder|holding)/i.test(text)) {
    return 'intent:holder';
  }
  if (/(收缩仓位|减仓|降低仓位|风控|riskcontrol|reduceposition|trimposition|de-?risk)/i.test(normalized)) {
    return 'intent:risk_control';
  }
  if (/(止损|stoploss|breaksupport|跌破)/i.test(normalized)) {
    return 'intent:stop_loss';
  }
  if (/(目标二区|targettwo|target2)/i.test(normalized)) {
    return 'intent:target_two';
  }
  if (/(目标一区|targetone|target1)/i.test(normalized)) {
    return 'intent:target_one';
  }
  if (/(目标区间|targetzone)/i.test(normalized)) {
    return 'intent:target_zone';
  }
  if (/(建仓|加仓|分批|试仓|buildstrategy|entry|scalein)/i.test(normalized)) {
    return 'intent:entry_strategy';
  }
  return `text:${normalized}`;
};

const narrativeSemanticKey = (text: string): string => {
  const normalized = normalizeComparableText(text);
  const label = extractLeadingLabel(text);
  if (label) {
    return `label:${label}`;
  }
  return `text:${normalized}`;
};

const coverageFieldSemanticKey = (text: string): string => {
  const trimmed = String(text || '').trim();
  if (!trimmed) {
    return '';
  }
  const labelMatch = trimmed.match(/^([^:：]{1,120})[:：]/);
  const candidate = labelMatch?.[1]?.trim() || trimmed;
  const semantic = normalizeMissingFieldSemanticKey(candidate);
  return semantic || normalizeComparableText(candidate);
};

const localizeSectionTitle = (title: string): string => {
  const normalized = normalizeComparableText(title);
  if (!normalized) {
    return title;
  }
  if (['行情表', '行情数据', 'markettable', 'marketdata'].some((token) => normalized.includes(normalizeComparableText(token)))) {
    return ui('report.marketDataTable');
  }
  if (['技术面表', '技术数据', 'technicaltable', 'technicaldata'].some((token) => normalized.includes(normalizeComparableText(token)))) {
    return ui('report.technicalDataTable');
  }
  if (['基本面表', '基本面数据', 'fundamentaltable', 'fundamentaldata'].some((token) => normalized.includes(normalizeComparableText(token)))) {
    return ui('report.fundamentalDataTable');
  }
  if (['财报表', '财报数据', 'earningstable', 'earningsdata'].some((token) => normalized.includes(normalizeComparableText(token)))) {
    return ui('report.earningsDataTable');
  }
  return title;
};

const collectDedupedItems = ({
  items,
  limit,
  keyResolver,
  seenKeys,
  blockedTexts,
}: {
  items: Array<string | null | undefined>;
  limit: number;
  keyResolver: (text: string) => string;
  seenKeys?: Set<string>;
  blockedTexts?: Array<string | null | undefined>;
}): string[] => {
  const accepted: string[] = [];
  const localNormalized: string[] = [];
  const blockedNormalized = (blockedTexts || [])
    .map((item) => normalizeComparableText(String(item || '').trim()))
    .filter(Boolean);
  const globalSeen = seenKeys || new Set<string>();

  items.forEach((item) => {
    if (accepted.length >= limit) {
      return;
    }
    const text = String(item || '').trim();
    if (!text || isMissingDisplayText(text)) {
      return;
    }
    const normalized = normalizeComparableText(text);
    if (!normalized) {
      return;
    }
    if (blockedNormalized.some((blocked) => hasNearDuplicateText(normalized, blocked))) {
      return;
    }
    if (localNormalized.some((existing) => hasNearDuplicateText(normalized, existing))) {
      return;
    }
    if (globalSeen.has(`text:${normalized}`)) {
      return;
    }

    const semanticKey = keyResolver(text);
    if (globalSeen.has(semanticKey)) {
      return;
    }

    accepted.push(text);
    localNormalized.push(normalized);
    globalSeen.add(semanticKey);
    globalSeen.add(`text:${normalized}`);
  });

  return accepted;
};

const buildSection = (
  section?: StandardReportTableSection,
  fallbackTitle?: string,
  fallbackFields?: StandardReportField[],
): StandardReportTableSection => ({
  title: localizeSectionTitle(section?.title || fallbackTitle || ui('report.evidence')),
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

const isPendingChecklistStatus = (status: string): boolean => ['warn', 'fail', 'na'].includes(status);

const missingCategoryLabel = (category: MissingFieldCategory): string => {
  if (category === 'integrated_unavailable') {
    return ui('report.missingIntegratedUnavailable');
  }
  if (category === 'not_integrated_yet') {
    return ui('report.missingNotIntegratedYet');
  }
  if (category === 'source_not_provided') {
    return ui('report.missingSourceNotProvided');
  }
  if (category === 'not_applicable') {
    return ui('report.missingNotApplicable');
  }
  return ui('report.missingOther');
};

const changeToneClass = (changePct?: string): string => {
  const numeric = parseNumericValue(changePct);
  if (numeric === undefined) {
    return 'text-secondary-text';
  }
  if (numeric > 0) {
    return 'text-[var(--market-up)]';
  }
  if (numeric < 0) {
    return 'text-[var(--market-down)]';
  }
  return 'text-secondary-text';
};

const SectionHeader: React.FC<{
  eyebrow?: string;
  title: string;
  description?: string;
  level?: 2 | 3 | 4;
}> = ({ eyebrow, title, description, level = 3 }) => (
  <div className="mb-4 space-y-2">
    {isMeaningfulText(eyebrow) ? (
      <p className={cn(renderGroupLabelClass(), 'tracking-[0.16em]')}>
        {eyebrow}
      </p>
    ) : null}
    <div className="flex items-start justify-between gap-3">
      {level === 2 ? (
        <h2 className="min-w-0 text-[1.28rem] font-normal tracking-[-0.03em] text-foreground md:text-[1.48rem]">
          {title}
        </h2>
      ) : level === 4 ? (
        <h4 className="min-w-0 text-[1.01rem] font-normal tracking-[-0.02em] text-foreground">
          {title}
        </h4>
      ) : (
        <h3 className="min-w-0 text-[1.08rem] font-normal tracking-[-0.02em] text-foreground">
          {title}
        </h3>
      )}
      {isMeaningfulText(description) ? (
        <p className="max-w-xs text-right text-xs leading-5 text-muted-text">{description}</p>
      ) : null}
    </div>
  </div>
);

const HeroStat: React.FC<{
  label: string;
  value?: string | number;
  support?: string;
  meter?: number;
  meterColor?: string;
  accent?: 'score' | 'default';
}> = ({
  label,
  value,
  support,
  meter,
  meterColor,
  accent = 'default',
}) => (
  <div className="theme-panel-subtle flex h-full flex-col rounded-[var(--cohere-radius-medium)] border border-[var(--theme-panel-subtle-border)] px-4 py-3.5">
    <p className={renderGroupLabelClass()}>{label}</p>
    <p
      className={cn(
        'mt-2 font-normal tracking-[-0.03em]',
        accent === 'score' ? 'text-[2.05rem] leading-none text-[var(--accent-primary)]' : 'text-[1.02rem] leading-7 text-foreground',
      )}
      style={accent === 'score' ? { fontFamily: 'var(--theme-heading-font)' } : undefined}
    >
      {softenMissingValue(typeof value === 'number' ? String(value) : value)}
    </p>
    {support ? (
      <p className="mt-1.5 text-xs leading-5 text-secondary-text">{support}</p>
    ) : null}
    {typeof meter === 'number' ? (
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--theme-panel-subtle-border)]">
        <span
          className="block h-full rounded-full"
          style={{
            width: `${meter}%`,
            backgroundColor: meterColor || 'var(--accent-primary)',
          }}
        />
      </div>
    ) : null}
  </div>
);

const ExecutionListCard: React.FC<{
  title: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'history';
  items: string[];
  emptyText: string;
  footer?: React.ReactNode;
  testId?: string;
}> = ({ title, tone = 'default', items, emptyText, footer, testId }) => (
  <div className={cn(subtlePanelClass, 'h-full')} data-testid={testId}>
    <div className="flex items-start justify-between gap-3 border-b border-[var(--theme-panel-subtle-border)] pb-2.5">
      <p className={groupHeadingClass}>{title}</p>
      <Badge variant={tone}>
        {tone === 'danger'
          ? ui('report.risk')
          : tone === 'success'
            ? ui('report.execution')
            : tone === 'info'
              ? ui('report.checklistState')
              : ui('report.note')}
      </Badge>
    </div>
    {items.length > 0 ? (
      <ul className="mt-3.5 space-y-2 text-sm leading-6 text-secondary-text">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="flex items-start gap-2.5 border-b border-[var(--theme-panel-subtle-border)] pb-2 last:border-b-0 last:pb-0">
            <span className="mt-2 inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-primary)]" />
            <span className="min-w-0 flex-1">{item}</span>
          </li>
        ))}
      </ul>
    ) : (
      <p className="mt-3 text-sm leading-6 text-muted-text">{emptyText}</p>
    )}
    {footer ? <div className="mt-3 border-t border-[var(--theme-panel-subtle-border)] pt-3">{footer}</div> : null}
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
    ? 'md:grid-cols-[minmax(0,1.1fr)_minmax(0,1.25fr)_minmax(0,0.9fr)_minmax(0,0.8fr)]'
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
                  <p className={cn(renderGroupLabelClass(), 'md:hidden')}>{ui('report.field')}</p>
                  <p className="text-sm font-medium leading-6 text-foreground break-words">{localizeReportTermLabel(field.label, isEnglishUi() ? 'en' : 'zh')}</p>
                </div>
                <div className="space-y-1">
                  <p className={cn(renderGroupLabelClass(), 'md:hidden')}>{ui('report.value')}</p>
                  <p className={cn('text-sm leading-6 break-words', isMissingDisplayText(field.value) ? 'text-muted-text' : 'text-secondary-text')}>
                    {softenMissingValue(field.value)}
                  </p>
                </div>
                {showSource ? (
                  <div className="space-y-1">
                    <p className={cn(renderGroupLabelClass(), 'md:hidden')}>{ui('report.source')}</p>
                    <p className="text-xs leading-5 text-muted-text break-words">{isMeaningfulMetaText(field.source) ? field.source : '—'}</p>
                  </div>
                ) : null}
                {showStatus ? (
                  <div className="space-y-1">
                    <p className={cn(renderGroupLabelClass(), 'md:hidden')}>{ui('report.status')}</p>
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

const CompactDecisionMetric: React.FC<{ label: string; value?: string | null }> = ({ label, value }) => (
  <div className="space-y-1">
    <p className={renderGroupLabelClass()}>{label}</p>
    <p className="text-sm leading-5 text-secondary-text">{softenMissingValue(value)}</p>
  </div>
);

const DecisionExecutionPanel: React.FC<{
  decisionPanel?: StandardReportDecisionPanel;
}> = ({ decisionPanel }) => (
  <section className={cn(solidCardClass)} data-testid="decision-execution-panel">
    <SectionHeader eyebrow={ui('report.executionRiskLayerTitle')} title={ui('report.tradeExecution')} />

    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
      <div className="theme-panel-subtle rounded-[1rem] px-4 py-4">
        <div className="flex flex-wrap items-center gap-2.5">
          <Badge variant="info">{softenControlledValue(decisionPanel?.setupType)}</Badge>
          <Badge variant="history">{ui('report.confidenceLabel')} {softenControlledValue(decisionPanel?.confidence)}</Badge>
        </div>
        <p className={cn('mt-3', renderGroupLabelClass())}>{ui('report.executionSummary')}</p>
        <p className="mt-2 text-base font-semibold leading-7 text-foreground">
          {softenControlledValue(decisionPanel?.keyAction || decisionPanel?.noPositionAdvice)}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <CompactDecisionMetric label={ui('report.keySupport')} value={softenControlledValue(decisionPanel?.support)} />
          <CompactDecisionMetric label={ui('report.keyResistance')} value={softenControlledValue(decisionPanel?.resistance)} />
          <CompactDecisionMetric label={ui('report.stopReason')} value={softenControlledValue(decisionPanel?.stopReason)} />
          <CompactDecisionMetric label={ui('report.targetReason')} value={softenControlledValue(decisionPanel?.targetReason)} />
        </div>
      </div>

      <div className="theme-panel-subtle rounded-[1rem] px-4 py-4">
        <p className={renderGroupLabelClass()}>{ui('report.structureSnapshot')}</p>
        <p className="mt-2 text-sm leading-6 text-secondary-text">
          {softenControlledValue(decisionPanel?.marketStructure)}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <CompactDecisionMetric label={ui('report.positionSizing')} value={softenControlledValue(decisionPanel?.positionSizing)} />
          <CompactDecisionMetric label={ui('report.targetZone')} value={softenControlledValue(decisionPanel?.targetZone || decisionPanel?.target)} />
        </div>
      </div>
    </div>
  </section>
);

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
            <p className="text-sm font-medium text-foreground">{localizeReportHeadingLabel(item.label, isEnglishUi() ? 'en' : 'zh')}</p>
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
          <p className="min-w-0 flex-1 text-sm leading-5 text-secondary-text">{softenControlledValue(item.text)}</p>
        </div>
      ))}
    </div>
  );
};

const DecisionBoardPanel: React.FC<{
  decisionContext?: StandardReportDecisionContext;
  checklistItems: StandardReportChecklistItem[];
  reasonLayer?: StandardReportReasonLayer;
  decisionPanel?: StandardReportDecisionPanel;
  highlights?: StandardReportHighlights;
  summaryOneLine?: string;
}> = ({
  decisionContext,
  checklistItems,
  reasonLayer,
  decisionPanel,
  highlights,
  summaryOneLine,
}) => {
  const rationaleBlockedTexts = [
    summaryOneLine,
    decisionPanel?.keyAction,
    decisionPanel?.noPositionAdvice,
    decisionPanel?.holderAdvice,
    decisionContext?.shortTermView,
    decisionContext?.compositeView,
    reasonLayer?.topRisk,
    reasonLayer?.topCatalyst,
    reasonLayer?.latestKeyUpdate,
    reasonLayer?.sentimentSummary,
    ...(highlights?.bullishFactors || []),
    ...(highlights?.bearishFactors || []),
    ...(highlights?.latestNews || []),
    ...(highlights?.positiveCatalysts || []),
    ...(highlights?.riskAlerts || []),
  ];
  const rationaleItems = collectDedupedItems({
    items: reasonLayer?.coreReasons || [],
    limit: 2,
    keyResolver: narrativeSemanticKey,
    blockedTexts: rationaleBlockedTexts,
  });
  const synthesizedRationaleItems = collectDedupedItems({
    items: [
      decisionContext?.changeReason,
      decisionContext?.adjustmentReason,
      reasonLayer?.checklistSummary,
    ],
    limit: 2,
    keyResolver: narrativeSemanticKey,
    blockedTexts: rationaleBlockedTexts,
  });
  const finalRationaleItems = rationaleItems.length > 0 ? rationaleItems : synthesizedRationaleItems;

  return (
    <div className={cn(solidCardClass)} data-testid="decision-board-panel">
      <SectionHeader eyebrow={ui('report.executionRiskLayerTitle')} title={ui('report.checklistAndScore')} />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
        <div className="grid gap-4">
          <div className={subtlePanelClass}>
            <p className={cn(groupHeadingClass, 'mb-0.5')}>{ui('report.topReasons')}</p>
            {finalRationaleItems.length > 0 ? (
              <ul className="mt-3 space-y-2 text-sm leading-5 text-secondary-text">
                {finalRationaleItems.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted-text">{ui('report.noReasons')}</p>
            )}
          </div>

          <div className={subtlePanelClass}>
            <p className={cn(groupHeadingClass, 'mb-0.5')}>{ui('report.checklistState')}</p>
            <div className="mt-2.5">
              <ChecklistPanel items={checklistItems} />
            </div>
          </div>
        </div>

        <div className="grid gap-4">
          <div className={subtlePanelClass}>
            <p className={cn(groupHeadingClass, 'mb-0.5')}>{ui('report.scoreBreakdown')}</p>
            <div className="mt-2.5">
              <ScoreBreakdownList items={decisionContext?.scoreBreakdown || []} />
            </div>
          </div>

          <div className={subtlePanelClass}>
            <p className={cn(groupHeadingClass, 'mb-0.5')}>{ui('report.scoreNotes')}</p>
            <div className="mt-2.5 grid gap-x-4 gap-y-3 sm:grid-cols-2">
              <CompactDecisionMetric label={ui('report.shortTermView')} value={decisionContext?.shortTermView ? softenControlledValue(decisionContext.shortTermView) : ui('report.noFields')} />
              <CompactDecisionMetric label={ui('report.compositeView')} value={decisionContext?.compositeView ? softenControlledValue(decisionContext.compositeView) : ui('report.noFields')} />
              <CompactDecisionMetric label={ui('report.checklistSummary')} value={reasonLayer?.checklistSummary || ui('report.noFields')} />
              <CompactDecisionMetric label={ui('report.changeReason')} value={decisionContext?.changeReason ? softenControlledValue(decisionContext.changeReason) : decisionContext?.adjustmentReason ? softenControlledValue(decisionContext.adjustmentReason) : ui('report.noFields')} />
              {isMeaningfulText(decisionContext?.adjustmentReason) ? (
                <CompactDecisionMetric label={ui('report.adjustmentReason')} value={softenControlledValue(decisionContext.adjustmentReason)} />
              ) : null}
              {decisionContext?.previousScore ? (
                <CompactDecisionMetric label={ui('report.previousScore')} value={decisionContext?.previousScore} />
              ) : null}
              {decisionContext?.scoreChange ? (
                <CompactDecisionMetric label={ui('report.scoreChange')} value={decisionContext?.scoreChange} />
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

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
    <div className="flex items-start justify-between gap-3 border-b border-[var(--theme-panel-subtle-border)] pb-2.5">
      <p className={groupHeadingClass}>{label}</p>
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
      <ul className="mt-3.5 space-y-2 text-sm leading-6 text-secondary-text">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="border-b border-[var(--theme-panel-subtle-border)] pb-2 last:border-b-0 last:pb-0">
            {localizeReportHeadingLabel(item, isEnglishUi() ? 'en' : 'zh')}
          </li>
        ))}
      </ul>
    ) : (
      <p className="mt-3 text-sm leading-6 text-muted-text">{emptyText}</p>
    )}
    {footer ? <div className="mt-3 border-t border-[var(--theme-panel-subtle-border)] pt-3">{footer}</div> : null}
  </div>
);

const NewsRiskPanel: React.FC<{
  highlights?: StandardReportHighlights;
  reasonLayer?: StandardReportReasonLayer;
}> = ({ highlights, reasonLayer }) => {
  const latestNews = highlights?.latestNews || [];
  const bullishFactors = highlights?.bullishFactors || highlights?.positiveCatalysts || [];
  const bearishFactors = highlights?.bearishFactors || highlights?.riskAlerts || [];
  const canonicalLatestUpdate = collectDedupedItems({
    items: [reasonLayer?.latestKeyUpdate, ...latestNews],
    limit: 1,
    keyResolver: narrativeSemanticKey,
  });
  const narrativeSeen = new Set<string>();

  const bullish = collectDedupedItems({
    items: [...bullishFactors, ...(highlights?.positiveCatalysts || [])],
    limit: 4,
    keyResolver: narrativeSemanticKey,
    seenKeys: narrativeSeen,
    blockedTexts: canonicalLatestUpdate,
  });
  const risks = collectDedupedItems({
    items: [reasonLayer?.topRisk, ...bearishFactors, ...(highlights?.riskAlerts || [])],
    limit: 5,
    keyResolver: narrativeSemanticKey,
    seenKeys: narrativeSeen,
    blockedTexts: canonicalLatestUpdate,
  });
  const catalystsAndWatch = collectDedupedItems({
    items: [
      ...canonicalLatestUpdate,
      reasonLayer?.topCatalyst,
      ...(highlights?.neutralFactors || []),
      isPresentValue(highlights?.earningsOutlook) ? joinLabelValue(ui('report.earningsOutlook'), softenMissingValue(highlights?.earningsOutlook)) : undefined,
    ],
    limit: 5,
    keyResolver: narrativeSemanticKey,
    seenKeys: narrativeSeen,
  });
  const narrativeSentimentItems = collectDedupedItems({
    items: [
      highlights?.socialSynthesis,
      reasonLayer?.sentimentSummary,
      highlights?.sentimentSummary,
    ],
    limit: 2,
    keyResolver: narrativeSemanticKey,
    seenKeys: narrativeSeen,
  });
  const structuredSentimentFallback = collectDedupedItems({
    items: [
      isPresentValue(highlights?.socialTone) ? joinLabelValue(ui('report.retailTone'), softenMissingValue(highlights?.socialTone)) : undefined,
      isPresentValue(highlights?.socialAttention) ? joinLabelValue(ui('report.attention'), softenMissingValue(highlights?.socialAttention)) : undefined,
      isPresentValue(highlights?.socialNarrativeFocus) ? joinLabelValue(ui('report.narrativeFocus'), softenMissingValue(highlights?.socialNarrativeFocus)) : undefined,
    ],
    limit: 1,
    keyResolver: narrativeSemanticKey,
    seenKeys: narrativeSeen,
    blockedTexts: narrativeSentimentItems,
  });
  const sentimentItems = narrativeSentimentItems.length > 0 ? narrativeSentimentItems : structuredSentimentFallback;

  return (
    <div className={cn(solidCardClass)} data-testid="risk-catalyst-panel">
      <SectionHeader eyebrow={ui('report.evidence')} title={ui('report.riskCatalystSentiment')} />

      <div className="grid gap-3 xl:grid-cols-2">
        <NarrativeBucketCard
          label={ui('report.coreBullishFactors')}
          items={bullish}
          emptyText={ui('report.noFields')}
          tone="success"
        />
        <NarrativeBucketCard
          label={ui('report.coreRisks')}
          items={risks}
          emptyText={ui('report.noFields')}
          tone="danger"
        />
        <NarrativeBucketCard
          label={ui('report.catalystsWatchConditions')}
          items={catalystsAndWatch}
          emptyText={ui('report.noFields')}
          tone="info"
        />
        <NarrativeBucketCard
          label={ui('report.marketSentiment')}
          items={sentimentItems}
          emptyText={ui('report.noFields')}
          tone="info"
        />
      </div>
    </div>
  );
};

const SentimentAppendixPanel: React.FC<{
  highlights?: StandardReportHighlights;
  reasonLayer?: StandardReportReasonLayer;
}> = ({ highlights, reasonLayer }) => {
  const sourceItems = uniqueMeaningfulItems(highlights?.socialSources || [], 6);
  const coverageContextItems = collectDedupedItems({
    items: [
      reasonLayer?.newsValueTier,
      highlights?.newsValueGrade,
    ],
    limit: 2,
    keyResolver: narrativeSemanticKey,
  });

  return (
    <div className={cn(solidCardClass)}>
      <SectionHeader eyebrow={ui('report.coverage')} title={ui('report.marketSentiment')} level={4} />
      <div className="grid gap-3 xl:grid-cols-2">
        <CoverageNoteList
          title={ui('report.socialSources')}
          items={sourceItems}
          emptyText={ui('report.noFields')}
        />
        <CoverageNoteList
          title={ui('report.sourceNotes')}
          items={coverageContextItems}
          emptyText={ui('report.noFields')}
        />
      </div>
    </div>
  );
};

const CoverageNoteList: React.FC<{ title: string; items: string[]; emptyText: string }> = ({
  title,
  items,
  emptyText,
}) => (
  <div className={subtlePanelClass}>
    <p className={cn(groupHeadingClass, 'border-b border-[var(--theme-panel-subtle-border)] pb-2.5')}>{title}</p>
    {items.length > 0 ? (
      <ul className="mt-3.5 space-y-2 text-sm leading-6 text-secondary-text">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="border-b border-[var(--theme-panel-subtle-border)] pb-2 last:border-b-0 last:pb-0">
            {localizeReportHeadingLabel(item, isEnglishUi() ? 'en' : 'zh')}
          </li>
        ))}
      </ul>
    ) : (
      <p className="mt-3 text-sm leading-6 text-muted-text">{emptyText}</p>
    )}
  </div>
);

const CoverageAuditPanel: React.FC<{
  coverageNotes?: StandardReport['coverageNotes'];
  missingFieldAudit: MissingFieldAuditSummary;
}> = ({ coverageNotes, missingFieldAudit }) => {
  const buckets = missingFieldAudit.buckets.filter((bucket) => bucket.entries.length > 0);
  const missingFieldSemanticKeys = new Set(
    buckets
      .flatMap((bucket) => bucket.entries.map((entry) => coverageFieldSemanticKey(entry.field)))
      .filter((token) => token.length > 0),
  );
  const coverageGapItems = collectDedupedItems({
    items: coverageNotes?.coverageGaps || coverageNotes?.missingFieldNotes || [],
    limit: 8,
    keyResolver: (text) => `field:${coverageFieldSemanticKey(text) || narrativeSemanticKey(text)}`,
  }).filter((item) => {
    const semantic = coverageFieldSemanticKey(item);
    if (!semantic || semantic.length < 3) {
      return true;
    }
    return !missingFieldSemanticKeys.has(semantic);
  });

  return (
    <div className={cn(solidCardClass)} data-testid="coverage-audit-panel">
      <SectionHeader eyebrow={ui('report.coverage')} title={ui('report.coverageAuditTitle')} description={ui('report.coverageAuditHint')} />

      <div className="grid gap-3 xl:grid-cols-2">
        <CoverageNoteList
          title={ui('report.dataSources')}
          items={uniqueMeaningfulItems(coverageNotes?.dataSources || [], 8)}
          emptyText={ui('report.noExtraSourceNotes')}
        />
        <CoverageNoteList
          title={ui('report.methods')}
          items={uniqueMeaningfulItems(coverageNotes?.methodNotes || [], 8)}
          emptyText={ui('report.noMethodNotes')}
        />
        <CoverageNoteList
          title={ui('report.conflicts')}
          items={uniqueMeaningfulItems(coverageNotes?.conflictNotes || [], 8)}
          emptyText={ui('report.noConflictNotes')}
        />
        <CoverageNoteList
          title={ui('report.coverageGaps')}
          items={coverageGapItems}
          emptyText={ui('report.noCoverageGaps')}
        />
      </div>

      {missingFieldAudit.totalMissingFields > 0 ? (
        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          {buckets.map((bucket) => (
            <div key={bucket.category} className={subtlePanelClass}>
              <div className="flex items-center justify-between gap-2">
                <p className={renderGroupLabelClass()}>
                  {missingCategoryLabel(bucket.category)}
                </p>
                <Badge variant="warning">{bucket.entries.length}</Badge>
              </div>
              <ul className="mt-3 space-y-2 text-sm leading-5 text-secondary-text">
                {bucket.entries.slice(0, 6).map((entry, index) => (
                  <li key={`${entry.field}-${entry.reason}-${index}`} className="border-b border-[var(--theme-panel-subtle-border)] pb-2 last:border-b-0 last:pb-0">
                    <span className="font-medium text-foreground">{localizeReportTermLabel(entry.field, isEnglishUi() ? 'en' : 'zh')}</span>
                    <span className="text-muted-text">{localeColon()}{localizeReportHeadingLabel(entry.reason, isEnglishUi() ? 'en' : 'zh')}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm leading-6 text-muted-text">{ui('report.noMissingFieldAudit')}</p>
      )}
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
    <div className={cn(solidCardClass)} data-testid="battle-plan-panel">
      <SectionHeader eyebrow={ui('report.execution')} title={ui('report.battlePlan')} />

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
                    <p className={renderGroupLabelClass()}>{localizeReportHeadingLabel(item.label, isEnglishUi() ? 'en' : 'zh')}</p>
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
                    <p className={renderGroupLabelClass()}>{localizeReportHeadingLabel(item.label, isEnglishUi() ? 'en' : 'zh')}</p>
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
          <p className={cn(renderGroupLabelClass(), 'text-[var(--accent-danger)]')}>{ui('report.reminders')}</p>
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

const MarketWarnings: React.FC<{ warnings: string[] }> = ({ warnings }) => {
  if (warnings.length === 0) {
    return null;
  }
  return (
    <div className="rounded-[1rem] border border-[hsl(var(--accent-warning-hsl)/0.46)] bg-[hsl(var(--accent-warning-hsl)/0.14)] px-4 py-3">
      <p className={cn(renderGroupLabelClass(), 'text-[var(--accent-warning)]')}>{ui('report.basisNotes')}</p>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-[hsl(var(--accent-warning-hsl)/0.9)]">
        {warnings.map((warning, index) => (
          <li key={`${warning}-${index}`}>{warning}</li>
        ))}
      </ul>
    </div>
  );
};

const DecisionSummaryHero: React.FC<{
  standardReport: StandardReport;
  report: AnalysisReport;
}> = ({ standardReport, report }) => {
  const reportLanguage = isEnglishUi() ? 'en' : 'zh';
  const summary = standardReport.summaryPanel || {};
  const visualBlocks = standardReport.visualBlocks || {};
  const score = summary.score ?? visualBlocks.score?.value;
  const companyTitle = report.meta.stockName || summary.stock || report.meta.stockCode;
  const tickerLabel = summary.ticker || report.meta.stockCode;
  const actionProfile = getReportControlledValueProfile(summary.operationAdvice || report.summary.operationAdvice, reportLanguage);
  const trendProfile = getReportControlledValueProfile(summary.trendPrediction || report.summary.trendPrediction, reportLanguage);
  const scoreSupport = score !== undefined ? getSentimentLabel(score, reportLanguage) : undefined;
  const compactMetaLine = uniqueMeaningfulItems(
    [
      summary.priceBasis,
      summary.marketSessionDate ? `${summary.marketSessionDate} ${ui('report.sessionSuffix')}` : summary.referenceSession,
      summary.snapshotTime ? `${ui('report.updatedShort')} ${summary.snapshotTime}` : undefined,
    ],
    3,
  ).join(' · ');

  return (
    <section className={cn(glassCardClass)} data-testid="hero-summary-card">
    <SectionHeader level={2} title={ui('report.topOverview')} description={compactMetaLine} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
            <h2 className="min-w-0 text-[1.9rem] font-normal tracking-[-0.04em] text-foreground md:text-[2.25rem]">
              {companyTitle}
            </h2>
            <span className="theme-inline-chip rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-muted-text">
              {tickerLabel}
            </span>
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-x-4 gap-y-2">
            <p className="text-[2.35rem] font-normal tracking-[-0.05em] text-foreground md:text-[2.8rem]">
              {softenMissingValue(summary.currentPrice)}
            </p>
            <p className={cn('pb-1 text-base font-normal md:text-lg', changeToneClass(summary.changePct))}>
              {softenMissingValue(summary.changeAmount)} / {softenMissingValue(summary.changePct)}
            </p>
          </div>

          <p className="mt-4 text-sm leading-6 text-secondary-text md:text-[15px] md:leading-7">
            {summary.oneSentence || report.summary.analysisSummary || ui('report.oneLineFallback')}
          </p>

          {isMeaningfulText(summary.reportGeneratedAt) ? (
            <p className="mt-3 text-xs text-muted-text">
              {ui('report.reportTime')} {softenMissingValue(summary.reportGeneratedAt)}
            </p>
          ) : null}
        </div>

        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
          <HeroStat
            label={ui('report.score')}
            value={score !== undefined ? `${score}` : 'NA'}
            support={scoreSupport}
            meter={score !== undefined ? Math.max(0, Math.min(100, score)) : undefined}
            meterColor={score !== undefined ? getSentimentColor(score) : undefined}
            accent="score"
          />
          <HeroStat
            label={ui('report.actionAdvice')}
            value={actionProfile.value}
            support={actionProfile.support}
          />
          <HeroStat
            label={ui('report.trend')}
            value={trendProfile.value}
            support={trendProfile.support}
          />
        </div>
      </div>
    </section>
  );
};

const ExecutionPlanLayer: React.FC<{
  decisionPanel?: StandardReportDecisionPanel;
  checklistItems: StandardReportChecklistItem[];
}> = ({
  decisionPanel,
  checklistItems,
}) => {
  const executionSeen = new Set<string>();
  const currentActionItems = collectDedupedItems({
    items: [softenControlledValue(decisionPanel?.keyAction || decisionPanel?.noPositionAdvice)],
    limit: 1,
    keyResolver: executionSemanticKey,
    seenKeys: executionSeen,
  });
  const newPositionItems = collectDedupedItems({
    items: [
      softenControlledValue(decisionPanel?.noPositionAdvice),
      isPresentValue(decisionPanel?.idealEntry) ? joinLabelValue(ui('report.idealEntry'), softenControlledValue(decisionPanel?.idealEntry)) : undefined,
      isPresentValue(decisionPanel?.backupEntry) ? joinLabelValue(ui('report.backupEntry'), softenControlledValue(decisionPanel?.backupEntry)) : undefined,
      decisionPanel?.buildStrategy ? joinLabelValue(ui('report.buildStrategy'), softenControlledValue(decisionPanel?.buildStrategy)) : undefined,
    ],
    limit: 4,
    keyResolver: executionSemanticKey,
    seenKeys: executionSeen,
  });
  const existingPositionItems = collectDedupedItems({
    items: [
      softenControlledValue(decisionPanel?.holderAdvice),
      decisionPanel?.positionSizing ? joinLabelValue(ui('report.positionSizing'), softenControlledValue(decisionPanel?.positionSizing)) : undefined,
    ],
    limit: 3,
    keyResolver: executionSemanticKey,
    seenKeys: executionSeen,
  });
  const baseConditionsAndRiskControl = collectDedupedItems({
    items: [
      ...checklistItems
        .filter((item) => isPendingChecklistStatus(item.status))
        .map((item) => localizeReportHeadingLabel(item.text, reportLanguage())),
      isPresentValue(decisionPanel?.stopLoss) ? joinLabelValue(ui('report.stopLoss'), softenControlledValue(decisionPanel?.stopLoss)) : undefined,
      isPresentValue(decisionPanel?.targetOne || decisionPanel?.target) ? joinLabelValue(ui('report.targetOne'), softenControlledValue(decisionPanel?.targetOne || decisionPanel?.target)) : undefined,
      isPresentValue(decisionPanel?.targetTwo) ? joinLabelValue(ui('report.targetTwo'), softenControlledValue(decisionPanel?.targetTwo)) : undefined,
      decisionPanel?.riskControlStrategy ? joinLabelValue(ui('report.riskControl'), softenControlledValue(decisionPanel?.riskControlStrategy)) : undefined,
    ],
    limit: 6,
    keyResolver: executionSemanticKey,
    seenKeys: executionSeen,
  });
  const compressedReminder = collectDedupedItems({
    items: (decisionPanel?.executionReminders || []).map((item) => localizeReportHeadingLabel(item, reportLanguage())),
    limit: 1,
    keyResolver: executionSemanticKey,
    seenKeys: executionSeen,
    blockedTexts: [
      ...currentActionItems,
      ...newPositionItems,
      ...existingPositionItems,
      ...baseConditionsAndRiskControl,
    ],
  });
  const conditionsAndRiskControl = [...baseConditionsAndRiskControl, ...compressedReminder].slice(0, 6);

  return (
    <section className={cn(solidCardClass)} data-testid="execution-risk-layer">
      <SectionHeader eyebrow={ui('report.executionRiskLayerTitle')} title={ui('report.executionPlanTitle')} />

      <div className="grid gap-3 xl:grid-cols-2">
        <ExecutionListCard
          title={ui('report.currentAction')}
          tone="success"
          items={currentActionItems}
          emptyText={ui('report.noFields')}
          testId="key-actions-card"
        />

        <ExecutionListCard
          title={ui('report.forNewPositions')}
          tone="info"
          items={newPositionItems}
          emptyText={ui('report.noFields')}
          testId="new-positions-card"
        />
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <ExecutionListCard
          title={ui('report.forExistingPositions')}
          tone="info"
          items={existingPositionItems}
          emptyText={ui('report.noFields')}
          testId="existing-positions-card"
        />

        <ExecutionListCard
          title={ui('report.conditionsRiskControl')}
          tone="info"
          items={conditionsAndRiskControl}
          emptyText={ui('report.noPendingConditions')}
          testId="watch-checklist-card"
        />
      </div>
    </section>
  );
};

const AppendixDisclosure: React.FC<{
  title: string;
  children: React.ReactNode;
  testId?: string;
}> = ({ title, children, testId }) => (
  <details className="report-hero-disclosure" data-testid={testId}>
    <summary>{title}</summary>
    <div className="report-hero-disclosure-body">{children}</div>
  </details>
);

export const StandardReportPanel: React.FC<StandardReportPanelProps> = ({
  report,
  chartFixtures,
  showLeadSummary = true,
}) => {
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
  const missingFieldAudit = buildMissingFieldAudit(collectMissingFieldEntriesFromStandardReport(standardReport));

  return (
    <div className="space-y-5 text-left md:space-y-6 xl:space-y-7" data-testid="standard-report-panel">
      {showLeadSummary ? <DecisionSummaryHero standardReport={standardReport} report={report} /> : null}

      <section className={cn(chartLayerCardClass)} data-testid="chart-context-layer">
        <ReportPriceChart
          stockCode={report.meta.stockCode}
          stockName={report.meta.stockName}
          summary={standardReport.summaryPanel}
          market={standardReport.market}
          decisionPanel={standardReport.decisionPanel}
          integrated
          fixtures={chartFixtures}
        />
      </section>

      <ExecutionPlanLayer
        decisionPanel={standardReport.decisionPanel}
        checklistItems={standardReport.checklistItems || []}
      />

      <NewsRiskPanel
        highlights={standardReport.highlights}
        reasonLayer={standardReport.reasonLayer}
      />

      <section className={cn(solidCardClass)} data-testid="deep-appendix-layer">
        <details className="report-hero-disclosure" data-testid="deep-appendix-disclosure">
          <summary>{ui('report.deepAppendix')}</summary>
          <div className="report-hero-disclosure-body space-y-4">
            <p className="text-xs leading-5 text-muted-text">{ui('report.deepAppendixHint')}</p>

            <AppendixDisclosure title={ui('report.appendixExecution')} testId="appendix-execution-disclosure">
              <div className="space-y-4">
                <DecisionExecutionPanel decisionPanel={standardReport.decisionPanel} />
                <BattlePlanPanel battlePlan={standardReport.battlePlanCompact} />
              </div>
            </AppendixDisclosure>

            <AppendixDisclosure title={ui('report.appendixDecision')} testId="appendix-decision-disclosure">
              <DecisionBoardPanel
                decisionContext={standardReport.decisionContext}
                checklistItems={standardReport.checklistItems || []}
                reasonLayer={standardReport.reasonLayer}
                decisionPanel={standardReport.decisionPanel}
                highlights={standardReport.highlights}
                summaryOneLine={standardReport.summaryPanel?.oneSentence || report.summary.analysisSummary}
              />
            </AppendixDisclosure>

            <AppendixDisclosure title={ui('report.appendixSentiment')} testId="appendix-sentiment-disclosure">
              <SentimentAppendixPanel
                highlights={standardReport.highlights}
                reasonLayer={standardReport.reasonLayer}
              />
            </AppendixDisclosure>

            <AppendixDisclosure title={ui('report.appendixTables')} testId="appendix-tables-disclosure">
              <div className="space-y-4">
                <div className={rowGridClass}>
                  <DenseTable
                    section={marketSection}
                    footer={<MarketWarnings warnings={warnings} />}
                  />
                  <DenseTable section={technicalSection} />
                </div>

                <div className={rowGridClass}>
                  <DenseTable section={fundamentalSection} />
                  <DenseTable section={earningsSection} />
                </div>
              </div>
            </AppendixDisclosure>

            <AppendixDisclosure title={ui('report.appendixCoverage')} testId="appendix-coverage-disclosure">
              <CoverageAuditPanel
                coverageNotes={standardReport.coverageNotes}
                missingFieldAudit={missingFieldAudit}
              />
            </AppendixDisclosure>
          </div>
        </details>
      </section>
    </div>
  );
};
