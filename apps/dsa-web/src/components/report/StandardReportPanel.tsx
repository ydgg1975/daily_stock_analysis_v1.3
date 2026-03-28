import React from 'react';
import type {
  AnalysisReport,
  StandardReport,
  StandardReportBattlePlanCompact,
  StandardReportBattlePlanItem,
  StandardReportChecklistItem,
  StandardReportDecisionContext,
  StandardReportField,
  StandardReportHighlights,
  StandardReportScoreBreakdownItem,
  StandardReportTableSection,
} from '../../types/analysis';
import { Badge } from '../common';
import { cn } from '../../utils/cn';

interface StandardReportPanelProps {
  report: AnalysisReport;
}

const solidCardClass =
  'rounded-[1.45rem] border border-white/8 bg-[#050505] px-4 py-4 shadow-[0_18px_42px_rgba(0,0,0,0.22)] md:px-5 md:py-5';
const glassCardClass =
  'rounded-[1.55rem] border border-white/10 bg-white/[0.045] px-4 py-4 shadow-[0_20px_48px_rgba(0,0,0,0.26)] backdrop-blur-xl md:px-5 md:py-5';
const subtlePanelClass = 'rounded-[1rem] border border-white/7 bg-white/[0.03] px-3.5 py-3';
const rowGridClass =
  'grid gap-4 lg:grid-cols-2';
const denseTableColumns =
  'md:grid-cols-[minmax(0,1.1fr)_minmax(0,1.25fr)_minmax(0,0.9fr)_minmax(0,0.8fr)]';

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

const lowerText = (value?: string | null): string => String(value || '').trim().toLowerCase();

const buildSection = (
  section?: StandardReportTableSection,
  fallbackTitle?: string,
  fallbackFields?: StandardReportField[],
): StandardReportTableSection => ({
  title: section?.title || fallbackTitle || '数据表',
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
    return '通过';
  }
  if (status === 'warn') {
    return '警惕';
  }
  if (status === 'fail') {
    return '不满足';
  }
  if (status === 'na') {
    return 'NA';
  }
  return '提示';
};

const scoreToneClass = (score?: number): string => {
  if (score === undefined) {
    return 'text-foreground';
  }
  if (score >= 70) {
    return 'text-emerald-300';
  }
  if (score >= 45) {
    return 'text-amber-200';
  }
  return 'text-rose-300';
};

const changeToneClass = (changePct?: string): string => {
  const numeric = parseNumericValue(changePct);
  if (numeric === undefined) {
    return 'text-secondary-text';
  }
  if (numeric > 0) {
    return 'text-emerald-300';
  }
  if (numeric < 0) {
    return 'text-rose-300';
  }
  return 'text-secondary-text';
};

const progressToneClass = (score?: number): string => {
  if (score === undefined) {
    return 'bg-white/20';
  }
  if (score >= 70) {
    return 'bg-emerald-400';
  }
  if (score >= 45) {
    return 'bg-amber-300';
  }
  return 'bg-rose-400';
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
      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">Report Block</p>
      <h3 className="mt-1 text-lg font-semibold tracking-tight text-foreground">{title}</h3>
    </div>
    {isMeaningfulText(description) ? (
      <p className="max-w-xs text-right text-xs leading-5 text-muted-text">{description}</p>
    ) : null}
  </div>
);

const MetaChip: React.FC<{ label: string; value?: string }> = ({ label, value }) => (
  <div className="inline-flex items-center gap-2 rounded-full border border-white/8 bg-black/20 px-3 py-1.5">
    <span className="text-[10px] uppercase tracking-[0.14em] text-muted-text">{label}</span>
    <span className="text-xs font-medium text-secondary-text">{value || 'NA（接口未返回）'}</span>
  </div>
);

const HeroStat: React.FC<{ label: string; value?: string | number; accent?: 'score' | 'advice' | 'trend' }> = ({
  label,
  value,
  accent = 'advice',
}) => {
  const accentClass =
    accent === 'score'
      ? 'text-cyan'
      : accent === 'trend'
        ? 'text-amber-200'
        : 'text-foreground';
  return (
    <div className="rounded-[1rem] border border-white/8 bg-black/25 px-3.5 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{label}</p>
      <p className={cn('mt-1.5 text-base font-semibold tracking-tight', accentClass)}>{value ?? 'NA'}</p>
    </div>
  );
};

