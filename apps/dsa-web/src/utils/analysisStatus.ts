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

export const ANALYSIS_STAGE_ORDER: AnalysisStageKey[] = [
  'submitted',
  'queued',
  'fetching',
  'generating',
  'notifying',
  'completed',
];

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
  } = {},
): AnalysisStageDescriptor | null {
  const stage = inferAnalysisStage(task, { isSubmitting: options.isSubmitting });

  if (options.duplicateError) {
    return {
      key: 'failed',
      label: translateForCurrentLanguage('status.conflict'),
      summary: translateForCurrentLanguage('status.conflict'),
      detail: options.duplicateError,
    };
  }

  if (options.globalError && !task) {
    return {
      key: 'failed',
      label: '分析失败',
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
      label: translateForCurrentLanguage('status.submitted'),
      summary: translateForCurrentLanguage('status.submittedSummary'),
      detail: translateForCurrentLanguage('status.submittedDetail'),
    };
  }

  if (stage === 'queued') {
    return {
      key: stage,
      label: translateForCurrentLanguage('status.queued'),
      summary: translateForCurrentLanguage('status.queuedSummary', {
        name: task?.stockName || task?.stockCode || '当前标的',
      }),
      detail: task?.message || translateForCurrentLanguage('status.queuedDetail'),
    };
  }

  if (stage === 'fetching') {
    return {
      key: stage,
      label: translateForCurrentLanguage('status.fetching'),
      summary: translateForCurrentLanguage('status.fetchingSummary', {
        name: task?.stockName || task?.stockCode || '当前标的',
      }),
      detail: task?.message || translateForCurrentLanguage('status.fetchingDetail'),
    };
  }

  if (stage === 'generating') {
    return {
      key: stage,
      label: translateForCurrentLanguage('status.generating'),
      summary: translateForCurrentLanguage('status.generatingSummary', {
        name: task?.stockName || task?.stockCode || '当前标的',
      }),
      detail: task?.message || translateForCurrentLanguage('status.generatingDetail'),
    };
  }

  if (stage === 'notifying') {
    return {
      key: stage,
      label: translateForCurrentLanguage('status.notifying'),
      summary: translateForCurrentLanguage('status.notifyingSummary', {
        name: task?.stockName || task?.stockCode || '当前标的',
      }),
      detail: task?.message || translateForCurrentLanguage('status.notifyingDetail'),
    };
  }

  if (stage === 'completed') {
    const isShowingLatestResult = options.selectedReport?.meta?.stockCode === task?.stockCode;
    return {
      key: stage,
      label: translateForCurrentLanguage('status.completed'),
      summary: translateForCurrentLanguage('status.completedSummary', {
        name: task?.stockName || task?.stockCode || '当前标的',
      }),
      detail: isShowingLatestResult
        ? translateForCurrentLanguage('status.completedDetailOpen')
        : options.selectedReport
          ? translateForCurrentLanguage('status.completedDetailStale')
          : translateForCurrentLanguage('status.completedDetailDefault'),
    };
  }

  const parsedFailure = getParsedApiError(task?.error || options.globalError || '分析失败');
  return {
    key: 'failed',
    label: translateForCurrentLanguage('status.failed'),
    summary: parsedFailure.title,
    detail: parsedFailure.message,
  };
}

export function getStatusRelationCopy(
  task: TaskInfo | null | undefined,
  selectedReport?: AnalysisReport | null,
): string | null {
  if (!task || !selectedReport?.meta?.stockCode) {
    return null;
  }

  if (selectedReport.meta.stockCode === task.stockCode) {
    if (task.status === 'completed') {
      return translateForCurrentLanguage('status.relationLatest');
    }
    return translateForCurrentLanguage('status.relationStale');
  }

  return translateForCurrentLanguage('status.relationCross', {
    selected: selectedReport.meta.stockCode,
    task: task.stockCode,
  });
}
