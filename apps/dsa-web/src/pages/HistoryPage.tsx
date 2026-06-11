import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { historyApi } from '../api/history';
import type { HistorySortBy, HistorySortOrder } from '../api/history';
import { getParsedApiError } from '../api/error';
import type { ParsedApiError } from '../api/error';
import { ApiErrorAlert, AppPage, EmptyState, Loading, PageHeader, Pagination } from '../components/common';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { HistoryItem } from '../types/analysis';
import { formatDateTime, getTodayInShanghai } from '../utils/format';

const PAGE_SIZE = 20;

type SortKey = HistorySortBy;
type SortDir = HistorySortOrder;

function SentimentBadge({ score }: { score?: number }) {
  if (score == null) return <span className="text-muted-text">--</span>;
  const color =
    score >= 70 ? 'text-success bg-success/10' :
    score >= 40 ? 'text-warning bg-warning/10' :
    'text-danger bg-danger/10';
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {score}
    </span>
  );
}

export default function HistoryPage() {
  const { t } = useUiLanguage();

  const [date, setDate] = useState(getTodayInShanghai);
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const requestIdRef = useRef(0);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadHistory = useCallback(async (targetDate: string, targetPage: number, sortBy: SortKey, sortOrder: SortDir) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const response = await historyApi.getList({
        startDate: targetDate,
        endDate: targetDate,
        page: targetPage,
        limit: PAGE_SIZE,
        sortBy,
        sortOrder,
      });
      if (requestId !== requestIdRef.current) return;
      setItems(response.items);
      setTotal(response.total);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setItems([]);
      setTotal(0);
      setError(getParsedApiError(err));
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadHistory(date, page, sortKey, sortDir);
  }, [date, page, sortKey, sortDir, loadHistory]);

  const handleDateChange = useCallback((value: string) => {
    if (!value) return;
    setDate(value);
    setPage(1);
  }, []);

  const handleSort = useCallback((key: SortKey) => {
    setSortKey((prevKey) => {
      if (prevKey !== key) {
        setSortDir('desc');
      } else {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      }
      return key;
    });
    setPage(1);
  }, []);

  const renderSortIcon = (key: SortKey) => {
    if (sortKey !== key) return <ArrowUpDown className="ml-1 inline h-3 w-3 opacity-40" />;
    return sortDir === 'asc'
      ? <ArrowUp className="ml-1 inline h-3 w-3 text-primary" />
      : <ArrowDown className="ml-1 inline h-3 w-3 text-primary" />;
  };

  return (
    <AppPage>
      <PageHeader
        title={t('history.page.title')}
        description={t('history.page.description')}
      />

      <div className="mb-4 flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-secondary-text">
          {t('history.page.dateLabel')}
          <input
            type="date"
            value={date}
            onChange={(e) => handleDateChange(e.target.value)}
            className="rounded-lg border border-border/60 bg-elevated px-3 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        </label>
        {!loading && (
          <span className="text-xs text-muted-text">
            {total} {total === 1 ? 'record' : 'records'}
          </span>
        )}
      </div>

      {error && <ApiErrorAlert error={error} className="mb-4" />}

      {loading ? (
        <Loading />
      ) : items.length === 0 ? (
        <EmptyState
          title={t('history.page.noResults')}
          description={t('history.page.noResultsDescription')}
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-border/60">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/40 bg-elevated/50 text-left text-xs text-secondary-text">
                  <th className="whitespace-nowrap px-4 py-3 font-medium">{t('history.page.stockName')}</th>
                  <th
                    className="whitespace-nowrap px-4 py-3 font-medium cursor-pointer select-none hover:text-foreground"
                    onClick={() => handleSort('sentiment_score')}
                  >
                    {t('history.page.sentimentScore')}
                    {renderSortIcon('sentiment_score')}
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">{t('history.page.operationAdvice')}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">{t('history.page.trendPrediction')}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">{t('history.page.timeSensitivity')}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium text-right">{t('history.page.idealBuy')}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium text-right">{t('history.page.secondaryBuy')}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium text-right">{t('history.page.stopLoss')}</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium text-right">{t('history.page.takeProfit')}</th>
                  <th
                    className="whitespace-nowrap px-4 py-3 font-medium cursor-pointer select-none hover:text-foreground"
                    onClick={() => handleSort('created_at')}
                  >
                    {t('history.page.createdAt')}
                    {renderSortIcon('created_at')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.id}
                    className="border-b border-border/20 transition-colors hover:bg-hover/50"
                  >
                    <td className="whitespace-nowrap px-4 py-3">
                      <div className="font-medium text-foreground">{item.stockName || '--'}</div>
                      <div className="text-xs text-muted-text">{item.stockCode}</div>
                    </td>
                    <td className="px-4 py-3">
                      <SentimentBadge score={item.sentimentScore} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-secondary-text">
                      {item.operationAdvice || item.actionLabel || '--'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-secondary-text">
                      {item.trendPrediction || '--'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-secondary-text">
                      {item.timeSensitivity || '--'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-secondary-text">
                      {item.idealBuy ?? '--'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-secondary-text">
                      {item.secondaryBuy ?? '--'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-secondary-text">
                      {item.stopLoss ?? '--'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-secondary-text">
                      {item.takeProfit ?? '--'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-text">
                      {item.createdAt ? formatDateTime(item.createdAt) : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={setPage}
              className="mt-4"
            />
          )}
        </>
      )}
    </AppPage>
  );
}
