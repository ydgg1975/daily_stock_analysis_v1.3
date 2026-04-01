import { describe, expect, it } from 'vitest';
import type { TaskInfo } from '../../types/analysis';
import {
  selectCompletedTasksByRecency,
  selectPrimaryTask,
  sortTasksByPriority,
} from '../taskQueue';

function buildTask(overrides: Partial<TaskInfo>): TaskInfo {
  return {
    taskId: overrides.taskId || 'task-1',
    stockCode: overrides.stockCode || 'AAPL',
    status: overrides.status || 'pending',
    progress: overrides.progress ?? 0,
    reportType: overrides.reportType || 'detailed',
    createdAt: overrides.createdAt || '2026-03-18T08:00:00Z',
    ...overrides,
  };
}

describe('taskQueue', () => {
  it('sorts tasks by active status first and recency second', () => {
    const ordered = sortTasksByPriority([
      buildTask({
        taskId: 'completed-latest',
        status: 'completed',
        createdAt: '2026-03-18T08:00:00Z',
        completedAt: '2026-03-18T10:00:00Z',
      }),
      buildTask({
        taskId: 'pending-newer',
        status: 'pending',
        createdAt: '2026-03-18T11:00:00Z',
      }),
      buildTask({
        taskId: 'processing-older',
        status: 'processing',
        createdAt: '2026-03-18T07:00:00Z',
        updatedAt: '2026-03-18T09:00:00Z',
      }),
      buildTask({
        taskId: 'failed-newest',
        status: 'failed',
        createdAt: '2026-03-18T12:00:00Z',
      }),
      buildTask({
        taskId: 'processing-newest',
        status: 'processing',
        createdAt: '2026-03-18T06:00:00Z',
        updatedAt: '2026-03-18T12:30:00Z',
      }),
    ]);

    expect(ordered.map((task) => task.taskId)).toEqual([
      'processing-newest',
      'processing-older',
      'pending-newer',
      'failed-newest',
      'completed-latest',
    ]);
  });

  it('selects the first task from the shared priority order as primary', () => {
    const primaryTask = selectPrimaryTask([
      buildTask({
        taskId: 'pending-task',
        status: 'pending',
        createdAt: '2026-03-18T12:00:00Z',
      }),
      buildTask({
        taskId: 'processing-task',
        status: 'processing',
        createdAt: '2026-03-18T08:00:00Z',
        updatedAt: '2026-03-18T08:30:00Z',
      }),
    ]);

    expect(primaryTask?.taskId).toBe('processing-task');
  });

  it('orders completed tasks by completion recency for latest-report follow-up', () => {
    const completedTasks = selectCompletedTasksByRecency([
      buildTask({
        taskId: 'completed-older',
        status: 'completed',
        completedAt: '2026-03-18T08:30:00Z',
      }),
      buildTask({
        taskId: 'completed-latest',
        status: 'completed',
        completedAt: '2026-03-18T09:30:00Z',
      }),
      buildTask({
        taskId: 'processing-task',
        status: 'processing',
        updatedAt: '2026-03-18T10:00:00Z',
      }),
    ]);

    expect(completedTasks.map((task) => task.taskId)).toEqual([
      'completed-latest',
      'completed-older',
    ]);
  });
});
