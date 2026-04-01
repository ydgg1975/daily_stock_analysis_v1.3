import { render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StandardReportPanel } from '../StandardReportPanel';
import type { AnalysisReport } from '../../../types/analysis';
import { previewChartFixtures } from '../../../dev/reportPreviewFixture';

vi.mock('../../../hooks/useElementSize', () => {
  let callCount = 0;
  return {
    useElementSize: () => {
      callCount += 1;
      if (callCount % 2 === 1) {
        return { ref: { current: null }, size: { width: 1360, height: 720 } };
      }
      return { ref: { current: null }, size: { width: 1280, height: 460 } };
    },
  };
});

vi.mock('../../../api/stocks', () => ({
  stocksApi: {
    getIntraday: vi.fn().mockResolvedValue({
      stockCode: 'NVDA',
      stockName: 'NVIDIA',
      interval: '5m',
      range: '1d',
      source: 'yfinance',
      data: [
        { time: '2026-03-28T09:30:00-04:00', open: 124.9, high: 125.6, low: 124.7, close: 125.3, volume: 1200 },
        { time: '2026-03-28T09:35:00-04:00', open: 125.3, high: 125.9, low: 125.1, close: 125.6, volume: 1600 },
      ],
    }),
    getHistory: vi.fn().mockResolvedValue({
      stockCode: 'NVDA',
      stockName: 'NVIDIA',
      period: 'daily',
      data: [
        { date: '2026-03-24', open: 120, high: 123, low: 119, close: 122, volume: 10 },
        { date: '2026-03-25', open: 122, high: 124, low: 121, close: 123, volume: 11 },
        { date: '2026-03-26', open: 123, high: 125, low: 122, close: 124, volume: 12 },
        { date: '2026-03-27', open: 124, high: 126, low: 123, close: 125.3, volume: 13 },
      ],
    }),
  },
}));

