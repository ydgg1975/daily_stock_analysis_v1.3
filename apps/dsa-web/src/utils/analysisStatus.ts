import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { translateForCurrentLanguage } from '../i18n/core';
import type { AnalysisReport, TaskInfo } from '../types/analysis';

export type AnalysisStageKey =
  | 'submitted'
  | 'queued'
  | 'fetching'
  | 'generating'
  | 'notifying'
  | 'completed'
  | 'failed';

export type AnalysisStageDescriptor = {
  key: AnalysisStageKey;
  label: string;
  summary: string;
  detail?: string;
};

export type StatusRailState = 'waiting' | 'active' | 'completed' | 'failed';
type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

export const ANALYSIS_STAGE_ORDER: AnalysisStageKey[] = [
  'submitted',
  'queued',
  'fetching',
  'generating',
  'notifying',
  'completed',
];

export function getWorkflowStageShortLabel(
  stage: AnalysisStageKey,
  translate: TranslateFn = translateForCurrentLanguage,
): string {
  return translate(`status.board.stageShort.${stage}`);
}

export function getStatusRailStateLabel(
  state: StatusRailState,
  translate: TranslateFn = translateForCurrentLanguage,
): string {
  return translate(`status.board.railState.${state}`);
}

function inferProcessingStage(task: TaskInfo): AnalysisStageKey {
  const message = String(task.message || '').trim().toLowerCase();
  const startedAt = task.startedAt ? Date.parse(task.startedAt) : Number.NaN;
  const elapsedSeconds = Number.isFinite(startedAt)
    ? Math.max(0, (Date.now() - startedAt) / 1000)
    : 0;

  if (
    message.includes('通知')
    || message.includes('discord')
    || message.includes('wechat')
    || message.includes('telegram')
    || message.includes('push')
    || message.includes('send')
    || message.includes('sync')
  ) {
    return 'notifying';
  }

  if (
    message.includes('生成')
    || message.includes('写报告')
    || message.includes('整理')
    || message.includes('final')
    || message.includes('summary')
  ) {
    return 'generating';
  }

  if (
    message.includes('拉取')
    || message.includes('行情')
    || message.includes('数据')
    || message.includes('news')
    || message.includes('fetch')
    || message.includes('quote')
  ) {
    return 'fetching';
  }

  return elapsedSeconds >= 12 ? 'generating' : 'fetching';
}

export function inferAnalysisStage(
  task?: TaskInfo | null,
  options: { isSubmitting?: boolean } = {},
): AnalysisStageKey | null {
  if (!task) {
    return options.isSubmitting ? 'submitted' : null;
  }

  if (task.status === 'failed') {
    return 'failed';
  }
  if (task.status === 'completed') {
    return 'completed';
  }
  if (task.status === 'pending') {
    return 'queued';
  }
  if (task.status === 'processing') {
    return inferProcessingStage(task);
  }

  return options.isSubmitting ? 'submitted' : null;
}

export function getAnalysisStageDescriptor(
  task?: TaskInfo | null,
  options: {
    isSubmitting?: boolean;
    selectedReport?: AnalysisReport | null;
    globalError?: ParsedApiError | null;
    duplicateError?: string | null;
    translate?: TranslateFn;
  } = {},
): AnalysisStageDescriptor | null {
  const translate = options.translate ?? translateForCurrentLanguage;
  const stage = inferAnalysisStage(task, { isSubmitting: options.isSubmitting });
  const fallbackName = task?.stockName || task?.stockCode || translate('status.currentTarget');

  if (options.duplicateError) {
    return {
      key: 'failed',
      label: translate('status.conflict'),
      summary: translate('status.conflict'),
      detail: options.duplicateError,
    };
  }

  if (options.globalError && !task) {
    return {
      key: 'failed',
      label: translate('status.failed'),
      summary: options.globalError.title,
      detail: options.globalError.message,
    };
  }

  if (!stage) {
    return null;
  }

  if (stage === 'submitted') {
    return {
      key: stage,
      label: translate('status.submitted'),
      summary: translate('status.submittedSummary'),
      detail: translate('status.submittedDetail'),
    };
  }

  if (stage === 'queued') {
    return {
      key: stage,
      label: translate('status.queued'),
      summary: translate('status.queuedSummary', {
        name: fallbackName,
      }),
      detail: task?.message || translate('status.queuedDetail'),
    };
  }

  if (stage === 'fetching') {
    return {
      key: stage,
      label: translate('status.fetching'),
      summary: translate('status.fetchingSummary', {
        name: fallbackName,
      }),
      detail: task?.message || translate('status.fetchingDetail'),
    };
  }

  if (stage === 'generating') {
    return {
      key: stage,
      label: translate('status.generating'),
      summary: translate('status.generatingSummary', {
        name: fallbackName,
      }),
      detail: task?.message || translate('status.generatingDetail'),
    };
  }

  if (stage === 'notifying') {
    return {
      key: stage,
      label: translate('status.notifying'),
      summary: translate('status.notifyingSummary', {
        name: fallbackName,
      }),
      detail: task?.message || translate('status.notifyingDetail'),
    };
  }

  if (stage === 'completed') {
    const isShowingLatestResult = options.selectedReport?.meta?.stockCode === task?.stockCode;
    return {
      key: stage,
      label: translate('status.completed'),
      summary: translate('status.completedSummary', {
        name: fallbackName,
      }),
      detail: isShowingLatestResult
        ? translate('status.completedDetailOpen')
        : options.selectedReport
          ? translate('status.completedDetailStale')
          : translate('status.completedDetailDefault'),
    };
  }

  const parsedFailure = getParsedApiError(task?.error || options.globalError || translate('status.failed'));
  return {
    key: 'failed',
    label: translate('status.failed'),
    summary: parsedFailure.title,
    detail: parsedFailure.message,
  };
}

export function getStatusRelationCopy(
  task: TaskInfo | null | undefined,
  selectedReport?: AnalysisReport | null,
  translate: TranslateFn = translateForCurrentLanguage,
): string | null {
  if (!task || !selectedReport?.meta?.stockCode) {
    return null;
  }

  if (selectedReport.meta.stockCode === task.stockCode) {
    if (task.status === 'completed') {
      return translate('status.relationLatest');
    }
    return translate('status.relationStale');
  }

  return translate('status.relationCross', {
    selected: selectedReport.meta.stockCode,
    task: task.stockCode,
  });
}