const DenseTable: React.FC<{
  section: StandardReportTableSection;
  description?: string;
  footer?: React.ReactNode;
}> = ({ section, description, footer }) => {
  const fields = section.fields || [];
  return (
    <div className={solidCardClass}>
      <SectionHeader title={section.title} description={description || section.note} />

      {fields.length > 0 ? (
        <div className="overflow-hidden rounded-[1rem] border border-white/7 bg-black/20">
          <div
            className={cn(
              'hidden items-center gap-3 border-b border-white/7 px-3 py-2.5 text-[11px] uppercase tracking-[0.16em] text-muted-text md:grid',
              denseTableColumns,
            )}
          >
            <span>字段</span>
            <span>数值</span>
            <span>来源</span>
            <span>口径 / 状态</span>
          </div>

          <div className="divide-y divide-white/6">
            {fields.map((field, index) => (
              <div
                key={`${field.label}-${index}`}
                className={cn(
                  'grid gap-3 px-3 py-3.5',
                  denseTableColumns,
                )}
              >
                <div className="space-y-1">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-muted-text md:hidden">字段</p>
                  <p className="text-sm font-medium leading-6 text-foreground break-words">{field.label}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-muted-text md:hidden">数值</p>
                  <p className="text-sm leading-6 text-secondary-text break-words">{field.value}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-muted-text md:hidden">来源</p>
                  <p className="text-xs leading-5 text-muted-text break-words">{field.source || 'NA（接口未返回）'}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-muted-text md:hidden">口径 / 状态</p>
                  <p className="text-xs leading-5 text-muted-text break-words">{field.status || 'NA（接口未返回）'}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-[1rem] border border-dashed border-white/8 bg-black/20 px-4 py-6 text-sm text-muted-text">
          暂无可展示字段
        </div>
      )}

      {footer ? <div className="mt-3">{footer}</div> : null}
    </div>
  );
};

const SummaryHero: React.FC<{
  standardReport: StandardReport;
  report: AnalysisReport;
}> = ({ standardReport, report }) => {
  const summary = standardReport.summaryPanel || {};
  const visualBlocks = standardReport.visualBlocks || {};
  const score = summary.score ?? visualBlocks.score?.value;
  const trendStrength = visualBlocks.trendStrength;
  const scorePercent = clampPercent(visualBlocks.score?.max ? ((score || 0) / visualBlocks.score.max) * 100 : score);
  const trendPercent = clampPercent(
    trendStrength?.max ? ((trendStrength.value || 0) / trendStrength.max) * 100 : trendStrength?.value,
  );

  return (
    <section className={cn(glassCardClass, 'animate-in slide-in-from-bottom-2 duration-300')} data-testid="hero-summary-card">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.85fr)]">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">Hero Summary</p>
          <div className="mt-2.5 flex flex-wrap items-end gap-x-3 gap-y-2">
            <h2 className="min-w-0 text-[1.9rem] font-semibold tracking-tight text-foreground md:text-[2.3rem]">
              {summary.stock || `${report.meta.stockName} (${report.meta.stockCode})`}
            </h2>
            <span className="rounded-full border border-white/8 bg-black/25 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-muted-text">
              {summary.ticker || report.meta.stockCode}
            </span>
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-x-4 gap-y-2">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">当前价 / 收盘价</p>
              <p className="mt-1 text-[2.35rem] font-semibold tracking-tight text-foreground md:text-[2.7rem]">
                {summary.currentPrice || 'NA（接口未返回）'}
              </p>
            </div>
            <div className="pb-0.5">
              <p className={cn('text-base font-semibold md:text-lg', changeToneClass(summary.changePct))}>
                {summary.changeAmount || 'NA（接口未返回）'} / {summary.changePct || 'NA（接口未返回）'}
              </p>
              <p className="mt-1 text-xs text-muted-text md:text-sm">同一 session 的收盘口径行情</p>
            </div>
          </div>

          <p className="mt-4 text-[15px] leading-7 text-secondary-text">
            {summary.oneSentence || report.summary.analysisSummary || '暂无一句话结论'}
          </p>

          <div className="mt-4 flex flex-wrap gap-2.5">
            <MetaChip label="交易日" value={summary.marketSessionDate} />
            <MetaChip label="市场时间" value={summary.marketTime} />
            <MetaChip label="会话类型" value={summary.sessionLabel} />
          </div>
        </div>

        <div className="grid gap-2.5">
          <div className="grid gap-2.5 sm:grid-cols-3 xl:grid-cols-3">
            <HeroStat label="综合评分" value={score !== undefined ? `${score}` : 'NA'} accent="score" />
            <HeroStat label="操作建议" value={summary.operationAdvice || report.summary.operationAdvice} accent="advice" />
            <HeroStat label="趋势判断" value={summary.trendPrediction || report.summary.trendPrediction} accent="trend" />
          </div>

          <div className={cn(subtlePanelClass, 'grid gap-3 md:grid-cols-2')}>
            <div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-text">评分强度</span>
                <span className={cn('text-sm font-semibold', scoreToneClass(score))}>{score ?? 'NA'}/100</span>
              </div>
              <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-white/8">
                <div className={cn('h-full rounded-full transition-all duration-300', progressToneClass(score))} style={{ width: `${scorePercent}%` }} />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-text">趋势强度</span>
                <span className="text-sm font-semibold text-foreground">
                  {trendStrength?.value ?? 'NA'}
                  {trendStrength?.max ? `/${trendStrength.max}` : ''}
                </span>
              </div>
              <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-white/8">
                <div className="h-full rounded-full bg-amber-300 transition-all duration-300" style={{ width: `${trendPercent}%` }} />
              </div>
            </div>
            {isMeaningfulText(trendStrength?.label) ? (
              <p className="md:col-span-2 text-sm text-secondary-text">{trendStrength?.label}</p>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
};

const NewsRiskPanel: React.FC<{
  highlights?: StandardReportHighlights;
}> = ({ highlights }) => {
  const latestNews = highlights?.latestNews || [];
  const positiveCatalysts = highlights?.positiveCatalysts || [];
  const riskAlerts = highlights?.riskAlerts || [];

  return (
    <div className={cn(solidCardClass, 'animate-in slide-in-from-bottom-2 duration-300')}>
      <SectionHeader title="新闻 / 情绪 / 风险" description="最近事件、情绪摘要与风险语义分区展示，避免旧财报解读伪装成最新动态。" />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div className="space-y-3">
          <div className={subtlePanelClass}>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">最新动态</p>
            {latestNews.length > 0 ? (
              <ul className="mt-3 space-y-2 text-sm leading-6 text-secondary-text">
                {latestNews.slice(0, 4).map((item, index) => (
                  <li key={`${item}-${index}`} className="border-b border-white/6 pb-2 last:border-b-0 last:pb-0">
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm leading-6 text-muted-text">未发现高价值新增动态</p>
            )}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className={subtlePanelClass}>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">情绪摘要</p>
              <p className="mt-3 text-sm leading-6 text-secondary-text">
                {highlights?.sentimentSummary || 'NA（接口未返回）'}
              </p>
            </div>
            <div className={subtlePanelClass}>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">业绩预期</p>
              <p className="mt-3 text-sm leading-6 text-secondary-text">
                {highlights?.earningsOutlook || 'NA（接口未返回）'}
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-3">
          <div className={subtlePanelClass}>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">利好摘要</p>
            {positiveCatalysts.length > 0 ? (
              <ul className="mt-3 space-y-2 text-sm leading-6 text-secondary-text">
                {positiveCatalysts.slice(0, 4).map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted-text">暂无新增利好摘要</p>
            )}
          </div>

          <div className={subtlePanelClass}>
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">风险摘要</p>
              {isMeaningfulText(highlights?.newsValueGrade) ? (
                <span className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{highlights?.newsValueGrade}</span>
              ) : null}
            </div>
            {riskAlerts.length > 0 ? (
              <ul className="mt-3 space-y-2 text-sm leading-6 text-secondary-text">
                {riskAlerts.slice(0, 4).map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted-text">暂无新增风险摘要</p>
            )}
          </div>
        </div>
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
      <SectionHeader title="作战计划" description="横向大卡片展示关键价位、仓位和执行规则，避免竖向窄条阅读。" />

      {topGridItems.length > 0 || lowerNotes.length > 0 ? (
        <div className="space-y-4">
          {topGridItems.length > 0 ? (
            <div
              data-testid="battle-plan-grid"
              className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-4"
            >
              {topGridItems.map((item, index) => (
                <div key={`${item.label}-${index}`} className="rounded-[1rem] border border-white/7 bg-black/20 px-3.5 py-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{item.label}</p>
                    <Badge variant={badgeTone(item.tone)} className="min-w-[3.75rem]">
                      {item.tone === 'buy'
                        ? '买点'
                        : item.tone === 'risk'
                          ? '风控'
                          : item.tone === 'target'
                            ? '目标'
                            : '计划'}
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
                <div key={`${item.label}-${index}`} className="rounded-[1rem] border border-white/7 bg-black/20 px-4 py-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{item.label}</p>
                    <Badge variant={badgeTone(item.tone)} className="min-w-[3.75rem]">
                      {item.tone === 'position'
                        ? '仓位'
                        : item.tone === 'risk'
                          ? '风控'
                          : '策略'}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-secondary-text break-words">{item.value}</p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="rounded-[1rem] border border-dashed border-white/8 bg-black/20 px-4 py-6 text-sm text-muted-text">
          暂无作战计划字段
        </div>
      )}

      {battlePlan?.warnings?.length ? (
        <div
          className="mt-4 rounded-[1rem] border border-rose-400/14 bg-rose-400/[0.06] px-4 py-3"
        >
          <p className="text-[11px] uppercase tracking-[0.16em] text-rose-200">执行提醒</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-rose-100">
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
    return <p className="text-sm text-muted-text">暂无评分拆解</p>;
  }

  return (
    <div className="space-y-3">
      {items.map((item, index) => (
        <div key={`${item.label}-${index}`} className="rounded-[0.95rem] border border-white/7 bg-black/20 px-3.5 py-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium text-foreground">{item.label}</p>
            <Badge variant={badgeTone(item.tone)} className="min-w-[3.5rem]">
              {item.score ?? 'NA'}
            </Badge>
          </div>
          {isMeaningfulText(item.note) ? (
            <p className="mt-2 text-sm leading-6 text-secondary-text">{item.note}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
};

const ChecklistPanel: React.FC<{ items: StandardReportChecklistItem[] }> = ({ items }) => {
  if (items.length === 0) {
    return <p className="text-sm text-muted-text">暂无 checklist</p>;
  }

  return (
    <div className="space-y-2.5">
      {items.map((item, index) => (
        <div key={`${item.text}-${index}`} className="flex items-start gap-3 rounded-[0.95rem] border border-white/7 bg-black/20 px-3.5 py-3">
          <Badge variant={checklistBadgeTone(item.status)} className="min-w-[5.25rem]">
            <span className="inline-flex items-center gap-1.5">
              <span className="text-[11px]">{item.icon}</span>
              <span>{checklistLabel(item.status)}</span>
            </span>
          </Badge>
          <p className="min-w-0 flex-1 text-sm leading-6 text-secondary-text">{item.text}</p>
        </div>
      ))}
    </div>
  );
};

const DecisionBoardPanel: React.FC<{
  decisionContext?: StandardReportDecisionContext;
  checklistItems: StandardReportChecklistItem[];
  highlights?: StandardReportHighlights;
}> = ({ decisionContext, checklistItems, highlights }) => (
  <div className={cn(solidCardClass, 'animate-in slide-in-from-bottom-2 duration-300')} data-testid="decision-board-panel">
    <SectionHeader title="Checklist / 评分拆解 / 风险摘要" description="把评分、执行状态和风险收在同一块，避免右侧碎卡和重复摘要。" />

    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.85fr)]">
      <div className="grid gap-4">
        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">Checklist 状态</p>
          <div className="mt-3">
            <ChecklistPanel items={checklistItems} />
          </div>
        </div>
      </div>

      <div className="grid gap-4">
        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">评分拆解</p>
          <div className="mt-3">
            <ScoreBreakdownList items={decisionContext?.scoreBreakdown || []} />
          </div>
        </div>

        <div className={subtlePanelClass}>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">评分变化说明</p>
          <div className="mt-3 space-y-3 text-sm leading-6 text-secondary-text">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">短线趋势</p>
              <p className="mt-1">{decisionContext?.shortTermView || 'NA（接口未返回）'}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">综合建议</p>
              <p className="mt-1">{decisionContext?.compositeView || 'NA（接口未返回）'}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">变动原因</p>
              <p className="mt-1">{decisionContext?.changeReason || decisionContext?.adjustmentReason || 'NA（字段待接入）'}</p>
            </div>
            {isMeaningfulText(decisionContext?.adjustmentReason) ? (
              <div>
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">调整说明</p>
                <p className="mt-1">{decisionContext?.adjustmentReason}</p>
              </div>
            ) : null}
            {(decisionContext?.previousScore || decisionContext?.scoreChange) ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">前次评分</p>
                  <p className="mt-1">{decisionContext?.previousScore || 'NA（字段待接入）'}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">评分变化</p>
                  <p className="mt-1">{decisionContext?.scoreChange || 'NA（字段待接入）'}</p>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-1">
          <div className={subtlePanelClass}>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">风险摘要</p>
            {highlights?.riskAlerts?.length ? (
              <ul className="mt-3 space-y-2 text-sm leading-6 text-secondary-text">
                {highlights.riskAlerts.slice(0, 4).map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted-text">暂无额外风险摘要</p>
            )}
          </div>
          <div className={subtlePanelClass}>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">利好摘要</p>
            {highlights?.positiveCatalysts?.length ? (
              <ul className="mt-3 space-y-2 text-sm leading-6 text-secondary-text">
                {highlights.positiveCatalysts.slice(0, 4).map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-muted-text">暂无额外利好摘要</p>
            )}
          </div>
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
    <div className="rounded-[1rem] border border-amber-300/16 bg-amber-300/[0.06] px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-amber-100">口径提示</p>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-50/90">
        {warnings.map((warning, index) => (
          <li key={`${warning}-${index}`}>{warning}</li>
        ))}
      </ul>
    </div>
  );
};

export const StandardReportPanel: React.FC<StandardReportPanelProps> = ({ report }) => {
  const standardReport = report.details?.standardReport;

  if (!standardReport) {
    return null;
  }

  const marketSection = buildSection(standardReport.tableSections?.market, '行情表', standardReport.market?.regularFields);
  const technicalSection = buildSection(standardReport.tableSections?.technical, '技术面表', standardReport.technicalFields);
  const fundamentalSection = buildSection(standardReport.tableSections?.fundamental, '基本面表', standardReport.fundamentalFields);
  const earningsSection = buildSection(standardReport.tableSections?.earnings, '财报表', standardReport.earningsFields);
  const warnings = standardReport.market?.consistencyWarnings || [];

  return (
    <div className="space-y-4 text-left" data-testid="standard-report-panel">
      <SummaryHero standardReport={standardReport} report={report} />

      <div className={rowGridClass}>
        <DenseTable
          section={marketSection}
          description="统一展示已收盘或实时会话的核心行情字段，口径与来源在同一张表内锁定。"
          footer={<MarketWarnings warnings={warnings} />}
        />
        <DenseTable
          section={technicalSection}
          description="标准技术指标优先走 API，策略型衍生指标继续由本地逻辑计算。"
        />
      </div>

      <div className={rowGridClass}>
        <DenseTable
          section={fundamentalSection}
          description="估值、现金流和资本结构集中展示，可疑 TTM 字段继续降级为明确的缺失原因。"
        />
        <DenseTable
          section={earningsSection}
          description="财报表只展示明确季度或同比口径，避免和 TTM / FY 混在一起。"
        />
      </div>

      <div className={rowGridClass}>
        <NewsRiskPanel highlights={standardReport.highlights} />
        <BattlePlanPanel battlePlan={standardReport.battlePlanCompact} />
      </div>

      <DecisionBoardPanel
        decisionContext={standardReport.decisionContext}
        checklistItems={standardReport.checklistItems || []}
        highlights={standardReport.highlights}
      />
    </div>
  );
};
