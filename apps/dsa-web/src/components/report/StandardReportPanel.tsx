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
import { Badge } from '../common';
import { cn } from '../../utils/cn';
import { ReportPriceChart, type ReportPriceChartFixtures } from './ReportPriceChart';

interface StandardReportPanelProps {
  report: AnalysisReport;
  chartFixtures?: ReportPriceChartFixtures;
}

const solidCardClass =
  'theme-panel-solid rounded-[1.45rem] px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6';
const glassCardClass =
  'theme-panel-glass rounded-[1.55rem] px-4 py-4 md:px-5 md:py-5 xl:px-6 xl:py-6';
const subtlePanelClass = 'theme-panel-subtle rounded-[1rem] px-3.5 py-3';
const rowGridClass = 'grid gap-4 lg:grid-cols-2';

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

const HeroStat: React.FC<{ label: string; value?: string | number; accent?: 'score' | 'default' }> = ({
  label,
  value,
  accent = 'default',
}) => (
  <div className="theme-panel-subtle rounded-[1rem] border border-[var(--theme-panel-subtle-border)] px-4 py-3.5">
    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{label}</p>
    <p
      className={cn(
        'mt-2 font-semibold tracking-tight',
        accent === 'score' ? 'text-[2.2rem] leading-none text-[var(--accent-primary)]' : 'text-[1.05rem] leading-7 text-foreground',
      )}
    >
      {softenMissingValue(typeof value === 'number' ? String(value) : value)}
    </p>
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
    <div className="flex items-center justify-between gap-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{title}</p>
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
      <ul className="mt-3 space-y-2 text-sm leading-6 text-secondary-text">
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

const CompactDecisionMetric: React.FC<{ label: string; value?: string | null }> = ({ label, value }) => (
  <div className="space-y-1">
    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{label}</p>
    <p className="text-sm leading-5 text-secondary-text">{softenMissingValue(value)}</p>
  </div>
);

const DecisionExecutionPanel: React.FC<{
  decisionPanel?: StandardReportDecisionPanel;
}> = ({ decisionPanel }) => (
  <section className={cn(solidCardClass)} data-testid="decision-execution-panel">
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

const DecisionBoardPanel: React.FC<{
  decisionContext?: StandardReportDecisionContext;
  checklistItems: StandardReportChecklistItem[];
  reasonLayer?: StandardReportReasonLayer;
}> = ({ decisionContext, checklistItems, reasonLayer }) => (
  <div className={cn(solidCardClass)} data-testid="decision-board-panel">
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
        </div>
      </div>
    </div>
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

  return (
    <div className={cn(solidCardClass)} data-testid="risk-catalyst-panel">
      <SectionHeader title={ui('report.riskCatalystSentiment')} />

      <div className="grid gap-3 xl:grid-cols-2">
        <NarrativeBucketCard
          label={ui('report.latestUpdate')}
          items={latestUpdates}
          emptyText={ui('report.oneLineFallback')}
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
          footer={isMeaningfulText(reasonLayer?.sentimentSummary || highlights?.sentimentSummary) ? (
            <p className="text-sm leading-5 text-secondary-text">
              {softenMissingValue(reasonLayer?.sentimentSummary || highlights?.sentimentSummary)}
            </p>
          ) : null}
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
    <div className={cn(solidCardClass)} data-testid="battle-plan-panel">
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

const DecisionSummaryHero: React.FC<{
  standardReport: StandardReport;
  report: AnalysisReport;
}> = ({ standardReport, report }) => {
  const summary = standardReport.summaryPanel || {};
  const visualBlocks = standardReport.visualBlocks || {};
  const score = summary.score ?? visualBlocks.score?.value;
  const companyTitle = report.meta.stockName || summary.stock || report.meta.stockCode;
  const tickerLabel = summary.ticker || report.meta.stockCode;
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
      <SectionHeader title={ui('report.topOverview')} description={compactMetaLine} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
            <h2 className="min-w-0 text-[1.9rem] font-semibold tracking-tight text-foreground md:text-[2.25rem]">
              {companyTitle}
            </h2>
            <span className="theme-inline-chip rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-muted-text">
              {tickerLabel}
            </span>
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-x-4 gap-y-2">
            <p className="text-[2.35rem] font-semibold tracking-tight text-foreground md:text-[2.8rem]">
              {softenMissingValue(summary.currentPrice)}
            </p>
            <p className={cn('pb-1 text-base font-semibold md:text-lg', changeToneClass(summary.changePct))}>
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
          <HeroStat label={ui('report.score')} value={score !== undefined ? `${score}` : 'NA'} accent="score" />
          <HeroStat label={ui('report.actionAdvice')} value={summary.operationAdvice || report.summary.operationAdvice} />
          <HeroStat label={ui('report.trend')} value={summary.trendPrediction || report.summary.trendPrediction} />
        </div>
      </div>
    </section>
  );
};

const ExecutionRiskLayer: React.FC<{
  decisionPanel?: StandardReportDecisionPanel;
  reasonLayer?: StandardReportReasonLayer;
  highlights?: StandardReportHighlights;
  checklistItems: StandardReportChecklistItem[];
  marketWarnings: string[];
  battlePlan?: StandardReportBattlePlanCompact;
}> = ({
  decisionPanel,
  reasonLayer,
  highlights,
  checklistItems,
  marketWarnings,
  battlePlan,
}) => {
  const actionItems = uniqueMeaningfulItems([
    decisionPanel?.keyAction,
    isPresentValue(decisionPanel?.idealEntry) ? `${ui('report.idealEntry')}：${softenMissingValue(decisionPanel?.idealEntry)}` : undefined,
    isPresentValue(decisionPanel?.backupEntry) ? `${ui('report.backupEntry')}：${softenMissingValue(decisionPanel?.backupEntry)}` : undefined,
    isPresentValue(decisionPanel?.stopLoss) ? `${ui('report.stopLoss')}：${softenMissingValue(decisionPanel?.stopLoss)}` : undefined,
    isPresentValue(decisionPanel?.targetOne || decisionPanel?.target) ? `${ui('report.targetOne')}：${softenMissingValue(decisionPanel?.targetOne || decisionPanel?.target)}` : undefined,
    isPresentValue(decisionPanel?.targetTwo) ? `${ui('report.targetTwo')}：${softenMissingValue(decisionPanel?.targetTwo)}` : undefined,
    decisionPanel?.positionSizing ? `${ui('report.positionSizing')}：${softenMissingValue(decisionPanel?.positionSizing)}` : undefined,
  ], 7);

  const riskItems = uniqueMeaningfulItems([
    reasonLayer?.topRisk,
    ...(highlights?.riskAlerts || []),
    ...(highlights?.bearishFactors || []),
    ...(battlePlan?.warnings || []),
    ...marketWarnings,
  ], 7);

  const watchItems = uniqueMeaningfulItems([
    ...checklistItems.map((item) => `${checklistLabel(item.status)}：${item.text}`),
    ...(decisionPanel?.executionReminders || []),
    isPresentValue(decisionPanel?.support) ? `${ui('report.keySupport')}：${softenMissingValue(decisionPanel?.support)}` : undefined,
    isPresentValue(decisionPanel?.resistance) ? `${ui('report.keyResistance')}：${softenMissingValue(decisionPanel?.resistance)}` : undefined,
    reasonLayer?.latestKeyUpdate ? `${ui('report.latestUpdate')}：${reasonLayer.latestKeyUpdate}` : undefined,
  ], 8);

  return (
    <section className={cn(solidCardClass)} data-testid="execution-risk-layer">
      <SectionHeader title={ui('report.executionRiskLayerTitle')} description={ui('report.executionRiskLayerHint')} />

      <div className="grid gap-3 xl:grid-cols-3">
        <ExecutionListCard
          title={ui('report.keyAction')}
          tone="success"
          items={actionItems}
          emptyText={ui('report.noFields')}
          testId="key-actions-card"
        />

        <ExecutionListCard
          title={ui('report.keyRisk')}
          tone="danger"
          items={riskItems}
          emptyText={ui('report.noFields')}
          testId="key-risks-card"
          footer={isMeaningfulText(decisionPanel?.riskControlStrategy) ? (
            <p className="text-xs leading-5 text-secondary-text">
              {ui('report.riskControl')}: {softenMissingValue(decisionPanel?.riskControlStrategy)}
            </p>
          ) : null}
        />

        <ExecutionListCard
          title={ui('report.watchChecklist')}
          tone="info"
          items={watchItems}
          emptyText={ui('report.noChecklist')}
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
      <DecisionSummaryHero standardReport={standardReport} report={report} />

      <section className={cn(solidCardClass)} data-testid="chart-context-layer">
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

      <ExecutionRiskLayer
        decisionPanel={standardReport.decisionPanel}
        reasonLayer={standardReport.reasonLayer}
        highlights={standardReport.highlights}
        checklistItems={standardReport.checklistItems || []}
        marketWarnings={warnings}
        battlePlan={standardReport.battlePlanCompact}
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
              />
            </AppendixDisclosure>

            <AppendixDisclosure title={ui('report.appendixSentiment')} testId="appendix-sentiment-disclosure">
              <NewsRiskPanel highlights={standardReport.highlights} reasonLayer={standardReport.reasonLayer} />
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
          </div>
        </details>
      </section>
    </div>
  );
};
