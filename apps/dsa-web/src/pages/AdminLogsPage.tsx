import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminLogsApi, type ExecutionLogSessionDetail, type ExecutionLogSessionSummary } from '../api/adminLogs';
import { useI18n } from '../contexts/UiLanguageContext';
import { ApiErrorAlert } from '../components/common';
import type { ParsedApiError } from '../api/error';

const ADMIN_UNLOCK_TOKEN_STORAGE_KEY = 'dsa-admin-settings-unlock-token';
const ADMIN_UNLOCK_EXPIRES_AT_STORAGE_KEY = 'dsa-admin-settings-unlock-expires-at';

function getAdminUnlockToken(): string | null {
  const token = window.sessionStorage.getItem(ADMIN_UNLOCK_TOKEN_STORAGE_KEY);
  const expiresAtRaw = window.sessionStorage.getItem(ADMIN_UNLOCK_EXPIRES_AT_STORAGE_KEY);
  if (!token || !expiresAtRaw) {
    return null;
  }
  const expiresAt = Number(expiresAtRaw);
  if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
    return null;
  }
  return token;
}

const STATUS_CLASS: Record<string, string> = {
  running: 'theme-log-status theme-log-status--running',
  completed: 'theme-log-status theme-log-status--success',
  failed: 'theme-log-status theme-log-status--danger',
  success: 'theme-log-status theme-log-status--success',
  partial_success: 'theme-log-status theme-log-status--warning',
  timeout_unknown: 'theme-log-status theme-log-status--warning',
  not_configured: 'theme-log-status',
  failed_runtime: 'theme-log-status theme-log-status--danger',
  empty_result: 'theme-log-status',
  invalid_response: 'theme-log-status theme-log-status--danger',
  insufficient_fields: 'theme-log-status theme-log-status--warning',
  switched_to_fallback: 'theme-log-status theme-log-status--info',
  succeeded: 'theme-log-status theme-log-status--success',
  timed_out: 'theme-log-status theme-log-status--warning',
};

function sourceText(value?: string | null): string {
  const text = String(value || '').trim();
  return text || '--';
}

function normalizeCategory(value?: string | null): string {
  return String(value || '').trim().toLowerCase();
}

function resolveCategoryLabel(category: string, t: (key: string) => string): string {
  const key = normalizeCategory(category);
  const mapping: Record<string, string> = {
    ai_route: 'adminLogs.category.ai_route',
    ai_model: 'adminLogs.category.ai_model',
    data_market: 'adminLogs.category.data_market',
    data_fundamentals: 'adminLogs.category.data_fundamentals',
    data_news: 'adminLogs.category.data_news',
    data_sentiment: 'adminLogs.category.data_sentiment',
    notification: 'adminLogs.category.notification',
    system: 'adminLogs.category.system',
  };
  return mapping[key] ? t(mapping[key]) : (category || '--');
}

function resolveActionLabel(action: string, t: (key: string) => string): string {
  const key = String(action || '').trim().toLowerCase();
  const mapping: Record<string, string> = {
    selected: 'adminLogs.action.selected',
    attempting: 'adminLogs.action.attempting',
    succeeded: 'adminLogs.action.succeeded',
    failed: 'adminLogs.action.failed',
    timeout: 'adminLogs.action.timeout',
    switched: 'adminLogs.action.switched',
    skipped: 'adminLogs.action.skipped',
    empty_result: 'adminLogs.action.empty_result',
    invalid_response: 'adminLogs.action.invalid_response',
    insufficient_fields: 'adminLogs.action.insufficient_fields',
    completed: 'adminLogs.action.completed',
    unknown: 'adminLogs.action.unknown',
  };
  return mapping[key] ? t(mapping[key]) : (action || '--');
}

