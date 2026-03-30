import type React from 'react';
import type { TaskInfo } from '../../types/analysis';
import { useI18n } from '../../contexts/UiLanguageContext';
import { inferAnalysisStage } from '../../utils/analysisStatus';

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
}

const TaskItem: React.FC<TaskItemProps> = ({ task }) => {
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
  const stateLabel = task.status === 'failed'
    ? t('tasks.failed')
    : task.status === 'completed'
      ? t('tasks.completed')
      : t('tasks.running');

  return (
    <div className="theme-list-item rounded-[0.95rem] px-2.5 py-2.5 transition-all duration-200 ease-out">
      <div className="flex items-start justify-between gap-2.5">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-[13px] font-medium text-foreground">
              {task.stockName || task.stockCode}
            </span>
            <span className="shrink-0 text-[10px] uppercase tracking-[0.12em] text-muted-text">{task.stockCode}</span>
          </div>
          <div className="theme-task-meta mt-2 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-text">
            <span className="theme-task-meta-chip rounded-full px-2 py-0.5">{stageLabel}</span>
            <span className="theme-task-meta-chip rounded-full px-2 py-0.5">{stateLabel}</span>
            <span>{t('tasks.createdAt')} {createdAt ? timeFormatter.format(new Date(createdAt)) : '--'}</span>
          </div>
        </div>
        <span
          className={`rounded-full border px-2 py-0.5 text-[9px] uppercase tracking-[0.12em] ${STATUS_TONE_CLASS[stage] ?? STATUS_TONE_CLASS.queued}`}
        >
          {stageLabel}
        </span>
      </div>
    </div>
  );
};

interface TaskPanelProps {
  tasks: TaskInfo[];
  visible?: boolean;
  title?: string;
  className?: string;
  embedded?: boolean;
}

export const TaskPanel: React.FC<TaskPanelProps> = ({
  tasks,
  visible = true,
  title,
  className = '',
  embedded = false,
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
      <div className={embedded ? 'theme-sidebar-divider flex items-center justify-between border-b px-3 py-2.5' : 'theme-sidebar-divider flex items-center justify-between border-b px-3 py-2'}>
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 theme-accent-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <div>
            <span className="block text-sm font-medium text-foreground">{title || t('tasks.title')}</span>
            {!embedded ? (
              <span className="block text-[10px] uppercase tracking-[0.16em] text-muted-text">{t('tasks.activeSubtitle')}</span>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 text-[11px] text-muted-text">
          {processingCount > 0 ? <span>{processingCount} {t('tasks.processing')}</span> : null}
          {completedCount > 0 ? <span>{completedCount} {t('tasks.completed')}</span> : null}
          {failedCount > 0 ? <span>{failedCount} {t('tasks.failed')}</span> : null}
        </div>
      </div>

      {tasks.length === 0 ? (
        <div className={embedded ? 'px-3 py-4 text-sm text-muted-text' : 'p-4 text-sm text-muted-text'}>
          {t('tasks.noTasks')}
        </div>
      ) : (
        <div className={embedded ? 'max-h-36 grid grid-cols-1 gap-1.5 overflow-y-auto px-3 pb-3 pt-3' : 'max-h-64 grid grid-cols-1 gap-1.5 overflow-y-auto p-2 lg:grid-cols-2'}>
          {tasks.map((task) => (
            <TaskItem key={task.taskId} task={task} />
          ))}
        </div>
      )}
    </div>
  );
};

export default TaskPanel;
