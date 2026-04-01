import { describe, expect, it } from 'vitest';
import type { AnalysisReport, FrontendReportContractMeta } from '../../../types/analysis';
import { decideReportRenderPath, resolveLegacyFallbackMode } from '../reportRenderPolicy';

const makeReport = (contractMeta: FrontendReportContractMeta): AnalysisReport => ({
  meta: {
    queryId: 'q-policy',
    stockCode: 'AAPL',
    stockName: 'Apple',
    reportType: 'full',
    createdAt: '2026-04-01T00:00:00Z',
  },
  summary: {
    analysisSummary: 'summary',
    operationAdvice: 'hold',
    trendPrediction: 'sideways',
    sentimentScore: 55,
  },
  contractMeta,
});

describe('reportRenderPolicy', () => {
  it('normalizes legacy fallback mode values', () => {
    expect(resolveLegacyFallbackMode('on')).toBe('on');
    expect(resolveLegacyFallbackMode('off')).toBe('off');
    expect(resolveLegacyFallbackMode('auto')).toBe('auto');
    expect(resolveLegacyFallbackMode('AUTO')).toBe('auto');
    expect(resolveLegacyFallbackMode('unknown')).toBe('auto');
    expect(resolveLegacyFallbackMode(undefined)).toBe('auto');
  });

  it('keeps standard path as primary for standard_report in auto mode', () => {
    const decision = decideReportRenderPath(
      makeReport({
        payloadVariant: 'standard_report',
        standardReportSource: 'details.standardReport',
      }),
      'auto',
    );
    expect(decision.renderPath).toBe('standard');
  });

  it('falls back to legacy in auto mode for legacy_only', () => {
    const decision = decideReportRenderPath(
      makeReport({
        payloadVariant: 'legacy_only',
        standardReportSource: 'none',
      }),
      'auto',
    );
    expect(decision.renderPath).toBe('legacy');
  });

  it('falls back to legacy in auto mode for legacy_empty', () => {
    const decision = decideReportRenderPath(
      makeReport({
        payloadVariant: 'legacy_empty',
        standardReportSource: 'none',
      }),
      'auto',
    );
    expect(decision.renderPath).toBe('legacy');
  });

  it('forces legacy fallback in on mode even for standard_report', () => {
    const decision = decideReportRenderPath(
      makeReport({
        payloadVariant: 'standard_report',
        standardReportSource: 'details.standardReport',
      }),
      'on',
    );
    expect(decision.renderPath).toBe('legacy');
  });

  it('disables fallback in off mode for legacy payloads', () => {
    const legacyOnly = decideReportRenderPath(
      makeReport({
        payloadVariant: 'legacy_only',
        standardReportSource: 'none',
      }),
      'off',
    );
    const legacyEmpty = decideReportRenderPath(
      makeReport({
        payloadVariant: 'legacy_empty',
        standardReportSource: 'none',
      }),
      'off',
    );
    expect(legacyOnly.renderPath).toBe('standard');
    expect(legacyEmpty.renderPath).toBe('standard');
  });
});

