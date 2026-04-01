import { create } from 'zustand';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { historyApi } from '../api/history';
import type { AnalysisReport, HistoryItem, HistoryListResponse, TaskInfo } from '../types/analysis';
import { translateForCurrentLanguage } from '../i18n/core';
import { MAX_RECENT_TASKS, sortTasksByPriority } from '../utils/taskQueue';
import { isObviouslyInvalidStockQuery, looksLikeStockCode, validateStockCode } from '../utils/validation';

const PAGE_SIZE = 20;
const SELECTED_HISTORY_ID_STORAGE_KEY = 'dsa-selected-history-id';
const TASK_QUEUE_STORAGE_KEY = 'dsa-task-queue-v1';
type SelectionSource = 'manual' | 'autocomplete' | 'import' | 'image';

type FetchHistoryOptions = {
  autoSelectFirst?: boolean;
  reset?: boolean;
  silent?: boolean;
};

type SubmitAnalysisOptions = {
  stockCode?: string;
  stockName?: string;
  originalQuery?: string;
  selectionSource?: SelectionSource;
};

let reportRequestSeq = 0;
let analyzeRequestSeq = 0;
let historyRequestSeq = 0;
const dismissedTaskIds = new Set<string>();

function readPersistedSelectedHistoryId(): number | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const raw = window.localStorage.getItem(SELECTED_HISTORY_ID_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function persistSelectedHistoryId(recordId?: number | null): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (recordId && Number.isFinite(recordId)) {
    window.localStorage.setItem(SELECTED_HISTORY_ID_STORAGE_KEY, String(recordId));
    return;
  }

  window.localStorage.removeItem(SELECTED_HISTORY_ID_STORAGE_KEY);
}

