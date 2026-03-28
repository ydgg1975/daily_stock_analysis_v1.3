import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StandardReportPanel } from '../StandardReportPanel';
import type { AnalysisReport } from '../../../types/analysis';

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
        stock: 'NVIDIA (NVDA)',
        ticker: 'NVDA',
        score: 78,
        currentPrice: '125.30',
        changeAmount: '2.30',
        changePct: '1.87%',
        marketTime: '2026-03-28 09:35:00 EDT',
        marketSessionDate: '2026-03-28',
        sessionLabel: '常规交易时段',
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
            { label: '当前价', value: '125.30' },
            { label: '涨跌幅', value: '1.87%' },
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
      highlights: {
        positiveCatalysts: ['数据中心需求回暖', 'AI 订单延续'],
        riskAlerts: ['估值仍偏高'],
        latestNews: ['公司发布新品并强化生态合作'],
        newsValueGrade: '高价值优先',
        sentimentSummary: '情绪边际回暖',
        earningsOutlook: '盈利预期改善',
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
  it('renders the rebuilt wide terminal layout without legacy tabs and narrow rails', () => {
    render(<StandardReportPanel report={report} />);

    expect(screen.getByText('NVIDIA (NVDA)')).toBeInTheDocument();
    expect(screen.getByText('等待回踩确认后再考虑加仓')).toBeInTheDocument();
    expect(screen.getAllByText('125.30').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1.87%').length).toBeGreaterThan(0);
    expect(screen.queryByRole('tab', { name: '概览' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '全部' })).not.toBeInTheDocument();
    expect(screen.getByTestId('hero-summary-card')).toBeInTheDocument();
    expect(screen.getAllByText('行情表').length).toBeGreaterThan(0);
    expect(screen.getAllByText('技术面表').length).toBeGreaterThan(0);
    expect(screen.getAllByText('基本面表').length).toBeGreaterThan(0);
    expect(screen.getAllByText('财报表').length).toBeGreaterThan(0);
    expect(screen.getByText('新闻 / 情绪 / 风险')).toBeInTheDocument();
    expect(screen.getByText('作战计划')).toBeInTheDocument();
    expect(screen.getByText('Checklist / 评分拆解 / 风险摘要')).toBeInTheDocument();
    expect(screen.getByText('评分拆解')).toBeInTheDocument();
    expect(screen.getAllByText('利好摘要').length).toBeGreaterThan(0);
    expect(screen.getAllByText('风险摘要').length).toBeGreaterThan(0);
    expect(screen.getByText('Checklist 状态')).toBeInTheDocument();
    expect(screen.getByText('短线趋势')).toBeInTheDocument();
    expect(screen.getByText('变动原因')).toBeInTheDocument();
    expect(screen.getByText('短线技术偏弱，等待均线重新收敛。')).toBeInTheDocument();
    expect(screen.getAllByText('MA5/10/20/60 已补齐，并保留基本面缓冲。').length).toBeGreaterThan(0);
    expect(screen.getByText('技术指标补齐导致')).toBeInTheDocument();
    expect(screen.getAllByText('数据中心需求回暖').length).toBeGreaterThan(0);
    expect(screen.getAllByText('估值仍偏高').length).toBeGreaterThan(0);
    expect(screen.getAllByText('FMP API').length).toBeGreaterThan(0);
    expect(screen.getAllByText('已就绪').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/口径 \/ 状态/).length).toBeGreaterThan(0);
    expect(screen.getByTestId('battle-plan-grid')).toBeInTheDocument();
    expect(screen.getByTestId('decision-board-panel')).toBeInTheDocument();
    expect(screen.getByText('若放量跌破支撑位，需立即收缩仓位')).toBeInTheDocument();
  });
});
