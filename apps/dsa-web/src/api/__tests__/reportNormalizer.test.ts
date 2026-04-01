import { describe, expect, it } from 'vitest';
import type { AnalysisReport } from '../../types/analysis';
import { normalizeAnalysisReport } from '../reportNormalizer';
import { previewReport } from '../../dev/reportPreviewFixture';

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
    expect(normalized.contractMeta).toEqual({
      payloadVariant: 'legacy_empty',
      standardReportSource: 'none',
    });
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
    expect(normalized.contractMeta).toEqual({
      payloadVariant: 'legacy_empty',
      standardReportSource: 'none',
    });
  });

  it('classifies reports with details but without any standard report payload as legacy_only', () => {
    const report = {
      meta: {
        queryId: 'q-legacy-only',
        stockCode: 'BABA',
        stockName: 'Alibaba',
        reportType: 'detailed',
        createdAt: '2026-03-26T00:00:00Z',
      },
      summary: {
        analysisSummary: 'legacy data',
        operationAdvice: 'hold',
        trendPrediction: 'sideways',
        sentimentScore: 51,
      },
      details: {
        rawResult: {
          dashboard: {
            structuredAnalysis: {
              note: 'exists but no standard report payload',
            },
          },
        },
      },
    } as unknown as AnalysisReport;

    const normalized = normalizeAnalysisReport(report);

    expect(normalized.contractMeta).toEqual({
      payloadVariant: 'legacy_only',
      standardReportSource: 'none',
    });
    expect(normalized.details?.standardReport).toBeUndefined();
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
    expect(normalized.contractMeta).toEqual({
      payloadVariant: 'standard_report',
      standardReportSource: 'details.rawResult.standardReport',
    });
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
    expect(normalized.contractMeta).toEqual({
      payloadVariant: 'standard_report',
      standardReportSource: 'details.standardReport',
    });
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
          decision_panel: {
            ideal_entry: '回踩 MA20 附近分批',
            backup_entry: '回踩 MA60 二次确认',
            stop_loss: '跌破 MA60',
            target: '前高附近',
            position_sizing: '轻仓试错',
          },
          reason_layer: {
            core_reasons: ['短线技术偏弱，价格位于 MA20 下方。'],
            top_risk: '估值压力仍在',
            top_catalyst: 'AI 需求延续',
            latest_key_update: '最新季度盈利继续改善',
            checklist_summary: '仍有1项执行条件待确认',
          },
          battle_plan_compact: {
            cards: [{ label: '理想买入点', value: '回踩 MA20 附近分批' }],
          },
          coverage_notes: {
            data_sources: ['FMP API', 'FMP Statements'],
            missing_field_notes: ['VWAP：字段待接入'],
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
    expect(normalized.details?.standardReport?.decisionPanel?.idealEntry).toBe('回踩 MA20 附近分批');
    expect(normalized.details?.standardReport?.reasonLayer?.topRisk).toBe('估值压力仍在');
    expect(normalized.details?.standardReport?.battlePlanCompact?.cards?.[0]?.value).toBe('回踩 MA20 附近分批');
    expect(normalized.details?.standardReport?.coverageNotes?.missingFieldNotes?.[0]).toBe('VWAP：字段待接入');
    expect(normalized.details?.standardReport?.checklistItems?.[0]?.status).toBe('warn');
    expect(normalized.contractMeta).toEqual({
      payloadVariant: 'standard_report',
      standardReportSource: 'details.standard_report',
    });
  });

  it('builds contract metadata matrix for supported standard report payload variants', () => {
    const baseMeta = {
      queryId: 'matrix-q',
      stockCode: 'AAPL',
      stockName: 'Apple',
      reportType: 'full' as const,
      createdAt: '2026-03-26T00:00:00Z',
    };
    const baseSummary = {
      analysisSummary: 'ok',
      operationAdvice: 'hold',
      trendPrediction: 'up',
      sentimentScore: 62,
    };
    const variants: Array<{
      source: string;
      report: AnalysisReport;
      expectedSource: string;
    }> = [
      {
        source: 'details.standardReport',
        report: {
          meta: baseMeta,
          summary: baseSummary,
          details: {
            standardReport: {
              summaryPanel: { ticker: 'AAPL' },
            },
          },
        },
        expectedSource: 'details.standardReport',
      },
      {
        source: 'details.standard_report',
        report: {
          meta: baseMeta,
          summary: baseSummary,
          details: {
            standard_report: {
              summary_panel: { ticker: 'AAPL' },
            },
          } as unknown as AnalysisReport['details'],
        },
        expectedSource: 'details.standard_report',
      },
      {
        source: 'details.rawResult.standardReport',
        report: {
          meta: baseMeta,
          summary: baseSummary,
          details: {
            rawResult: {
              standardReport: {
                summaryPanel: { ticker: 'AAPL' },
              },
            },
          },
        },
        expectedSource: 'details.rawResult.standardReport',
      },
      {
        source: 'details.rawResult.standard_report',
        report: {
          meta: baseMeta,
          summary: baseSummary,
          details: {
            rawResult: {
              standard_report: {
                summary_panel: { ticker: 'AAPL' },
              },
            } as unknown as Record<string, unknown>,
          },
        },
        expectedSource: 'details.rawResult.standard_report',
      },
      {
        source: 'details.rawResult.dashboard.standardReport',
        report: {
          meta: baseMeta,
          summary: baseSummary,
          details: {
            rawResult: {
              dashboard: {
                standardReport: {
                  summaryPanel: { ticker: 'AAPL' },
                },
              },
            },
          },
        },
        expectedSource: 'details.rawResult.dashboard.standardReport',
      },
      {
        source: 'details.rawResult.dashboard.standard_report',
        report: {
          meta: baseMeta,
          summary: baseSummary,
          details: {
            rawResult: {
              dashboard: {
                standard_report: {
                  summary_panel: { ticker: 'AAPL' },
                },
              },
            } as unknown as Record<string, unknown>,
          },
        },
        expectedSource: 'details.rawResult.dashboard.standard_report',
      },
    ];

    for (const variant of variants) {
      const normalized = normalizeAnalysisReport(variant.report);
      expect(normalized.contractMeta?.payloadVariant, variant.source).toBe('standard_report');
      expect(normalized.contractMeta?.standardReportSource, variant.source).toBe(variant.expectedSource);
      expect(normalized.details?.standardReport?.summaryPanel?.ticker, variant.source).toBe('AAPL');
    }
  });

  it('keeps preview and production-like payloads aligned at normalized contract level', () => {
    const previewNormalized = normalizeAnalysisReport(previewReport);
    const productionLike = {
      ...previewReport,
      details: {
        standard_report: {
          summary_panel: {
            ticker: previewReport.details?.standardReport?.summaryPanel?.ticker,
            score: previewReport.details?.standardReport?.summaryPanel?.score,
            market_session_date: previewReport.details?.standardReport?.summaryPanel?.marketSessionDate,
          },
          decision_panel: {
            setup_type: previewReport.details?.standardReport?.decisionPanel?.setupType,
          },
        },
      },
    } as unknown as AnalysisReport;

    const productionLikeNormalized = normalizeAnalysisReport(productionLike);

    expect(previewNormalized.details?.standardReport?.summaryPanel?.ticker).toBe(
      productionLikeNormalized.details?.standardReport?.summaryPanel?.ticker,
    );
    expect(previewNormalized.details?.standardReport?.summaryPanel?.score).toBe(
      productionLikeNormalized.details?.standardReport?.summaryPanel?.score,
    );
    expect(previewNormalized.details?.standardReport?.summaryPanel?.marketSessionDate).toBe(
      productionLikeNormalized.details?.standardReport?.summaryPanel?.marketSessionDate,
    );
    expect(previewNormalized.details?.standardReport?.decisionPanel?.setupType).toBe(
      productionLikeNormalized.details?.standardReport?.decisionPanel?.setupType,
    );
    expect(previewNormalized.contractMeta?.payloadVariant).toBe('standard_report');
    expect(productionLikeNormalized.contractMeta?.payloadVariant).toBe('standard_report');
  });
});
