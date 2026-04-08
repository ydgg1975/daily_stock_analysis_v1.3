import type React from 'react';
import type { TaskInfo } from '../../types/analysis';
import { useI18n } from '../../contexts/UiLanguageContext';
import { inferAnalysisStage } from '../../utils/analysisStatus';
import { buildTaskExecutionSummary } from '../../utils/runtimeExecution';
import { ExecutionSummaryCard } from '../runtime/ExecutionSummaryCard';

const STATUS_TONE_CLASS: Record<string, string> = {
  queued: 'theme-task-status theme-task-status--queued',
  fetching: 'theme-task-status theme-task-status--fetching',
  generating: 'theme-task-status theme-task-status--generating',
  notifying: 'theme-task-status theme-task-status--notifying',
  completed: 'theme-task-status theme-task-status--completed',
  failed: 'theme-task-status theme-task-status--failed',
  submitted: 'theme-task-status theme-task-status--submitted',
};

interface TaskItemProps {
  task: TaskInfo;
  showExecutionSummary?: boolean;
}

const TaskItem: React.FC<TaskItemProps> = ({ task, showExecutionSummary = true }) => {
  const { language, t } = useI18n();
  const stage = inferAnalysisStage(task, { isSubmitting: false }) || 'queued';
  const timeFormatter = new Intl.DateTimeFormat(language === 'zh' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  const stageLabel = t(`tasks.${stage}`);
  const createdAt = task.createdAt || task.startedAt || task.updatedAt;
  const createdAtLabel = createdAt
    ? `${t('tasks.createdAt')} ${timeFormatter.format(new Date(createdAt))}`
    : `${t('tasks.createdAt')} --`;
  const stateLabel = task.status === 'failed'
    ? t('tasks.failed')
    : task.status === 'completed'
      ? t('tasks.completed')
      : t('tasks.running');

  return (
    <div className="theme-list-item min-w-0 rounded-[var(--theme-panel-radius-md)] px-3.5 py-3 transition-all duration-200 ease-out">
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="block min-w-0 flex-1 truncate text-[0.93rem] font-normal leading-5 tracking-[-0.01em] text-foreground sm:text-[0.95rem]">
              {task.stockName || task.stockCode}
            </span>
            <span className="theme-task-meta-chip shrink-0 rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-muted-text">
              {task.stockCode}
            </span>
          </div>
          <div className="theme-task-meta mt-2 flex min-w-0 flex-wrap items-center gap-1.5 text-[10px] leading-4 text-muted-text sm:text-[11px]">
            <span className="theme-task-meta-chip rounded-full px-2 py-0.5 whitespace-nowrap">{stageLabel}</span>
            <span className="truncate">{createdAtLabel}</span>
          </div>
        </div>
        <span
          className={`self-start whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] sm:shrink-0 ${STATUS_TONE_CLASS[stage] ?? STATUS_TONE_CLASS.queued}`}
        >
          {stateLabel}
        </span>
      </div>
      {showExecutionSummary ? <ExecutionSummaryCard summary={buildTaskExecutionSummary(task)} compact /> : null}
    </div>
  );
};

interface TaskPanelProps {
  tasks: TaskInfo[];
  visible?: boolean;
  title?: string;
  className?: string;
  embedded?: boolean;
  onRefresh?: () => void | Promise<void>;
  isRefreshing?: boolean;
  hasRunningTasks?: boolean;
  showExecutionSummary?: boolean;
}

export const TaskPanel: React.FC<TaskPanelProps> = ({
  tasks,
  visible = true,
  title,
  className = '',
  embedded = false,
  onRefresh,
  isRefreshing = false,
  hasRunningTasks = false,
  showExecutionSummary = true,
}) => {
  const { t } = useI18n();

  if (!visible) {
    return null;
  }

  const processingCount = tasks.filter((task) => ['pending', 'processing'].includes(task.status)).length;
  const completedCount = tasks.filter((task) => task.status === 'completed').length;
  const failedCount = tasks.filter((task) => task.status === 'failed').length;

  const wrapperClass = embedded
    ? `theme-panel-solid overflow-hidden rounded-[1rem] ${className}`
    : `theme-panel-solid overflow-hidden rounded-[1rem] ${className}`;

  return (
    <div className={wrapperClass}>
      <div className={embedded ? 'theme-sidebar-divider flex items-center justify-between border-b px-3 py-2.5' : 'theme-sidebar-divider flex items-center justify-between border-b px-3 py-2.5'}>
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 theme-accent-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <div>
            <span className="block text-sm font-normal tracking-[-0.01em] text-foreground">{title || t('tasks.title')}</span>
            {!embedded ? (
              <span className="block text-[10px] uppercase tracking-[0.16em] text-muted-text">{t('tasks.activeSubtitle')}</span>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 text-[11px] text-muted-text">
          {hasRunningTasks ? <span>{t('tasks.autoRefreshing')}</span> : null}
          {processingCount > 0 ? <span>{processingCount} {t('tasks.processing')}</span> : null}
          {completedCount > 0 ? <span>{completedCount} {t('tasks.completed')}</span> : null}
          {failedCount > 0 ? <span>{failedCount} {t('tasks.failed')}</span> : null}
          {onRefresh ? (
            <button
              type="button"
              onClick={() => void onRefresh()}
              disabled={isRefreshing}
              className="inline-flex items-center gap-1.5 rounded-[var(--theme-button-radius)] border border-[var(--theme-panel-subtle-border)] bg-transparent px-3 py-1.5 text-[11px] uppercase tracking-[0.14em] text-secondary-text transition-colors hover:border-[var(--border-default)] hover:bg-[var(--overlay-hover)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
            >
              <svg className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>{isRefreshing ? t('tasks.refreshing') : t('tasks.refresh')}</span>
            </button>
          ) : null}
        </div>
      </div>

      {tasks.length === 0 ? (
        <div className={embedded ? 'px-3 py-4 text-sm text-muted-text' : 'p-4 text-sm text-muted-text'}>
          {t('tasks.noTasks')}
        </div>
      ) : (
        <div className={embedded ? 'max-h-36 grid grid-cols-1 gap-1.5 overflow-y-auto px-3 pb-3 pt-2.5' : 'max-h-64 grid grid-cols-1 gap-1.5 overflow-y-auto p-2 lg:grid-cols-2'}>
          {tasks.map((task) => (
            <TaskItem key={task.taskId} task={task} showExecutionSummary={showExecutionSummary} />
          ))}
        </div>
      )}
    </div>
  );
};

export default TaskPanel;
