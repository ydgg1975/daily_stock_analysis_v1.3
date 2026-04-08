/**
 * SpaceX live refactor: keeps the progressive task-driven draft generation logic
 * unchanged while presenting it as a cinematic mission log with a restrained
 * rail, spectral telemetry, and section scaffolds that stay readable in motion.
 */
import type React from 'react';
import { Button } from '../common';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { RuntimeExecutionSummary, TaskInfo } from '../../types/analysis';
import { buildTaskExecutionSummary } from '../../utils/runtimeExecution';
import { cn } from '../../utils/cn';

type GenerationPhase =
  | 'initializing'
  | 'fetching_market_data'
  | 'analyzing_signals'
  | 'assembling_report'
  | 'finalizing'
  | 'completed'
  | 'failed';

type SectionStatus = 'waiting' | 'generating' | 'completed' | 'failed';
type RailState = 'waiting' | 'active' | 'complete' | 'failed';

type DraftSection = {
  key: string;
  title: string;
  status: SectionStatus;
  entries: string[];
  footnote?: string;
};

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

type ProgressiveReportGenerationProps = {
  task: TaskInfo;
  onRetry?: () => void;
  openingFinalReport?: boolean;
};

const PHASE_THRESHOLDS: Array<{ phase: GenerationPhase; progress: number }> = [
  { phase: 'finalizing', progress: 88 },
  { phase: 'assembling_report', progress: 72 },
  { phase: 'analyzing_signals', progress: 46 },
  { phase: 'fetching_market_data', progress: 18 },
];

function getProgressPhase(task: TaskInfo): GenerationPhase {
  if (task.status === 'completed') {
    return 'completed';
  }
  if (task.status === 'failed') {
    return 'failed';
  }

  const message = String(task.message || '').trim().toLowerCase();
  if (message.includes('归档') || message.includes('交付') || message.includes('final')) {
    return 'finalizing';
  }
  if (message.includes('组装') || message.includes('结论') || message.includes('report')) {
    return 'assembling_report';
  }
  if (message.includes('信号') || message.includes('证据') || message.includes('analysis')) {
    return 'analyzing_signals';
  }
  if (message.includes('行情') || message.includes('数据') || message.includes('context')) {
    return 'fetching_market_data';
  }

  const matched = PHASE_THRESHOLDS.find((item) => task.progress >= item.progress);
  return matched?.phase ?? 'initializing';
}

function getReachedMilestone(task: TaskInfo): number {
  if (task.status === 'completed') {
    return 5;
  }
  if (task.status === 'failed') {
    if (task.progress >= 88) return 4;
    if (task.progress >= 72) return 3;
    if (task.progress >= 46) return 2;
    if (task.progress >= 18) return 1;
    return 0;
  }

  const phase = getProgressPhase(task);
  switch (phase) {
    case 'finalizing':
      return 4;
    case 'assembling_report':
      return 3;
    case 'analyzing_signals':
      return 2;
    case 'fetching_market_data':
      return 1;
    default:
      return 0;
  }
}

function phaseLabel(t: TranslateFn, phase: GenerationPhase, openingFinalReport: boolean): string {
  if (phase === 'completed' && openingFinalReport) {
    return t('report.generation.phase.openingReport');
  }
  return t(`report.generation.phase.${phase}`);
}

function sectionStatusLabel(t: TranslateFn, status: SectionStatus): string {
  return t(`report.generation.sectionStatus.${status}`);
}

function railStateLabel(t: TranslateFn, status: RailState): string {
  return t(`report.generation.railState.${status}`);
}

function sourceLine(t: TranslateFn, label: string, source?: string | null, status?: string): string {
  if (!source) {
    return t('report.generation.source.preparing', { label });
  }

  const normalizedStatus = String(status || '').trim().toLowerCase();
  if (normalizedStatus === 'ok' || normalizedStatus === 'success') {
    return t('report.generation.source.ready', { label, source });
  }
  if (normalizedStatus === 'not_configured') {
    return t('report.generation.source.notConfigured', { label });
  }
  return t('report.generation.source.inProgress', { label, source });
}

function uniqueEntries(entries: Array<string | null | undefined>): string[] {
  return Array.from(new Set(entries.map((item) => String(item || '').trim()).filter(Boolean)));
}

