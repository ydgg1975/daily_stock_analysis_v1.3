import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, Sparkles } from 'lucide-react';
import {
  ApiErrorAlert,
  Button,
  EmptyState,
  InlineAlert,
  PageHeader,
  Pagination,
} from '../components/common';
import { screenApi, type ScreenResultRow } from '../api/screen';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { useScreenStore } from '../stores/screenStore';

const QUICK_QUERIES: string[] = [
  '今天涨幅超过5%的A股',
  '市盈率低于20且市值大于500亿的A股',
  '最近5日连续上涨的股票',
  '今日成交额排名前20的A股',
];

// Known field keys to detect stock code / name columns from MiaoXiang response.
const CODE_KEY_CANDIDATES = [
  '证券代码',
  '股票代码',
  '代码',
  'SECURITY_CODE',
  'StockCode',
];
const NAME_KEY_CANDIDATES = [
  '证券简称',
  '股票简称',
  '名称',
  '简称',
  'SECURITY_SHORT_NAME',
  'StockName',
];

// Columns hidden from the result table (internal IDs / redundant metadata).
const HIDDEN_COLUMNS = new Set<string>([
  '市场代码简称',
  'choiceInnerCode',
  'inOptional',
]);

// Front-end pagination page size for the result table.
const PAGE_SIZE = 20;

function pickField(row: ScreenResultRow, candidates: string[]): string | undefined {
  for (const key of candidates) {
    if (key in row && row[key]) return row[key];
  }
  // Fuzzy: contains keyword
  for (const key of Object.keys(row)) {
    for (const cand of candidates) {
      if (key.includes(cand) || key.toLowerCase().includes(cand.toLowerCase())) {
        if (row[key]) return row[key];
      }
    }
  }
  return undefined;
}

// 尝试把 "2058.42亿" / "3692.10万" / "-3.71" / "19.96" / "87.10%" 解析为纯数值，
// 便于数字列按大小排序；无法解析返回 null，回退到字符串比较。
function parseNumeric(raw: unknown): number | null {
  if (raw == null) return null;
  const s = String(raw).trim();
  if (!s || s === '-' || s === '--') return null;
  const match = s.match(/^(-?[\d,]+(?:\.\d+)?)\s*([亿万%]?)$/);
  if (match) {
    const base = parseFloat(match[1].replace(/,/g, ''));
    if (Number.isNaN(base)) return null;
    if (match[2] === '亿') return base * 1e8;
    if (match[2] === '万') return base * 1e4;
    return base;
  }
  const n = parseFloat(s);
  return Number.isNaN(n) ? null : n;
}

// 在可见列中找到包含"涨跌幅"的列名，作为默认排序列。
function findChangePercentColumn(cols: string[]): string | null {
  return cols.find((c) => c.includes('涨跌幅')) ?? null;
}

