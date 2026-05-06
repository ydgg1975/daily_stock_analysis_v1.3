import { useEffect, useRef, useCallback } from 'react';
import { analysisApi } from '../api/analysis';
import type { TaskInfo } from '../types/analysis';
import { useTaskStream } from './useTaskStream';

type UseDashboardLifecycleOptions = {
  loadInitialHistory: () => Promise<void>;
  refreshHistory: (silent?: boolean) => Promise<void>;
  syncTaskCreated: (task: TaskInfo) => void;
  syncTaskUpdated: (task: TaskInfo) => void;
  syncTaskFailed: (task: TaskInfo) => void;
  removeTask: (taskId: string) => void;
  enabled?: boolean;
};

export function useDashboardLifecycle({
  loadInitialHistory,
  refreshHistory,
  syncTaskCreated,
  syncTaskUpdated,
  syncTaskFailed,
  removeTask,
  enabled = true,
}: UseDashboardLifecycleOptions): void {
  const removalTimeoutsRef = useRef<number[]>([]);

  // Sync active tasks from the API to reconcile stale store state.
  // This handles the case where tasks completed while the component was unmounted.
  const syncActiveTasksFromApi = useCallback(async () => {
    try {
      const response = await analysisApi.getTasks({ limit: 50 });
      const serverTasks = response.tasks ?? [];
      const serverActiveIds = new Set<string>();

      for (const task of serverTasks) {
        if (task.status === 'pending' || task.status === 'processing') {
          serverActiveIds.add(task.taskId);
          // Ensure task exists in store with latest state
          syncTaskCreated(task);
          syncTaskUpdated(task);
        } else if (task.status === 'completed') {
          // Task completed while we were away - remove it from store
          removeTask(task.taskId);
        } else if (task.status === 'failed') {
          removeTask(task.taskId);
        }
      }

      // Remove tasks from store that are no longer in the server response
      // (they completed/failed while the component was unmounted)
      const { useStockPoolStore } = await import('../stores/stockPoolStore');
      const { activeTasks } = useStockPoolStore.getState();
      for (const storeTask of activeTasks) {
        if (!serverActiveIds.has(storeTask.taskId)) {
          removeTask(storeTask.taskId);
        }
      }
    } catch {
      // Silently ignore - SSE will eventually sync state
    }
  }, [syncTaskCreated, syncTaskUpdated, removeTask]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    void loadInitialHistory();
    void syncActiveTasksFromApi();
  }, [enabled, loadInitialHistory, syncActiveTasksFromApi]);

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

  useEffect(() => {
    return () => {
      removalTimeoutsRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      removalTimeoutsRef.current = [];
    };
  }, []);

  const scheduleTaskRemoval = (taskId: string, delayMs: number) => {
    const timeoutId = window.setTimeout(() => {
      removeTask(taskId);
      removalTimeoutsRef.current = removalTimeoutsRef.current.filter((item) => item !== timeoutId);
    }, delayMs);

    removalTimeoutsRef.current.push(timeoutId);
  };

  useTaskStream({
    onTaskCreated: syncTaskCreated,
    onTaskStarted: syncTaskUpdated,
    onTaskProgress: syncTaskUpdated,
    onTaskCompleted: (task) => {
      syncTaskUpdated(task);
      void refreshHistory(true);
      scheduleTaskRemoval(task.taskId, 2_000);
    },
    onTaskFailed: (task) => {
      syncTaskFailed(task);
      scheduleTaskRemoval(task.taskId, 5_000);
    },
    onError: () => {
      console.warn('SSE connection disconnected, reconnecting...');
    },
    enabled,
  });
}

export default useDashboardLifecycle;
