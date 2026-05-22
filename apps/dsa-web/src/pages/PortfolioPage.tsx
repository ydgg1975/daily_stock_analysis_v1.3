import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pie, PieChart, ResponsiveContainer, Tooltip, Legend, Cell } from 'recharts';
import { portfolioApi } from '../api/portfolio';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Card, Badge, ConfirmDialog, EmptyState, InlineAlert } from '../components/common';
import { toDateInputValue } from '../utils/format';
import type {
  PaperTradeExecuteResponse,
  PaperTradePerformanceResponse,
  PaperTradePrepareResponse,
  PortfolioAccountItem,
  PortfolioCashDirection,
  PortfolioCashLedgerListItem,
  PortfolioCorporateActionListItem,
  PortfolioCorporateActionType,
  PortfolioCostMethod,
  PortfolioFxRefreshResponse,
  PortfolioImportBrokerItem,
  PortfolioImportCommitResponse,
  PortfolioImportParseResponse,
  PortfolioPositionItem,
  PortfolioRiskResponse,
  PortfolioSide,
  PortfolioSnapshotResponse,
  PortfolioTradeListItem,
} from '../types/portfolio';

const PIE_COLORS = ['#00d4ff', '#00ff88', '#ffaa00', '#ff7a45', '#7f8cff', '#ff4466'];
const DEFAULT_PAGE_SIZE = 20;
const FALLBACK_BROKERS: PortfolioImportBrokerItem[] = [
  { broker: 'huatai', aliases: [], displayName: 'Huatai' },
  { broker: 'citic', aliases: ['citic'], displayName: 'CITIC' },
  { broker: 'cmb', aliases: ['cmbchina'], displayName: 'CMB' },
];

type AccountOption = 'all' | number;
type EventType = 'trade' | 'cash' | 'corporate';

type FlatPosition = PortfolioPositionItem & {
  accountId: number;
  accountName: string;
};

type PendingDelete =
  | { eventType: 'trade'; id: number; message: string }
  | { eventType: 'cash'; id: number; message: string }
  | { eventType: 'corporate'; id: number; message: string };

type FxRefreshFeedback = {
  tone: 'neutral' | 'success' | 'warning';
  text: string;
};

type FxRefreshContext = {
  viewKey: string;
  requestId: number;
};

type PortfolioAlertVariant = 'info' | 'success' | 'warning' | 'danger';

const PORTFOLIO_INPUT_CLASS =
  'input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
const PORTFOLIO_SELECT_CLASS = `${PORTFOLIO_INPUT_CLASS} appearance-none pr-10`;
const PORTFOLIO_FILE_PICKER_CLASS =
  'input-surface input-focus-glow flex h-11 w-full cursor-pointer items-center justify-center rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

function getTodayIso(): string {
  return toDateInputValue(new Date());
}