function readPersistedTasks(): TaskInfo[] {
  if (typeof window === 'undefined') {
    return [];
  }

  const raw = window.localStorage.getItem(TASK_QUEUE_STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as TaskInfo[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistTasks(tasks: TaskInfo[]): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(TASK_QUEUE_STORAGE_KEY, JSON.stringify(tasks.slice(0, MAX_RECENT_TASKS)));
}

function touchTask(task: TaskInfo): TaskInfo {
  const now = new Date().toISOString();
  return {
    ...task,
    updatedAt: task.updatedAt || task.completedAt || task.startedAt || now,
  };
}

function upsertTask(tasks: TaskInfo[], task: TaskInfo): TaskInfo[] {
  const normalizedTask = touchTask(task);
  const nextTasks = [...tasks];
  const index = nextTasks.findIndex((item) => item.taskId === task.taskId);
  if (index >= 0) {
    nextTasks[index] = {
      ...nextTasks[index],
      ...normalizedTask,
      updatedAt: new Date().toISOString(),
    };
  } else {
    nextTasks.unshift({
      ...normalizedTask,
      updatedAt: new Date().toISOString(),
    });
  }
  return sortTasksByPriority(nextTasks);
}

export interface StockPoolState {
  query: string;
  selectionSource: SelectionSource;
  inputError?: string;
  duplicateError: string | null;
  error: ParsedApiError | null;
  isAnalyzing: boolean;
  historyItems: HistoryItem[];
  highlightedHistoryId: number | null;
  selectedHistoryIds: number[];
  isDeletingHistory: boolean;
  isLoadingHistory: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  currentPage: number;
  selectedReport: AnalysisReport | null;
  isLoadingReport: boolean;
  activeTasks: TaskInfo[];
  markdownDrawerOpen: boolean;
  setQuery: (query: string) => void;
  clearError: () => void;
  clearInlineMessages: () => void;
  openMarkdownDrawer: () => void;
  closeMarkdownDrawer: () => void;
  loadInitialHistory: () => Promise<void>;
  refreshHistory: (silent?: boolean) => Promise<void>;
  hydrateRecentTasks: () => Promise<void>;
  loadMoreHistory: () => Promise<void>;
  selectHistoryItem: (recordId: number) => Promise<void>;
  toggleHistorySelection: (recordId: number) => void;
  toggleSelectAllVisible: () => void;
  deleteSelectedHistory: () => Promise<void>;
  submitAnalysis: (options?: SubmitAnalysisOptions) => Promise<void>;
  focusLatestHistoryForStock: (stockCode: string) => Promise<number | null>;
  clearHighlightedHistory: () => void;
  syncTaskCreated: (task: TaskInfo) => void;
  syncTaskUpdated: (task: TaskInfo) => void;
  syncTaskFailed: (task: TaskInfo) => void;
  removeTask: (taskId: string) => void;
  resetDashboardState: () => void;
}

const initialState = {
  query: '',
  selectionSource: 'manual' as SelectionSource,
  inputError: undefined,
  duplicateError: null,
  error: null,
  isAnalyzing: false,
  historyItems: [] as HistoryItem[],
  highlightedHistoryId: null as number | null,
  selectedHistoryIds: [] as number[],
  isDeletingHistory: false,
  isLoadingHistory: false,
  isLoadingMore: false,
  hasMore: true,
  currentPage: 1,
  selectedReport: null as AnalysisReport | null,
  isLoadingReport: false,
  activeTasks: readPersistedTasks() as TaskInfo[],
  markdownDrawerOpen: false,
};

function buildHistoryParams(page: number) {
  return {
    page,
    limit: PAGE_SIZE,
  };
}

function isSameStockCode(left?: string, right?: string): boolean {
  return String(left || '').trim().toUpperCase() === String(right || '').trim().toUpperCase();
}

async function fetchHistory(
  get: () => StockPoolState,
  set: (partial: Partial<StockPoolState>) => void,
  options: FetchHistoryOptions = {},
): Promise<HistoryListResponse | null> {
  const { autoSelectFirst = false, reset = true, silent = false } = options;
  const currentState = get();
  const page = reset ? 1 : currentState.currentPage + 1;
  const requestId = ++historyRequestSeq;

  if (!silent) {
    set(
      reset
        ? { isLoadingHistory: true, isLoadingMore: false, currentPage: 1 }
        : { isLoadingMore: true },
    );
  }

  try {
    const response = await historyApi.getList(buildHistoryParams(page));
    if (requestId !== historyRequestSeq) {
      return null;
    }

    if (silent && reset) {
      const existingIds = new Set(get().historyItems.map((item) => item.id));
      const newItems = response.items.filter((item) => !existingIds.has(item.id));
      if (newItems.length > 0) {
        set({ historyItems: [...newItems, ...get().historyItems] });
      }
    } else if (reset) {
      set({
        historyItems: response.items,
        currentPage: 1,
      });
    } else {
      set({
        historyItems: [...get().historyItems, ...response.items],
        currentPage: page,
      });
    }

    if (!silent) {
      const totalLoaded = reset ? response.items.length : get().historyItems.length;
      set({ hasMore: totalLoaded < response.total });
    }

    const visibleIds = new Set(get().historyItems.map((item) => item.id));
    set({
      selectedHistoryIds: get().selectedHistoryIds.filter((id) => visibleIds.has(id)),
    });

    const currentSelectedId = get().selectedReport?.meta.id;
    const persistedSelectedId = readPersistedSelectedHistoryId();
    const preferredId = response.items.find((item) => item.id === currentSelectedId)?.id
      ?? response.items.find((item) => item.id === persistedSelectedId)?.id;

    if (preferredId && preferredId !== currentSelectedId) {
      await get().selectHistoryItem(preferredId);
    } else if (autoSelectFirst && response.items.length > 0 && !get().selectedReport) {
      await get().selectHistoryItem(response.items[0].id);
    }

    return response;
  } catch (error) {
    if (requestId !== historyRequestSeq) {
      return null;
    }
    set({ error: getParsedApiError(error) });
    return null;
  } finally {
    if (requestId === historyRequestSeq) {
      set({
        isLoadingHistory: false,
        isLoadingMore: false,
      });
    }
  }
}

export const useStockPoolStore = create<StockPoolState>((set, get) => ({
  ...initialState,

  setQuery: (query) => {
    set({
      query,
      selectionSource: 'manual',
      inputError: undefined,
      duplicateError: null,
    });
  },

  clearError: () => set({ error: null }),

  clearInlineMessages: () => set({ inputError: undefined, duplicateError: null }),

  openMarkdownDrawer: () => set({ markdownDrawerOpen: true }),

  closeMarkdownDrawer: () => set({ markdownDrawerOpen: false }),

  loadInitialHistory: async () => {
    await fetchHistory(get, set, { autoSelectFirst: true, reset: true });
  },

  refreshHistory: async (silent = false) => {
    await fetchHistory(get, set, { reset: true, silent });
  },

  hydrateRecentTasks: async () => {
    try {
      const response = await analysisApi.getTasks({ limit: MAX_RECENT_TASKS });
      const hydrated = sortTasksByPriority((response.tasks || []).map((task) => ({
        ...task,
        updatedAt: task.updatedAt || task.completedAt || task.startedAt || task.createdAt,
      })));
      persistTasks(hydrated);
      set({ activeTasks: hydrated });
    } catch {
      const persisted = sortTasksByPriority(readPersistedTasks());
      persistTasks(persisted);
      set({ activeTasks: persisted });
    }
  },

  loadMoreHistory: async () => {
    const state = get();
    if (state.isLoadingMore || !state.hasMore) {
      return;
    }
    await fetchHistory(get, set, { reset: false });
  },

  selectHistoryItem: async (recordId) => {
    const requestId = ++reportRequestSeq;
    const shouldShowInitialLoading = !get().selectedReport;

    if (shouldShowInitialLoading) {
      set({ isLoadingReport: true });
    }

    try {
      const report = await historyApi.getDetail(recordId);
      if (requestId !== reportRequestSeq) {
        return;
      }

      set({
        selectedReport: report,
        error: null,
        isLoadingReport: false,
      });
      persistSelectedHistoryId(report.meta.id ?? recordId);
    } catch (error) {
      if (requestId !== reportRequestSeq) {
        return;
      }

      set({
        error: getParsedApiError(error),
        isLoadingReport: false,
      });
    }
  },

  toggleHistorySelection: (recordId) => {
    const selected = new Set(get().selectedHistoryIds);
    if (selected.has(recordId)) {
      selected.delete(recordId);
    } else {
      selected.add(recordId);
    }

    set({ selectedHistoryIds: Array.from(selected) });
  },

  toggleSelectAllVisible: () => {
    const visibleIds = get().historyItems.map((item) => item.id);
    const selectedIds = get().selectedHistoryIds;
    const visibleSet = new Set(visibleIds);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

    set({
      selectedHistoryIds: allSelected
        ? selectedIds.filter((id) => !visibleSet.has(id))
        : Array.from(new Set([...selectedIds, ...visibleIds])),
    });
  },

  deleteSelectedHistory: async () => {
    const state = get();
    const recordIds = Array.from(new Set(state.selectedHistoryIds));
    if (recordIds.length === 0 || state.isDeletingHistory) {
      return;
    }

    set({ isDeletingHistory: true });
    try {
      await historyApi.deleteRecords(recordIds);

      const deletedIds = new Set(recordIds);
      const selectedWasDeleted = state.selectedReport?.meta.id !== undefined
        && deletedIds.has(state.selectedReport.meta.id);

      set({ selectedHistoryIds: [] });

      const freshPage = await fetchHistory(get, set, { reset: true });

      if (selectedWasDeleted) {
        const nextItem = freshPage?.items?.[0];
        if (nextItem) {
          await get().selectHistoryItem(nextItem.id);
        } else {
          set({ selectedReport: null });
          persistSelectedHistoryId(null);
        }
      }
    } catch (error) {
      set({ error: getParsedApiError(error) });
    } finally {
      set({ isDeletingHistory: false });
    }
  },

  submitAnalysis: async (options) => {
    const state = get();
    const rawStockCode = options?.stockCode ?? state.query;
    const stockCodeInput = rawStockCode.trim();
    const stockName = options?.stockName;
    const selectionSource = options?.selectionSource ?? state.selectionSource;
    const originalQuery = (options?.originalQuery ?? state.query).trim();

    if (!stockCodeInput) {
      set({ inputError: translateForCurrentLanguage('home.inputRequired'), duplicateError: null });
      return;
    }

    if (selectionSource !== 'autocomplete' && isObviouslyInvalidStockQuery(stockCodeInput)) {
      set({ inputError: translateForCurrentLanguage('home.invalidInput'), duplicateError: null });
      return;
    }

    let normalizedStockCode = stockCodeInput;
    if (selectionSource === 'autocomplete' || looksLikeStockCode(stockCodeInput)) {
      const { valid, message, normalized } = validateStockCode(stockCodeInput);
      if (!valid) {
        set({ inputError: message, duplicateError: null });
        return;
      }
      normalizedStockCode = normalized;
    }

    set({
      inputError: undefined,
      duplicateError: null,
      error: null,
      isAnalyzing: true,
    });

    const requestId = ++analyzeRequestSeq;
    try {
      const response = await analysisApi.analyzeAsync({
        stockCode: normalizedStockCode,
        reportType: 'detailed',
        stockName,
        originalQuery: originalQuery || stockCodeInput,
        selectionSource,
      });

      if (requestId !== analyzeRequestSeq) {
        return;
      }

      if ('taskId' in response) {
        get().syncTaskCreated({
          taskId: response.taskId,
          stockCode: normalizedStockCode,
          stockName,
          status: response.status,
          progress: 0,
          message: response.message || translateForCurrentLanguage('tasks.submitted'),
          reportType: 'detailed',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          originalQuery: originalQuery || stockCodeInput,
          selectionSource,
        });
      }

      set({
        query: '',
        selectionSource: 'manual',
      });
    } catch (error) {
      if (requestId !== analyzeRequestSeq) {
        return;
      }

      if (error instanceof DuplicateTaskError) {
        set({
          duplicateError: translateForCurrentLanguage('home.duplicateTask', { stockCode: error.stockCode }),
        });
        return;
      }

      set({ error: getParsedApiError(error) });
    } finally {
      if (requestId === analyzeRequestSeq) {
        set({ isAnalyzing: false });
      }
    }
  },

  focusLatestHistoryForStock: async (stockCode) => {
    try {
      const response = await historyApi.getList(buildHistoryParams(1));
      const visibleIds = new Set(response.items.map((item) => item.id));

      set({
        historyItems: response.items,
        currentPage: 1,
        hasMore: response.items.length < response.total,
        selectedHistoryIds: get().selectedHistoryIds.filter((id) => visibleIds.has(id)),
      });

      const latestMatch = response.items.find((item) => isSameStockCode(item.stockCode, stockCode));
      if (!latestMatch) {
        return null;
      }

      await get().selectHistoryItem(latestMatch.id);
      set({ highlightedHistoryId: latestMatch.id, error: null });
      return latestMatch.id;
    } catch (error) {
      set({ error: getParsedApiError(error) });
      return null;
    }
  },

  clearHighlightedHistory: () => set({ highlightedHistoryId: null }),

  syncTaskCreated: (task) => {
    if (dismissedTaskIds.has(task.taskId)) {
      return;
    }
    const nextTasks = upsertTask(get().activeTasks, task);
    persistTasks(nextTasks);
    set({ activeTasks: nextTasks });
  },

  syncTaskUpdated: (task) => {
    if (dismissedTaskIds.has(task.taskId)) {
      return;
    }
    const index = get().activeTasks.findIndex((item) => item.taskId === task.taskId);
    if (index < 0) {
      return;
    }
    const nextTasks = upsertTask(get().activeTasks, task);
    persistTasks(nextTasks);
    set({ activeTasks: nextTasks });
  },

  syncTaskFailed: (task) => {
    get().syncTaskUpdated(task);
    set({ error: getParsedApiError(task.error || '分析失败') });
  },

  removeTask: (taskId) => {
    dismissedTaskIds.add(taskId);
    const nextTasks = get().activeTasks.filter((task) => task.taskId !== taskId);
    persistTasks(nextTasks);
    set({ activeTasks: nextTasks });
  },

  resetDashboardState: () => {
    historyRequestSeq += 1;
    reportRequestSeq = 0;
    analyzeRequestSeq = 0;
    dismissedTaskIds.clear();
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(TASK_QUEUE_STORAGE_KEY);
    }
    set({ ...initialState });
  },
}));
