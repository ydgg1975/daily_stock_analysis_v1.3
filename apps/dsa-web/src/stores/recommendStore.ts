import { create } from 'zustand';
import { recommendationApi } from '../api/recommendation';
import type {
  RecommendationResult,
  RecommendTaskStatus,
  RecommendHistoryItem,
} from '../types/recommendation';

interface RecommendState {
  // Form state
  markets: string[];
  priceMin: string;
  priceMax: string;
  urls: string[];
  note: string;
  files: File[];

  // Task state
  taskId: string | null;
  taskStatus: RecommendTaskStatus | null;
  submitting: boolean;
  polling: boolean;

  // Result
  result: RecommendationResult | null;

  // History
  history: RecommendHistoryItem[];
  historyTotal: number;
  historyLoading: boolean;

  // Error
  error: string | null;
}

interface RecommendActions {
  setMarkets: (markets: string[]) => void;
  setPriceMin: (v: string) => void;
  setPriceMax: (v: string) => void;
  setUrls: (urls: string[]) => void;
  setNote: (note: string) => void;
  setFiles: (files: File[]) => void;
  clearError: () => void;
  resetForm: () => void;

  submit: () => Promise<void>;
  pollStatus: () => Promise<void>;
  stopPolling: () => void;
  loadHistory: (limit?: number, offset?: number) => Promise<void>;
}

let pollingTimer: ReturnType<typeof setInterval> | null = null;

export const useRecommendStore = create<RecommendState & RecommendActions>((set, get) => ({
  // Initial state
  markets: ['a_share'],
  priceMin: '',
  priceMax: '',
  urls: [''],
  note: '',
  files: [],

  taskId: null,
  taskStatus: null,
  submitting: false,
  polling: false,

  result: null,

  history: [],
  historyTotal: 0,
  historyLoading: false,

  error: null,

  // Form actions
  setMarkets: (markets) => set({ markets }),
  setPriceMin: (v) => set({ priceMin: v }),
  setPriceMax: (v) => set({ priceMax: v }),
  setUrls: (urls) => set({ urls }),
  setNote: (note) => set({ note }),
  setFiles: (files) => set({ files }),
  clearError: () => set({ error: null }),
  resetForm: () =>
    set({
      markets: ['a_share'],
      priceMin: '',
      priceMax: '',
      urls: [''],
      note: '',
      files: [],
      taskId: null,
      taskStatus: null,
      result: null,
      error: null,
      submitting: false,
      polling: false,
    }),

  // Submit recommendation request
  submit: async () => {
    const { markets, priceMin, priceMax, urls, note, files } = get();
    if (markets.length === 0) {
      set({ error: '请至少选择一个市场' });
      return;
    }

    set({ submitting: true, error: null, result: null, taskStatus: null });

    try {
      const formData = new FormData();
      formData.append('markets', markets.join(','));
      if (priceMin) formData.append('price_min', priceMin);
      if (priceMax) formData.append('price_max', priceMax);

      const filteredUrls = urls.filter((u) => u.trim());
      if (filteredUrls.length > 0) {
        formData.append('urls', JSON.stringify(filteredUrls));
      }
      if (note.trim()) {
        formData.append('note', note.trim());
      }
      for (const file of files) {
        formData.append('files', file);
      }

      const resp = await recommendationApi.submit(formData);
      set({ taskId: resp.taskId, submitting: false });

      // Start polling
      get().pollStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '提交失败';
      set({ error: msg, submitting: false });
    }
  },

  // Poll task status
  pollStatus: async () => {
    const { taskId } = get();
    if (!taskId) return;

    set({ polling: true });

    // Clear existing timer
    if (pollingTimer) {
      clearInterval(pollingTimer);
      pollingTimer = null;
    }

    const poll = async () => {
      const currentTaskId = get().taskId;
      if (!currentTaskId) {
        get().stopPolling();
        return;
      }

      try {
        const status = await recommendationApi.getStatus(currentTaskId);
        set({ taskStatus: status });

        if (status.status === 'completed') {
          set({ result: status.result ?? null, polling: false });
          get().stopPolling();
          // Refresh history
          get().loadHistory();
        } else if (status.status === 'failed') {
          set({ error: status.error ?? '推荐任务失败', polling: false });
          get().stopPolling();
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '查询状态失败';
        set({ error: msg, polling: false });
        get().stopPolling();
      }
    };

    // Immediate first poll
    await poll();

    // Continue polling if still in progress
    if (get().polling) {
      pollingTimer = setInterval(poll, 3000);
    }
  },

  stopPolling: () => {
    if (pollingTimer) {
      clearInterval(pollingTimer);
      pollingTimer = null;
    }
    set({ polling: false });
  },

  // Load history
  loadHistory: async (limit = 10, offset = 0) => {
    set({ historyLoading: true });
    try {
      const resp = await recommendationApi.getHistory({ limit, offset });
      set({
        history: resp.items,
        historyTotal: resp.total,
        historyLoading: false,
      });
    } catch {
      set({ historyLoading: false });
    }
  },
}));