const report: AnalysisReport = {
  meta: {
    queryId: 'q1',
    stockCode: 'NVDA',
    stockName: 'NVIDIA',
    reportType: 'full',
    createdAt: '2026-03-28T21:35:00+08:00',
  },
  summary: {
    analysisSummary: '等待回踩确认',
    operationAdvice: '观望',
    trendPrediction: '看多',
    sentimentScore: 78,
  },
  details: {
    standardReport: {
      summaryPanel: {
        stock: 'NVIDIA',
        ticker: 'NVDA',
        score: 78,
        currentPrice: '125.30',
        priceLabel: 'Analysis Price',
        priceBasis: 'Intraday snapshot',
        priceBasisDetail: 'Captured from a market snapshot during the current session, not streaming tick-by-tick data.',
        changeAmount: '2.30',
        changePct: '1.87%',
        marketTime: '2026-03-28 09:35:00 EDT',
        marketSessionDate: '2026-03-28',
        sessionLabel: '常规交易时段',
        referenceSession: '2026-03-28 regular session',
        snapshotTime: '2026-03-28 09:35:00 EDT',
        reportGeneratedAt: '2026-03-28 21:35:00 CST',
        priceContextNote: 'Entry, stop, target, support and resistance are anchored to the same intraday snapshot shown above.',
        operationAdvice: '观望',
        trendPrediction: '看多',
        oneSentence: '等待回踩确认后再考虑加仓',
        timeSensitivity: '3日内',
        tags: [
          { label: '交易日', value: '2026-03-28' },
          { label: '市场时间', value: '2026-03-28 09:35:00' },
          { label: '会话类型', value: '常规交易时段' },
        ],
      },
      market: {
        consistencyWarnings: ['常规时段多源涨跌口径存在较大偏差，已优先采用当前价与昨收重算结果'],
      },
      tableSections: {
        market: {
          title: '行情表',
          fields: [
            { label: 'Analysis Price', value: '125.30' },
            { label: 'Change %', value: '1.87%' },
          ],
        },
        technical: {
          title: '技术面表',
          fields: [
            { label: 'MA20', value: '120.99', source: 'FMP API', status: '已就绪' },
            { label: 'RSI14', value: '56.78', source: 'FMP API', status: '已就绪' },
          ],
        },
        fundamental: {
          title: '基本面表',
          fields: [
            { label: '总市值(最新值)', value: '1234.00亿', source: 'FMP', status: '最新值' },
            { label: '市盈率(TTM)', value: '28.10', source: 'FMP', status: 'TTM' },
          ],
        },
        earnings: {
          title: '财报表',
          fields: [
            { label: '财报趋势摘要(最新季度)', value: '最新季度同比口径：营收与利润同向改善。', source: 'FMP Statements', status: '最新季度' },
            { label: '营收同比增速(最新季度同比)', value: '12.00%', source: 'FMP Statements', status: '最新季度同比' },
          ],
        },
      },
      visualBlocks: {
        score: {
          value: 78,
          max: 100,
        },
        trendStrength: {
          value: 72,
          max: 100,
          label: '多头排列',
        },
        pricePosition: {
          currentPrice: 125.3,
          ma20: 120.99,
          ma60: 118.88,
          distanceToMa20Pct: 3.56,
          distanceToMa60Pct: 5.40,
          vsMa20: '上方',
          vsMa60: '上方',
        },
        riskOpportunity: {
          positiveCount: 2,
          riskCount: 1,
          latestNewsCount: 1,
        },
      },
      decisionContext: {
        shortTermView: '短线技术偏弱，等待均线重新收敛。',
        compositeView: '基本面仍有支撑，综合建议以观望为主。',
        adjustmentReason: 'MA5/10/20/60 已补齐，并保留基本面缓冲。',
        changeReason: '技术指标补齐导致',
        previousScore: '81',
        scoreChange: '-3',
        scoreBreakdown: [
          { label: '技术分', score: 38, note: '均线结构偏空', tone: 'danger' },
          { label: '基本面分', score: 72, note: '现金流健康', tone: 'success' },
        ],
      },
      decisionPanel: {
        setupType: '回踩买点',
        confidence: '中高',
        keyAction: '优先等待回踩 MA20 一带出现承接，再考虑分批试仓。',
        analysisPrice: 125.3,
        support: '120.10（近期支撑 / MA 簇）',
        supportLevel: 120.1,
        resistance: '132.00（前高 / 压力位）',
        resistanceLevel: 132,
        idealEntry: '120-121',
        idealEntryCenter: 120.5,
        backupEntry: '118',
        backupEntryCenter: 118,
        stopLoss: '115',
        stopLossLevel: 115,
        target: '132',
        targetOne: '132',
        targetOneLevel: 132,
        targetTwo: '138',
        targetTwoLevel: 138,
        targetZone: '132-138',
        stopReason: '跌破最近支撑后，做多结构被技术性否定。',
        targetReason: '优先锚定前高与更强压力位。',
        marketStructure: 'MA5/10/20/60 = 123.4 / 122.8 / 120.9 / 118.8',
        atrProxy: 2.4,
        positionSizing: '分批试仓',
        buildStrategy: '等待回踩后分两笔建立底仓',
        riskControlStrategy: '放量跌破支撑位则收缩仓位',
        noPositionAdvice: '等待回踩确认后分批试仓',
        holderAdvice: '量价结构未破坏前继续跟踪',
        executionReminders: ['若放量跌破支撑位，需立即收缩仓位'],
      },
      reasonLayer: {
        coreReasons: ['基本面仍有支撑，综合建议以观望为主。', '短线技术偏弱，等待均线重新收敛。', '数据中心需求回暖'],
        topRisk: '估值仍偏高',
        topCatalyst: '数据中心需求回暖',
        latestKeyUpdate: '公司发布新品并强化生态合作',
        sentimentSummary: '情绪边际回暖',
        checklistSummary: '仍有1项执行条件待确认，建议继续观察量价配合。',
        newsValueTier: '高价值优先',
      },
      highlights: {
        positiveCatalysts: ['数据中心需求回暖', 'AI 订单延续'],
        riskAlerts: ['估值仍偏高'],
        latestNews: ['公司发布新品并强化生态合作'],
        newsValueGrade: '高价值优先',
        sentimentSummary: '情绪边际回暖',
        earningsOutlook: '盈利预期改善',
        bullishFactors: ['数据中心需求回暖', 'AI 订单延续'],
        bearishFactors: ['估值仍偏高', '上方前高压力仍在'],
        neutralFactors: ['暂无新的公司级催化，短线更依赖技术结构确认。'],
        socialSynthesis: '综合 Reddit / X / Polymarket 的讨论语义：discussion appears elevated，tone is mixed，当前关注点集中在 AI 需求与突破确认。该卡片为 LLM 综合讨论摘要，不等同于已核实硬新闻。',
        socialAttention: 'discussion appears elevated',
        socialTone: 'mixed',
        socialNarrativeFocus: 'AI 需求与突破确认',
        socialSources: ['Reddit', 'X / Twitter'],
      },
      coverageNotes: {
        dataSources: ['FMP API', 'FMP Statements', '本地派生'],
        coverageGaps: ['VWAP'],
        conflictNotes: ['ROE(TTM待复核)：TTM待复核'],
        missingFieldNotes: ['VWAP：字段待接入'],
        methodNotes: ['标准技术指标优先使用 API 原始值。'],
      },
      battlePlanCompact: {
        cards: [
          { label: '理想买入点', value: '120-121', tone: 'buy' },
          { label: '止损位', value: '115', tone: 'risk' },
          { label: '目标位', value: '132', tone: 'target' },
          { label: '仓位建议', value: '分批试仓', tone: 'position' },
        ],
        notes: [
          { label: '建仓策略', value: '等待回踩后分两笔建立底仓', tone: 'note' },
        ],
        warnings: ['若放量跌破支撑位，需立即收缩仓位'],
      },
      checklistItems: [
        { status: 'warn', icon: '⚠️', text: '等待回踩确认' },
        { status: 'pass', icon: '✅', text: '量价结构未破坏' },
      ],
    },
  },
};

