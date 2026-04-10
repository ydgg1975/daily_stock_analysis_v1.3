/**
 * SpaceX live refinement: preserves stage inference, duplicate/error handling,
 * and task relation copy while collapsing the old decision-context panel into
 * a denser single research-status surface so the canonical decision summary stays below.
 */
import type React from 'react';
import type { AnalysisReport, TaskInfo } from '../../types/analysis';
import type { ParsedApiError } from '../../api/error';
import { cn } from '../../utils/cn';
import {
  ANALYSIS_STAGE_ORDER,
  type AnalysisStageDescriptor,
  getAnalysisStageDescriptor,
  getStatusRailStateLabel,
  getStatusRelationCopy,
  getWorkflowStageShortLabel,
  inferAnalysisStage,
} from '../../utils/analysisStatus';
import { getParsedApiError } from '../../api/error';
import { useI18n } from '../../contexts/UiLanguageContext';

type StatusBlocksProps = {
  task: TaskInfo | null;
  isAnalyzing: boolean;
  selectedReport: AnalysisReport | null;
  duplicateError: string | null;
  error: ParsedApiError | null;
  layout?: 'stacked' | 'split' | 'workflow';
};

export const StatusBlocks: React.FC<StatusBlocksProps> = ({
  task,
  isAnalyzing,
  selectedReport,
  duplicateError,
  error,
  layout = 'stacked',
}) => {
  const { language, t } = useI18n();
  const descriptor = getAnalysisStageDescriptor(task, {
    isSubmitting: isAnalyzing,
    selectedReport,
    globalError: error,
    duplicateError,
    translate: t,
  });

  const displayDescriptor: AnalysisStageDescriptor = descriptor ?? (
    selectedReport
      ? {
          key: 'completed',
          label: t('status.completed'),
          summary: t('status.completedSummary', {
            name: selectedReport.meta.stockName || selectedReport.meta.stockCode,
          }),
          detail: t('status.completedDetailDefault'),
        }
      : {
          key: 'submitted',
          label: t('status.board.readyLabel'),
          summary: t('status.board.readySummary'),
          detail: t('status.board.readyDetail'),
        }
  );

  const stage = inferAnalysisStage(task, { isSubmitting: isAnalyzing }) || (selectedReport ? 'completed' : null);
  const orderedStage = stage === 'failed' ? 'generating' : stage;
  const orderedStageIndex = orderedStage ? ANALYSIS_STAGE_ORDER.indexOf(orderedStage) : -1;
  const taskError = displayDescriptor.key === 'failed'
    ? getParsedApiError(task?.error || error || duplicateError || t('status.failed'))
    : null;
  const relationCopy = getStatusRelationCopy(task, selectedReport, t);
  const titleLabel = task?.stockName || selectedReport?.meta.stockName || task?.stockCode || selectedReport?.meta.stockCode;
  const tickerLabel = task?.stockCode || selectedReport?.meta.stockCode;
  const primaryMessage = taskError?.message || duplicateError || displayDescriptor.summary;
  const detailCandidates = [
    task?.message,
    relationCopy,
    displayDescriptor.detail,
    taskError?.message,
    duplicateError,
  ].filter((item): item is string => Boolean(item && String(item).trim()));
  const normalizedPrimaryMessage = String(primaryMessage || '').trim();
  const supportLine = detailCandidates.find((item) => item.trim() !== normalizedPrimaryMessage) || null;
  const progressValue = task
    ? `${Math.min(task.progress || 0, 100)}%`
    : selectedReport
      ? t('status.board.value.loaded')
      : t('status.board.value.standby');
  const identityLabel = titleLabel
    ? tickerLabel && tickerLabel !== titleLabel
      ? `${titleLabel} · ${tickerLabel}`
      : titleLabel
    : t('status.board.value.noTargetSelected');
  const shouldShowSupportLine = Boolean(taskError || duplicateError || displayDescriptor.key === 'failed');

  return (
    <section
      className="workspace-statusboard"
      data-language={language}
      data-layout={layout}
      data-testid="analysis-status-strip"
      role="status"
      aria-live="polite"
    >
      <article className="workspace-statusboard__panel workspace-statusboard__panel--workflow">
        <div className="workspace-statusboard__rail-head">
          <div className="workspace-statusboard__heading">
            <p className="workspace-statusboard__rail-label">
              {t('status.board.title')}
            </p>
            <span
              className={cn(
                'workspace-status-badge',
                displayDescriptor.key === 'failed'
                  ? 'workspace-status-badge--failed'
                  : displayDescriptor.key === 'completed'
                    ? 'workspace-status-badge--completed'
                    : 'workspace-status-badge--active',
              )}
            >
              {displayDescriptor.label}
            </span>
          </div>

          <div className="workspace-statusboard__identity">
            {titleLabel ? (
              <span className="workspace-statusboard__ticker" title={identityLabel}>
                <span>{titleLabel}</span>
                {tickerLabel ? (
                  <span className="theme-task-meta-chip shrink-0 rounded-full px-2 py-0.5 text-[10px] font-normal uppercase tracking-[0.12em] text-muted-text">
                    {tickerLabel}
                  </span>
                ) : null}
              </span>
            ) : (
              <span className="workspace-statusboard__identity-placeholder">{identityLabel}</span>
            )}
            <span className="workspace-statusboard__progress">{progressValue}</span>
          </div>
        </div>

        <p className="workspace-statusboard__copy">{primaryMessage}</p>
        {supportLine && shouldShowSupportLine ? (
          <p
            className={cn(
              taskError || duplicateError ? 'workspace-statusboard__error' : 'workspace-statusboard__detail',
            )}
          >
            {supportLine}
          </p>
        ) : null}

        <ol
          className="workspace-statusboard__rail-list workspace-statusboard__rail-list--grid"
          aria-label={t('status.board.aria')}
        >
          {ANALYSIS_STAGE_ORDER.map((item) => {
            const hasStage = Boolean(orderedStage);
            const isComplete = Boolean(
              hasStage
              && displayDescriptor.key !== 'failed'
              && ANALYSIS_STAGE_ORDER.indexOf(item) < orderedStageIndex,
            );
            const isActive = Boolean(hasStage && displayDescriptor.key !== 'failed' && item === orderedStage);
            const isFailed = displayDescriptor.key === 'failed' && item === orderedStage;
            const state = isFailed
              ? 'failed'
              : isComplete
                ? 'completed'
                : isActive
                  ? 'active'
                  : 'waiting';

            return (
              <li
                key={item}
                className="workspace-status-step"
                data-active={isActive}
                data-complete={isComplete}
                data-failed={isFailed}
                data-state={state}
                aria-current={isActive ? 'step' : undefined}
              >
                <span
                  className={cn(
                    'workspace-status-dot',
                    isFailed
                      ? 'workspace-status-dot--failed'
                      : isComplete
                        ? 'workspace-status-dot--complete'
                        : isActive
                          ? 'workspace-status-dot--active'
                          : '',
                  )}
                />
                <span
                  className={cn(
                    'workspace-status-step__label',
                    language === 'en' ? 'font-medium tracking-[0.04em]' : 'tracking-[0.1em]',
                  )}
                  title={t(`status.${item}`)}
                >
                  {getWorkflowStageShortLabel(item, t)}
                </span>
                <span className="workspace-status-step__state">{getStatusRailStateLabel(state, t)}</span>
              </li>
            );
          })}
        </ol>
      </article>
    </section>
  );
};

export default StatusBlocks;
