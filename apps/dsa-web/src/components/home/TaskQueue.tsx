/**
 * SpaceX live refactor: exposes the active/recent task queue below the decision
 * summary so multi-task runs remain visible while the primary task continues to
 * drive the live report surface.
 */
import type React from 'react';
import { useMemo } from 'react';
import type { TaskInfo } from '../../types/analysis';
import { useI18n } from '../../contexts/UiLanguageContext';
import { getWorkflowStageShortLabel, inferAnalysisStage } from '../../utils/analysisStatus';
import { sortTasksByPriority } from '../../utils/taskQueue';
import { cn } from '../../utils/cn';

type TaskQueueProps = {
  tasks: TaskInfo[];
  primaryTaskId?: string | null;
  viewedStockCode?: string | null;
  onTaskSelect?: (task: TaskInfo) => void;
};

const MAX_VISIBLE_TASKS = 6;

const getTaskStateLabel = (task: TaskInfo, t: (key: string, vars?: Record<string, string | number | undefined>) => string): string => {
  if (task.status === 'failed') {
    return t('tasks.failed');
  }
  if (task.status === 'completed') {
    return t('tasks.completed');
  }
  if (task.status === 'processing') {
    return t('tasks.running');
  }
  return t('tasks.queued');
};

const getTaskStateTone = (task: TaskInfo): 'queued' | 'running' | 'completed' | 'failed' => {
  if (task.status === 'failed') {
    return 'failed';
  }
  if (task.status === 'completed') {
    return 'completed';
  }
  if (task.status === 'processing') {
    return 'running';
  }
  return 'queued';
};

export const TaskQueue: React.FC<TaskQueueProps> = ({
  tasks,
  primaryTaskId = null,
  viewedStockCode = null,
  onTaskSelect,
}) => {
  const { t } = useI18n();
  const queueTasks = useMemo(() => sortTasksByPriority(tasks), [tasks]);
  const visibleTasks = queueTasks.slice(0, MAX_VISIBLE_TASKS);
  const overflowCount = Math.max(0, queueTasks.length - visibleTasks.length);

  return (
    <section className="home-task-queue theme-panel-solid rounded-[var(--cohere-radius-signature)]" data-testid="home-task-queue">
      <div className="home-task-queue__header">
        <div>
          <p className="home-task-queue__eyebrow">{t('tasks.activeTitle')}</p>
          <h3 className="home-task-queue__title">{t('tasks.queueTitle')}</h3>
        </div>
        <p className="home-task-queue__subtitle">{t('tasks.queueSubtitle')}</p>
      </div>

      {queueTasks.length > 0 ? (
        <div className="home-task-queue__list" role="list" aria-label={t('tasks.queueTitle')}>
          {visibleTasks.map((task) => {
            const stage = inferAnalysisStage(task, { isSubmitting: false }) || 'queued';
            const isFocused = task.taskId === primaryTaskId;
            const isViewed = !isFocused && viewedStockCode ? task.stockCode === viewedStockCode : false;
            const stateLabel = getTaskStateLabel(task, t);
            const stateTone = getTaskStateTone(task);
            const stageLabel = getWorkflowStageShortLabel(stage, t);

            return (
              <button
                key={task.taskId}
                type="button"
                role="listitem"
                onClick={() => onTaskSelect?.(task)}
                className={cn(
                  'home-task-queue__item text-left',
                  isFocused ? 'home-task-queue__item--focused' : '',
                  isViewed ? 'home-task-queue__item--viewed' : '',
                )}
                aria-label={`${task.stockName || task.stockCode} ${t('tasks.openTask')}`}
              >
                <div className="home-task-queue__item-top">
                  <div className="home-task-queue__name-row">
                    <span className="home-task-queue__name">{task.stockName || task.stockCode}</span>
                    <span className="home-task-queue__code">{task.stockCode}</span>
                  </div>

                  <div className="home-task-queue__badges">
                    {isFocused ? <span className="home-task-queue__focus">{t('tasks.focused')}</span> : null}
                    {!isFocused && isViewed ? <span className="home-task-queue__focus">{t('tasks.viewed')}</span> : null}
                  </div>
                </div>

                <div className="home-task-queue__pill-row">
                  <span
                    className={cn('home-task-queue__status-indicator', `home-task-queue__status-indicator--${stateTone}`)}
                    aria-label={stateLabel}
                    title={stateLabel}
                  >
                    <span className="sr-only">{stateLabel}</span>
                  </span>
                  <span className={cn('home-task-queue__stage', task.status === 'failed' ? 'home-task-queue__stage--failed' : '')}>
                    {stageLabel}
                  </span>
                </div>
              </button>
            );
          })}
          {overflowCount > 0 ? (
            <div
              className="home-task-queue__item home-task-queue__item--overflow text-left"
              role="listitem"
              aria-label={`${t('tasks.more')} ${overflowCount}`}
            >
              <div className="home-task-queue__item-top">
                <div className="home-task-queue__name-row">
                  <span className="home-task-queue__name">+{overflowCount}</span>
                  <span className="home-task-queue__code">{t('tasks.more')}</span>
                </div>
              </div>
              <div className="home-task-queue__pill-row">
                <span className="home-task-queue__overflow-label">{t('tasks.more')}</span>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="home-task-queue__empty">
          <p>{t('tasks.noTasks')}</p>
          <p>{t('tasks.keep')}</p>
        </div>
      )}
    </section>
  );
};

export default TaskQueue;