describe('StandardReportPanel', () => {
  it('renders the layered report IA with compact summary, execution/risk focus, and appendix disclosures', async () => {
    render(<StandardReportPanel report={report} chartFixtures={previewChartFixtures} />);

    expect(screen.getAllByText('NVIDIA').length).toBeGreaterThan(0);
    expect(screen.getAllByText('等待回踩确认后再考虑加仓').length).toBeGreaterThan(0);
    expect(screen.getAllByText('125.30').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1.87%').length).toBeGreaterThan(0);
    expect(screen.queryAllByText(/Intraday snapshot/).length).toBeGreaterThan(0);
    expect(screen.queryByRole('tab', { name: '概览' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '全部' })).not.toBeInTheDocument();

    expect(screen.getByTestId('hero-summary-card')).toBeInTheDocument();
    expect(screen.getByTestId('chart-context-layer')).toBeInTheDocument();
    expect(screen.getByTestId('report-price-chart')).toBeInTheDocument();
    expect(screen.getByTestId('execution-risk-layer')).toBeInTheDocument();
    expect(screen.getByTestId('key-actions-card')).toBeInTheDocument();
    expect(screen.getByTestId('watch-checklist-card')).toBeInTheDocument();
    expect(screen.getByText('执行计划与入场条件')).toBeInTheDocument();
    expect(screen.getAllByText('观望').length).toBe(1);

    const deepAppendix = screen.getByTestId('deep-appendix-disclosure');
    expect(deepAppendix).toBeInTheDocument();
    expect(deepAppendix).not.toHaveAttribute('open');
    expect(screen.getByText('深度附录')).toBeInTheDocument();

    expect(screen.getByTestId('appendix-execution-disclosure')).toBeInTheDocument();
    expect(screen.getByTestId('appendix-decision-disclosure')).toBeInTheDocument();
    expect(screen.getByTestId('appendix-sentiment-disclosure')).toBeInTheDocument();
    expect(screen.getByTestId('appendix-tables-disclosure')).toBeInTheDocument();
    expect(screen.getByTestId('appendix-coverage-disclosure')).toBeInTheDocument();

    expect(screen.getByTestId('decision-execution-panel')).toBeInTheDocument();
    expect(screen.getByTestId('decision-board-panel')).toBeInTheDocument();
    expect(screen.getAllByTestId('risk-catalyst-panel').length).toBeGreaterThan(0);
    expect(screen.getByTestId('coverage-audit-panel')).toBeInTheDocument();
    expect(screen.getByTestId('battle-plan-grid')).toBeInTheDocument();

    expect(screen.getAllByText('120-121').length).toBeGreaterThan(0);
    expect(screen.getAllByText('等待回踩后分两笔建立底仓').length).toBeGreaterThan(0);
    expect(screen.getAllByText('关键动作').length).toBeGreaterThan(0);
    expect(screen.getAllByText('入场前检查').length).toBeGreaterThan(0);
    expect(screen.getAllByText('核心风险').length).toBeGreaterThan(0);
    expect(screen.getAllByText('催化与观察条件').length).toBeGreaterThan(0);
    expect(screen.getAllByText('行情表').length).toBeGreaterThan(0);
    expect(screen.getAllByText('技术面表').length).toBeGreaterThan(0);
    expect(screen.getAllByText('基本面表').length).toBeGreaterThan(0);
    expect(screen.getAllByText('财报表').length).toBeGreaterThan(0);
    expect(screen.getAllByText('催化、风险与情绪').length).toBeGreaterThan(0);
    expect(screen.getByText('作战计划')).toBeInTheDocument();
    expect(screen.getByText('Checklist 与评分')).toBeInTheDocument();
    expect(screen.getByText('评分拆解')).toBeInTheDocument();
    expect(screen.getAllByText('核心看多因素').length).toBeGreaterThan(0);
    expect(screen.getAllByText('市场情绪').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Checklist 状态').length).toBeGreaterThan(0);
    expect(screen.getByText('短线趋势')).toBeInTheDocument();
    expect(screen.getByText('变动原因')).toBeInTheDocument();
    expect(screen.getAllByText('短线技术偏弱，等待均线重新收敛。').length).toBeGreaterThan(0);
    expect(screen.getAllByText('MA5/10/20/60 已补齐，并保留基本面缓冲。').length).toBeGreaterThan(0);
    expect(screen.getByText('技术指标补齐导致')).toBeInTheDocument();
    expect(screen.getAllByText('数据中心需求回暖').length).toBeGreaterThan(0);
    expect(screen.getAllByText('估值仍偏高').length).toBeGreaterThan(0);
    expect(screen.getAllByText('上方前高压力仍在').length).toBeGreaterThan(0);
    expect(screen.getAllByText('FMP API').length).toBeGreaterThan(0);
    expect(screen.getAllByText('若放量跌破支撑位，需立即收缩仓位').length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getAllByText('会话指标').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('成交额').length).toBeGreaterThan(0);
    expect(screen.queryByText('Report Block')).not.toBeInTheDocument();
    expect(screen.queryByText(/先看最重要的最新更新/)).not.toBeInTheDocument();
  });

  it('keeps extended-session NA fields out of main decision layers for A-share reports', () => {
    const baseStandard = report.details?.standardReport;
    if (!baseStandard) {
      throw new Error('Missing standard report fixture');
    }

    const aShareReport: AnalysisReport = {
      ...report,
      meta: {
        ...report.meta,
        stockCode: '600519',
        stockName: '贵州茅台',
      },
      details: {
        ...report.details,
        standardReport: {
          ...baseStandard,
          market: {
            ...baseStandard.market,
            displayFields: [
              { label: '最新价', value: '123.40' },
            ],
            extendedFields: [
              { label: '盘前成交额', value: 'NA（会话不适用）' },
              { label: '盘后成交量', value: 'NA（当前市场不支持）' },
            ],
          },
          highlights: {
            ...baseStandard.highlights,
            latestNews: [],
            positiveCatalysts: [],
            riskAlerts: [],
            bullishFactors: [],
            bearishFactors: [],
            socialTone: '',
            socialAttention: '',
            socialNarrativeFocus: '',
          },
          reasonLayer: {
            ...baseStandard.reasonLayer,
            topRisk: '',
            topCatalyst: '',
            latestKeyUpdate: '',
            sentimentSummary: '',
          },
          checklistItems: [
            { status: 'pass', icon: '✅', text: '量价结构未破坏' },
          ],
        },
      },
    };

    render(<StandardReportPanel report={aShareReport} chartFixtures={previewChartFixtures} />);

    const executionLayer = screen.getByTestId('execution-risk-layer');
    const marketSignalLayer = screen.getAllByTestId('risk-catalyst-panel')[0];

    expect(within(executionLayer).queryByText(/盘前|盘后|extended/i)).not.toBeInTheDocument();
    expect(within(marketSignalLayer).queryByText(/盘前|盘后|extended/i)).not.toBeInTheDocument();
  });
});
