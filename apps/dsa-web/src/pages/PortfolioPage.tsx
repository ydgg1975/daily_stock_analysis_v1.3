import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pie, PieChart, ResponsiveContainer, Tooltip, Legend, Cell } from 'recharts';
import { portfolioApi } from '../api/portfolio';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Card, Badge, ConfirmDialog, Disclosure, WorkspacePageHeader } from '../components/common';
import { toDateInputValue } from '../utils/format';
import { getMarketDirectionColor } from '../utils/marketColors';
import type {
  PortfolioAccountItem,
  PortfolioBrokerConnectionItem,
  PortfolioCashDirection,
  PortfolioCashLedgerListItem,
  PortfolioCorporateActionListItem,
  PortfolioCorporateActionType,
  PortfolioCostMethod,
  PortfolioFxRefreshResponse,
  PortfolioImportBrokerItem,
  PortfolioImportCommitResponse,
  PortfolioImportParseResponse,
  PortfolioIbkrSyncResponse,
  PortfolioPositionItem,
  PortfolioRiskResponse,
  PortfolioSide,
  PortfolioSnapshotResponse,
  PortfolioTradeListItem,
} from '../types/portfolio';

const PIE_COLORS = ['#f0f0fa', '#d8d8e2', '#b5b5c1', '#8d8d98', '#6b6b74', '#4c4c53'];
const DEFAULT_PAGE_SIZE = 20;
const FALLBACK_BROKERS: PortfolioImportBrokerItem[] = [
  { broker: 'huatai', aliases: [], displayName: '华泰', fileExtensions: ['csv'] },
  { broker: 'citic', aliases: ['zhongxin'], displayName: '中信', fileExtensions: ['csv'] },
  { broker: 'cmb', aliases: ['cmbchina', 'zhaoshang'], displayName: '招商', fileExtensions: ['csv'] },
  { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: 'Interactive Brokers', fileExtensions: ['xml'] },
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

function formatSideLabel(value: PortfolioSide): string {
  return value === 'buy' ? '买入' : '卖出';
}

function formatCashDirectionLabel(value: PortfolioCashDirection): string {
  return value === 'in' ? '流入' : '流出';
}

function formatCorporateActionLabel(value: PortfolioCorporateActionType): string {
  return value === 'cash_dividend' ? '现金分红' : '拆并股调整';
}

function formatBrokerLabel(value: string, displayName?: string): string {
  if (displayName && displayName.trim()) return `${value}（${displayName.trim()}）`;
  if (value === 'huatai') return 'huatai（华泰）';
  if (value === 'citic') return 'citic（中信）';
  if (value === 'cmb') return 'cmb（招商）';
  if (value === 'ibkr') return 'ibkr（Interactive Brokers）';
  return value;
}

function formatAccountMarketLabel(value: string): string {
  if (value === 'global') return '全球市场';
  if (value === 'hk') return '港股';
  if (value === 'us') return '美股';
  return 'A 股';
}

function formatPositionContext(market: string, currency: string): string {
  const marketLabel = market === 'hk' ? 'HK' : market === 'us' ? 'US' : market === 'cn' ? 'CN' : market.toUpperCase();
  return `${marketLabel} / ${currency || '--'}`;
}

function extractIbkrSyncConfig(connection?: PortfolioBrokerConnectionItem | null): {
  apiBaseUrl?: string;
  verifySsl?: boolean;
  brokerAccountRef?: string;
  lastSyncAt?: string;
} {
  const metadata = connection?.syncMetadata;
  if (!metadata || typeof metadata !== 'object') {
    return {};
  }
  const nested = (metadata as Record<string, unknown>).ibkrApi;
  if (!nested || typeof nested !== 'object') {
    return {};
  }
  const record = nested as Record<string, unknown>;
  return {
    apiBaseUrl: typeof record.apiBaseUrl === 'string' ? record.apiBaseUrl : undefined,
    verifySsl: typeof record.verifySsl === 'boolean' ? record.verifySsl : undefined,
    brokerAccountRef: typeof record.brokerAccountRef === 'string' ? record.brokerAccountRef : undefined,
    lastSyncAt: typeof (metadata as Record<string, unknown>).lastSyncAt === 'string'
      ? ((metadata as Record<string, unknown>).lastSyncAt as string)
      : undefined,
  };
}

function buildFxRefreshFeedback(data: PortfolioFxRefreshResponse): FxRefreshFeedback {
  if (data.refreshEnabled === false) {
    return {
      tone: 'neutral',
      text: '汇率在线刷新已被禁用。',
    };
  }

  if (data.pairCount === 0) {
    return {
      tone: 'neutral',
      text: '当前范围无可刷新的汇率对。',
    };
  }

  if (data.updatedCount > 0 && data.staleCount === 0 && data.errorCount === 0) {
    return {
      tone: 'success',
      text: `汇率已刷新，共更新 ${data.updatedCount} 对。`,
    };
  }

  const summary = `更新 ${data.updatedCount} 对，仍过期 ${data.staleCount} 对，失败 ${data.errorCount} 对。`;
  if (data.staleCount > 0) {
    return {
      tone: 'warning',
      text: `已尝试刷新，但仍有部分货币对使用 stale/fallback 汇率。${summary}`,
    };
  }

  return {
    tone: 'warning',
    text: `在线刷新未完全成功。${summary}`,
  };
}

const PortfolioPage: React.FC = () => {
  // Set page title
  useEffect(() => {
    document.title = '持仓分析 - WolfyStock';
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
    market: 'cn' as 'cn' | 'hk' | 'us' | 'global',
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
  const [brokerConnections, setBrokerConnections] = useState<PortfolioBrokerConnectionItem[]>([]);
  const [selectedBroker, setSelectedBroker] = useState('huatai');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvDryRun, setCsvDryRun] = useState(true);
  const [csvParsing, setCsvParsing] = useState(false);
  const [csvCommitting, setCsvCommitting] = useState(false);
  const [csvParseResult, setCsvParseResult] = useState<PortfolioImportParseResponse | null>(null);
  const [csvCommitResult, setCsvCommitResult] = useState<PortfolioImportCommitResponse | null>(null);
  const [brokerLoadWarning, setBrokerLoadWarning] = useState<string | null>(null);
  const [ibkrApiBaseUrl, setIbkrApiBaseUrl] = useState('https://localhost:5000/v1/api');
  const [ibkrVerifySsl, setIbkrVerifySsl] = useState(false);
  const [ibkrSessionToken, setIbkrSessionToken] = useState('');
  const [ibkrBrokerAccountRef, setIbkrBrokerAccountRef] = useState('');
  const [ibkrSyncing, setIbkrSyncing] = useState(false);
  const [ibkrSyncResult, setIbkrSyncResult] = useState<PortfolioIbkrSyncResponse | null>(null);

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

  const queryAccountId = selectedAccount === 'all' ? undefined : selectedAccount;
  const refreshViewKey = `${selectedAccount === 'all' ? 'all' : `account:${selectedAccount}`}:cost:${costMethod}`;
  const refreshContextRef = useRef<FxRefreshContext>({ viewKey: refreshViewKey, requestId: 0 });
  const hasAccounts = accounts.length > 0;
  const writableAccount = selectedAccount === 'all' ? undefined : accounts.find((item) => item.id === selectedAccount);
  const writableAccountId = writableAccount?.id;
  const writeBlocked = !writableAccountId;
  const selectedBrokerSpec = useMemo(
    () => brokers.find((item) => item.broker === selectedBroker) || FALLBACK_BROKERS.find((item) => item.broker === selectedBroker),
    [brokers, selectedBroker],
  );
  const ibkrConnection = useMemo(
    () => brokerConnections.find((item) => item.brokerType === 'ibkr') || null,
    [brokerConnections],
  );
  const importFileAccept = useMemo(() => {
    const extensions = selectedBrokerSpec?.fileExtensions?.length ? selectedBrokerSpec.fileExtensions : ['csv'];
    return extensions.map((item) => `.${item.replace(/^\./, '')}`).join(',');
  }, [selectedBrokerSpec]);
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
        setBrokerLoadWarning('券商列表接口返回为空，已回退为内置券商列表（华泰/中信/招商/IBKR）。');
        setSelectedBroker((prev) => (
          FALLBACK_BROKERS.some((item) => item.broker === prev)
            ? prev
            : FALLBACK_BROKERS[0].broker
        ));
        return;
      }
      setBrokers(brokerItems);
      setBrokerLoadWarning(null);
      setSelectedBroker((prev) => (
        brokerItems.some((item) => item.broker === prev)
          ? prev
          : brokerItems[0].broker
      ));
    } catch {
      setBrokers(FALLBACK_BROKERS);
      setBrokerLoadWarning('券商列表接口不可用，已回退为内置券商列表（华泰/中信/招商/IBKR）。');
      setSelectedBroker((prev) => (
        FALLBACK_BROKERS.some((item) => item.broker === prev)
          ? prev
          : FALLBACK_BROKERS[0].broker
      ));
    }
  }, []);

  const loadBrokerConnections = useCallback(async (accountId?: number) => {
    if (!accountId) {
      setBrokerConnections([]);
      return;
    }
    try {
      const response = await portfolioApi.listBrokerConnections(accountId);
      setBrokerConnections(response.connections || []);
    } catch {
      setBrokerConnections([]);
    }
  }, []);

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
        setRiskWarning(parsed.message || '风险数据获取失败，已降级为仅展示快照数据。');
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

  useEffect(() => {
    void loadAccounts();
    void loadBrokers();
  }, [loadAccounts, loadBrokers]);

  useEffect(() => {
    void loadBrokerConnections(writableAccountId);
  }, [loadBrokerConnections, writableAccountId]);

  useEffect(() => {
    const config = extractIbkrSyncConfig(ibkrConnection);
    setIbkrApiBaseUrl(config.apiBaseUrl || 'https://localhost:5000/v1/api');
    setIbkrVerifySsl(config.verifySsl ?? false);
    setIbkrBrokerAccountRef(config.brokerAccountRef || ibkrConnection?.brokerAccountRef || '');
  }, [ibkrConnection, writableAccountId]);

  useEffect(() => {
    setIbkrSyncResult(null);
    if (selectedBroker !== 'ibkr') {
      setIbkrSessionToken('');
    }
  }, [selectedBroker, writableAccountId]);

  useEffect(() => {
    void loadSnapshotAndRisk();
  }, [loadSnapshotAndRisk]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

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
      setWriteWarning('请先在右上角选择具体账户，再进行录入或导入提交。');
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

  const handleCashSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writableAccountId) {
      setWriteWarning('请先在右上角选择具体账户，再进行录入或导入提交。');
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
      setWriteWarning('请先在右上角选择具体账户，再进行录入或导入提交。');
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
      setWriteWarning('请先在右上角选择具体账户，再进行录入或导入提交。');
      return;
    }
    try {
      setWriteWarning(null);
      setCsvCommitting(true);
      const committed = await portfolioApi.commitCsvImport(writableAccountId, selectedBroker, csvFile, csvDryRun);
      setCsvCommitResult(committed);
      await loadBrokerConnections(writableAccountId);
      if (!csvDryRun) {
        await refreshPortfolioData();
      }
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setCsvCommitting(false);
    }
  };

  const handleSyncIbkr = async () => {
    if (!writableAccountId) {
      setWriteWarning('请先在右上角选择具体账户，再触发 IBKR 只读同步。');
      return;
    }
    if (!ibkrSessionToken.trim()) {
      setWriteWarning('请提供当前有效的 IBKR session token，再执行只读同步。');
      return;
    }
    try {
      setWriteWarning(null);
      setIbkrSyncing(true);
      const result = await portfolioApi.syncIbkrReadOnly({
        accountId: writableAccountId,
        brokerConnectionId: ibkrConnection?.id,
        brokerAccountRef: ibkrBrokerAccountRef.trim() || undefined,
        sessionToken: ibkrSessionToken.trim(),
        apiBaseUrl: ibkrApiBaseUrl.trim() || undefined,
        verifySsl: ibkrVerifySsl,
      });
      setIbkrSyncResult(result);
      setIbkrSessionToken('');
      await loadBrokerConnections(writableAccountId);
      await refreshPortfolioData();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIbkrSyncing(false);
    }
  };

  const openDeleteDialog = (item: PendingDelete) => {
    if (!writableAccountId) {
      setWriteWarning('请先在右上角选择具体账户，再进行删除修正。');
      return;
    }
    setPendingDelete(item);
  };

  const handleConfirmDelete = async () => {
    if (!pendingDelete || deleteLoading) return;
    if (!writableAccountId) {
      setWriteWarning('请先在右上角选择具体账户，再进行删除修正。');
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
      setAccountCreateError('账户名称不能为空。');
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
      setAccountCreateSuccess('账户创建成功，已自动切换到该账户。');
    } catch (err) {
      const parsed = getParsedApiError(err);
      setAccountCreateError(parsed.message || '创建账户失败，请稍后重试。');
      setAccountCreateSuccess(null);
    } finally {
      setAccountCreating(false);
    }
  };

  const handleRefresh = async () => {
    await Promise.all([loadAccounts(), loadSnapshotAndRisk(), loadEvents(), loadBrokers(), loadBrokerConnections(writableAccountId)]);
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
        setRiskWarning(parsed.message || '风险数据获取失败，已降级为仅展示快照数据。');
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
  const showEventAuditDisclosureByDefault = eventLoading
    || currentEventCount > 0
    || Boolean(eventDateFrom)
    || Boolean(eventDateTo)
    || Boolean(eventSymbol)
    || Boolean(eventSide)
    || Boolean(eventDirection)
    || Boolean(eventActionType);

  return (
    <div className="workspace-page workspace-page--portfolio">
      <WorkspacePageHeader
        eyebrow="WolfyStock Portfolio Desk"
        title="持仓管理"
        description="组合快照与风险评估"
        actions={hasAccounts ? (
          <>
            <button
              type="button"
              className="btn-secondary text-sm"
              onClick={() => {
                setShowCreateAccount((prev) => !prev);
                setAccountCreateError(null);
                setAccountCreateSuccess(null);
              }}
            >
              {showCreateAccount ? '收起新建' : '新建账户'}
            </button>
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={isLoading || fxRefreshing}
              className="btn-secondary text-sm"
            >
              {isLoading ? '刷新中...' : '刷新数据'}
            </button>
          </>
        ) : (
          <p className="workspace-header-actions-note">
            还没有可用账户，请先创建账户后再录入交易或导入券商文件。
          </p>
        )}
      >
        {hasAccounts ? (
          <div className="workspace-surface-muted p-3.5">
            <div className="grid grid-cols-1 gap-2 xl:grid-cols-[minmax(0,1fr)_220px_minmax(0,260px)] xl:items-end">
              <div>
                <p className="mb-1 text-xs text-secondary">账户视图</p>
                <select
                  value={String(selectedAccount)}
                  onChange={(e) => setSelectedAccount(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                  className="input-terminal w-full text-sm"
                >
                  <option value="all">全部账户</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name} · {formatAccountMarketLabel(account.market)} · {account.baseCurrency} (#{account.id})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <p className="mb-1 text-xs text-secondary">成本口径</p>
                <select
                  value={costMethod}
                  onChange={(e) => setCostMethod(e.target.value as PortfolioCostMethod)}
                  className="input-terminal w-full text-sm"
                >
                  <option value="fifo">先进先出（FIFO）</option>
                  <option value="avg">均价成本（AVG）</option>
                </select>
              </div>
              <p className="workspace-header-actions-note xl:text-right">
                当前视图会同步刷新组合快照、风险指标与账户维度的持仓明细。
              </p>
            </div>
          </div>
        ) : null}
      </WorkspacePageHeader>

      {error ? <ApiErrorAlert error={error} onDismiss={() => setError(null)} /> : null}
      {riskWarning ? (
        <div className="rounded-xl border border-[hsl(var(--accent-warning-hsl)/0.35)] bg-[hsl(var(--accent-warning-hsl)/0.1)] px-4 py-3 text-[hsl(var(--accent-warning-hsl))] text-sm">
          风险模块降级：{riskWarning}
        </div>
      ) : null}
      {writeWarning ? (
        <div className="rounded-xl border border-[hsl(var(--accent-warning-hsl)/0.35)] bg-[hsl(var(--accent-warning-hsl)/0.1)] px-4 py-3 text-[hsl(var(--accent-warning-hsl))] text-sm">
          操作提示：{writeWarning}
        </div>
      ) : null}

      {(showCreateAccount || !hasAccounts) ? (
        <Card padding="md">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-foreground">新建账户</h2>
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
                收起
              </button>
            ) : (
              <span className="text-xs text-secondary">创建后自动切换到该账户</span>
            )}
          </div>
          {accountCreateError ? (
            <div className="mt-2 text-xs text-danger rounded-lg border border-[hsl(var(--accent-danger-hsl)/0.3)] bg-[hsl(var(--accent-danger-hsl)/0.12)] px-2 py-1">
              {accountCreateError}
            </div>
          ) : null}
          {accountCreateSuccess ? (
            <div className="mt-2 text-xs text-success rounded-lg border border-[hsl(var(--accent-positive-hsl)/0.3)] bg-[hsl(var(--accent-positive-hsl)/0.12)] px-2 py-1">
              {accountCreateSuccess}
            </div>
          ) : null}
          <form className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2" onSubmit={handleCreateAccount}>
            <input
              className="input-terminal text-sm md:col-span-2"
              placeholder="账户名称（必填）"
              value={accountForm.name}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, name: e.target.value }))}
            />
            <input
              className="input-terminal text-sm"
              placeholder="券商（可选，如 Demo/华泰）"
              value={accountForm.broker}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, broker: e.target.value }))}
            />
            <input
              className="input-terminal text-sm"
              placeholder="基准币（如 CNY/USD/HKD）"
              value={accountForm.baseCurrency}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, baseCurrency: e.target.value.toUpperCase() }))}
            />
            <select
              className="input-terminal text-sm"
              value={accountForm.market}
              onChange={(e) => setAccountForm((prev) => ({ ...prev, market: e.target.value as 'cn' | 'hk' | 'us' | 'global' }))}
            >
              <option value="cn">市场：A 股（cn）</option>
              <option value="hk">市场：港股（hk）</option>
              <option value="us">市场：美股（us）</option>
              <option value="global">市场：全球账户（global）</option>
            </select>
            <button type="submit" className="btn-secondary text-sm" disabled={accountCreating}>
              {accountCreating ? '创建中...' : '创建账户'}
            </button>
          </form>
        </Card>
      ) : null}

      <div className="space-y-3">
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <Card variant="gradient" padding="md">
            <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">总权益 / Total Equity</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{formatMoney(snapshot?.totalEquity, snapshot?.currency || 'CNY')}</p>
          </Card>
          <Card variant="gradient" padding="md">
            <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">总市值 / Market Value</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{formatMoney(snapshot?.totalMarketValue, snapshot?.currency || 'CNY')}</p>
          </Card>
          <Card variant="gradient" padding="md">
            <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">总现金 / Cash Balance</p>
            <p className="mt-1 text-xl font-semibold text-foreground">{formatMoney(snapshot?.totalCash, snapshot?.currency || 'CNY')}</p>
          </Card>
          <Card variant="gradient" padding="md">
            <div className="flex items-start justify-between gap-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">汇率状态 / FX Status</p>
              <button
                type="button"
                className="btn-secondary !px-3 !py-1 !text-[11px] uppercase tracking-widest shrink-0"
                onClick={() => void handleRefreshFx()}
                disabled={!hasAccounts || isLoading || fxRefreshing}
              >
                {fxRefreshing ? '刷新中' : '刷新汇率'}
              </button>
            </div>
            <div className="mt-2">{snapshot?.fxStale ? <Badge variant="warning">过期</Badge> : <Badge variant="success">最新</Badge>}</div>
            {fxRefreshFeedback ? (
              <p
                className={`mt-2 text-xs ${
                  fxRefreshFeedback.tone === 'success'
                    ? 'text-success'
                    : fxRefreshFeedback.tone === 'warning'
                      ? 'text-[hsl(var(--accent-warning-hsl))]'
                      : 'text-secondary'
                }`}
              >
                {fxRefreshFeedback.text}
              </p>
            ) : null}
          </Card>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Card padding="md">
            <h3 className="text-[11px] uppercase tracking-[0.14em] text-secondary-text mb-3">回撤监控 / Drawdown</h3>
            <div className="text-xs text-secondary space-y-1.5">
              <div className="flex justify-between"><span>最大回撤:</span> <span className="text-foreground font-mono">{formatPct(risk?.drawdown?.maxDrawdownPct)}</span></div>
              <div className="flex justify-between"><span>当前回撤:</span> <span className="text-foreground font-mono">{formatPct(risk?.drawdown?.currentDrawdownPct)}</span></div>
              <div className="flex justify-between"><span>告警:</span> <span className={risk?.drawdown?.alert ? 'text-danger font-medium' : 'text-success font-medium'}>{risk?.drawdown?.alert ? '是' : '否'}</span></div>
            </div>
          </Card>
          <Card padding="md">
            <h3 className="text-[11px] uppercase tracking-[0.14em] text-secondary-text mb-3">止损接近预警 / Stop Loss</h3>
            <div className="text-xs text-secondary space-y-1.5">
              <div className="flex justify-between"><span>触发数:</span> <span className="text-foreground font-mono">{risk?.stopLoss?.triggeredCount ?? 0}</span></div>
              <div className="flex justify-between"><span>接近数:</span> <span className="text-foreground font-mono">{risk?.stopLoss?.nearCount ?? 0}</span></div>
              <div className="flex justify-between"><span>告警:</span> <span className={risk?.stopLoss?.nearAlert ? 'text-warning font-medium' : 'text-success font-medium'}>{risk?.stopLoss?.nearAlert ? '是' : '否'}</span></div>
            </div>
          </Card>
          <Card padding="md">
            <h3 className="text-[11px] uppercase tracking-[0.14em] text-secondary-text mb-3">口径 / Scope</h3>
            <div className="text-xs text-secondary space-y-1.5">
              <div className="flex justify-between"><span>账户数:</span> <span className="text-foreground font-mono">{snapshot?.accountCount ?? 0}</span></div>
              <div className="flex justify-between"><span>计价币种:</span> <span className="text-foreground font-mono">{snapshot?.currency || 'CNY'}</span></div>
              <div className="flex justify-between"><span>成本法:</span> <span className="text-foreground font-mono">{(snapshot?.costMethod || costMethod).toUpperCase()}</span></div>
            </div>
          </Card>
        </section>

        {writeBlocked && hasAccounts ? (
          <div className="text-xs text-[hsl(var(--accent-warning-hsl))] rounded-lg border border-[hsl(var(--accent-warning-hsl)/0.3)] bg-[hsl(var(--accent-warning-hsl)/0.12)] px-3 py-2">
            当前处于“全部账户”视图。为避免误写，请先选择一个具体账户后再进行手工录入或券商文件导入提交。
          </div>
        ) : null}

        <section className="grid grid-cols-1 xl:grid-cols-3 gap-3">
          <Card className="xl:col-span-2" padding="md">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">持仓明细 / Positions</h2>
              <span className="text-[11px] uppercase tracking-widest text-secondary">共 {positionRows.length} 项</span>
            </div>
            {positionRows.length === 0 ? (
              <p className="text-sm text-muted py-6 text-center">当前无持仓数据</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-[11px] uppercase tracking-[0.14em] text-secondary border-b border-[var(--border-muted)]">
                    <tr>
                      <th className="text-left py-2 pr-2 font-medium">账户</th>
                      <th className="text-left py-2 pr-2 font-medium">代码</th>
                      <th className="text-left py-2 pr-2 font-medium">市场 / 币种</th>
                      <th className="text-right py-2 pr-2 font-medium">数量</th>
                      <th className="text-right py-2 pr-2 font-medium">均价</th>
                      <th className="text-right py-2 pr-2 font-medium">现价</th>
                      <th className="text-right py-2 pr-2 font-medium">市值</th>
                      <th className="text-right py-2 font-medium">未实现盈亏</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positionRows.map((row) => (
                      <tr key={`${row.accountId}-${row.symbol}-${row.market}`} className="border-b border-[var(--border-muted)] hover:bg-[var(--overlay-hover)] transition-colors">
                        <td className="py-2.5 pr-2 text-secondary-text text-xs">{row.accountName}</td>
                        <td className="py-2.5 pr-2 font-mono text-foreground text-xs">{row.symbol}</td>
                        <td className="py-2.5 pr-2 text-secondary-text text-xs">{formatPositionContext(row.market, row.currency)}</td>
                        <td className="py-2.5 pr-2 text-right font-mono text-secondary-text text-xs">{row.quantity.toFixed(2)}</td>
                        <td className="py-2.5 pr-2 text-right font-mono text-secondary-text text-xs">{row.avgCost.toFixed(4)}</td>
                        <td className="py-2.5 pr-2 text-right font-mono text-secondary-text text-xs">{row.lastPrice.toFixed(4)}</td>
                        <td className="py-2.5 pr-2 text-right font-mono text-foreground text-xs">{formatMoney(row.marketValueBase, row.valuationCurrency)}</td>
                        <td
                          className="py-2.5 text-right font-mono text-xs"
                          style={{ color: getMarketDirectionColor(row.unrealizedPnlBase) }}
                        >
                          {formatMoney(row.unrealizedPnlBase, row.valuationCurrency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card padding="md">
            <h2 className="text-[11px] uppercase tracking-[0.14em] text-secondary-text mb-3">{concentrationMode === 'sector' ? '行业集中度 / Sectors' : '个股集中度 / Symbols (Fallback)'}</h2>
            {concentrationPieData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={concentrationPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90}>
                      {concentrationPieData.map((entry, index) => (
                        <Cell key={`cell-${entry.name}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => `${Number(value).toFixed(2)}%`} contentStyle={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--border-muted)' }} />
                    <Legend wrapperStyle={{ fontSize: '11px', color: 'var(--text-secondary)' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="rounded-md border border-dashed border-[var(--border-muted)] bg-[var(--surface-1)] px-4 py-8 text-center h-64 flex flex-col items-center justify-center">
                <p className="text-[11px] uppercase tracking-widest text-foreground">暂无集中度数据</p>
                <p className="mt-2 text-xs leading-5 text-muted-text max-w-[20ch]">
                  补齐持仓市值后将显示集中度分布
                </p>
              </div>
            )}
            <div className="mt-3 text-xs text-secondary space-y-1.5 border-t border-[var(--border-muted)] pt-3">
              <div className="flex justify-between"><span>展示口径:</span> <span className="text-foreground">{concentrationMode === 'sector' ? '行业维度' : '个股维度（降级显示）'}</span></div>
              <div className="flex justify-between"><span>板块告警:</span> <span className={risk?.sectorConcentration?.alert ? 'text-warning font-medium' : 'text-success font-medium'}>{risk?.sectorConcentration?.alert ? '是' : '否'}</span></div>
              <div className="flex justify-between"><span>Top1 权重:</span> <span className="text-foreground font-mono">{formatPct(risk?.sectorConcentration?.topWeightPct ?? risk?.concentration?.topWeightPct)}</span></div>
            </div>
          </Card>
        </section>

        <section>
          <Card padding="md" className="border-[var(--border-strong)] bg-[var(--surface-2)] shadow-[var(--glow-soft)]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[11px] uppercase tracking-[0.14em] text-foreground">数据同步 / Data Sync</h3>
              <span className="text-[10px] uppercase tracking-widest text-muted-text hidden sm:inline">Broker Import</span>
            </div>
            
            <div className="space-y-4">
              {brokerLoadWarning ? (
                <div className="text-xs text-[hsl(var(--accent-warning-hsl))] rounded-md border border-[hsl(var(--accent-warning-hsl)/0.3)] bg-[hsl(var(--accent-warning-hsl)/0.12)] px-3 py-2">
                  {brokerLoadWarning}
                </div>
              ) : null}

              {writableAccount ? (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-1)] px-3 py-2.5 text-xs text-secondary-text">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-foreground">当前导入账户</span>
                    <span>{writableAccount.name}</span>
                    <Badge>{formatAccountMarketLabel(writableAccount.market)}</Badge>
                    <Badge>{writableAccount.baseCurrency}</Badge>
                  </div>
                  {brokerConnections.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {brokerConnections.map((connection) => (
                        <span
                          key={connection.id}
                          className="inline-flex items-center gap-1 rounded-full border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)] px-2 py-1 text-[11px]"
                        >
                          <span className="font-mono text-foreground">{connection.connectionName}</span>
                          {connection.brokerAccountRef ? <span>{connection.brokerAccountRef}</span> : null}
                          <span className="text-muted-text">{connection.status}</span>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-[11px] text-muted-text">该账户还没有已保存的券商连接，首次导入会自动创建用户自有连接。</p>
                  )}
                </div>
              ) : null}
              
              <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
                <select className="input-terminal text-sm md:w-[160px] h-[2.6rem]" value={selectedBroker} onChange={(e) => setSelectedBroker(e.target.value)}>
                  {brokers.length > 0 ? (
                    brokers.map((item) => <option key={item.broker} value={item.broker}>{formatBrokerLabel(item.broker, item.displayName)}</option>)
                  ) : (
                    <option value="huatai">huatai（华泰）</option>
                  )}
                </select>
                
                <label className="input-terminal text-sm flex-1 flex items-center justify-center cursor-pointer border-dashed hover:border-[var(--border-strong)] bg-[var(--surface-1)] transition-colors min-h-[2.6rem]">
                  <span className="truncate text-secondary-text">
                    {csvFile ? csvFile.name : selectedBroker === 'ibkr' ? '选择 IBKR Flex XML 导出文件...' : '选择券商导出文件...'}
                  </span>
                  <input type="file" accept={importFileAccept} className="hidden"
                    onChange={(e) => setCsvFile(e.target.files && e.target.files[0] ? e.target.files[0] : null)} />
                </label>

                <div className="flex items-center justify-center gap-2 px-3 py-2 border border-[var(--input-border)] rounded-[var(--theme-control-radius)] bg-[var(--surface-1)] h-[2.6rem]">
                  <input id="csv-dry-run" type="checkbox" className="theme-checkbox" checked={csvDryRun} onChange={(e) => setCsvDryRun(e.target.checked)} />
                  <label htmlFor="csv-dry-run" className="text-xs text-secondary-text cursor-pointer whitespace-nowrap">仅预演</label>
                </div>

                <div className="flex gap-2">
                  <button type="button" className="btn-secondary h-[2.6rem] px-4 whitespace-nowrap text-xs" disabled={!csvFile || csvParsing} onClick={() => void handleParseCsv()}>
                    {csvParsing ? '解析中...' : '解析文件'}
                  </button>
                  <button type="button" className="btn-primary h-[2.6rem] px-4 whitespace-nowrap text-xs shadow-[var(--glow-soft)]" disabled={!csvFile || !writableAccountId || csvCommitting} onClick={() => void handleCommitCsv()}>
                    {csvCommitting ? '提交中...' : '提交导入'}
                  </button>
                </div>
              </div>

              <p className="text-[11px] text-muted-text">
                {selectedBroker === 'ibkr'
                  ? 'IBKR 首版推荐使用 Flex Query XML 导出；系统会将导入记录绑定到当前用户自己的 broker connection。'
                  : '保留现有 A 股券商文件导入路径，兼容华泰 / 中信 / 招商 CSV。'}
              </p>

              {selectedBroker === 'ibkr' ? (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-1)] px-3 py-3 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.14em] text-foreground">IBKR 只读同步 / Read-only Sync</p>
                      <p className="mt-1 text-[11px] text-muted-text">
                        仅同步账户状态与持仓，不会暴露任何交易 / 下单能力。session token 只用于本次同步，不会保存到系统。
                      </p>
                    </div>
                    <Badge>Read-only</Badge>
                  </div>
                  <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.2fr)_180px] gap-2">
                    <input
                      className="input-terminal text-sm"
                      placeholder="IBKR API Base URL（默认 https://localhost:5000/v1/api）"
                      value={ibkrApiBaseUrl}
                      onChange={(e) => setIbkrApiBaseUrl(e.target.value)}
                    />
                    <input
                      className="input-terminal text-sm"
                      placeholder="IBKR Account Ref（可选，例 U1234567）"
                      value={ibkrBrokerAccountRef}
                      onChange={(e) => setIbkrBrokerAccountRef(e.target.value.toUpperCase())}
                    />
                    <input
                      className="input-terminal text-sm xl:col-span-2"
                      type="password"
                      placeholder="IBKR Session Token（本次手动同步使用，不保存）"
                      value={ibkrSessionToken}
                      onChange={(e) => setIbkrSessionToken(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <label className="inline-flex items-center gap-2 text-xs text-secondary-text">
                      <input
                        type="checkbox"
                        className="theme-checkbox"
                        checked={ibkrVerifySsl}
                        onChange={(e) => setIbkrVerifySsl(e.target.checked)}
                      />
                      <span>校验 IBKR HTTPS 证书</span>
                    </label>
                    <button
                      type="button"
                      className="btn-secondary h-[2.5rem] px-4 text-xs whitespace-nowrap"
                      disabled={!writableAccountId || !ibkrSessionToken.trim() || ibkrSyncing}
                      onClick={() => void handleSyncIbkr()}
                    >
                      {ibkrSyncing ? '同步中...' : '只读同步 IBKR'}
                    </button>
                  </div>
                  {ibkrSyncResult ? (
                    <div className="text-[11px] tracking-wide text-secondary-text rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)] px-3 py-2.5">
                      <span className="font-semibold text-foreground uppercase tracking-[0.14em] mr-2">同步结果</span>
                      持仓 <span className="text-foreground font-mono">{ibkrSyncResult.positionCount}</span> ·
                      现金币种 <span className="text-foreground font-mono">{ibkrSyncResult.cashBalanceCount}</span> ·
                      总权益 <span className="text-success font-mono">{formatMoney(ibkrSyncResult.totalEquity, ibkrSyncResult.baseCurrency)}</span>
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-muted-text">
                        <span>Ref: <span className="font-mono text-foreground">{ibkrSyncResult.brokerAccountRef}</span></span>
                        <span>同步时间: <span className="text-foreground">{ibkrSyncResult.syncedAt.replace('T', ' ')}</span></span>
                        <span>{ibkrSyncResult.snapshotOverlayActive ? '当前日期快照已切换到 API 同步视图' : '已保存同步结果'}</span>
                      </div>
                      {ibkrSyncResult.warnings.length > 0 ? (
                        <div className="mt-2 rounded-[var(--theme-panel-radius-md)] border border-[hsl(var(--accent-warning-hsl)/0.28)] bg-[hsl(var(--accent-warning-hsl)/0.08)] px-2.5 py-2 text-[11px] text-[hsl(var(--accent-warning-hsl))]">
                          {ibkrSyncResult.warnings.map((warning) => (
                            <p key={warning} className="leading-5">
                              {warning}
                            </p>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {csvParseResult || csvCommitResult ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                  {csvParseResult ? (
                    <div className="text-[11px] tracking-wide text-secondary-text rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-1)] px-3 py-2.5">
                      <span className="font-semibold text-foreground uppercase tracking-[0.14em] mr-2">解析结果</span>
                      有效 <span className="text-success font-mono">{csvParseResult.recordCount}</span> ·
                      现金 <span className="text-foreground font-mono">{csvParseResult.cashRecordCount ?? 0}</span> ·
                      公司行为 <span className="text-foreground font-mono">{csvParseResult.corporateActionCount ?? 0}</span> ·
                      跳过 <span className="text-warning font-mono">{csvParseResult.skippedCount}</span> ·
                      错误 <span className="text-danger font-mono">{csvParseResult.errorCount}</span>
                      {csvParseResult.metadata?.brokerAccountRef ? (
                        <div className="mt-2 text-[11px] text-muted-text">
                          账户映射: <span className="font-mono text-foreground">{String(csvParseResult.metadata.brokerAccountRef)}</span>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {csvCommitResult ? (
                    <div className="text-[11px] tracking-wide text-secondary-text rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-1)] px-3 py-2.5">
                      <span className="font-semibold text-foreground uppercase tracking-[0.14em] mr-2">提交结果</span>
                      写入 <span className="text-success font-mono">{csvCommitResult.insertedCount}</span> ·
                      现金 <span className="text-foreground font-mono">{csvCommitResult.cashInsertedCount ?? 0}</span> ·
                      公司行为 <span className="text-foreground font-mono">{csvCommitResult.corporateActionInsertedCount ?? 0}</span> ·
                      重复 <span className="text-warning font-mono">{csvCommitResult.duplicateCount}</span> ·
                      失败 <span className="text-danger font-mono">{csvCommitResult.failedCount}</span>
                      {csvCommitResult.duplicateImport ? (
                        <div className="mt-2 text-[11px] text-[hsl(var(--accent-warning-hsl))]">
                          检测到同一 broker connection 的重复文件指纹，本次未重复写入。
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {csvParseResult?.warnings?.length ? (
                <div className="rounded-[var(--theme-panel-radius-md)] border border-[hsl(var(--accent-warning-hsl)/0.25)] bg-[hsl(var(--accent-warning-hsl)/0.08)] px-3 py-2 text-[11px] text-[hsl(var(--accent-warning-hsl))]">
                  {csvParseResult.warnings[0]}
                </div>
              ) : null}
            </div>
          </Card>
        </section>

        <section className="space-y-3">
          <Disclosure summary="高级：手工录入与修正 / Manual Entry" defaultOpen={false}>
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
              <Card padding="md">
                <h3 className="text-[11px] uppercase tracking-[0.14em] text-secondary-text mb-3">手工录入：交易 / Trade</h3>
                <form className="space-y-2" onSubmit={handleTradeSubmit}>
                  <input className="input-terminal w-full text-sm" placeholder="股票代码（例如 600519）" value={tradeForm.symbol}
                    onChange={(e) => setTradeForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input className="input-terminal text-sm" type="date" value={tradeForm.tradeDate}
                      onChange={(e) => setTradeForm((prev) => ({ ...prev, tradeDate: e.target.value }))} required />
                    <select className="input-terminal text-sm" value={tradeForm.side}
                      onChange={(e) => setTradeForm((prev) => ({ ...prev, side: e.target.value as PortfolioSide }))}>
                      <option value="buy">买入</option>
                      <option value="sell">卖出</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input className="input-terminal text-sm" type="number" min="0" step="0.0001" placeholder="数量" value={tradeForm.quantity}
                      onChange={(e) => setTradeForm((prev) => ({ ...prev, quantity: e.target.value }))} required />
                    <input className="input-terminal text-sm" type="number" min="0" step="0.0001" placeholder="成交价" value={tradeForm.price}
                      onChange={(e) => setTradeForm((prev) => ({ ...prev, price: e.target.value }))} required />
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input className="input-terminal text-sm" type="number" min="0" step="0.0001" placeholder="手续费 (可选)" value={tradeForm.fee}
                      onChange={(e) => setTradeForm((prev) => ({ ...prev, fee: e.target.value }))} />
                    <input className="input-terminal text-sm" type="number" min="0" step="0.0001" placeholder="税费 (可选)" value={tradeForm.tax}
                      onChange={(e) => setTradeForm((prev) => ({ ...prev, tax: e.target.value }))} />
                  </div>
                  <button type="submit" className="btn-secondary w-full mt-2 text-[11px]" disabled={!writableAccountId}>提交交易</button>
                </form>
              </Card>

              <Card padding="md">
                <h3 className="text-[11px] uppercase tracking-[0.14em] text-secondary-text mb-3">手工录入：资金 / Cash</h3>
                <form className="space-y-2" onSubmit={handleCashSubmit}>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input className="input-terminal text-sm" type="date" value={cashForm.eventDate}
                      onChange={(e) => setCashForm((prev) => ({ ...prev, eventDate: e.target.value }))} required />
                    <select className="input-terminal text-sm" value={cashForm.direction}
                      onChange={(e) => setCashForm((prev) => ({ ...prev, direction: e.target.value as PortfolioCashDirection }))}>
                      <option value="in">流入</option>
                      <option value="out">流出</option>
                    </select>
                  </div>
                  <input className="input-terminal w-full text-sm" type="number" min="0" step="0.0001" placeholder="金额"
                    value={cashForm.amount} onChange={(e) => setCashForm((prev) => ({ ...prev, amount: e.target.value }))} required />
                  <input className="input-terminal w-full text-sm" placeholder={`币种（可选，默认 ${writableAccount?.baseCurrency || '账户基准币'}）`} value={cashForm.currency}
                    onChange={(e) => setCashForm((prev) => ({ ...prev, currency: e.target.value }))} />
                  <button type="submit" className="btn-secondary w-full mt-2 text-[11px]" disabled={!writableAccountId}>提交资金流水</button>
                </form>
              </Card>

              <Card padding="md">
                <h3 className="text-[11px] uppercase tracking-[0.14em] text-secondary-text mb-3">手工录入：公司行为 / Corp</h3>
                <form className="space-y-2" onSubmit={handleCorporateSubmit}>
                  <input className="input-terminal w-full text-sm" placeholder="股票代码" value={corpForm.symbol}
                    onChange={(e) => setCorpForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input className="input-terminal text-sm" type="date" value={corpForm.effectiveDate}
                      onChange={(e) => setCorpForm((prev) => ({ ...prev, effectiveDate: e.target.value }))} required />
                    <select className="input-terminal text-sm" value={corpForm.actionType}
                      onChange={(e) => setCorpForm((prev) => ({ ...prev, actionType: e.target.value as PortfolioCorporateActionType }))}>
                      <option value="cash_dividend">现金分红</option>
                      <option value="split_adjustment">拆并股调整</option>
                    </select>
                  </div>
                  {corpForm.actionType === 'cash_dividend' ? (
                    <input className="input-terminal w-full text-sm" type="number" min="0" step="0.000001" placeholder="每股分红"
                      value={corpForm.cashDividendPerShare}
                      onChange={(e) => setCorpForm((prev) => ({ ...prev, cashDividendPerShare: e.target.value, splitRatio: '' }))} required />
                  ) : (
                    <input className="input-terminal w-full text-sm" type="number" min="0" step="0.000001" placeholder="拆并股比例"
                      value={corpForm.splitRatio}
                      onChange={(e) => setCorpForm((prev) => ({ ...prev, splitRatio: e.target.value, cashDividendPerShare: '' }))} required />
                  )}
                  <button type="submit" className="btn-secondary w-full mt-2 text-[11px]" disabled={!writableAccountId}>提交企业行为</button>
                </form>
              </Card>
            </div>
          </Disclosure>

          <Disclosure summary="流水与审计 / Audit & Ledger" defaultOpen={showEventAuditDisclosureByDefault}>
            <Card padding="md" className="border-0 bg-transparent">
              <div className="space-y-3">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <select className="input-terminal text-sm" value={eventType} onChange={(e) => setEventType(e.target.value as EventType)}>
                    <option value="trade">交易流水</option>
                    <option value="cash">资金流水</option>
                    <option value="corporate">公司行为</option>
                  </select>
                  <button type="button" className="btn-secondary text-[11px] uppercase tracking-widest" onClick={() => void loadEvents()} disabled={eventLoading}>
                    {eventLoading ? '加载中...' : '刷新流水'}
                  </button>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <input className="input-terminal text-sm" type="date" value={eventDateFrom} onChange={(e) => setEventDateFrom(e.target.value)} />
                  <input className="input-terminal text-sm" type="date" value={eventDateTo} onChange={(e) => setEventDateTo(e.target.value)} />
                </div>
                {(eventType === 'trade' || eventType === 'corporate') ? (
                  <input className="input-terminal text-sm w-full" placeholder="按股票代码筛选" value={eventSymbol}
                    onChange={(e) => setEventSymbol(e.target.value)} />
                ) : null}
                {eventType === 'trade' ? (
                  <select className="input-terminal text-sm w-full" value={eventSide} onChange={(e) => setEventSide(e.target.value as '' | PortfolioSide)}>
                    <option value="">全部买卖方向</option>
                    <option value="buy">买入</option>
                    <option value="sell">卖出</option>
                  </select>
                ) : null}
                {eventType === 'cash' ? (
                  <select className="input-terminal text-sm w-full" value={eventDirection}
                    onChange={(e) => setEventDirection(e.target.value as '' | PortfolioCashDirection)}>
                    <option value="">全部资金方向</option>
                    <option value="in">流入</option>
                    <option value="out">流出</option>
                  </select>
                ) : null}
                {eventType === 'corporate' ? (
                  <select className="input-terminal text-sm w-full" value={eventActionType}
                    onChange={(e) => setEventActionType(e.target.value as '' | PortfolioCorporateActionType)}>
                    <option value="">全部公司行为</option>
                    <option value="cash_dividend">现金分红</option>
                    <option value="split_adjustment">拆并股调整</option>
                  </select>
                ) : null}
                <div className="text-[11px] text-secondary-text">
                  {writeBlocked ? '删除修正仅在单账户视图可用。请先选择具体账户后再删除错误流水。' : '如有错误流水，可直接删除后重新录入。'}
                </div>
                <div className="rounded-md border border-[var(--border-muted)] bg-[var(--surface-1)] p-2 max-h-none overflow-visible lg:max-h-[400px] lg:overflow-auto">
                  {eventType === 'trade' && tradeEvents.map((item) => (
                    <div key={`t-${item.id}`} className="flex items-center justify-between gap-3 border-b border-[var(--border-muted)] py-2.5 text-xs text-secondary-text last:border-0 hover:bg-[var(--overlay-hover)] transition-colors px-2">
                      <div className="min-w-0 font-mono flex-1 flex flex-wrap gap-x-4 gap-y-1">
                        <span className="text-muted-text">{item.tradeDate}</span>
                        <span className={item.side === 'buy' ? 'text-success' : 'text-warning'}>{formatSideLabel(item.side)}</span>
                        <span className="text-foreground font-semibold">{item.symbol}</span>
                        <span>数量 <span className="text-foreground">{item.quantity}</span></span>
                        <span>价格 <span className="text-foreground">{item.price}</span></span>
                      </div>
                      {!writeBlocked ? (
                        <button
                          type="button"
                          className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                          onClick={() => openDeleteDialog({
                            eventType: 'trade',
                            id: item.id,
                            message: `确认删除 ${item.tradeDate} 的${formatSideLabel(item.side)}流水 ${item.symbol}（数量 ${item.quantity}，价格 ${item.price}）吗？`,
                          })}
                        >
                          删除
                        </button>
                      ) : null}
                    </div>
                  ))}
                  {eventType === 'cash' && cashEvents.map((item) => (
                    <div key={`c-${item.id}`} className="flex items-center justify-between gap-3 border-b border-[var(--border-muted)] py-2.5 text-xs text-secondary-text last:border-0 hover:bg-[var(--overlay-hover)] transition-colors px-2">
                      <div className="min-w-0 font-mono flex-1 flex flex-wrap gap-x-4 gap-y-1">
                        <span className="text-muted-text">{item.eventDate}</span>
                        <span className={item.direction === 'in' ? 'text-success' : 'text-warning'}>{formatCashDirectionLabel(item.direction)}</span>
                        <span className="text-foreground">{item.amount}</span>
                        <span className="text-foreground font-semibold">{item.currency}</span>
                      </div>
                      {!writeBlocked ? (
                        <button
                          type="button"
                          className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                          onClick={() => openDeleteDialog({
                            eventType: 'cash',
                            id: item.id,
                            message: `确认删除 ${item.eventDate} 的资金流水（${formatCashDirectionLabel(item.direction)} ${item.amount} ${item.currency}）吗？`,
                          })}
                        >
                          删除
                        </button>
                      ) : null}
                    </div>
                  ))}
                  {eventType === 'corporate' && corporateEvents.map((item) => (
                    <div key={`ca-${item.id}`} className="flex items-center justify-between gap-3 border-b border-[var(--border-muted)] py-2.5 text-xs text-secondary-text last:border-0 hover:bg-[var(--overlay-hover)] transition-colors px-2">
                      <div className="min-w-0 font-mono flex-1 flex flex-wrap gap-x-4 gap-y-1">
                        <span className="text-muted-text">{item.effectiveDate}</span>
                        <span className="text-info">{formatCorporateActionLabel(item.actionType)}</span>
                        <span className="text-foreground font-semibold">{item.symbol}</span>
                      </div>
                      {!writeBlocked ? (
                        <button
                          type="button"
                          className="btn-secondary shrink-0 !px-3 !py-1 !text-[11px]"
                          onClick={() => openDeleteDialog({
                            eventType: 'corporate',
                            id: item.id,
                            message: `确认删除 ${item.effectiveDate} 的公司行为 ${formatCorporateActionLabel(item.actionType)}（${item.symbol}）吗？`,
                          })}
                        >
                          删除
                        </button>
                      ) : null}
                    </div>
                  ))}
                  {!eventLoading
                    && ((eventType === 'trade' && tradeEvents.length === 0)
                      || (eventType === 'cash' && cashEvents.length === 0)
                      || (eventType === 'corporate' && corporateEvents.length === 0)) ? (
                        <div className="px-2 py-6 text-center">
                          <p className="text-[11px] uppercase tracking-widest text-foreground">暂无流水记录</p>
                          <p className="mt-1 text-xs leading-5 text-muted-text">
                            调整筛选条件，或先录入流水。
                          </p>
                        </div>
                      ) : null}
                </div>
                <div className="flex flex-col gap-2 text-[11px] uppercase tracking-widest text-secondary-text sm:flex-row sm:items-center sm:justify-between px-1">
                  <span>PAGE {eventPage} / {totalEventPages}</span>
                  <div className="flex gap-2">
                    <button type="button" className="btn-secondary text-[11px] px-4 py-1" disabled={eventPage <= 1}
                      onClick={() => setEventPage((prev) => Math.max(1, prev - 1))}>
                      PREV
                    </button>
                    <button type="button" className="btn-secondary text-[11px] px-4 py-1" disabled={eventPage >= totalEventPages}
                      onClick={() => setEventPage((prev) => Math.min(totalEventPages, prev + 1))}>
                      NEXT
                    </button>
                  </div>
                </div>
              </div>
            </Card>
          </Disclosure>
        </section>
      </div>
      <ConfirmDialog
        isOpen={Boolean(pendingDelete)}
        title="删除错误流水"
        message={pendingDelete?.message || '确认删除这条流水吗？'}
        confirmText={deleteLoading ? '删除中...' : '确认删除'}
        cancelText="取消"
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