function buildDraftSections(
  task: TaskInfo,
  runtime: RuntimeExecutionSummary | null,
  t: TranslateFn,
  openingFinalReport: boolean,
): DraftSection[] {
  const reachedMilestone = getReachedMilestone(task);
  const summaryStatus: SectionStatus = task.status === 'failed'
    ? 'failed'
    : reachedMilestone >= 0
      ? task.status === 'completed'
        ? 'completed'
        : 'generating'
      : 'waiting';

  const makeStatus = (requiredMilestone: number): SectionStatus => {
    if (task.status === 'completed') {
      return 'completed';
    }
    if (task.status === 'failed') {
      if (requiredMilestone < reachedMilestone) {
        return 'completed';
      }
      if (requiredMilestone === reachedMilestone) {
        return 'failed';
      }
      return 'waiting';
    }
    if (requiredMilestone < reachedMilestone) {
      return 'completed';
    }
    if (requiredMilestone === reachedMilestone) {
      return 'generating';
    }
    return 'waiting';
  };

  const market = runtime?.data?.market;
  const fundamentals = runtime?.data?.fundamentals;
  const news = runtime?.data?.news;
  const sentiment = runtime?.data?.sentiment;
  const ai = runtime?.ai;

  const summaryEntries = uniqueEntries([
    `${task.stockName || task.stockCode} (${task.stockCode})`,
    task.message,
    task.status === 'completed'
      ? t(openingFinalReport ? 'report.generation.summaryState.openingReady' : 'report.generation.summaryState.ready')
      : task.status === 'failed'
        ? t('report.generation.summaryState.stopped')
        : null,
  ]);

  const marketEntries = uniqueEntries([
    sourceLine(t, t('report.generation.labels.marketFeed'), market?.source, market?.status),
    sourceLine(t, t('report.generation.labels.fundamentals'), fundamentals?.source, fundamentals?.status),
    t('report.generation.marketState.stableSurface'),
  ]);

  const evidenceEntries = uniqueEntries([
    ai?.model
      ? t('report.generation.evidenceState.modelResolved', { model: ai.model })
      : t('report.generation.evidenceState.modelPending'),
    t('report.generation.evidenceState.signalSynthesis'),
    ai?.gateway
      ? t('report.generation.evidenceState.gateway', { gateway: ai.gateway })
      : null,
  ]);

  const catalystEntries = uniqueEntries([
    sourceLine(t, t('report.generation.labels.newsContext'), news?.source, news?.status),
    sourceLine(t, t('report.generation.labels.sentimentContext'), sentiment?.source, sentiment?.status),
    t('report.generation.catalystsState.settling'),
  ]);

  const riskEntries = uniqueEntries([
    task.status === 'failed'
      ? (task.error
        ? t('report.generation.riskState.error', { error: task.error })
        : t('report.generation.riskState.finalValidation'))
      : null,
    (news?.status === 'not_configured' || sentiment?.status === 'not_configured')
      ? t('report.generation.riskState.missingSource')
      : t('report.generation.riskState.explicitMarkers'),
  ]);

  const actionEntries = uniqueEntries([
    task.status === 'completed'
      ? t(openingFinalReport ? 'report.generation.actionState.openingArchive' : 'report.generation.actionState.executionReady')
      : task.status === 'failed'
        ? t('report.generation.actionState.retryPreserves')
        : t('report.generation.actionState.finalSection'),
  ]);

  return [
    {
      key: 'summary',
      title: t('report.generation.sections.summary'),
      status: summaryStatus,
      entries: summaryEntries,
    },
    {
      key: 'market',
      title: t('report.generation.sections.market'),
      status: makeStatus(1),
      entries: marketEntries,
    },
    {
      key: 'evidence',
      title: t('report.generation.sections.evidence'),
      status: makeStatus(2),
      entries: evidenceEntries,
    },
    {
      key: 'catalysts',
      title: t('report.generation.sections.catalysts'),
      status: makeStatus(2),
      entries: catalystEntries,
    },
    {
      key: 'risk',
      title: t('report.generation.sections.risk'),
      status: makeStatus(3),
      entries: riskEntries,
    },
    {
      key: 'action',
      title: t('report.generation.sections.action'),
      status: makeStatus(4),
      entries: actionEntries,
    },
  ];
}

