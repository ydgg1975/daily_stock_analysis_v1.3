import type { AnalysisReport, FrontendReportContractMeta } from '../../types/analysis';
import { normalizeFrontendReportContract } from '../../api/reportNormalizer';

export type LegacyFallbackMode = 'on' | 'off' | 'auto';

const DEFAULT_MODE: LegacyFallbackMode = 'auto';

const DEFAULT_CONTRACT_META: FrontendReportContractMeta = {
  payloadVariant: 'legacy_empty',
  standardReportSource: 'none',
};

export function resolveLegacyFallbackMode(value: unknown): LegacyFallbackMode {
  if (typeof value !== 'string') {
    return DEFAULT_MODE;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === 'on' || normalized === 'off' || normalized === 'auto') {
    return normalized;
  }
  return DEFAULT_MODE;
}

export function getLegacyFallbackModeFromEnv(): LegacyFallbackMode {
  return resolveLegacyFallbackMode(import.meta.env.VITE_REPORT_LEGACY_FALLBACK);
}

export interface ReportRenderDecision {
  normalizedReport: AnalysisReport;
  mode: LegacyFallbackMode;
  contractMeta: FrontendReportContractMeta;
  renderPath: 'standard' | 'legacy';
}

export function decideReportRenderPath(
  report: AnalysisReport,
  mode = getLegacyFallbackModeFromEnv(),
): ReportRenderDecision {
  const normalizedReport = report.contractMeta ? report : normalizeFrontendReportContract(report);
  const contractMeta = normalizedReport.contractMeta ?? DEFAULT_CONTRACT_META;
  const hasStandardContract = contractMeta.payloadVariant === 'standard_report';

  let renderPath: 'standard' | 'legacy' = 'standard';
  if (mode === 'on') {
    renderPath = 'legacy';
  } else if (!hasStandardContract && mode === 'auto') {
    renderPath = 'legacy';
  }

  return {
    normalizedReport,
    mode,
    contractMeta,
    renderPath,
  };
}
