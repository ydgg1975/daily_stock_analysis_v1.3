import type React from 'react';
import type { TaskInfo } from '../../types/analysis';

/**
 * 任务项组件属性
 */
interface TaskItemProps {
  task: TaskInfo;
}

/**
 * 单个任务项
 */
const TaskItem: React.FC<TaskItemProps> = ({ task }) => {
  const isPending = task.status === 'pending';
  const isProcessing = task.status === 'processing';

  return (
    <div className="flex items-center gap-3 rounded-[0.9rem] border border-white/6 bg-white/[0.03] px-3 py-2 transition-all duration-200 ease-out hover:border-white/10 hover:bg-white/[0.045]">
      {/* 状态图标 */}
      <div className="shrink-0">
        {isProcessing ? (
          // 加载动画
          <svg className="h-4 w-4 animate-spin text-cyan" fill="none" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        ) : isPending ? (
          // 等待图标
          <svg className="w-4 h-4 text-muted-text" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        ) : null}
      </div>

      {/* 任务信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground truncate">
            {task.stockName || task.stockCode}
          </span>
          <span className="text-xs text-muted-text">
            {task.stockCode}
          </span>
        </div>
        {task.message && (
          <p className="text-xs text-secondary-text truncate mt-0.5">
            {task.message}
          </p>
        )}
      </div>

      {/* 状态标签 */}
      <div className="flex-shrink-0">
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] ${
            isProcessing
              ? 'border border-cyan/12 bg-cyan/[0.08] text-cyan'
              : 'border border-white/8 bg-white/[0.03] text-muted-text'
          }`}
        >
          {isProcessing ? '分析中' : '等待中'}
        </span>
      </div>
    </div>
  );
};

/**
 * 任务面板属性
 */
interface TaskPanelProps {
  /** 任务列表 */
  tasks: TaskInfo[];
  /** 是否显示 */
  visible?: boolean;
  /** 标题 */
  title?: string;
  /** 自定义类名 */
  className?: string;
  embedded?: boolean;
}

/**
 * 任务面板组件
 * 显示进行中的分析任务列表
 */
export const TaskPanel: React.FC<TaskPanelProps> = ({
  tasks,
  visible = true,
  title = '分析任务',
  className = '',
  embedded = false,
}) => {
  // 筛选活跃任务（pending 和 processing）
  const activeTasks = tasks.filter(
    (t) => t.status === 'pending' || t.status === 'processing'
  );

  // 无任务或不可见时不渲染
  if (!visible || activeTasks.length === 0) {
    return null;
  }

  const pendingCount = activeTasks.filter((t) => t.status === 'pending').length;
  const processingCount = activeTasks.filter((t) => t.status === 'processing').length;

  const wrapperClass = embedded
    ? `overflow-hidden ${className}`
    : `overflow-hidden rounded-[1rem] border border-white/6 bg-[#050505] shadow-[0_12px_28px_rgba(0,0,0,0.22)] ${className}`;

  return (
    <div className={wrapperClass}>
      {/* 标题栏 */}
      <div className={embedded ? 'flex items-center justify-between border-b border-white/6 px-3 py-2.5' : 'flex items-center justify-between border-b border-white/6 px-3 py-2'}>
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-cyan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span className="text-sm font-medium text-foreground">{title}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-text">
          {processingCount > 0 && (
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse" />
              {processingCount} 进行中
            </span>
          )}
          {pendingCount > 0 && (
            <span>{pendingCount} 等待中</span>
          )}
        </div>
      </div>

      {/* 任务列表 */}
      <div className={embedded ? 'max-h-52 space-y-2 overflow-y-auto px-3 pb-3 pt-3' : 'max-h-64 space-y-2 overflow-y-auto p-2'}>
        {activeTasks.map((task) => (
          <TaskItem key={task.taskId} task={task} />
        ))}
      </div>
    </div>
  );
};

export default TaskPanel;
