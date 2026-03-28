import { describe, expect, it } from 'vitest';
import type { AnalysisReport } from '../../types/analysis';
import { normalizeAnalysisReport } from '../reportNormalizer';

describe('normalizeAnalysisReport', () => {
  it('fills required summary fields and defaults sentiment score when missing', () => {
    const report = {
      meta: {
        queryId: 'q1',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'detailed',
        createdAt: '2026-03-26T00:00:00Z',
      },
      summary: {
        analysisSummary: undefined,
        operationAdvice: undefined,
        trendPrediction: undefined,
        sentimentScore: undefined,
      },
    } as unknown as AnalysisReport;

    const normalized = normalizeAnalysisReport(report);

    expect(normalized.summary.analysisSummary).toBe('');
    expect(normalized.summary.operationAdvice).toBe('');
    expect(normalized.summary.trendPrediction).toBe('');
    expect(normalized.summary.sentimentScore).toBe(50);
  });

  it('uses top-level fallback metadata when report.meta fields are missing', () => {
    const report = {
      meta: {
        queryId: '',
        stockCode: '',
        stockName: '',
        reportType: undefined,
        createdAt: '',
      },
      summary: {
        analysisSummary: 'ok',
        operationAdvice: 'hold',
        trendPrediction: 'up',
        sentimentScore: 62,
      },
    } as unknown as AnalysisReport;

    const normalized = normalizeAnalysisReport(report, {
      queryId: 'q-fallback',
      stockCode: 'MSFT',
      stockName: 'Microsoft',
      createdAt: '2026-03-26T08:00:00+08:00',
    });

    expect(normalized.meta.queryId).toBe('q-fallback');
    expect(normalized.meta.stockCode).toBe('MSFT');
    expect(normalized.meta.stockName).toBe('Microsoft');
    expect(normalized.meta.reportType).toBe('detailed');
    expect(normalized.meta.createdAt).toBe('2026-03-26T08:00:00+08:00');
  });

  it('keeps standardReport when only camelCase rawResult fallback exists', () => {
    const standardReport = { market: { regularFields: [{ label: '当前价', value: '125.30' }] } };
    const report = {
      meta: {
        queryId: 'q2',
        stockCode: 'NVDA',
        stockName: 'NVIDIA',
        reportType: 'detailed',
        createdAt: '2026-03-26T00:00:00Z',
      },
      summary: {
        analysisSummary: 'ok',
        operationAdvice: 'hold',
        trendPrediction: 'up',
        sentimentScore: 62,
      },
      details: {
        rawResult: {
          standardReport,
        },
      },
    } as unknown as AnalysisReport;

    const normalized = normalizeAnalysisReport(report);

    expect(normalized.details?.standardReport).toEqual(standardReport);
  });

  it('keeps structured standardReport summary blocks for compact web rendering', () => {
    const standardReport = {
      summaryPanel: {
        stock: 'NVIDIA (NVDA)',
        ticker: 'NVDA',
        score: 78,
      },
      tableSections: {
        market: {
          title: '行情表',
          fields: [{ label: '当前价', value: '125.30' }],
        },
      },
      battlePlanCompact: {
        cards: [{ label: '理想买入点', value: '120-121' }],
      },
    };
    const report = {
      meta: {
        queryId: 'q3',
        stockCode: 'NVDA',
        stockName: 'NVIDIA',
        reportType: 'full',
        createdAt: '2026-03-26T00:00:00Z',
      },
      summary: {
        analysisSummary: 'ok',
        operationAdvice: 'hold',
        trendPrediction: 'up',
        sentimentScore: 62,
      },
      details: {
        standardReport,
      },
    } as unknown as AnalysisReport;

    const normalized = normalizeAnalysisReport(report);

    expect(normalized.details?.standardReport?.summaryPanel?.ticker).toBe('NVDA');
    expect(normalized.details?.standardReport?.tableSections?.market?.title).toBe('行情表');
    expect(normalized.details?.standardReport?.battlePlanCompact?.cards?.[0]?.value).toBe('120-121');
  });

  it('camelizes snake_case standard_report payloads from history and API detail responses', () => {
    const report = {
      meta: {
        queryId: 'q4',
        stockCode: 'TSLA',
        stockName: 'Tesla',
        reportType: 'full',
        createdAt: '2026-03-28T00:00:00Z',
      },
      summary: {
        analysisSummary: 'ok',
        operationAdvice: 'hold',
        trendPrediction: 'up',
        sentimentScore: 62,
      },
      details: {
        standard_report: {
          summary_panel: {
            ticker: 'TSLA',
            current_price: '362.19',
            market_session_date: '2026-03-27',
          },
          table_sections: {
            market: {
              title: '行情表',
              note: '按当前价与昨收重算',
            },
            technical: {
              title: '技术面表',
              fields: [{ label: 'MA20', value: '360.12', source: 'FMP API', status: '已就绪' }],
            },
          },
          visual_blocks: {
            price_position: {
              current_price: 362.19,
              distance_to_ma20_pct: 2.16,
            },
          },
          decision_context: {
            short_term_view: '短线技术偏弱，价格位于 MA20 下方。',
            composite_view: '基本面仍有支撑，综合建议维持观望。',
            adjustment_reason: 'MA5/10/20/60 已补齐，并保留基本面缓冲。',
            change_reason: '技术指标补齐导致',
            score_breakdown: [
              { label: '技术分', score: 38, note: '均线结构偏空', tone: 'danger' },
            ],
          },
          battle_plan_compact: {
            cards: [{ label: '理想买入点', value: '回踩 MA20 附近分批' }],
          },
          checklist_items: [{ status: 'warn', icon: '⚠️', text: '等待回踩确认' }],
        },
      },
    } as unknown as AnalysisReport;

    const normalized = normalizeAnalysisReport(report);

    expect(normalized.details?.standardReport?.summaryPanel?.ticker).toBe('TSLA');
    expect(normalized.details?.standardReport?.summaryPanel?.currentPrice).toBe('362.19');
    expect(normalized.details?.standardReport?.summaryPanel?.marketSessionDate).toBe('2026-03-27');
    expect(normalized.details?.standardReport?.tableSections?.market?.note).toBe('按当前价与昨收重算');
    expect(normalized.details?.standardReport?.tableSections?.technical?.fields?.[0]?.source).toBe('FMP API');
    expect(normalized.details?.standardReport?.tableSections?.technical?.fields?.[0]?.status).toBe('已就绪');
    expect(normalized.details?.standardReport?.visualBlocks?.pricePosition?.distanceToMa20Pct).toBe(2.16);
    expect(normalized.details?.standardReport?.decisionContext?.shortTermView).toBe('短线技术偏弱，价格位于 MA20 下方。');
    expect(normalized.details?.standardReport?.decisionContext?.adjustmentReason).toBe('MA5/10/20/60 已补齐，并保留基本面缓冲。');
    expect(normalized.details?.standardReport?.decisionContext?.changeReason).toBe('技术指标补齐导致');
    expect(normalized.details?.standardReport?.decisionContext?.scoreBreakdown?.[0]?.score).toBe(38);
    expect(normalized.details?.standardReport?.battlePlanCompact?.cards?.[0]?.value).toBe('回踩 MA20 附近分批');
    expect(normalized.details?.standardReport?.checklistItems?.[0]?.status).toBe('warn');
  });
});
