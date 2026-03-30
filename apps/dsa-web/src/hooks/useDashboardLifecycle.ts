import { useEffect } from 'react';
import type { TaskInfo } from '../types/analysis';
import { useTaskStream } from './useTaskStream';

type UseDashboardLifecycleOptions = {
  loadInitialHistory: () => Promise<void>;
  refreshHistory: (silent?: boolean) => Promise<void>;
  hydrateRecentTasks: () => Promise<void>;
  syncTaskCreated: (task: TaskInfo) => void;
  syncTaskUpdated: (task: TaskInfo) => void;
  syncTaskFailed: (task: TaskInfo) => void;
  enabled?: boolean;
};

export function useDashboardLifecycle({
  loadInitialHistory,
  refreshHistory,
  hydrateRecentTasks,
  syncTaskCreated,
  syncTaskUpdated,
  syncTaskFailed,
  enabled = true,
}: UseDashboardLifecycleOptions): void {
  useEffect(() => {
    if (!enabled) {
      return;
    }

    void loadInitialHistory();
    void hydrateRecentTasks();
  }, [enabled, hydrateRecentTasks, loadInitialHistory]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshHistory(true);
    }, 30_000);

    return () => window.clearInterval(intervalId);
  }, [enabled, refreshHistory]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void refreshHistory(true);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [enabled, refreshHistory]);

  useTaskStream({
    onTaskCreated: syncTaskCreated,
    onTaskStarted: syncTaskUpdated,
    onTaskCompleted: (task) => {
      syncTaskUpdated(task);
      void refreshHistory(true);
    },
    onTaskFailed: (task) => {
      syncTaskFailed(task);
    },
    onError: () => {
      console.warn('SSE connection disconnected, reconnecting...');
    },
    enabled,
  });
}

export default useDashboardLifecycle;
