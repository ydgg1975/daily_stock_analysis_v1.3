import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { scannerApi } from '../api/scanner';
import { ApiErrorAlert, Badge, Button, Card, Pagination, Select, WorkspacePageHeader } from '../components/common';
import { useI18n } from '../contexts/UiLanguageContext';
import type { ScannerCandidate, ScannerRunDetail, ScannerRunHistoryItem } from '../types/scanner';

const HISTORY_PAGE_SIZE = 8;
const PROFILE_DEFAULTS = {
  cn: {
    profile: 'cn_preopen_v1',
    shortlistSize: '5',
    universeLimit: '300',
    detailLimit: '60',
  },
  us: {
    profile: 'us_preopen_v1',
    shortlistSize: '5',
    universeLimit: '180',
    detailLimit: '40',
  },
  hk: {
    profile: 'hk_preopen_v1',
    shortlistSize: '5',
    universeLimit: '120',
    detailLimit: '30',
  },
} as const;

function formatTimestamp(value?: string | null): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function statusVariant(status?: string | null): 'success' | 'warning' | 'danger' | 'history' {
  if (status === 'completed') return 'success';
  if (status === 'empty') return 'warning';
  if (status === 'failed') return 'danger';
  return 'history';
}

function marketVariant(market?: string | null): 'success' | 'info' | 'warning' | 'history' {
  if (market === 'us') return 'success';
  if (market === 'hk') return 'warning';
  if (market === 'cn') return 'info';
  return 'history';
}