// 从列名末尾剥离时间戳后缀（HH:MM[:SS] / YYYYMMDD），
// 返回 { displayName, date, time }，用于把时间集中展示在 meta 区域。
function stripColumnTimestamp(col: string): {
  displayName: string;
  date: string | null;
  time: string | null;
} {
  let name = col;
  let time: string | null = null;
  let date: string | null = null;

  const timeMatch = name.match(/^(.*?)(\d{1,2}:\d{2}(?::\d{2})?)\s*$/);
  if (timeMatch) {
    name = timeMatch[1];
    time = timeMatch[2];
  }
  const dateMatch = name.match(/^(.*?)(\d{8})\s*$/);
  if (dateMatch) {
    name = dateMatch[1];
    const raw = dateMatch[2];
    date = `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
  }
  return { displayName: name.trim() || col, date, time };
}

// 汇总列名中的时间戳为统一的 meta 字符串：优先 "YYYY-MM-DD HH:MM[:SS]"。
function aggregateTimestamp(cols: string[]): string | null {
  let maxDate: string | null = null;
  let maxTime: string | null = null;
  for (const c of cols) {
    const { date, time } = stripColumnTimestamp(c);
    if (date && (!maxDate || date > maxDate)) maxDate = date;
    if (time && (!maxTime || time > maxTime)) maxTime = time;
  }
  if (maxDate && maxTime) return `${maxDate} ${maxTime}`;
  if (maxDate) return maxDate;
  if (maxTime) return maxTime;
  return null;
}

const ScreenPage: React.FC = () => {
  // 跨路由保留的选股状态（来自全局 store）
  const input = useScreenStore((s) => s.input);
  const setInput = useScreenStore((s) => s.setInput);
  const rows = useScreenStore((s) => s.rows);
  const lastQuery = useScreenStore((s) => s.lastQuery);
  const resultsCount = useScreenStore((s) => s.resultsCount);
  const returnedCount = useScreenStore((s) => s.returnedCount);
  const emptyMessage = useScreenStore((s) => s.emptyMessage);
  const currentPage = useScreenStore((s) => s.currentPage);
  const setCurrentPage = useScreenStore((s) => s.setCurrentPage);
  const sortKey = useScreenStore((s) => s.sortKey);
  const sortDir = useScreenStore((s) => s.sortDir);
  const setSort = useScreenStore((s) => s.setSort);
  const setResults = useScreenStore((s) => s.setResults);
  const clearResults = useScreenStore((s) => s.clearResults);

  // 仅当前页会话的瞬态状态
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [submittingCodes, setSubmittingCodes] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    document.title = 'AI选股 - DSA';
  }, []);

  // 若已有结果但尚未设置排序列（例如历史状态未带默认），自动按涨跌幅降序兜底
  useEffect(() => {
    if (!sortKey && rows.length > 0) {
      const cols = Object.keys(rows[0]).filter((k) => !HIDDEN_COLUMNS.has(k));
      const fallback = findChangePercentColumn(cols);
      if (fallback) setSort(fallback, 'desc');
    }
  }, [sortKey, rows, setSort]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(id);
  }, [toast]);

  // Column order: keep order of first row's keys, excluding hidden internal columns.
  // 额外规则：将"流通市值"列与"证券类型"列位置互换（若两者都存在）。
  const columns = useMemo<string[]>(() => {
    if (rows.length === 0) return [];
    const base = Object.keys(rows[0]).filter((key) => !HIDDEN_COLUMNS.has(key));
    const liuTongIdx = base.findIndex((c) => c.includes('流通市值'));
    const typeIdx = base.findIndex((c) => c.includes('证券类型'));
    if (liuTongIdx !== -1 && typeIdx !== -1) {
      [base[liuTongIdx], base[typeIdx]] = [base[typeIdx], base[liuTongIdx]];
    }
    return base;
  }, [rows]);

  // 去除列名末尾时间戳后的"显示名"映射：原始列名 -> 去时间戳后的标题。
  const columnDisplayNames = useMemo<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    for (const c of columns) map[c] = stripColumnTimestamp(c).displayName;
    return map;
  }, [columns]);

  // 汇总到 meta 区域显示的统一时间戳。
  const dataTimestamp = useMemo<string | null>(() => aggregateTimestamp(columns), [columns]);

  // 对 rows 按 sortKey + sortDir 排序：数字列按数值，其它按 localeCompare。
  const sortedRows = useMemo<ScreenResultRow[]>(() => {
    if (!sortKey || rows.length === 0) return rows;
    const dirFactor = sortDir === 'asc' ? 1 : -1;
    const arr = [...rows];
    arr.sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      const na = parseNumeric(va);
      const nb = parseNumeric(vb);
      if (na !== null && nb !== null) return (na - nb) * dirFactor;
      // 只有一侧能解析为数字 → 数字永远排前面（desc 时放前，asc 时放后）
      if (na !== null) return -1 * dirFactor;
      if (nb !== null) return 1 * dirFactor;
      const sa = va == null ? '' : String(va);
      const sb = vb == null ? '' : String(vb);
      return sa.localeCompare(sb, 'zh-Hans-CN') * dirFactor;
    });
    return arr;
  }, [rows, sortKey, sortDir]);

  // Front-end pagination derived state.
  const totalPages = Math.max(1, Math.ceil(sortedRows.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const pagedRows = useMemo<ScreenResultRow[]>(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return sortedRows.slice(start, start + PAGE_SIZE);
  }, [sortedRows, safePage]);

  const handleSortColumn = useCallback(
    (col: string) => {
      if (sortKey === col) {
        setSort(col, sortDir === 'desc' ? 'asc' : 'desc');
      } else {
        setSort(col, 'desc');
      }
    },
    [sortKey, sortDir, setSort],
  );

  const handleSearch = useCallback(
    async (overrideQuery?: string) => {
      const q = (overrideQuery ?? input).trim();
      if (!q || loading) return;

      setLoading(true);
      setError(null);
      try {
        const resp = await screenApi.query(q);
        const resultRows = resp.results || [];
        let nextEmpty: string | null = null;
        if (!resp.success) {
          nextEmpty = resp.error || resp.message || '选股未返回结果';
        } else if (resultRows.length === 0) {
          nextEmpty = resp.message || '未找到符合条件的股票';
        }
        // 默认按"涨跌幅"列降序（若列存在）
        const visibleCols =
          resultRows.length > 0
            ? Object.keys(resultRows[0]).filter((k) => !HIDDEN_COLUMNS.has(k))
            : [];
        const defaultSortKey = findChangePercentColumn(visibleCols);
        setResults({
          query: resp.query || q,
          rows: resultRows,
          resultsCount: resp.resultsCount || 0,
          returnedCount: resp.returnedCount || resultRows.length,
          emptyMessage: nextEmpty,
          defaultSortKey,
        });
      } catch (err) {
        setError(getParsedApiError(err));
        clearResults();
      } finally {
        setLoading(false);
      }
    },
    [input, loading, setResults, clearResults],
  );

  const handleQuickQuery = useCallback(
    (q: string) => {
      setInput(q);
      void handleSearch(q);
    },
    [handleSearch, setInput],
  );

  const handleAnalyze = useCallback(
    async (row: ScreenResultRow) => {
      const code = pickField(row, CODE_KEY_CANDIDATES);
      const name = pickField(row, NAME_KEY_CANDIDATES);
      if (!code) {
        setToast({ type: 'error', text: '未识别到股票代码，无法分析' });
        return;
      }

      setSubmittingCodes((prev) => new Set(prev).add(code));
      try {
        await analysisApi.analyzeAsync({
          stockCode: code,
          stockName: name,
          reportType: 'detailed',
          originalQuery: lastQuery || input,
          selectionSource: 'manual',
          notify: true,
        });
        setToast({ type: 'success', text: `已提交 ${name || code} 分析任务，可在首页查看进度` });
      } catch (err) {
        if (err instanceof DuplicateTaskError) {
          setToast({ type: 'error', text: `${name || code} 正在分析中，请稍候` });
        } else {
          const parsed = getParsedApiError(err);
          setToast({ type: 'error', text: parsed.message || '提交分析任务失败' });
        }
      } finally {
        setSubmittingCodes((prev) => {
          const next = new Set(prev);
          next.delete(code);
          return next;
        });
      }
    },
    [input, lastQuery],
  );

  return (
    <div
      data-testid="screen-page"
      className="flex h-[calc(100vh-5rem)] w-full flex-col overflow-hidden sm:h-[calc(100vh-5.5rem)] lg:h-[calc(100vh-2rem)]"
    >
      <div className="flex flex-1 flex-col min-h-0 min-w-0 max-w-full lg:max-w-6xl mx-auto w-full px-3 py-3 md:px-4 md:py-4">
        <PageHeader
          title="AI选股"
          description="基于东方财富妙想智能选股API，用一句话筛选 A股 / 港股 / 美股 / 板块 / ETF。选出的股票可一键提交分析。"
        />

        {/* Input row */}
        <div className="mt-4 flex flex-wrap items-center gap-2.5 md:flex-nowrap">
          <div className="relative min-w-0 flex-1">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !loading && input.trim()) {
                  e.preventDefault();
                  void handleSearch();
                }
              }}
              placeholder='例如：今天涨幅超过5%的A股 / 市盈率低于20的沪深300成分股'
              disabled={loading}
              className="input-surface input-focus-glow h-10 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            />
          </div>
          <button
            type="button"
            onClick={() => void handleSearch()}
            disabled={!input.trim() || loading}
            className="btn-primary flex h-10 flex-shrink-0 items-center gap-1.5 whitespace-nowrap"
          >
            {loading ? (
              <>
                <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                选股中
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                选股
              </>
            )}
          </button>
        </div>

        {/* Quick queries */}
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="text-xs text-muted-text font-medium uppercase tracking-wider mt-1.5">
            快捷条件
          </span>
          {QUICK_QUERIES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => handleQuickQuery(q)}
              disabled={loading}
              className="rounded-full border border-subtle bg-surface/60 px-3 py-1 text-xs text-secondary-text transition-colors hover:border-subtle-hover hover:text-foreground disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Error */}
        {error ? (
          <div className="mt-3">
            <ApiErrorAlert error={error} />
          </div>
        ) : null}

        {/* Toast */}
        {toast ? (
          <div className="mt-3">
            <InlineAlert
              variant={toast.type === 'success' ? 'success' : 'danger'}
              message={toast.text}
            />
          </div>
        ) : null}

        {/* Meta info */}
        {lastQuery && !error ? (
          <div className="mt-3 text-xs text-secondary-text">
            查询：<span className="text-foreground">{lastQuery}</span>
            {resultsCount > 0 ? (
              <span className="ml-3">
                共 {resultsCount} 条{returnedCount < resultsCount ? `，显示前 ${returnedCount} 条` : ''}
              </span>
            ) : null}
            {dataTimestamp ? (
              <span className="ml-3">
                数据时间：<span className="text-foreground">{dataTimestamp}</span>
              </span>
            ) : null}
          </div>
        ) : null}

        {/* Results */}
        <div className="mt-3 flex-1 min-h-0 overflow-auto rounded-xl border border-subtle bg-surface/40">
          {rows.length === 0 ? (
            <div className="flex h-full items-center justify-center p-8">
              <EmptyState
                title={emptyMessage || '输入条件开始智能选股'}
                description={
                  emptyMessage
                    ? '请调整条件或检查 MX_APIKEY 是否正确配置（设置页 → 数据源）'
                    : '支持自然语言描述条件，如 "今天涨幅超过5%的A股"'
                }
              />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm">
                <tr className="border-b border-subtle">
                  {columns.map((col) => {
                    const active = sortKey === col;
                    const SortIcon = active
                      ? sortDir === 'asc'
                        ? ArrowUp
                        : ArrowDown
                      : ArrowUpDown;
                    return (
                      <th
                        key={col}
                        scope="col"
                        className={`px-3 py-2 text-left text-xs font-medium whitespace-nowrap ${
                          active ? 'text-foreground' : 'text-muted-text'
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => handleSortColumn(col)}
                          className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
                          aria-label={`按 ${col} 排序`}
                          aria-sort={
                            active
                              ? sortDir === 'asc'
                                ? 'ascending'
                                : 'descending'
                              : 'none'
                          }
                        >
                          <span>{columnDisplayNames[col] ?? col}</span>
                          <SortIcon
                            className={`h-3 w-3 ${active ? 'opacity-100' : 'opacity-40'}`}
                          />
                        </button>
                      </th>
                    );
                  })}
                  <th className="sticky right-0 bg-card/95 px-3 py-2 text-right text-xs font-medium text-muted-text whitespace-nowrap">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {pagedRows.map((row, idx) => {
                  const code = pickField(row, CODE_KEY_CANDIDATES);
                  const submitting = code ? submittingCodes.has(code) : false;
                  return (
                    <tr
                      key={`${safePage}-${idx}`}
                      className="border-b border-subtle/60 hover:bg-hover/50 transition-colors"
                    >
                      {columns.map((col) => (
                        <td key={col} className="px-3 py-2 whitespace-nowrap text-foreground">
                          {row[col] || '-'}
                        </td>
                      ))}
                      <td className="sticky right-0 bg-card/95 px-3 py-2 text-right whitespace-nowrap">
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={!code || submitting}
                          onClick={() => void handleAnalyze(row)}
                        >
                          {submitting ? '提交中' : '分析'}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {rows.length > PAGE_SIZE ? (
          <div className="mt-3">
            <Pagination
              currentPage={safePage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
            />
            <p className="mt-1 text-center text-xs text-muted-text">
              共 {rows.length} 条 · 第 {safePage} / {totalPages} 页
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default ScreenPage;
