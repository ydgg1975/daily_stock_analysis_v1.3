import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import {
  ApiErrorAlert,
  Button,
  EmptyState,
  InlineAlert,
  PageHeader,
} from '../components/common';
import { screenApi, type ScreenResultRow } from '../api/screen';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { getParsedApiError, type ParsedApiError } from '../api/error';

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

const ScreenPage: React.FC = () => {
  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [rows, setRows] = useState<ScreenResultRow[]>([]);
  const [lastQuery, setLastQuery] = useState<string>('');
  const [resultsCount, setResultsCount] = useState(0);
  const [returnedCount, setReturnedCount] = useState(0);
  const [emptyMessage, setEmptyMessage] = useState<string | null>(null);
  const [submittingCodes, setSubmittingCodes] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    document.title = 'AI选股 - DSA';
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(id);
  }, [toast]);

  // Column order: keep order of first row's keys
  const columns = useMemo<string[]>(() => {
    if (rows.length === 0) return [];
    return Object.keys(rows[0]);
  }, [rows]);

  const handleSearch = useCallback(
    async (overrideQuery?: string) => {
      const q = (overrideQuery ?? input).trim();
      if (!q || loading) return;

      setLoading(true);
      setError(null);
      setEmptyMessage(null);
      try {
        const resp = await screenApi.query(q);
        setLastQuery(resp.query || q);
        setRows(resp.results || []);
        setResultsCount(resp.resultsCount || 0);
        setReturnedCount(resp.returnedCount || (resp.results?.length ?? 0));
        if (!resp.success) {
          setEmptyMessage(resp.error || resp.message || '选股未返回结果');
        } else if ((resp.results?.length ?? 0) === 0) {
          setEmptyMessage(resp.message || '未找到符合条件的股票');
        }
      } catch (err) {
        setError(getParsedApiError(err));
        setRows([]);
        setResultsCount(0);
        setReturnedCount(0);
      } finally {
        setLoading(false);
      }
    },
    [input, loading],
  );

  const handleQuickQuery = useCallback(
    (q: string) => {
      setInput(q);
      void handleSearch(q);
    },
    [handleSearch],
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

  const handleGoHome = useCallback(() => navigate('/'), [navigate]);

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
                  {columns.map((col) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-left text-xs font-medium text-muted-text whitespace-nowrap"
                    >
                      {col}
                    </th>
                  ))}
                  <th className="sticky right-0 bg-card/95 px-3 py-2 text-right text-xs font-medium text-muted-text whitespace-nowrap">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => {
                  const code = pickField(row, CODE_KEY_CANDIDATES);
                  const submitting = code ? submittingCodes.has(code) : false;
                  return (
                    <tr
                      key={idx}
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

        {/* Footer hint */}
        {rows.length > 0 ? (
          <div className="mt-2 flex items-center justify-between text-xs text-muted-text">
            <span>提示：点击"分析"按钮即可为该股票提交深度分析任务</span>
            <button
              type="button"
              onClick={handleGoHome}
              className="text-primary hover:underline"
            >
              前往首页查看分析进度 →
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default ScreenPage;
