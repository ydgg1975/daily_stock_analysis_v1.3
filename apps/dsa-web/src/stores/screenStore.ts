import { create } from 'zustand';
import type { ScreenResultRow } from '../api/screen';

export type SortDirection = 'asc' | 'desc';

interface ScreenState {
  // 输入框内容（跨路由保留，方便用户返回后继续编辑）
  input: string;
  // 末次查询文本（用于结果区显示 "查询：xxx"）
  lastQuery: string;
  // 选股结果
  rows: ScreenResultRow[];
  resultsCount: number;
  returnedCount: number;
  // 空态/错误提示
  emptyMessage: string | null;
  // 分页
  currentPage: number;
  // 排序
  sortKey: string | null;
  sortDir: SortDirection;

  // Actions
  setInput: (input: string) => void;
  setCurrentPage: (page: number) => void;
  setSort: (key: string | null, dir?: SortDirection) => void;
  setResults: (payload: {
    query: string;
    rows: ScreenResultRow[];
    resultsCount: number;
    returnedCount: number;
    emptyMessage: string | null;
    defaultSortKey?: string | null;
  }) => void;
  clearResults: () => void;
}

export const useScreenStore = create<ScreenState>((set) => ({
  input: '',
  lastQuery: '',
  rows: [],
  resultsCount: 0,
  returnedCount: 0,
  emptyMessage: null,
  currentPage: 1,
  sortKey: null,
  sortDir: 'desc',

  setInput: (input) => set({ input }),
  setCurrentPage: (page) => set({ currentPage: page }),
  setSort: (key, dir = 'desc') => set({ sortKey: key, sortDir: dir, currentPage: 1 }),
  setResults: ({ query, rows, resultsCount, returnedCount, emptyMessage, defaultSortKey }) =>
    set({
      lastQuery: query,
      rows,
      resultsCount,
      returnedCount,
      emptyMessage,
      currentPage: 1,
      sortKey: defaultSortKey ?? null,
      sortDir: 'desc',
    }),
  clearResults: () =>
    set({
      rows: [],
      resultsCount: 0,
      returnedCount: 0,
      lastQuery: '',
      emptyMessage: null,
      currentPage: 1,
      sortKey: null,
      sortDir: 'desc',
    }),
}));