function formatPercent(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(1)}%`;
}

function CandidateActionRow({
  candidate,
  onAnalyze,
}: {
  candidate: ScannerCandidate;
  onAnalyze: (candidate: ScannerCandidate) => void;
}) {
  const navigate = useNavigate();
  const { t } = useI18n();

  return (
    <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
      <Button size="sm" className="w-full sm:w-auto" onClick={() => onAnalyze(candidate)}>
        {t('scanner.actionAnalyze')}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="w-full sm:w-auto"
        onClick={() => navigate(`/chat?stock=${encodeURIComponent(candidate.symbol)}&name=${encodeURIComponent(candidate.name)}`)}
      >
        {t('scanner.actionAsk')}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="w-full sm:w-auto"
        onClick={() => navigate('/backtest', { state: { prefillCode: candidate.symbol, prefillName: candidate.name } })}
      >
        {t('scanner.actionBacktest')}
      </Button>
    </div>
  );
}

const UserScannerPage: React.FC = () => {
  const navigate = useNavigate();
  const { t, language } = useI18n();
  const [market, setMarket] = useState<'cn' | 'us' | 'hk'>('cn');
  const [profile, setProfile] = useState('cn_preopen_v1');
  const [shortlistSize, setShortlistSize] = useState('5');
  const [universeLimit, setUniverseLimit] = useState('300');
  const [detailLimit, setDetailLimit] = useState('60');
  const [runDetail, setRunDetail] = useState<ScannerRunDetail | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [historyItems, setHistoryItems] = useState<ScannerRunHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingRun, setIsLoadingRun] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);

  useEffect(() => {
    document.title = t('scanner.documentTitle');
  }, [t]);

  const profileOptions = useMemo(() => (
    market === 'us'
      ? [{ value: 'us_preopen_v1', label: t('scanner.profileOptionUs') }]
      : market === 'hk'
        ? [{ value: 'hk_preopen_v1', label: t('scanner.profileOptionHk') }]
        : [{ value: 'cn_preopen_v1', label: t('scanner.profileOptionCn') }]
  ), [market, t]);

  const universeOptions = useMemo(() => (
    market === 'us'
      ? [
        { value: '120', label: '120' },
        { value: '180', label: '180' },
        { value: '240', label: '240' },
      ]
      : market === 'hk'
        ? [
          { value: '80', label: '80' },
          { value: '120', label: '120' },
          { value: '180', label: '180' },
        ]
      : [
        { value: '200', label: '200 只' },
        { value: '300', label: '300 只' },
        { value: '500', label: '500 只' },
      ]
  ), [market]);

  const detailOptions = useMemo(() => (
    market === 'us'
      ? [
        { value: '30', label: '30' },
        { value: '40', label: '40' },
        { value: '60', label: '60' },
      ]
      : market === 'hk'
        ? [
          { value: '20', label: '20' },
          { value: '30', label: '30' },
          { value: '40', label: '40' },
        ]
      : [
        { value: '40', label: '40 只' },
        { value: '60', label: '60 只' },
        { value: '80', label: '80 只' },
      ]
  ), [market]);

  const selectedMarketCopy = useMemo(() => (
    market === 'us'
      ? {
        subtitle: language === 'en'
          ? 'Run manual scanner sessions under your own account. System watchlists and schedules stay in admin-only operator space.'
          : '以你的个人账户执行手动扫描。系统 watchlist 与调度留在 admin-only operator 空间。',
        runHint: t('scanner.runHintUs'),
        currentRunFallback: t('scanner.currentRunFallbackUs'),
      }
      : market === 'hk'
        ? {
          subtitle: language === 'en'
            ? 'Run personal Hong Kong scanner sessions under your own account. Operator watchlists and schedules remain admin-only.'
            : '以你的个人账户执行港股手动扫描。系统 watchlist 与调度继续保留在 admin-only operator 空间。',
          runHint: t('scanner.runHintHk'),
          currentRunFallback: t('scanner.currentRunFallbackHk'),
        }
      : {
        subtitle: language === 'en'
          ? 'Generate personal scanner runs and keep shortlist history scoped to your own account.'
          : '生成个人扫描结果，并将 shortlist 历史限制在你自己的账户范围内。',
        runHint: t('scanner.runHintCn'),
        currentRunFallback: t('scanner.currentRunFallbackCn'),
      }
  ), [language, market, t]);

  const handleMarketChange = useCallback((nextMarket: string) => {
    const normalizedMarket = nextMarket === 'us' ? 'us' : nextMarket === 'hk' ? 'hk' : 'cn';
    const defaults = PROFILE_DEFAULTS[normalizedMarket];
    setMarket(normalizedMarket);
    setProfile(defaults.profile);
    setShortlistSize(defaults.shortlistSize);
    setUniverseLimit(defaults.universeLimit);
    setDetailLimit(defaults.detailLimit);
  }, []);

  const loadRun = useCallback(async (runId: number) => {
    setIsLoadingRun(true);
    try {
      const response = await scannerApi.getRun(runId);
      setRunDetail(response);
      setSelectedRunId(response.id);
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsLoadingRun(false);
    }
  }, []);

  const fetchHistory = useCallback(async (page = 1, preferredRunId?: number | null) => {
    setIsLoadingHistory(true);
    try {
      const response = await scannerApi.getRuns({
        market,
        profile,
        page,
        limit: HISTORY_PAGE_SIZE,
      });
      setHistoryItems(response.items);
      setHistoryTotal(response.total);
      setHistoryPage(response.page);
      setHistoryError(null);

      const targetRunId = preferredRunId
        || (selectedRunId && response.items.some((item) => item.id === selectedRunId) ? selectedRunId : null)
        || response.items[0]?.id
        || null;
      if (targetRunId && targetRunId !== selectedRunId) {
        void loadRun(targetRunId);
      }
      if (!targetRunId) {
        setRunDetail(null);
        setSelectedRunId(null);
      }
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, [loadRun, market, profile, selectedRunId]);

  useEffect(() => {
    setRunDetail(null);
    setSelectedRunId(null);
  }, [market, profile]);

  useEffect(() => {
    void fetchHistory(1);
  }, [fetchHistory]);

  const handleRun = useCallback(async () => {
    setIsRunning(true);
    try {
      const response = await scannerApi.run({
        market,
        profile,
        shortlistSize: Number.parseInt(shortlistSize, 10),
        universeLimit: Number.parseInt(universeLimit, 10),
        detailLimit: Number.parseInt(detailLimit, 10),
      });
      setRunDetail(response);
      setSelectedRunId(response.id);
      setPageError(null);
      await fetchHistory(1, response.id);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsRunning(false);
    }
  }, [detailLimit, fetchHistory, market, profile, shortlistSize, universeLimit]);

  const handleStartAnalysis = useCallback(async (candidate: ScannerCandidate) => {
    try {
      await analysisApi.analyzeAsync({
        stockCode: candidate.symbol,
        stockName: candidate.name,
        originalQuery: candidate.symbol,
        selectionSource: 'manual',
      });
      navigate('/');
    } catch (error) {
      if (error instanceof DuplicateTaskError) {
        navigate('/');
        return;
      }
      setPageError(getParsedApiError(error));
    }
  }, [navigate]);

  const totalHistoryPages = useMemo(
    () => Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE)),
    [historyTotal],
  );

  return (
    <div className="space-y-6">
      <WorkspacePageHeader
        eyebrow={t('scanner.eyebrow')}
        title={t('scanner.title')}
        description={selectedMarketCopy.subtitle}
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(22rem,0.92fr)]">
          <Card title={t('scanner.runPanelTitle')} subtitle={language === 'en' ? 'My Scanner Run' : '我的扫描运行'}>
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Select
                  label={t('scanner.marketLabel')}
                  value={market}
                  onChange={handleMarketChange}
                  options={[
                    { value: 'cn', label: t('scanner.marketCn') },
                    { value: 'us', label: t('scanner.marketUs') },
                    { value: 'hk', label: t('scanner.marketHk') },
                  ]}
                />
                <Select
                  label={t('scanner.profileLabel')}
                  value={profile}
                  onChange={setProfile}
                  options={profileOptions}
                />
                <Select
                  label={t('scanner.shortlistLabel')}
                  value={shortlistSize}
                  onChange={setShortlistSize}
                  options={[
                    { value: '5', label: 'Top 5' },
                    { value: '8', label: 'Top 8' },
                    { value: '10', label: 'Top 10' },
                  ]}
                />
                <Select
                  label={t('scanner.universeLabel')}
                  value={universeLimit}
                  onChange={setUniverseLimit}
                  options={universeOptions}
                />
                <Select
                  label={t('scanner.detailLabel')}
                  value={detailLimit}
                  onChange={setDetailLimit}
                  options={detailOptions}
                />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-secondary-text">{selectedMarketCopy.runHint}</p>
                <Button type="button" onClick={() => void handleRun()} isLoading={isRunning} loadingText={t('scanner.running')}>
                  {t('scanner.run')}
                </Button>
              </div>
            </div>
          </Card>

          <Card title={language === 'en' ? 'Current personal run' : '当前个人 run'} subtitle={language === 'en' ? 'Owner-scoped detail' : '个人范围详情'}>
            {runDetail ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={marketVariant(runDetail.market)}>
                    {runDetail.market === 'us' ? t('scanner.marketUs') : runDetail.market === 'hk' ? t('scanner.marketHk') : t('scanner.marketCn')}
                  </Badge>
                  <Badge variant="info">{runDetail.profileLabel || runDetail.profile}</Badge>
                  <Badge variant={statusVariant(runDetail.status)}>{t(`scanner.status.${runDetail.status}`)}</Badge>
                  {runDetail.watchlistDate ? <Badge variant="history">{runDetail.watchlistDate}</Badge> : null}
                  {runDetail.runAt ? <Badge variant="history">{formatTimestamp(runDetail.runAt)}</Badge> : null}
                </div>
                <div>
                  <h2 className="text-[1.05rem] text-foreground md:text-[1.15rem]">
                    {runDetail.headline || selectedMarketCopy.currentRunFallback}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-secondary-text">
                    {runDetail.sourceSummary || (language === 'en'
                      ? 'Manual scanner output scoped to the current signed-in user.'
                      : '手动扫描结果已限制在当前登录用户范围内。')}
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.metricUniverse')}</p>
                    <p className="mt-1 text-foreground">{runDetail.universeSize}</p>
                  </div>
                  <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.metricShortlist')}</p>
                    <p className="mt-1 text-foreground">{runDetail.shortlistSize}</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm leading-6 text-secondary-text">
                {language === 'en'
                  ? 'No personal scanner run yet. Run the scanner to create an owner-scoped shortlist.'
                  : '你还没有个人扫描结果。运行扫描后即可生成 owner-scoped shortlist。'}
              </div>
            )}
          </Card>
        </div>
      </WorkspacePageHeader>

      {pageError ? <ApiErrorAlert error={pageError} /> : null}

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.18fr)_minmax(23rem,0.82fr)]">
        <section className="space-y-4">
          <Card title={t('scanner.shortlistTitle')} subtitle={language === 'en' ? 'My candidates' : '我的候选'}>
            {isLoadingRun ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm text-secondary-text">
                {t('scanner.loading')}
              </div>
            ) : null}

            {!isLoadingRun && runDetail?.shortlist?.length ? (
              <div className="grid gap-4 xl:grid-cols-2">
                {runDetail.shortlist.map((candidate) => (
                  <Card key={`${candidate.symbol}-${candidate.rank}`} variant="bordered" padding="md" className="space-y-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="info">#{candidate.rank}</Badge>
                          <Badge variant="history">{candidate.symbol}</Badge>
                          <Badge variant="success">{candidate.score.toFixed(1)}</Badge>
                        </div>
                        <div>
                          <h3 className="text-base font-semibold text-foreground">{candidate.name}</h3>
                          <p className="mt-1 text-sm text-secondary-text">{candidate.reasonSummary || '--'}</p>
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-3 py-3">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.reviewMetricReturn')}</p>
                        <p className="mt-1 text-foreground">{formatPercent(candidate.realizedOutcome.reviewWindowReturnPct)}</p>
                      </div>
                      <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/55 px-3 py-3">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.aiTitle')}</p>
                        <p className="mt-1 text-foreground">{candidate.aiInterpretation.summary || candidate.aiInterpretation.message || '--'}</p>
                      </div>
                    </div>

                    <div className="grid gap-4 xl:grid-cols-2">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.riskTitle')}</p>
                        <div className="mt-2 space-y-2">
                          {(candidate.riskNotes.length ? candidate.riskNotes.slice(0, 2) : ['--']).map((note) => (
                            <div key={`${candidate.symbol}-${note}`} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                              {note}
                            </div>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">{t('scanner.watchTitle')}</p>
                        <div className="mt-2 space-y-2">
                          {(candidate.watchContext.length ? candidate.watchContext.slice(0, 2) : [{ label: '--', value: '--' }]).map((item) => (
                            <div key={`${candidate.symbol}-${item.label}-${item.value}`} className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-3 py-2 text-sm leading-6 text-secondary-text">
                              <span className="text-foreground">{item.label}</span>
                              <span className="mx-2 text-muted-text">·</span>
                              <span>{item.value}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    <CandidateActionRow candidate={candidate} onAnalyze={(item) => void handleStartAnalysis(item)} />
                  </Card>
                ))}
              </div>
            ) : null}

            {!isLoadingRun && !runDetail?.shortlist?.length ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-6 text-sm leading-6 text-secondary-text">
                <p className="text-base text-foreground">{t('scanner.emptyTitle')}</p>
                <p className="mt-2">
                  {language === 'en'
                    ? 'Run a manual scan to generate a shortlist that belongs to your own account.'
                    : '运行一次手动扫描，生成只属于你自己账户的 shortlist。'}
                </p>
              </div>
            ) : null}
          </Card>
        </section>

        <section className="space-y-4">
          <Card title={language === 'en' ? 'My recent runs' : '我的近期 runs'} subtitle={language === 'en' ? 'Owner-scoped history' : '个人范围历史'}>
            {historyError ? <ApiErrorAlert error={historyError} /> : null}
            {isLoadingHistory ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm text-secondary-text">
                {t('scanner.loadingHistory')}
              </div>
            ) : null}

            {!isLoadingHistory && historyItems.length ? (
              <div className="space-y-3">
                {historyItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => void loadRun(item.id)}
                    className={`w-full rounded-[var(--theme-panel-radius-md)] border px-4 py-3 text-left transition-colors ${
                      item.id === selectedRunId
                        ? 'border-[var(--border-strong)] bg-[var(--overlay-selected)]'
                        : 'border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/35 hover:border-[var(--border-muted)]'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={marketVariant(item.market)}>
                        {item.market === 'us' ? t('scanner.marketUs') : item.market === 'hk' ? t('scanner.marketHk') : t('scanner.marketCn')}
                      </Badge>
                      <Badge variant={statusVariant(item.status)}>{t(`scanner.status.${item.status}`)}</Badge>
                      {item.watchlistDate ? <Badge variant="history">{item.watchlistDate}</Badge> : null}
                    </div>
                    <p className="mt-3 text-sm font-semibold text-foreground">
                      {item.headline || (item.market === 'us'
                        ? t('scanner.currentRunFallbackUs')
                        : item.market === 'hk'
                          ? t('scanner.currentRunFallbackHk')
                          : t('scanner.currentRunFallbackCn'))}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-secondary-text">
                      <span>{`${t('scanner.metricShortlist')}: ${item.shortlistSize}`}</span>
                      <span>{`${t('scanner.metricUniverse')}: ${item.universeSize}`}</span>
                      <span>{formatTimestamp(item.runAt)}</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : null}

            {!isLoadingHistory && !historyItems.length ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-dashed border-[var(--theme-panel-subtle-border)] px-4 py-5 text-sm leading-6 text-secondary-text">
                {language === 'en'
                  ? 'No personal scanner history yet.'
                  : '你还没有个人扫描历史。'}
              </div>
            ) : null}

            {totalHistoryPages > 1 ? (
              <div className="pt-2">
                <Pagination
                  currentPage={historyPage}
                  totalPages={totalHistoryPages}
                  onPageChange={(page) => void fetchHistory(page)}
                />
              </div>
            ) : null}
          </Card>

          <Card title={language === 'en' ? 'Why the user surface is different' : '为什么用户界面与 admin 不同'} subtitle={language === 'en' ? 'Surface split' : '界面分层'}>
            <div className="space-y-3 text-sm leading-6 text-secondary-text">
              <p>
                {language === 'en'
                  ? 'This page keeps manual runs, shortlist detail, and cross-feature handoff inside the standard signed-in product.'
                  : '这个页面只保留手动运行、shortlist 详情和跨功能联动，作为标准登录用户的产品面。'}
              </p>
              <p>
                {language === 'en'
                  ? 'Operational status, system watchlists, schedules, and channel internals remain in admin-only operator surfaces.'
                  : '运营状态、系统 watchlist、调度和通道内部配置继续保留在 admin-only 的 operator 界面。'}
              </p>
            </div>
          </Card>
        </section>
      </div>
    </div>
  );
};

export default UserScannerPage;
