import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import type { AnalysisReport, TaskInfo } from '../types/analysis';

export type AnalysisStageKey =
  | 'submitted'
  | 'queued'
  | 'fetching'
  | 'generating'
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
  'completed',
];

function inferProcessingStage(task: TaskInfo): AnalysisStageKey {
  const message = String(task.message || '').trim().toLowerCase();
  const startedAt = task.startedAt ? Date.parse(task.startedAt) : Number.NaN;
  const elapsedSeconds = Number.isFinite(startedAt)
    ? Math.max(0, (Date.now() - startedAt) / 1000)
    : 0;

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
      label: '分析冲突',
      summary: '同一标的已有任务在进行中',
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
      label: '已提交',
      summary: '分析请求已提交，正在等待任务进入队列',
      detail: '如果当前展示的是历史报告，最新任务完成后会自动刷新历史列表。',
    };
  }

  if (stage === 'queued') {
    return {
      key: stage,
      label: '排队中',
      summary: `${task?.stockName || task?.stockCode || '当前标的'} 已进入分析队列`,
      detail: task?.message || '队列繁忙时会稍后开始执行。',
    };
  }

  if (stage === 'fetching') {
    return {
      key: stage,
      label: '拉取行情 / 数据中',
      summary: `${task?.stockName || task?.stockCode || '当前标的'} 正在拉取行情、技术面和新闻数据`,
      detail: task?.message || '这一步会优先获取当前会话所需的行情与基础信息。',
    };
  }

  if (stage === 'generating') {
    return {
      key: stage,
      label: '生成分析中',
      summary: `${task?.stockName || task?.stockCode || '当前标的'} 的结构化报告正在生成`,
      detail: task?.message || '系统已进入总结与决策生成阶段。',
    };
  }

  if (stage === 'completed') {
    const isShowingLatestResult = options.selectedReport?.meta?.stockCode === task?.stockCode;
    return {
      key: stage,
      label: '已完成',
      summary: `${task?.stockName || task?.stockCode || '当前标的'} 的分析已完成`,
      detail: isShowingLatestResult
        ? '最新结果已自动打开，可以继续查看完整报告或追问 AI。'
        : options.selectedReport
          ? '历史列表已刷新；如果你仍在查看旧报告，可从左侧选择最新结果。'
          : '历史列表已刷新，可以继续打开完整报告或追问 AI。',
    };
  }

  const parsedFailure = getParsedApiError(task?.error || options.globalError || '分析失败');
  return {
    key: 'failed',
    label: '失败',
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
      return '当前已自动切换到最新结果。';
    }
    return '当前展示的是历史版本，新的同标的结果生成后可从左侧刷新查看。';
  }

  return `当前正在查看 ${selectedReport.meta.stockCode} 的历史报告，后台任务正在分析 ${task.stockCode}。`;
}