const AdminLogsPage: React.FC = () => {
  const { language, t } = useI18n();
  const [stockFilter, setStockFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [keywordFilter, setKeywordFilter] = useState('');
  const [sessions, setSessions] = useState<ExecutionLogSessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExecutionLogSessionDetail | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [detailError, setDetailError] = useState<ParsedApiError | null>(null);
  const adminUnlockToken = useMemo(getAdminUnlockToken, []);

  const loadSessions = useCallback(async () => {
    if (!adminUnlockToken) return;
    setIsLoadingList(true);
    setError(null);
    try {
      const response = await adminLogsApi.listSessions(
        {
          stock: stockFilter.trim() || undefined,
          status: statusFilter.trim() || undefined,
          category: categoryFilter.trim() || undefined,
          provider: keywordFilter.trim() || undefined,
          limit: 100,
        },
        adminUnlockToken,
      );
      setSessions(response.items || []);
      if ((response.items || []).length) {
        setSelectedSessionId((prev) => prev || response.items[0].sessionId);
      }
    } catch (err) {
      setError((err as { parsedError?: ParsedApiError }).parsedError || null);
    } finally {
      setIsLoadingList(false);
    }
  }, [adminUnlockToken, categoryFilter, keywordFilter, statusFilter, stockFilter]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!selectedSessionId || !adminUnlockToken) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setIsLoadingDetail(true);
    setDetailError(null);
    void adminLogsApi.getSessionDetail(selectedSessionId, adminUnlockToken)
      .then((res) => {
        if (!cancelled) setDetail(res);
      })
      .catch((err) => {
        if (!cancelled) {
          setDetailError((err as { parsedError?: ParsedApiError }).parsedError || null);
          setDetail(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [adminUnlockToken, selectedSessionId]);

  if (!adminUnlockToken) {
    return (
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-6 md:px-6">
        <section className="theme-panel-solid rounded-[1rem] border border-border/60 p-4">
          <h1 className="text-lg font-semibold text-foreground">{t('adminLogs.title')}</h1>
          <p className="mt-2 text-sm text-secondary-text">{t('adminLogs.unlockRequired')}</p>
          <Link className="mt-4 inline-flex text-sm font-medium text-accent hover:underline" to="/settings">
            {t('adminLogs.goToSettings')}
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-[1400px] flex-col gap-4 px-4 py-4 md:px-6">
      <section className="theme-panel-solid rounded-[1rem] border border-border/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-foreground">{t('adminLogs.title')}</h1>
            <p className="text-sm text-secondary-text">{t('adminLogs.subtitle')}</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              className="input-surface h-10 rounded-[var(--theme-control-radius)] px-3 text-sm"
              placeholder={t('adminLogs.stockFilter')}
              value={stockFilter}
              onChange={(e) => setStockFilter(e.target.value)}
            />
            <select
              className="input-surface h-10 rounded-[var(--theme-control-radius)] px-3 text-sm"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">{t('adminLogs.allCategory')}</option>
              <option value="ai_route">{t('adminLogs.category.ai_route')}</option>
              <option value="ai_model">{t('adminLogs.category.ai_model')}</option>
              <option value="data_market">{t('adminLogs.category.data_market')}</option>
              <option value="data_fundamentals">{t('adminLogs.category.data_fundamentals')}</option>
              <option value="data_news">{t('adminLogs.category.data_news')}</option>
              <option value="data_sentiment">{t('adminLogs.category.data_sentiment')}</option>
              <option value="notification">{t('adminLogs.category.notification')}</option>
              <option value="system">{t('adminLogs.category.system')}</option>
            </select>
            <input
              className="input-surface h-10 rounded-[var(--theme-control-radius)] px-3 text-sm"
              placeholder={t('adminLogs.keywordFilter')}
              value={keywordFilter}
              onChange={(e) => setKeywordFilter(e.target.value)}
            />
            <select
              className="input-surface h-10 rounded-[var(--theme-control-radius)] px-3 text-sm"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">{t('adminLogs.allStatus')}</option>
              <option value="running">{t('adminLogs.status.running')}</option>
              <option value="completed">{t('adminLogs.status.completed')}</option>
              <option value="failed">{t('adminLogs.status.failed')}</option>
            </select>
            <button
              type="button"
              className="btn-secondary px-3 py-1.5 text-sm"
              onClick={() => void loadSessions()}
              disabled={isLoadingList}
            >
              {isLoadingList ? t('adminLogs.loading') : t('adminLogs.refresh')}
            </button>
          </div>
        </div>
      </section>

      {error ? <ApiErrorAlert error={error} /> : null}

      <section className="grid gap-4 lg:grid-cols-[420px,minmax(0,1fr)]">
        <div className="theme-panel-solid max-h-[72vh] overflow-y-auto rounded-[1rem] border border-border/60 p-3">
          {sessions.length === 0 ? (
            <p className="px-2 py-3 text-sm text-muted-text">{t('adminLogs.noSessions')}</p>
          ) : (
            <div className="space-y-2">
              {sessions.map((item) => {
                const cls = STATUS_CLASS[item.overallStatus] || STATUS_CLASS.running;
                const selected = selectedSessionId === item.sessionId;
                const summary = item.readableSummary || {};
                const notifState = String(summary.notificationClassification || '').trim();
                return (
                  <button
                    key={item.sessionId}
                    type="button"
                    onClick={() => setSelectedSessionId(item.sessionId)}
                    className={`w-full rounded-lg border px-3 py-2 text-left ${selected ? 'border-accent bg-accent/10' : 'border-border/50 bg-muted/10 hover:bg-muted/20'}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-foreground">{item.name || item.code || '--'}</p>
                        <p className="truncate text-xs text-muted-text">{item.sessionId}</p>
                      </div>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] ${cls}`}>
                        {t(`adminLogs.status.${item.overallStatus}`)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-secondary-text">
                      {(item.startedAt && new Date(item.startedAt).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')) || '--'}
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-secondary-text">
                      <span>{t('adminLogs.finalAiModel')}: {summary.finalAiModel || '--'}</span>
                      {summary.aiFallbackUsed ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          {t('adminLogs.badge.aiFallback')}
                        </span>
                      ) : null}
                      {summary.dataFallbackUsed ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          {t('adminLogs.badge.dataFallback')}
                        </span>
                      ) : null}
                      {notifState ? (
                        <span className={`rounded-full px-2 py-0.5 ${STATUS_CLASS[notifState] || STATUS_CLASS.running}`}>
                          {t('adminLogs.notification')}: {t(`adminLogs.status.${notifState}`)}
                        </span>
                      ) : null}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="theme-panel-solid max-h-[72vh] overflow-y-auto rounded-[1rem] border border-border/60 p-4">
          {detailError ? <ApiErrorAlert error={detailError} /> : null}
          {isLoadingDetail ? (
            <p className="text-sm text-muted-text">{t('adminLogs.loading')}</p>
          ) : detail ? (
            <div className="space-y-4">
              {(() => {
                const readable = detail.readableSummary || {};
                const notificationState = String(readable.notificationClassification || '').trim();
                return (
                  <section className="rounded-lg border border-border/60 bg-muted/10 p-3">
                    <h3 className="text-sm font-semibold text-foreground">{t('adminLogs.executiveSummary')}</h3>
                    <div className="mt-2 grid gap-2 text-xs md:grid-cols-2">
                      <p className="text-secondary-text">{t('adminLogs.finalAiModel')}: <span className="text-foreground">{sourceText(readable.finalAiModel)}</span></p>
                      <p className="text-secondary-text">{t('adminLogs.aiAttempts')}: <span className="text-foreground">{String(readable.aiAttemptsCount || 0)}</span></p>
                      <p className="text-secondary-text">{t('adminLogs.finalMarketSource')}: <span className="text-foreground">{sourceText(readable.finalMarketSource)}</span></p>
                      <p className="text-secondary-text">{t('adminLogs.finalFundamentalSource')}: <span className="text-foreground">{sourceText(readable.finalFundamentalSource)}</span></p>
                      <p className="text-secondary-text">{t('adminLogs.finalNewsSource')}: <span className="text-foreground">{sourceText(readable.finalNewsSource)}</span></p>
                      <p className="text-secondary-text">{t('adminLogs.finalSentimentSource')}: <span className="text-foreground">{sourceText(readable.finalSentimentSource)}</span></p>
                      <p className="text-secondary-text">
                        {t('adminLogs.notification')}: <span className="text-foreground">{notificationState ? t(`adminLogs.status.${notificationState}`) : '--'}</span>
                      </p>
                      <p className="text-secondary-text">
                        {t('adminLogs.topFailureReason')}: <span className="text-foreground">{sourceText(readable.topFailureReason)}</span>
                      </p>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      {readable.aiFallbackUsed ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          {t('adminLogs.badge.aiFallback')}
                        </span>
                      ) : null}
                      {readable.dataFallbackUsed ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          {t('adminLogs.badge.dataFallback')}
                        </span>
                      ) : null}
                      {notificationState ? (
                        <span className={`rounded-full px-2 py-0.5 text-[11px] ${STATUS_CLASS[notificationState] || STATUS_CLASS.running}`}>
                          {t(`adminLogs.status.${notificationState}`)}
                        </span>
                      ) : null}
                    </div>
                    {readable.summaryParagraph ? (
                      <p className="mt-2 rounded-md border border-border/40 bg-base/60 px-2.5 py-2 text-xs leading-5 text-secondary-text">
                        {readable.summaryParagraph}
                      </p>
                    ) : null}
                  </section>
                );
              })()}
              <div>
                <h2 className="text-base font-semibold text-foreground">
                  {detail.name || detail.code || '--'}
                </h2>
                <p className="mt-1 text-xs text-muted-text">{detail.sessionId}</p>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                <p className="text-xs text-secondary-text">{t('adminLogs.queryId')}: <span className="text-foreground">{detail.queryId || '--'}</span></p>
                <p className="text-xs text-secondary-text">{t('adminLogs.taskId')}: <span className="text-foreground">{detail.taskId || '--'}</span></p>
              </div>
              <h3 className="text-sm font-semibold text-foreground">{t('adminLogs.systemActionTimeline')}</h3>
              <div className="space-y-2">
                {detail.events.map((event) => {
                  const statusKey = STATUS_CLASS[event.status] ? event.status : (event.status === 'failed' ? 'failed_runtime' : 'running');
                  const category = normalizeCategory(event.category || event.phase);
                  const action = String(event.action || event.step || '--').trim();
                  const outcome = String(event.outcome || '').trim().toLowerCase();
                  const reason = String(event.reason || '').trim();
                  return (
                    <div key={event.id} className="rounded-md border border-border/50 bg-muted/10 px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-border/60 bg-base/60 px-2 py-0.5 text-[11px] font-medium text-foreground">
                          {resolveCategoryLabel(category, t)}
                        </span>
                        <span className="rounded-full border border-border/50 px-2 py-0.5 text-[11px] text-secondary-text">
                          {resolveActionLabel(action, t)}
                        </span>
                        <span className={`rounded-full px-2 py-0.5 text-[11px] ${STATUS_CLASS[statusKey]}`}>{event.status}</span>
                        {outcome ? (
                          <span className="rounded-full border border-border/50 bg-base/60 px-2 py-0.5 text-[11px] text-secondary-text">
                            {t('adminLogs.outcome')}: {t(`adminLogs.outcomeState.${outcome}`)}
                          </span>
                        ) : null}
                        <span className="text-xs text-muted-text">{event.target || '--'}</span>
                      </div>
                      {event.message ? (
                        <p className="mt-1 break-words text-xs text-secondary-text">{event.message}</p>
                      ) : null}
                      {reason ? (
                        <p className="mt-1 break-words text-[11px] text-muted-text">
                          {t('adminLogs.reason')}: {reason}
                        </p>
                      ) : null}
                      <p className="mt-1 text-[11px] text-muted-text">
                        {(event.eventAt && new Date(event.eventAt).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')) || '--'}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-text">{t('adminLogs.selectSession')}</p>
          )}
        </div>
      </section>
    </main>
  );
};

export default AdminLogsPage;