export const ProgressiveReportGeneration: React.FC<ProgressiveReportGenerationProps> = ({
  task,
  onRetry,
  openingFinalReport = false,
}) => {
  const { t } = useI18n();
  const runtime = buildTaskExecutionSummary(task);
  const phase = getProgressPhase(task);
  const sections = buildDraftSections(task, runtime, t, openingFinalReport);
  const progress = Math.min(task.progress || 0, 100);
  const stateFlow = [
    'initializing',
    'fetching_market_data',
    'analyzing_signals',
    'assembling_report',
    'finalizing',
  ] as const;
  const currentPhaseIndex = phase === 'completed'
    ? stateFlow.length - 1
    : phase === 'failed'
      ? Math.max(0, getReachedMilestone(task))
      : Math.max(0, stateFlow.indexOf(phase as typeof stateFlow[number]));

  return (
    <section
      className="report-generation-preview"
      data-testid="report-generation-preview"
      data-status={task.status}
    >
      <div className="report-generation-preview__header">
        <div className="report-generation-preview__intro">
          <p className="report-generation-preview__eyebrow">
            {t('report.generation.eyebrow')}
          </p>
          <h2 className="report-generation-preview__title">
            {task.stockName || task.stockCode}
            <span className="report-generation-preview__code">{task.stockCode}</span>
          </h2>
          <p className="report-generation-preview__body">
            {t('report.generation.body')}
          </p>
        </div>

        <div className="report-generation-preview__summary">
          <span
            className={cn(
              'report-generation-preview__phase',
              task.status === 'failed'
                ? 'report-generation-preview__phase--failed'
                : task.status === 'completed'
                  ? 'report-generation-preview__phase--complete'
                  : 'report-generation-preview__phase--active',
            )}
          >
            {phaseLabel(t, phase, openingFinalReport)}
          </span>

          <div className="report-generation-preview__telemetry">
            <span className="report-generation-preview__progress">{progress}%</span>
            {task.message ? (
              <p className="report-generation-preview__message">{task.message}</p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="report-generation-preview__progressbar" aria-hidden="true">
        <span style={{ width: `${progress}%` }} />
      </div>

      <div className="report-generation-preview__mission">
        <ol className="report-generation-preview__steps" aria-label={t('report.generation.aria')}>
          {stateFlow.map((item, index) => {
            const state: RailState = task.status === 'failed'
              ? index < currentPhaseIndex
                ? 'complete'
                : index === currentPhaseIndex
                  ? 'failed'
                  : 'waiting'
              : phase === 'completed'
                ? 'complete'
                : index < currentPhaseIndex
                  ? 'complete'
                  : index === currentPhaseIndex
                    ? 'active'
                    : 'waiting';

            return (
              <li key={item} className="report-generation-preview__step" data-state={state}>
                <span className="report-generation-preview__step-index">{String(index + 1).padStart(2, '0')}</span>
                <div className="report-generation-preview__step-copy">
                  <span className="report-generation-preview__step-label">
                    {phaseLabel(t, item, false)}
                  </span>
                  <span className="report-generation-preview__step-state">
                    {railStateLabel(t, state)}
                  </span>
                </div>
              </li>
            );
          })}
        </ol>

        <div className="report-generation-preview__sections">
          {sections.map((section, index) => (
            <article
              key={section.key}
              className="report-generation-preview__section"
              data-status={section.status}
              style={{ ['--reveal-index' as string]: index + 1 }}
            >
              <div className="report-generation-preview__section-head">
                <h3>{section.title}</h3>
                <span className="report-generation-preview__section-badge">
                  {sectionStatusLabel(t, section.status)}
                </span>
              </div>

              {section.status === 'waiting' ? (
                <div className="report-generation-preview__skeleton" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              ) : (
                <div className="report-generation-preview__entries">
                  {section.entries.map((entry) => (
                    <p key={entry}>{entry}</p>
                  ))}
                </div>
              )}

              {section.footnote ? (
                <p className="report-generation-preview__footnote">{section.footnote}</p>
              ) : null}

              {section.status === 'failed' && onRetry ? (
                <div className="report-generation-preview__section-action">
                  <Button variant="home-action-report" size="sm" onClick={onRetry}>
                    {t('report.generation.restartGeneration')}
                  </Button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      </div>

      {task.status === 'failed' && onRetry ? (
        <div className="report-generation-preview__footer">
          <Button variant="home-action-report" size="sm" onClick={onRetry}>
            {t('report.generation.retryAnalysis')}
          </Button>
        </div>
      ) : null}
    </section>
  );
};

export default ProgressiveReportGeneration;