function formatMoney(value: number | undefined | null, currency = 'CNY'): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${currency} ${Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatPct(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(2)}%`;
}

function formatSignedPct(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function hasPositionPrice(row: PortfolioPositionItem): boolean {
  return row.priceAvailable !== false && row.priceSource !== 'missing';
}

function formatPositionPrice(row: PortfolioPositionItem): string {
  if (!hasPositionPrice(row)) return '--';
  return row.lastPrice.toFixed(4);
}

function formatPositionMoney(value: number, row: PortfolioPositionItem): string {
  if (!hasPositionPrice(row)) return '--';
  return formatMoney(value, row.valuationCurrency);
}

function getPositionPriceLabel(row: PortfolioPositionItem): string {
  if (!hasPositionPrice(row)) return '가격 없음';
  if (row.priceSource === 'realtime_quote') {
    return row.priceProvider ? `실시간가 · ${row.priceProvider}` : '실시간가';
  }
  if (row.priceSource === 'history_close') {
    return row.priceStale && row.priceDate ? `종가 · ${row.priceDate}` : '종가';
  }
  return row.priceSource || '알 수 없는 출처';
}

function formatSideLabel(value: PortfolioSide): string {
  return value === 'buy' ? '매수' : '매도';
}

function formatCashDirectionLabel(value: PortfolioCashDirection): string {
  return value === 'in' ? '입금' : '출금';
}

function formatCorporateActionLabel(value: PortfolioCorporateActionType): string {
  return value === 'cash_dividend' ? '현금 배당' : '분할/병합 조정';
}

function formatBrokerLabel(value: string, displayName?: string): string {
  if (displayName && displayName.trim()) return `${value}(${displayName.trim()})`;
  if (value === 'huatai') return 'huatai(Huatai)';
  if (value === 'citic') return 'citic(CITIC)';
  if (value === 'cmb') return 'cmb(CMB)';
  return value;
}

function buildFxRefreshFeedback(data: PortfolioFxRefreshResponse): FxRefreshFeedback {
  if (data.refreshEnabled === false) {
    return {
      tone: 'neutral',
      text: '환율 온라인 새로고침이 비활성화되어 있습니다.',
    };
  }

  if (data.pairCount === 0) {
    return {
      tone: 'neutral',
      text: '현재 범위에서 새로고침할 환율 쌍이 없습니다.',
    };
  }

  if (data.updatedCount > 0 && data.staleCount === 0 && data.errorCount === 0) {
    return {
      tone: 'success',
      text: `환율 새로고침 완료, ${data.updatedCount}개 업데이트됨`,
    };
  }

  const summary = `업데이트 ${data.updatedCount}개, 지연 ${data.staleCount}개, 실패 ${data.errorCount}개`;
  if (data.staleCount > 0) {
    return {
      tone: 'warning',
      text: `일부 환율은 최신값을 가져오지 못해 기존값 또는 대체값을 사용합니다. ${summary}`,
    };
  }

  return {
    tone: 'warning',
    text: `온라인 새로고침이 완전히 성공하지 못했습니다. ${summary}`,
  };
}

function getFxRefreshFeedbackVariant(tone: FxRefreshFeedback['tone']): PortfolioAlertVariant {
  if (tone === 'success') return 'success';
  if (tone === 'warning') return 'warning';
  return 'info';
}

function getCsvParseVariant(result: PortfolioImportParseResponse): PortfolioAlertVariant {
  return result.errorCount > 0 || result.skippedCount > 0 ? 'warning' : 'info';
}

function getCsvCommitVariant(result: PortfolioImportCommitResponse, isDryRun: boolean): PortfolioAlertVariant {
  if (isDryRun) return 'info';
  return result.failedCount > 0 || result.duplicateCount > 0 ? 'warning' : 'success';
}

function getPaperRiskTone(item: Record<string, unknown>): PortfolioAlertVariant {
  const status = String(item.status ?? item.result ?? '').toLowerCase();
  if (item.passed === false || ['blocked', 'danger', 'failed', 'fail', 'error'].includes(status)) return 'danger';
  if (['warning', 'warn', 'caution'].includes(status)) return 'warning';
  return 'success';
}

function formatPaperRiskCheck(item: Record<string, unknown>): string {
  const name = item.name ?? item.type ?? item.check ?? 'risk_check';
  const status = item.status ?? item.result ?? (item.passed === false ? 'failed' : 'passed');
  const message = item.message ?? item.reason ?? item.detail;
  return message ? `${String(name)} · ${String(status)} · ${String(message)}` : `${String(name)} · ${String(status)}`;
}

function formatPaperOrderValue(order: Record<string, unknown> | undefined | null, key: string): string {
  const value = order?.[key];
  if (value == null || value === '') return '--';
  return String(value);
}

function formatPaperSideLabel(value: string): string {
  if (value === 'buy' || value === 'sell') return formatSideLabel(value);
  return value || '--';
}

function formatPaperOutcomeLabel(value: string): string {
  if (value === 'win') return '승';
  if (value === 'loss') return '패';
  if (value === 'flat') return '무';
  return value || '--';
}

const PortfolioPage: React.FC = () => {
  // Set page title
  useEffect(() => {
    document.title = '포트폴리오 관리 - DSA';
  }, []);

  const [accounts, setAccounts] = useState<PortfolioAccountItem[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<AccountOption>('all');
  const [showCreateAccount, setShowCreateAccount] = useState(false);
  const [accountCreating, setAccountCreating] = useState(false);
  const [accountCreateError, setAccountCreateError] = useState<string | null>(null);
  const [accountCreateSuccess, setAccountCreateSuccess] = useState<string | null>(null);
  const [accountForm, setAccountForm] = useState({
    name: '',
    broker: 'Demo',
    market: 'cn' as 'cn' | 'hk' | 'us' | 'kr',
    baseCurrency: 'CNY',
  });
  const [costMethod, setCostMethod] = useState<PortfolioCostMethod>('fifo');
  const [snapshot, setSnapshot] = useState<PortfolioSnapshotResponse | null>(null);
  const [risk, setRisk] = useState<PortfolioRiskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [fxRefreshing, setFxRefreshing] = useState(false);
  const [fxRefreshFeedback, setFxRefreshFeedback] = useState<FxRefreshFeedback | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [riskWarning, setRiskWarning] = useState<string | null>(null);
  const [writeWarning, setWriteWarning] = useState<string | null>(null);

  const [brokers, setBrokers] = useState<PortfolioImportBrokerItem[]>([]);
  const [selectedBroker, setSelectedBroker] = useState('huatai');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvDryRun, setCsvDryRun] = useState(true);
  const [csvParsing, setCsvParsing] = useState(false);
  const [csvCommitting, setCsvCommitting] = useState(false);
  const [csvParseResult, setCsvParseResult] = useState<PortfolioImportParseResponse | null>(null);
  const [csvCommitResult, setCsvCommitResult] = useState<PortfolioImportCommitResponse | null>(null);
  const [brokerLoadWarning, setBrokerLoadWarning] = useState<string | null>(null);

  const [eventType, setEventType] = useState<EventType>('trade');
  const [eventDateFrom, setEventDateFrom] = useState('');
  const [eventDateTo, setEventDateTo] = useState('');
  const [eventSymbol, setEventSymbol] = useState('');
  const [eventSide, setEventSide] = useState<'' | PortfolioSide>('');
  const [eventDirection, setEventDirection] = useState<'' | PortfolioCashDirection>('');
  const [eventActionType, setEventActionType] = useState<'' | PortfolioCorporateActionType>('');
  const [eventPage, setEventPage] = useState(1);
  const [eventTotal, setEventTotal] = useState(0);
  const [eventLoading, setEventLoading] = useState(false);
  const [tradeEvents, setTradeEvents] = useState<PortfolioTradeListItem[]>([]);
  const [cashEvents, setCashEvents] = useState<PortfolioCashLedgerListItem[]>([]);
  const [corporateEvents, setCorporateEvents] = useState<PortfolioCorporateActionListItem[]>([]);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [tradeForm, setTradeForm] = useState({
    symbol: '',
    tradeDate: getTodayIso(),
    side: 'buy' as PortfolioSide,
    quantity: '',
    price: '',
    fee: '',
    tax: '',
    tradeUid: '',
    note: '',
  });
  const [cashForm, setCashForm] = useState({
    eventDate: getTodayIso(),
    direction: 'in' as PortfolioCashDirection,
    amount: '',
    currency: '',
    note: '',
  });
  const [corpForm, setCorpForm] = useState({
    symbol: '',
    effectiveDate: getTodayIso(),
    actionType: 'cash_dividend' as PortfolioCorporateActionType,
    cashDividendPerShare: '',
    splitRatio: '',
    note: '',
  });
  const [paperPreparing, setPaperPreparing] = useState(false);
  const [paperExecuting, setPaperExecuting] = useState(false);
  const [paperPrepareResult, setPaperPrepareResult] = useState<PaperTradePrepareResponse | null>(null);
  const [paperExecuteResult, setPaperExecuteResult] = useState<PaperTradeExecuteResponse | null>(null);
  const [paperPerformance, setPaperPerformance] = useState<PaperTradePerformanceResponse | null>(null);
  const [paperPerformanceLoading, setPaperPerformanceLoading] = useState(false);
  const [paperPerformanceWarning, setPaperPerformanceWarning] = useState<string | null>(null);
  const [paperForm, setPaperForm] = useState({
    symbol: '',
    tradeDate: getTodayIso(),
    side: 'buy' as PortfolioSide,
    quantity: '',
    price: '',
    market: 'us' as 'cn' | 'hk' | 'us',
    currency: 'USD',
    reason: '',
  });

  const queryAccountId = selectedAccount === 'all' ? undefined : selectedAccount;
  const refreshViewKey = `${selectedAccount === 'all' ? 'all' : `account:${selectedAccount}`}:cost:${costMethod}`;
  const refreshContextRef = useRef<FxRefreshContext>({ viewKey: refreshViewKey, requestId: 0 });
  const hasAccounts = accounts.length > 0;
  const writableAccount = selectedAccount === 'all' ? undefined : accounts.find((item) => item.id === selectedAccount);
  const writableAccountId = writableAccount?.id;
  const writeBlocked = !writableAccountId;
  const totalEventPages = Math.max(1, Math.ceil(eventTotal / DEFAULT_PAGE_SIZE));
  const currentEventCount = eventType === 'trade'
    ? tradeEvents.length
    : eventType === 'cash'
      ? cashEvents.length
      : corporateEvents.length;

  const isActiveRefreshContext = (requestedViewKey: string, requestedRequestId: number) => {
    return (
      refreshContextRef.current.viewKey === requestedViewKey
      && refreshContextRef.current.requestId === requestedRequestId
    );
  };

  const loadAccounts = useCallback(async () => {
    try {
      const response = await portfolioApi.getAccounts(false);
      const items = response.accounts || [];
      setAccounts(items);
      setSelectedAccount((prev) => {
        if (items.length === 0) return 'all';
        if (prev !== 'all' && !items.some((item) => item.id === prev)) return items[0].id;
        return prev;
      });
      if (items.length === 0) setShowCreateAccount(true);
    } catch (err) {
      setError(getParsedApiError(err));
    }
  }, []);

  const loadBrokers = useCallback(async () => {
    try {
      const response = await portfolioApi.listImportBrokers();
      const brokerItems = response.brokers || [];
      if (brokerItems.length === 0) {
        setBrokers(FALLBACK_BROKERS);
        setBrokerLoadWarning('브로커 목록 API 응답이 없어 기본 브로커(Huatai/CITIC/CMB)로 대체했습니다.');
        if (!FALLBACK_BROKERS.some((item) => item.broker === selectedBroker)) {
          setSelectedBroker(FALLBACK_BROKERS[0].broker);
        }
        return;
      }
      setBrokers(brokerItems);
      setBrokerLoadWarning(null);
      if (!brokerItems.some((item) => item.broker === selectedBroker)) {
        setSelectedBroker(brokerItems[0].broker);
      }
    } catch {
      setBrokers(FALLBACK_BROKERS);
      setBrokerLoadWarning('브로커 목록 API를 사용할 수 없어 기본 브로커(Huatai/CITIC/CMB)로 대체했습니다.');
      if (!FALLBACK_BROKERS.some((item) => item.broker === selectedBroker)) {
        setSelectedBroker(FALLBACK_BROKERS[0].broker);
      }
    }
  }, [selectedBroker]);

  const loadSnapshotAndRisk = useCallback(async () => {
    setIsLoading(true);
    setRiskWarning(null);
    try {
      const snapshotData = await portfolioApi.getSnapshot({
        accountId: queryAccountId,
        costMethod,
      });
      setSnapshot(snapshotData);
      setError(null);

      try {
        const riskData = await portfolioApi.getRisk({
          accountId: queryAccountId,
          costMethod,
        });
        setRisk(riskData);
      } catch (riskErr) {
        setRisk(null);
        const parsed = getParsedApiError(riskErr);
        setRiskWarning(parsed.message || '리스크 데이터를 가져오지 못해 스냅샷 데이터만 표시합니다.');
      }
    } catch (err) {
      setSnapshot(null);
      setRisk(null);
      setError(getParsedApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [queryAccountId, costMethod]);

  const loadEventsPage = useCallback(async (page: number) => {
    setEventLoading(true);
    try {
      if (eventType === 'trade') {
        const response = await portfolioApi.listTrades({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          symbol: eventSymbol || undefined,
          side: eventSide || undefined,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setTradeEvents(response.items || []);
        setEventTotal(response.total || 0);
      } else if (eventType === 'cash') {
        const response = await portfolioApi.listCashLedger({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          direction: eventDirection || undefined,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setCashEvents(response.items || []);
        setEventTotal(response.total || 0);
      } else {
        const response = await portfolioApi.listCorporateActions({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          symbol: eventSymbol || undefined,
          actionType: eventActionType || undefined,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setCorporateEvents(response.items || []);
        setEventTotal(response.total || 0);
      }
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setEventLoading(false);
    }
  }, [
    eventActionType,
    eventDateFrom,
    eventDateTo,
    eventDirection,
    eventSide,
    eventSymbol,
    eventType,
    queryAccountId,
  ]);

  const loadEvents = useCallback(async () => {
    await loadEventsPage(eventPage);
  }, [eventPage, loadEventsPage]);

  const refreshPortfolioData = useCallback(async (page = eventPage) => {
    await Promise.all([loadSnapshotAndRisk(), loadEventsPage(page)]);
  }, [eventPage, loadEventsPage, loadSnapshotAndRisk]);

  const loadPaperPerformance = useCallback(async () => {
    setPaperPerformanceLoading(true);
    setPaperPerformanceWarning(null);
    try {
      const data = await portfolioApi.getPaperPerformance({
        accountId: queryAccountId,
        costMethod,
      });
      setPaperPerformance(data);
    } catch (err) {
      setPaperPerformance(null);
      const parsed = getParsedApiError(err);
      setPaperPerformanceWarning(parsed.message || 'Paper trading 성과를 가져오지 못했습니다.');
    } finally {
      setPaperPerformanceLoading(false);
    }
  }, [costMethod, queryAccountId]);

  useEffect(() => {
    void loadAccounts();
    void loadBrokers();
  }, [loadAccounts, loadBrokers]);

  useEffect(() => {
    void loadSnapshotAndRisk();
  }, [loadSnapshotAndRisk]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    void loadPaperPerformance();
  }, [loadPaperPerformance]);

  useEffect(() => {
    refreshContextRef.current = {
      viewKey: refreshViewKey,
      requestId: refreshContextRef.current.requestId + 1,
    };
    setFxRefreshing(false);
    setFxRefreshFeedback(null);
  }, [refreshViewKey]);

  useEffect(() => {
    setEventPage(1);
  }, [eventType, queryAccountId, eventDateFrom, eventDateTo, eventSymbol, eventSide, eventDirection, eventActionType]);

  useEffect(() => {
    if (!writeBlocked) {
      setWriteWarning(null);
    }
  }, [writeBlocked]);

  const positionRows: FlatPosition[] = useMemo(() => {
    if (!snapshot) return [];
    const rows: FlatPosition[] = [];
    for (const account of snapshot.accounts || []) {
      for (const position of account.positions || []) {
        rows.push({
          ...position,
          accountId: account.accountId,
          accountName: account.accountName,
        });
      }
    }
    rows.sort((a, b) => Number(b.marketValueBase || 0) - Number(a.marketValueBase || 0));
    return rows;
  }, [snapshot]);

  const sectorPieData = useMemo(() => {
    const sectors = risk?.sectorConcentration?.topSectors || [];
    return sectors
      .slice(0, 6)
      .map((item) => ({
        name: item.sector,
        value: Number(item.weightPct || 0),
      }))
      .filter((item) => item.value > 0);
  }, [risk]);

  const positionFallbackPieData = useMemo(() => {
    if (!risk?.concentration?.topPositions?.length) {
      return [];
    }
    return risk.concentration.topPositions
      .slice(0, 6)
      .map((item) => ({
        name: item.symbol,
        value: Number(item.weightPct || 0),
      }))
      .filter((item) => item.value > 0);
  }, [risk]);

  const concentrationPieData = sectorPieData.length > 0 ? sectorPieData : positionFallbackPieData;
  const concentrationMode = sectorPieData.length > 0 ? 'sector' : 'position';

  const handleTradeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writableAccountId) {
      setWriteWarning('다른 계좌에 쓰려면 특정 계좌를 선택한 뒤 입력 또는 CSV 제출을 진행하세요.');
      return;
    }
    try {
      setWriteWarning(null);
      await portfolioApi.createTrade({
        accountId: writableAccountId,
        symbol: tradeForm.symbol,
        tradeDate: tradeForm.tradeDate,
        side: tradeForm.side,
        quantity: Number(tradeForm.quantity),
        price: Number(tradeForm.price),
        fee: Number(tradeForm.fee || 0),
        tax: Number(tradeForm.tax || 0),
        tradeUid: tradeForm.tradeUid || undefined,
        note: tradeForm.note || undefined,
      });
      await refreshPortfolioData();
      setTradeForm((prev) => ({ ...prev, symbol: '', tradeUid: '', note: '' }));
    } catch (err) {
      setError(getParsedApiError(err));
    }
  };

  const handlePaperPrepare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writableAccountId) {
      setWriteWarning('Paper 주문을 준비하려면 특정 계좌를 선택하세요.');
      return;
    }

    try {
      setPaperPreparing(true);
      setWriteWarning(null);
      setPaperExecuteResult(null);
      const prepared = await portfolioApi.preparePaperOrder({
        accountId: writableAccountId,
        symbol: paperForm.symbol,
        tradeDate: paperForm.tradeDate,
        side: paperForm.side,
        quantity: Number(paperForm.quantity),
        price: Number(paperForm.price),
        market: paperForm.market,
        currency: paperForm.currency || undefined,
        reason: paperForm.reason || undefined,
        costMethod,
      });
      setPaperPrepareResult(prepared);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setPaperPreparing(false);
    }
  };

  const handlePaperExecute = async (approved: boolean) => {
    if (!paperPrepareResult || paperExecuting) return;

    try {
      setPaperExecuting(true);
      setWriteWarning(null);
      const executed = await portfolioApi.executePaperOrder({
        preparedOrder: paperPrepareResult.order,
        approvalToken: paperPrepareResult.approvalToken,
        approved,
      });
      setPaperExecuteResult(executed);
      if (approved && executed.tradeId) {
        setEventType('trade');
        setEventPage(1);
        await refreshPortfolioData(1);
        await loadPaperPerformance();
      }
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setPaperExecuting(false);
    }
  };

  const handleCashSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writableAccountId) {
      setWriteWarning('다른 계좌에 쓰려면 특정 계좌를 선택한 뒤 입력 또는 CSV 제출을 진행하세요.');
      return;
    }
    try {
      setWriteWarning(null);
      await portfolioApi.createCashLedger({
        accountId: writableAccountId,
        eventDate: cashForm.eventDate,
        direction: cashForm.direction,
        amount: Number(cashForm.amount),
        currency: cashForm.currency || undefined,
        note: cashForm.note || undefined,
      });
      await refreshPortfolioData();
      setCashForm((prev) => ({ ...prev, note: '' }));
    } catch (err) {
      setError(getParsedApiError(err));
    }
  };

  const handleCorporateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writableAccountId) {
      setWriteWarning('다른 계좌에 쓰려면 특정 계좌를 선택한 뒤 입력 또는 CSV 제출을 진행하세요.');
      return;
    }
    try {
      setWriteWarning(null);
      await portfolioApi.createCorporateAction({
        accountId: writableAccountId,
        symbol: corpForm.symbol,
        effectiveDate: corpForm.effectiveDate,
        actionType: corpForm.actionType,
        cashDividendPerShare: corpForm.cashDividendPerShare ? Number(corpForm.cashDividendPerShare) : undefined,
        splitRatio: corpForm.splitRatio ? Number(corpForm.splitRatio) : undefined,
        note: corpForm.note || undefined,
      });
      await refreshPortfolioData();
      setCorpForm((prev) => ({ ...prev, symbol: '', note: '' }));
    } catch (err) {
      setError(getParsedApiError(err));
    }
  };

  const handleParseCsv = async () => {
    if (!csvFile) return;
    try {
      setCsvParsing(true);
      const parsed = await portfolioApi.parseCsvImport(selectedBroker, csvFile);
      setCsvParseResult(parsed);
      setCsvCommitResult(null);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setCsvParsing(false);
    }
  };

  const handleCommitCsv = async () => {
    if (!csvFile) return;
    if (!writableAccountId) {
      setWriteWarning('다른 계좌에 쓰려면 특정 계좌를 선택한 뒤 입력 또는 CSV 제출을 진행하세요.');
      return;
    }
    try {
      setWriteWarning(null);
      setCsvCommitting(true);
      const committed = await portfolioApi.commitCsvImport(writableAccountId, selectedBroker, csvFile, csvDryRun);
      setCsvCommitResult(committed);
      if (!csvDryRun) {
        await refreshPortfolioData();
      }
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setCsvCommitting(false);
    }
  };

  const openDeleteDialog = (item: PendingDelete) => {
    if (!writableAccountId) {
      setWriteWarning('삭제 또는 수정하려면 특정 계좌를 선택하세요.');
      return;
    }
    setPendingDelete(item);
  };

  const handleConfirmDelete = async () => {
    if (!pendingDelete || deleteLoading) return;
    if (!writableAccountId) {
      setWriteWarning('삭제 또는 수정하려면 특정 계좌를 선택하세요.');
      setPendingDelete(null);
      return;
    }

    const nextPage = currentEventCount === 1 && eventPage > 1 ? eventPage - 1 : eventPage;
    try {
      setDeleteLoading(true);
      setWriteWarning(null);
      if (pendingDelete.eventType === 'trade') {
        await portfolioApi.deleteTrade(pendingDelete.id);
      } else if (pendingDelete.eventType === 'cash') {
        await portfolioApi.deleteCashLedger(pendingDelete.id);
      } else {
        await portfolioApi.deleteCorporateAction(pendingDelete.id);
      }
      setPendingDelete(null);
      if (nextPage !== eventPage) {
        setEventPage(nextPage);
      }
      await refreshPortfolioData(nextPage);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = accountForm.name.trim();
    if (!name) {
      setAccountCreateError('계좌 이름은 필수입니다.');
      setAccountCreateSuccess(null);
      return;
    }
    try {
      setAccountCreating(true);
      setAccountCreateError(null);
      setAccountCreateSuccess(null);
      const created = await portfolioApi.createAccount({
        name,
        broker: accountForm.broker.trim() || undefined,
        market: accountForm.market,
        baseCurrency: accountForm.baseCurrency.trim() || 'CNY',
      });
      await loadAccounts();
      setSelectedAccount(created.id);
      setShowCreateAccount(false);
      setWriteWarning(null);
      setAccountForm({
        name: '',
        broker: 'Demo',
        market: accountForm.market,
        baseCurrency: accountForm.baseCurrency,
      });
      setAccountCreateSuccess('계좌가 생성되었고 해당 계좌로 전환되었습니다.');
    } catch (err) {
      const parsed = getParsedApiError(err);
      setAccountCreateError(parsed.message || '계좌 생성에 실패했습니다. 잠시 후 다시 시도하세요.');
      setAccountCreateSuccess(null);
    } finally {
      setAccountCreating(false);
    }
  };

  const handleRefresh = async () => {
    await Promise.all([loadAccounts(), loadSnapshotAndRisk(), loadEvents(), loadBrokers()]);
  };

  const reloadSnapshotAndRiskForScope = useCallback(async (
    requestedViewKey: string,
    requestedRequestId: number,
    requestedAccountId: number | undefined,
    requestedCostMethod: PortfolioCostMethod,
  ): Promise<boolean> => {
    if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
      return false;
    }

    setRiskWarning(null);

    try {
      const snapshotData = await portfolioApi.getSnapshot({
        accountId: requestedAccountId,
        costMethod: requestedCostMethod,
      });
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return false;
      }
      setSnapshot(snapshotData);
      setError(null);

      try {
        const riskData = await portfolioApi.getRisk({
          accountId: requestedAccountId,
          costMethod: requestedCostMethod,
        });
        if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
          return false;
        }
        setRisk(riskData);
        setRiskWarning(null);
      } catch (riskErr) {
        if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
          return false;
        }
        setRisk(null);
        const parsed = getParsedApiError(riskErr);
        setRiskWarning(parsed.message || '리스크 데이터를 가져오지 못해 스냅샷 데이터만 표시합니다.');
      }
      return true;
    } catch (err) {
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return false;
      }
      setSnapshot(null);
      setRisk(null);
      setError(getParsedApiError(err));
      return false;
    }
  }, []);

  const handleRefreshFx = async () => {
    if (!hasAccounts || isLoading || fxRefreshing) {
      return;
    }

    const requestedViewKey = refreshViewKey;
    const requestedAccountId = queryAccountId;
    const requestedCostMethod = costMethod;
    const requestedRequestId = refreshContextRef.current.requestId + 1;
    refreshContextRef.current = {
      viewKey: requestedViewKey,
      requestId: requestedRequestId,
    };

    try {
      setFxRefreshing(true);
      setFxRefreshFeedback(null);
      const result = await portfolioApi.refreshFx({
        accountId: requestedAccountId,
      });
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return;
      }
      const reloaded = await reloadSnapshotAndRiskForScope(
        requestedViewKey,
        requestedRequestId,
        requestedAccountId,
        requestedCostMethod,
      );
      if (!reloaded || !isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return;
      }
      setFxRefreshFeedback(buildFxRefreshFeedback(result));
    } catch (err) {
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return;
      }
      setError(getParsedApiError(err));
    } finally {
      if (isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        setFxRefreshing(false);
      }
    }
  };

  return (
    <div className="portfolio-page min-h-screen space-y-4 p-4 md:p-6">
      <section className="space-y-3">
        <div className="space-y-2">
          <h1 className="text-xl md:text-2xl font-semibold text-foreground">포트폴리오 관리</h1>
          <p className="text-xs md:text-sm text-secondary">
            포트폴리오 보유 현황, 수동 입력, CSV 가져오기, 리스크 분석을 한 화면에서 관리합니다.
          </p>
        </div>
        {hasAccounts ? (
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
            <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_220px_280px] gap-2 items-end">
              <div>
                <p className="text-xs text-secondary mb-1">계좌 보기</p>
                <select
                  value={String(selectedAccount)}
                  onChange={(e) => setSelectedAccount(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                  className={PORTFOLIO_SELECT_CLASS}
                >
                  <option value="all">전체 계좌</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name} (#{account.id})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <p className="text-xs text-secondary mb-1">원가 계산</p>
                <select
                  value={costMethod}
                  onChange={(e) => setCostMethod(e.target.value as PortfolioCostMethod)}
                  className={PORTFOLIO_SELECT_CLASS}
                >
                  <option value="fifo">선입선출(FIFO)</option>
                  <option value="avg">평균 원가(AVG)</option>
                </select>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-secondary text-sm flex-1"
                  onClick={() => {
                    setShowCreateAccount((prev) => !prev);
                    setAccountCreateError(null);
                    setAccountCreateSuccess(null);
                  }}
                >
                  {showCreateAccount ? '계좌 만들기 닫기' : '새 계좌'}
                </button>
                <button
                  type="button"
                  onClick={() => void handleRefresh()}
                  disabled={isLoading || fxRefreshing}
                  className="btn-secondary text-sm flex-1"
                >
                  {isLoading ? '새로고침 중...' : '데이터 새로고침'}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <InlineAlert
            variant="warning"
            className="inline-block rounded-lg px-3 py-2 text-xs shadow-none"
            message="사용 가능한 계좌가 없습니다. 새 계좌를 만든 뒤 거래 입력 또는 CSV 가져오기를 진행하세요."
          />
        )}
      </section>

      {error ? <ApiErrorAlert error={error} onDismiss={() => setError(null)} /> : null}
      {riskWarning ? (
        <InlineAlert
          variant="warning"
          title="리스크 데이터 제한"
          message={riskWarning}
        />
      ) : null}
      {writeWarning ? (
        <InlineAlert
          variant="warning"
          title="작업 안내"
          message={writeWarning}
        />
      ) : null}

      {(showCreateAccount || !hasAccounts) ? (
        <Card padding="md">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-foreground">새 계좌</h2>
            {hasAccounts ? (
              <button
                type="button"
                className="btn-secondary text-xs px-3 py-1"
                onClick={() => {
                  setShowCreateAccount(false);
                  setAccountCreateError(null);
                  setAccountCreateSuccess(null);
                }}
              >
                닫기
              </button>
            ) : (
              <span className="text-xs text-secondary">생성 후 해당 계좌로 전환됩니다.</span>
            )}
          </div>
          {accountCreateError ? (
            <InlineAlert
              variant="danger"
              className="mt-2 rounded-lg px-2 py-1 text-xs shadow-none"
              title="계좌 생성 실패"
              message={accountCreateError}
            />
          ) : null}
          {accountCreateSuccess ? (
            <InlineAlert
              variant="success"
              className="mt-2 rounded-lg px-2 py-1 text-xs shadow-none"
              title="계좌 생성 성공"
              message={accountCreateSuccess}
            />
          ) : null}
          <form className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2" onSubmit={handleCreateAccount}>
            <input
              className={`${PORTFOLIO_INPUT_CLASS} md:col-span-2`}
              placeholder="계좌 이름(필수)"
              value={accountForm.name}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, name: e.target.value }))}
            />
            <input
              className={PORTFOLIO_INPUT_CLASS}
              placeholder="브로커 선택, 예: Demo/Huatai"
              value={accountForm.broker}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, broker: e.target.value }))}
            />
            <input
              className={PORTFOLIO_INPUT_CLASS}
              placeholder="기준 통화, 예: CNY/USD/HKD/KRW"
              value={accountForm.baseCurrency}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, baseCurrency: e.target.value.toUpperCase() }))}
            />
            <select
              className={PORTFOLIO_SELECT_CLASS}
              value={accountForm.market}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, market: e.target.value as 'cn' | 'hk' | 'us' | 'kr' }))}
            >
              <option value="cn">시장: 중국 A주(cn)</option>
              <option value="hk">시장: 홍콩 주식(hk)</option>
              <option value="us">시장: 미국 주식(us)</option>
              <option value='kr'>시장: 한국 주식(kr)</option>
            </select>
            <button type="submit" className="btn-secondary text-sm" disabled={accountCreating}>
              {accountCreating ? '생성 중...' : '계좌 생성'}
            </button>
          </form>
        </Card>
      ) : null}

      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <Card variant="gradient" padding="md">
          <p className="text-xs text-secondary">총자산</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{formatMoney(snapshot?.totalEquity, snapshot?.currency || 'CNY')}</p>
        </Card>
        <Card variant="gradient" padding="md">
          <p className="text-xs text-secondary">총평가액</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{formatMoney(snapshot?.totalMarketValue, snapshot?.currency || 'CNY')}</p>
        </Card>
        <Card variant="gradient" padding="md">
          <p className="text-xs text-secondary">총현금</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{formatMoney(snapshot?.totalCash, snapshot?.currency || 'CNY')}</p>
        </Card>
        <Card variant="gradient" padding="md">
          <div className="flex items-start justify-between gap-3">
            <p className="text-xs text-secondary">환율 상태</p>
            <button
              type="button"
              className="btn-secondary !px-3 !py-1 !text-xs shrink-0"
              onClick={() => void handleRefreshFx()}
              disabled={!hasAccounts || isLoading || fxRefreshing}
            >
              {fxRefreshing ? '새로고침 중...' : '환율 새로고침'}
            </button>
          </div>
          <div className="mt-2">{snapshot?.fxStale ? <Badge variant="warning">지연</Badge> : <Badge variant="success">최신</Badge>}</div>
          {fxRefreshFeedback ? (
            <InlineAlert
              variant={getFxRefreshFeedbackVariant(fxRefreshFeedback.tone)}
              title="환율 새로고침 결과"
              message={fxRefreshFeedback.text}
              className="mt-3 rounded-xl px-3 py-2 text-xs shadow-none"
            />
          ) : null}
        </Card>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-3">
        <Card className="xl:col-span-2" padding="md">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-foreground">보유 종목</h2>
            <span className="text-xs text-secondary">총 {positionRows.length}개</span>
          </div>
          {positionRows.length === 0 ? (
            <EmptyState
              title="현재 보유 데이터가 없습니다"
              description="거래를 입력하거나 CSV를 가져오면 계좌 보유 내역이 여기에 표시됩니다."
              className="border-none bg-transparent px-4 py-8 shadow-none"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-secondary border-b border-white/10">
                  <tr>
                    <th className="text-left py-2 pr-2">계좌</th>
                    <th className="text-left py-2 pr-2">코드</th>
                    <th className="text-right py-2 pr-2">수량</th>
                    <th className="text-right py-2 pr-2">평균가</th>
                    <th className="text-right py-2 pr-2">현재가</th>
                    <th className="text-right py-2 pr-2">평가액</th>
                    <th className="text-right py-2">미실현 손익</th>
                    <th className="text-right py-2">수익률</th>
                  </tr>
                </thead>
                <tbody>
                  {positionRows.map((row) => (
                    <tr key={`${row.accountId}-${row.symbol}-${row.market}`} className="border-b border-white/5">
                      <td className="py-2 pr-2 text-secondary">{row.accountName}</td>
                      <td className="py-2 pr-2 font-mono text-foreground">{row.symbol}</td>
                      <td className="py-2 pr-2 text-right">{row.quantity.toFixed(2)}</td>
                      <td className="py-2 pr-2 text-right">{row.avgCost.toFixed(4)}</td>
                      <td className="py-2 pr-2 text-right">
                        <div>{formatPositionPrice(row)}</div>
                        <div className={`text-[11px] ${hasPositionPrice(row) ? 'text-secondary' : 'text-warning'}`}>
                          {getPositionPriceLabel(row)}
                        </div>
                      </td>
                      <td className="py-2 pr-2 text-right">{formatPositionMoney(row.marketValueBase, row)}</td>
                      <td
                        className={`py-2 text-right ${
                          hasPositionPrice(row)
                            ? row.unrealizedPnlBase >= 0
                              ? 'text-success'
                              : 'text-danger'
                            : 'text-secondary'
                        }`}
                      >
                        {formatPositionMoney(row.unrealizedPnlBase, row)}
                      </td>
                      <td
                        className={`py-2 text-right ${
                          hasPositionPrice(row) && row.unrealizedPnlPct !== null && row.unrealizedPnlPct !== undefined
                            ? row.unrealizedPnlPct >= 0
                              ? 'text-success'
                              : 'text-danger'
                            : 'text-secondary'
                        }`}
                      >
                        {formatSignedPct(row.unrealizedPnlPct)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card padding="md">
          <h2 className="text-sm font-semibold text-foreground mb-3">{concentrationMode === 'sector' ? '업종 집중도 분포' : '개별 종목 집중도'}</h2>
          {concentrationPieData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={concentrationPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90}>
                    {concentrationPieData.map((entry, index) => (
                      <Cell key={`cell-${entry.name}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => `${Number(value).toFixed(2)}%`} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState
              title="집중도 데이터 없음"
              description="리스크 계산이 완료되면 업종 또는 종목 기준 집중도 분포가 여기에 표시됩니다."
              className="border-none bg-transparent px-4 py-10 shadow-none"
            />
          )}
          <div className="mt-3 text-xs text-secondary space-y-1">
            <div>표시 기준: {concentrationMode === 'sector' ? '업종 기준' : '종목 기준'}</div>
            <div>집중도 경고: {risk?.sectorConcentration?.alert ? '예' : '아니오'}</div>
            <div>Top1 비중: {formatPct(risk?.sectorConcentration?.topWeightPct ?? risk?.concentration?.topWeightPct)}</div>
          </div>
        </Card>
      </section>

      {writeBlocked && hasAccounts ? (
        <InlineAlert
          variant="warning"
          className="rounded-lg px-3 py-2 text-xs shadow-none"
          message="현재 전체 계좌 보기입니다. 수동 입력이나 CSV 제출을 진행하려면 특정 계좌를 선택하세요."
        />
      ) : null}

      <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card padding="md">
          <h3 className="text-sm font-semibold text-foreground mb-2">낙폭 모니터링</h3>
          <div className="text-xs text-secondary space-y-1">
            <div>최대 낙폭: {formatPct(risk?.drawdown?.maxDrawdownPct)}</div>
            <div>현재 낙폭: {formatPct(risk?.drawdown?.currentDrawdownPct)}</div>
            <div>경고: {risk?.drawdown?.alert ? '예' : '아니오'}</div>
          </div>
        </Card>
        <Card padding="md">
          <h3 className="text-sm font-semibold text-foreground mb-2">손절 접근 알림</h3>
          <div className="text-xs text-secondary space-y-1">
            <div>트리거: {risk?.stopLoss?.triggeredCount ?? 0}</div>
            <div>접근 중: {risk?.stopLoss?.nearCount ?? 0}</div>
            <div>경고: {risk?.stopLoss?.nearAlert ? '예' : '아니오'}</div>
          </div>
        </Card>
        <Card padding="md">
          <h3 className="text-sm font-semibold text-foreground mb-2">계정</h3>
          <div className="text-xs text-secondary space-y-1">
            <div>계좌 수: {snapshot?.accountCount ?? 0}</div>
            <div>표시 통화: {snapshot?.currency || 'CNY'}</div>
            <div>원가 방식: {(snapshot?.costMethod || costMethod).toUpperCase()}</div>
          </div>
        </Card>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        <Card padding="md">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h3 className="text-sm font-semibold text-foreground">Paper 주문 준비</h3>
            <Badge variant="info">approval required</Badge>
          </div>
          <form className="space-y-2" onSubmit={handlePaperPrepare}>
            <input className={PORTFOLIO_INPUT_CLASS} placeholder="Paper 종목 코드, 예: AAPL" value={paperForm.symbol}
              onChange={(e) => setPaperForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
            <div className="grid grid-cols-2 gap-2">
              <input className={PORTFOLIO_INPUT_CLASS} type="date" value={paperForm.tradeDate}
                onChange={(e) => setPaperForm((prev) => ({ ...prev, tradeDate: e.target.value }))} required />
              <select className={PORTFOLIO_SELECT_CLASS} value={paperForm.side}
                onChange={(e) => setPaperForm((prev) => ({ ...prev, side: e.target.value as PortfolioSide }))}>
                <option value="buy">매수</option>
                <option value="sell">매도</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="Paper 수량"
                value={paperForm.quantity} onChange={(e) => setPaperForm((prev) => ({ ...prev, quantity: e.target.value }))} required />
              <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="Paper 가격"
                value={paperForm.price} onChange={(e) => setPaperForm((prev) => ({ ...prev, price: e.target.value }))} required />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select className={PORTFOLIO_SELECT_CLASS} value={paperForm.market}
                onChange={(e) => setPaperForm((prev) => ({ ...prev, market: e.target.value as 'cn' | 'hk' | 'us' }))}>
                <option value="us">US</option>
                <option value="hk">HK</option>
                <option value="cn">CN</option>
              </select>
              <input className={PORTFOLIO_INPUT_CLASS} placeholder="통화, 예: USD" value={paperForm.currency}
                onChange={(e) => setPaperForm((prev) => ({ ...prev, currency: e.target.value.toUpperCase() }))} />
            </div>
            <textarea className={`${PORTFOLIO_INPUT_CLASS} min-h-24 py-3`} placeholder="주문 사유 또는 thesis"
              value={paperForm.reason} onChange={(e) => setPaperForm((prev) => ({ ...prev, reason: e.target.value }))} />
            <button type="submit" className="btn-secondary w-full" disabled={!writableAccountId || paperPreparing}>
              {paperPreparing ? '검토 중...' : 'Paper 주문 검토'}
            </button>
          </form>
        </Card>

        <Card padding="md">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h3 className="text-sm font-semibold text-foreground">Paper 주문 검토 결과</h3>
            {paperPrepareResult ? <Badge variant={paperPrepareResult.canExecuteAfterApproval ? 'success' : 'warning'}>{paperPrepareResult.status}</Badge> : null}
          </div>
          {paperPrepareResult ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div className="rounded-lg border border-border bg-surface/40 p-2">
                  <div className="text-tertiary">종목</div>
                  <div className="font-semibold text-foreground">{formatPaperOrderValue(paperPrepareResult.order, 'symbol')}</div>
                </div>
                <div className="rounded-lg border border-border bg-surface/40 p-2">
                  <div className="text-tertiary">방향</div>
                  <div className="font-semibold text-foreground">{formatPaperSideLabel(formatPaperOrderValue(paperPrepareResult.order, 'side'))}</div>
                </div>
                <div className="rounded-lg border border-border bg-surface/40 p-2">
                  <div className="text-tertiary">수량</div>
                  <div className="font-semibold text-foreground">{formatPaperOrderValue(paperPrepareResult.order, 'quantity')}</div>
                </div>
                <div className="rounded-lg border border-border bg-surface/40 p-2">
                  <div className="text-tertiary">가격</div>
                  <div className="font-semibold text-foreground">{formatPaperOrderValue(paperPrepareResult.order, 'price')}</div>
                </div>
              </div>
              <div className="text-xs text-secondary space-y-1">
                <div>실행 모드: {paperPrepareResult.mode}</div>
                <div>브로커 실행: {paperPrepareResult.brokerExecution}</div>
                <div>승인 토큰: {paperPrepareResult.approvalToken}</div>
              </div>
              <div className="space-y-2">
                {(paperPrepareResult.riskChecks || []).length > 0 ? (
                  paperPrepareResult.riskChecks.map((item, index) => (
                    <InlineAlert
                      key={`${String(item.name ?? item.type ?? 'risk')}-${index}`}
                      variant={getPaperRiskTone(item)}
                      className="rounded-lg px-3 py-2 text-xs shadow-none"
                      message={formatPaperRiskCheck(item)}
                    />
                  ))
                ) : (
                  <InlineAlert
                    variant="info"
                    className="rounded-lg px-3 py-2 text-xs shadow-none"
                    message="리스크 체크 결과가 비어 있습니다."
                  />
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={!paperPrepareResult.canExecuteAfterApproval || paperExecuting}
                  onClick={() => void handlePaperExecute(true)}
                >
                  {paperExecuting ? '처리 중...' : '승인 후 기록'}
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={paperExecuting}
                  onClick={() => void handlePaperExecute(false)}
                >
                  거절 기록
                </button>
              </div>
              {paperExecuteResult ? (
                <InlineAlert
                  variant={paperExecuteResult.status === 'recorded' ? 'success' : 'info'}
                  title={paperExecuteResult.status === 'recorded' ? 'Paper 거래 기록 완료' : 'Paper 주문 처리 결과'}
                  message={
                    paperExecuteResult.tradeId
                      ? `거래 ID ${paperExecuteResult.tradeId}로 저장되었습니다.`
                      : (paperExecuteResult.reason || paperExecuteResult.status)
                  }
                  className="rounded-lg px-3 py-2 text-xs shadow-none"
                />
              ) : null}
            </div>
          ) : (
            <EmptyState
              title="검토 대기"
              description="Paper 주문을 준비하면 risk check와 승인 가능 여부가 여기에 표시됩니다."
              className="border-none bg-transparent px-4 py-10 shadow-none"
            />
          )}
        </Card>
      </section>

      <Card padding="md">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Paper Trading 성과</h3>
            <p className="text-xs text-secondary mt-1">paper 거래의 수익률, 보유 기간, 승패를 현재 스냅샷 기준으로 추적합니다.</p>
          </div>
          <button type="button" className="btn-secondary text-sm" onClick={() => void loadPaperPerformance()} disabled={paperPerformanceLoading}>
            {paperPerformanceLoading ? '계산 중...' : '성과 새로고침'}
          </button>
        </div>
        {paperPerformanceWarning ? (
          <InlineAlert
            variant="warning"
            className="rounded-lg px-3 py-2 text-xs shadow-none mb-3"
            message={paperPerformanceWarning}
          />
        ) : null}
        {paperPerformance ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-tertiary">총 paper 거래</div>
                <div className="font-semibold text-foreground">{paperPerformance.totalTrades}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-tertiary">열림/닫힘</div>
                <div className="font-semibold text-foreground">{paperPerformance.openTrades}/{paperPerformance.closedTrades}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-tertiary">승패</div>
                <div className="font-semibold text-foreground">{paperPerformance.winCount}/{paperPerformance.lossCount}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-tertiary">승률</div>
                <div className="font-semibold text-foreground">{formatPct(paperPerformance.winRatePct)}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-tertiary">평균 수익률</div>
                <div className="font-semibold text-foreground">{formatSignedPct(paperPerformance.avgReturnPct)}</div>
              </div>
            </div>
            {paperPerformance.backtestComparison ? (
              <InlineAlert
                variant="info"
                className="rounded-lg px-3 py-2 text-xs shadow-none"
                title="백테스트 비교"
                message={`백테스트 평균 수익률 ${formatSignedPct(paperPerformance.backtestComparison.avgReturnPct)}, 승률 ${formatPct(paperPerformance.backtestComparison.winRatePct)}, 평가 ${paperPerformance.backtestComparison.totalEvaluations ?? 0}건`}
              />
            ) : (
              <InlineAlert
                variant="info"
                className="rounded-lg px-3 py-2 text-xs shadow-none"
                message="비교 가능한 백테스트 summary가 아직 없습니다."
              />
            )}
            {paperPerformance.items.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="min-w-[820px] w-full text-xs">
                  <thead className="bg-surface/70 text-secondary">
                    <tr>
                      <th className="px-3 py-2 text-left">종목</th>
                      <th className="px-3 py-2 text-left">상태</th>
                      <th className="px-3 py-2 text-right">수익률</th>
                      <th className="px-3 py-2 text-right">손익</th>
                      <th className="px-3 py-2 text-right">보유일</th>
                      <th className="px-3 py-2 text-right">진입/평가</th>
                      <th className="px-3 py-2 text-right">잔여</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paperPerformance.items.map((item) => (
                      <tr key={`${item.tradeId}-${item.tradeUid || item.symbol}`} className="border-t border-border/70">
                        <td className="px-3 py-2 font-semibold text-foreground">{item.symbol}</td>
                        <td className="px-3 py-2">
                          <Badge variant={item.outcome === 'win' ? 'success' : item.outcome === 'loss' ? 'danger' : 'default'}>
                            {item.status === 'closed' ? '종료' : '진행'} · {formatPaperOutcomeLabel(item.outcome)}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-right">{formatSignedPct(item.returnPct)}</td>
                        <td className="px-3 py-2 text-right">{item.pnl.toFixed(2)}</td>
                        <td className="px-3 py-2 text-right">{item.holdingDays}일</td>
                        <td className="px-3 py-2 text-right">{item.entryPrice.toFixed(2)} / {item.markPrice.toFixed(2)}</td>
                        <td className="px-3 py-2 text-right">{item.remainingQuantity.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="paper 거래 없음"
                description="승인된 paper 주문이 기록되면 성과 추적표가 표시됩니다."
                className="border-none bg-transparent px-4 py-10 shadow-none"
              />
            )}
          </div>
        ) : (
          <EmptyState
            title="성과 데이터 없음"
            description="Paper trading 성과를 불러오면 요약과 거래별 결과가 표시됩니다."
            className="border-none bg-transparent px-4 py-10 shadow-none"
          />
        )}
      </Card>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-3">
        <Card padding="md">
          <h3 className="text-sm font-semibold text-foreground mb-3">수동 입력: 거래</h3>
          <form className="space-y-2" onSubmit={handleTradeSubmit}>
            <input className={PORTFOLIO_INPUT_CLASS} placeholder="종목 코드, 예: KR005930" value={tradeForm.symbol}
              onChange={(e) => setTradeForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
            <div className="grid grid-cols-2 gap-2">
              <input className={PORTFOLIO_INPUT_CLASS} type="date" value={tradeForm.tradeDate}
                onChange={(e) => setTradeForm((prev) => ({ ...prev, tradeDate: e.target.value }))} required />
              <select className={PORTFOLIO_SELECT_CLASS} value={tradeForm.side}
                onChange={(e) => setTradeForm((prev) => ({ ...prev, side: e.target.value as PortfolioSide }))}>
                <option value="buy">매수</option>
                <option value="sell">매도</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="수량(필수)" value={tradeForm.quantity}
                onChange={(e) => setTradeForm((prev) => ({ ...prev, quantity: e.target.value }))} required />
              <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="가격(필수)" value={tradeForm.price}
                onChange={(e) => setTradeForm((prev) => ({ ...prev, price: e.target.value }))} required />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="수수료(선택)" value={tradeForm.fee}
                onChange={(e) => setTradeForm((prev) => ({ ...prev, fee: e.target.value }))} />
              <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="세금(선택)" value={tradeForm.tax}
                onChange={(e) => setTradeForm((prev) => ({ ...prev, tax: e.target.value }))} />
            </div>
            <p className="text-xs text-secondary">수수료와 세금이 비어 있으면 시스템에서 0으로 처리합니다.</p>
            <button type="submit" className="btn-secondary w-full" disabled={!writableAccountId}>거래 제출</button>
          </form>
        </Card>

        <Card padding="md">
          <h3 className="text-sm font-semibold text-foreground mb-3">수동 입력: 현금 내역</h3>
          <form className="space-y-2" onSubmit={handleCashSubmit}>
            <div className="grid grid-cols-2 gap-2">
              <input className={PORTFOLIO_INPUT_CLASS} type="date" value={cashForm.eventDate}
                onChange={(e) => setCashForm((prev) => ({ ...prev, eventDate: e.target.value }))} required />
              <select className={PORTFOLIO_SELECT_CLASS} value={cashForm.direction}
                onChange={(e) => setCashForm((prev) => ({ ...prev, direction: e.target.value as PortfolioCashDirection }))}>
                <option value="in">입금</option>
                <option value="out">출금</option>
              </select>
            </div>
            <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="금액"
              value={cashForm.amount} onChange={(e) => setCashForm((prev) => ({ ...prev, amount: e.target.value }))} required />
            <input className={PORTFOLIO_INPUT_CLASS} placeholder={`통화(선택, 기본값: ${writableAccount?.baseCurrency || '계좌 기준 통화'})`} value={cashForm.currency}
              onChange={(e) => setCashForm((prev) => ({ ...prev, currency: e.target.value }))} />
            <button type="submit" className="btn-secondary w-full" disabled={!writableAccountId}>현금 내역 제출</button>
          </form>
        </Card>

        <Card padding="md">
          <h3 className="text-sm font-semibold text-foreground mb-3">수동 입력: 기업 행동</h3>
          <form className="space-y-2" onSubmit={handleCorporateSubmit}>
            <input className={PORTFOLIO_INPUT_CLASS} placeholder="종목 코드" value={corpForm.symbol}
              onChange={(e) => setCorpForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
            <div className="grid grid-cols-2 gap-2">
              <input className={PORTFOLIO_INPUT_CLASS} type="date" value={corpForm.effectiveDate}
                onChange={(e) => setCorpForm((prev) => ({ ...prev, effectiveDate: e.target.value }))} required />
              <select className={PORTFOLIO_SELECT_CLASS} value={corpForm.actionType}
                onChange={(e) => setCorpForm((prev) => ({ ...prev, actionType: e.target.value as PortfolioCorporateActionType }))}>
                <option value="cash_dividend">현금 배당</option>
                <option value="split_adjustment">분할/병합 조정</option>
              </select>
            </div>
            {corpForm.actionType === 'cash_dividend' ? (
              <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.000001" placeholder="주당 배당"
                value={corpForm.cashDividendPerShare}
                onChange={(e) => setCorpForm((prev) => ({ ...prev, cashDividendPerShare: e.target.value, splitRatio: '' }))} required />
            ) : (
              <input className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.000001" placeholder="분할/병합 비율"
                value={corpForm.splitRatio}
                onChange={(e) => setCorpForm((prev) => ({ ...prev, splitRatio: e.target.value, cashDividendPerShare: '' }))} required />
            )}
            <button type="submit" className="btn-secondary w-full" disabled={!writableAccountId}>기업 행동 제출</button>
          </form>
        </Card>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        <Card padding="md">
          <h3 className="text-sm font-semibold text-foreground mb-3">브로커 CSV 가져오기</h3>
          <div className="space-y-2">
            {brokerLoadWarning ? (
              <InlineAlert
                variant="warning"
                className="rounded-lg px-2 py-1 text-xs shadow-none"
                message={brokerLoadWarning}
              />
            ) : null}
            <div className="grid grid-cols-2 gap-2">
              <select className={PORTFOLIO_SELECT_CLASS} value={selectedBroker} onChange={(e) => setSelectedBroker(e.target.value)}>
                {brokers.length > 0 ? (
                  brokers.map((item) => <option key={item.broker} value={item.broker}>{formatBrokerLabel(item.broker, item.displayName)}</option>)
                ) : (
                  <option value="huatai">huatai(Huatai)</option>
                )}
              </select>
              <label className={PORTFOLIO_FILE_PICKER_CLASS}>
                CSV 선택
                <input type="file" accept=".csv" className="hidden"
                  onChange={(e) => setCsvFile(e.target.files && e.target.files[0] ? e.target.files[0] : null)} />
              </label>
            </div>
            <div className="flex items-center gap-2 text-xs text-secondary">
              <input id="csv-dry-run" type="checkbox" checked={csvDryRun} onChange={(e) => setCsvDryRun(e.target.checked)} />
              <label htmlFor="csv-dry-run">미리보기만 실행</label>
            </div>
            <div className="flex gap-2">
              <button type="button" className="btn-secondary flex-1" disabled={!csvFile || csvParsing} onClick={() => void handleParseCsv()}>
                {csvParsing ? '파싱 중...' : '파일 파싱'}
              </button>
              <button type="button" className="btn-secondary flex-1"
                disabled={!csvFile || !writableAccountId || csvCommitting} onClick={() => void handleCommitCsv()}>
                {csvCommitting ? '제출 중...' : '가져오기 제출'}
              </button>
            </div>
            {csvParseResult ? (
              <InlineAlert
                variant={getCsvParseVariant(csvParseResult)}
                title="CSV 파싱 결과"
                message={`유효 ${csvParseResult.recordCount}개, 건너뜀 ${csvParseResult.skippedCount}개, 오류 ${csvParseResult.errorCount}개`}
                className="rounded-lg px-3 py-2 text-xs shadow-none"
              />
            ) : null}
            {csvCommitResult ? (
              <InlineAlert
                variant={getCsvCommitVariant(csvCommitResult, csvDryRun)}
                title={csvDryRun ? 'CSV 미리보기 결과' : 'CSV 제출 결과'}
                message={`${csvDryRun ? '미리보기' : '실제 저장'}: 저장 ${csvCommitResult.insertedCount}개, 중복 ${csvCommitResult.duplicateCount}개, 실패 ${csvCommitResult.failedCount}개`}
                className="rounded-lg px-3 py-2 text-xs shadow-none"
              />
            ) : null}
          </div>
        </Card>

        <Card padding="md">
          <h3 className="text-sm font-semibold text-foreground mb-3">이벤트 기록</h3>
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <select className={PORTFOLIO_SELECT_CLASS} value={eventType} onChange={(e) => setEventType(e.target.value as EventType)}>
                <option value="trade">거래 내역</option>
                <option value="cash">현금 내역</option>
                <option value="corporate">기업 행동</option>
              </select>
              <button type="button" className="btn-secondary text-sm" onClick={() => void loadEvents()} disabled={eventLoading}>
                {eventLoading ? '불러오는 중...' : '내역 새로고침'}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input className={PORTFOLIO_INPUT_CLASS} type="date" value={eventDateFrom} onChange={(e) => setEventDateFrom(e.target.value)} />
              <input className={PORTFOLIO_INPUT_CLASS} type="date" value={eventDateTo} onChange={(e) => setEventDateTo(e.target.value)} />
            </div>
            {(eventType === 'trade' || eventType === 'corporate') ? (
              <input className={PORTFOLIO_INPUT_CLASS} placeholder="종목 코드 필터" value={eventSymbol}
                onChange={(e) => setEventSymbol(e.target.value)} />
            ) : null}
            {eventType === 'trade' ? (
              <select className={PORTFOLIO_SELECT_CLASS} value={eventSide} onChange={(e) => setEventSide(e.target.value as '' | PortfolioSide)}>
                <option value="">모든 매매 방향</option>
                <option value="buy">매수</option>
                <option value="sell">매도</option>
              </select>
            ) : null}
            {eventType === 'cash' ? (
              <select className={PORTFOLIO_SELECT_CLASS} value={eventDirection}
                onChange={(e) => setEventDirection(e.target.value as '' | PortfolioCashDirection)}>
                <option value="">모든 현금 방향</option>
                <option value="in">입금</option>
                <option value="out">출금</option>
              </select>
            ) : null}
            {eventType === 'corporate' ? (
              <select className={PORTFOLIO_SELECT_CLASS} value={eventActionType}
                onChange={(e) => setEventActionType(e.target.value as '' | PortfolioCorporateActionType)}>
                <option value="">모든 기업 행동</option>
                <option value="cash_dividend">현금 배당</option>
                <option value="split_adjustment">분할/병합 조정</option>
              </select>
            ) : null}
            <div className="text-[11px] text-secondary">
              {writeBlocked ? '삭제와 수정은 단일 계좌 보기에서만 사용할 수 있습니다. 특정 계좌를 선택한 뒤 내역을 삭제하세요.' : '내역을 삭제하면 다시 입력할 수 있습니다.'}
            </div>
            <div className="max-h-64 overflow-auto rounded-lg border border-white/10 p-2">
              {eventType === 'trade' && tradeEvents.map((item) => (
                <div key={`t-${item.id}`} className="flex items-start justify-between gap-3 border-b border-white/5 py-2 text-xs text-secondary">
                  <div className="min-w-0">
                    {item.tradeDate} {formatSideLabel(item.side)} {item.symbol} 수량={item.quantity} 가격={item.price}
                  </div>
                  {!writeBlocked ? (
                    <button
                      type="button"
                      className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                      onClick={() => openDeleteDialog({
                        eventType: 'trade',
                        id: item.id,
                        message: `삭제 확인: ${item.tradeDate} ${formatSideLabel(item.side)} 내역 ${item.symbol}(수량 ${item.quantity}, 가격 ${item.price})을 삭제할까요?`,
                      })}
                    >
                      삭제
                    </button>
                  ) : null}
                </div>
              ))}
              {eventType === 'cash' && cashEvents.map((item) => (
                <div key={`c-${item.id}`} className="flex items-start justify-between gap-3 border-b border-white/5 py-2 text-xs text-secondary">
                  <div className="min-w-0">
                    {item.eventDate} {formatCashDirectionLabel(item.direction)} {item.amount} {item.currency}
                  </div>
                  {!writeBlocked ? (
                    <button
                      type="button"
                      className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                      onClick={() => openDeleteDialog({
                        eventType: 'cash',
                        id: item.id,
                        message: `삭제 확인: ${item.eventDate} 현금 내역(${formatCashDirectionLabel(item.direction)} ${item.amount} ${item.currency})을 삭제할까요?`,
                      })}
                    >
                      삭제
                    </button>
                  ) : null}
                </div>
              ))}
              {eventType === 'corporate' && corporateEvents.map((item) => (
                <div key={`ca-${item.id}`} className="flex items-start justify-between gap-3 border-b border-white/5 py-2 text-xs text-secondary">
                  <div className="min-w-0">
                    {item.effectiveDate} {formatCorporateActionLabel(item.actionType)} {item.symbol}
                  </div>
                  {!writeBlocked ? (
                    <button
                      type="button"
                      className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                      onClick={() => openDeleteDialog({
                        eventType: 'corporate',
                        id: item.id,
                        message: `삭제 확인: ${item.effectiveDate} 기업 행동 ${formatCorporateActionLabel(item.actionType)}(${item.symbol})을 삭제할까요?`,
                      })}
                    >
                      삭제
                    </button>
                  ) : null}
                </div>
              ))}
              {!eventLoading
                && ((eventType === 'trade' && tradeEvents.length === 0)
                  || (eventType === 'cash' && cashEvents.length === 0)
                  || (eventType === 'corporate' && corporateEvents.length === 0)) ? (
                    <EmptyState
                      title="내역 없음"
                      description="필터 조건을 조정하거나 거래, 현금 내역, 기업 행동을 먼저 입력하세요."
                      className="border-none bg-transparent px-3 py-6 shadow-none"
                    />
                  ) : null}
            </div>
            <div className="flex items-center justify-between text-xs text-secondary">
              <span>페이지 {eventPage} / {totalEventPages}</span>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary text-xs px-3 py-1" disabled={eventPage <= 1}
                  onClick={() => setEventPage((prev) => Math.max(1, prev - 1))}>
                  이전 페이지
                </button>
                <button type="button" className="btn-secondary text-xs px-3 py-1" disabled={eventPage >= totalEventPages}
                  onClick={() => setEventPage((prev) => Math.min(totalEventPages, prev + 1))}>
                  다음 페이지
                </button>
              </div>
            </div>
          </div>
        </Card>
      </section>
      <ConfirmDialog
        isOpen={Boolean(pendingDelete)}
        title="선택한 내역 삭제"
        message={pendingDelete?.message || '이 내역을 삭제할까요?'}
        confirmText={deleteLoading ? '삭제 중...' : '삭제 확인'}
        cancelText="취소"
        isDanger
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => {
          if (!deleteLoading) {
            setPendingDelete(null);
          }
        }}
      />
    </div>
  );
};

export default PortfolioPage;


