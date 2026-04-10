/**
 * SpaceX live refinement: preserves report render-path selection and execution/detail
 * behavior while allowing the homepage to suppress duplicated lead summaries so the
 * canonical decision brief stays in the top workspace and lower modules start earlier.
 */
import React, { useEffect, useRef } from 'react';
import type { AnalysisResult, AnalysisReport } from '../../types/analysis';
import { ReportOverview } from './ReportOverview';
import { ReportStrategy } from './ReportStrategy';
import { ReportNews } from './ReportNews';
import { ReportDetails } from './ReportDetails';
import { StandardReportPanel } from './StandardReportPanel';
import { SupportPanel } from '../common';
import { ExecutionSummaryCard } from '../runtime/ExecutionSummaryCard';
import { useI18n } from '../../contexts/UiLanguageContext';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { localizeReportControlledValue } from '../../utils/reportTerminology';
import { decideReportRenderPath } from './reportRenderPolicy';
import { buildReportExecutionSummary } from '../../utils/runtimeExecution';

interface ReportSummaryProps {
  data: AnalysisResult | AnalysisReport;
  showExecutionSummary?: boolean;
  leadSummaryMode?: 'default' | 'compact-home';
}

interface StandardOnlyCompatibilityPanelProps {
  report: AnalysisReport;
  mode: 'on' | 'off' | 'auto';
}

const StandardOnlyCompatibilityPanel: React.FC<StandardOnlyCompatibilityPanelProps> = ({ report, mode }) => {
  const { t, language } = useI18n();
  const reportLanguage = normalizeReportLanguage(language);
  const stockLabel = report.meta.stockName || report.meta.stockCode || '--';
  const reportTime = report.meta.createdAt || '--';
  const summary = report.summary.analysisSummary?.trim();
  const advice = localizeReportControlledValue(report.summary.operationAdvice, reportLanguage);
  const trend = localizeReportControlledValue(report.summary.trendPrediction, reportLanguage);

  return (
    <SupportPanel
      title={t('report.compatibility.title')}
      body={t('report.compatibility.body')}
      role="status"
      className="report-empty-state"
      titleClassName="report-empty-state-title"
      bodyClassName="report-empty-state-body"
      actions={(
        <span className="text-xs text-muted-text">
          {t('report.compatibility.mode', { mode })}
        </span>
      )}
    >
      <div data-testid="report-standard-only-degraded" className="space-y-2 text-left text-xs text-secondary-text">
        <p>
          {t('report.compatibility.record')}: <span className="font-medium text-foreground">{stockLabel}</span>
        </p>
        <p>
          {t('report.compatibility.reportTime')}: <span className="font-medium text-foreground">{reportTime}</span>
        </p>
        {summary ? (
          <p>
            {t('report.compatibility.summary')}: <span className="font-medium text-foreground">{summary}</span>
          </p>
        ) : null}
        {advice ? (
          <p>
            {t('report.compatibility.advice')}: <span className="font-medium text-foreground">{advice}</span>
          </p>
        ) : null}
        {trend ? (
          <p>
            {t('report.compatibility.trend')}: <span className="font-medium text-foreground">{trend}</span>
          </p>
        ) : null}
        <p className="text-muted-text">{t('report.compatibility.note')}</p>
      </div>
    </SupportPanel>
  );
};

/**
 * 完整报告展示组件
 * 整合概览、策略、资讯、详情四个区域
 */
export const ReportSummary: React.FC<ReportSummaryProps> = ({
  data,
  showExecutionSummary = true,
  leadSummaryMode = 'default',
}) => {
  const { language } = useI18n();
  // 兼容 AnalysisResult 和 AnalysisReport 两种数据格式
  const originalReport: AnalysisReport = 'report' in data ? data.report : data;
  const {
    normalizedReport: report,
    mode: fallbackMode,
    contractMeta,
    renderPath,
  } = decideReportRenderPath(originalReport);
  const didLogFallbackRef = useRef<string | null>(null);
  // 使用 report id，因为 queryId 在批量分析时可能重复，且历史报告详情接口需要 recordId 来获取关联资讯和详情数据
  const recordId = report.meta.id;

  const { meta, summary, strategy, details } = report;
  const isLegacyFallback = renderPath === 'legacy';
  const isStandardOnlyNonStandard =
    fallbackMode === 'off' && contractMeta.payloadVariant !== 'standard_report';
  const uiReportLanguage = normalizeReportLanguage(language);
  const text = getReportText(uiReportLanguage);
  const modelUsed = (meta.modelUsed || '').trim();
  const shouldShowModel = Boolean(
    modelUsed && !['unknown', 'error', 'none', 'null', 'n/a'].includes(modelUsed.toLowerCase()),
  );
  const runtimeSummary = buildReportExecutionSummary(report);

  useEffect(() => {
    if (!isLegacyFallback) {
      return;
    }
    const isDevOrTest = import.meta.env.DEV || import.meta.env.MODE === 'test';
    if (!isDevOrTest) {
      return;
    }

    const key = `${meta.id ?? meta.queryId}:${contractMeta.payloadVariant}:${contractMeta.standardReportSource}:${fallbackMode}`;
    if (didLogFallbackRef.current === key) {
      return;
    }
    didLogFallbackRef.current = key;
    console.info('[report-legacy-fallback]', {
      payloadVariant: contractMeta.payloadVariant,
      standardReportSource: contractMeta.standardReportSource,
      fallbackMode,
      reportId: meta.id ?? null,
      queryId: meta.queryId,
      stockCode: meta.stockCode,
    });
  }, [
    contractMeta.payloadVariant,
    contractMeta.standardReportSource,
    fallbackMode,
    isLegacyFallback,
    meta.id,
    meta.queryId,
    meta.stockCode,
  ]);

  return (
    <div className="space-y-5 pb-8 animate-fade-in">
      {showExecutionSummary ? (
        <div className="report-reveal-section" style={{ ['--reveal-index' as string]: 0 }}>
          <ExecutionSummaryCard summary={runtimeSummary} />
        </div>
      ) : null}
      <div className="report-reveal-section" style={{ ['--reveal-index' as string]: 1 }}>
        {isStandardOnlyNonStandard ? (
          <StandardOnlyCompatibilityPanel report={report} mode={fallbackMode} />
        ) : renderPath === 'standard' ? (
          <StandardReportPanel report={report} showLeadSummary={leadSummaryMode !== 'compact-home'} />
        ) : (
          <>
            {leadSummaryMode !== 'compact-home' ? (
              <ReportOverview meta={meta} summary={summary} />
            ) : null}
            <ReportStrategy strategy={strategy} language={uiReportLanguage} />
          </>
        )}
      </div>

      {/* 资讯区：standard report 已内置终端化新闻面板，避免重复渲染旧资讯块 */}
      {renderPath === 'legacy' ? (
        <div className="report-reveal-section" style={{ ['--reveal-index' as string]: 2 }}>
          <ReportNews recordId={recordId} limit={8} language={uiReportLanguage} />
        </div>
      ) : null}

      {/* 透明度与追溯区 */}
      <div className="report-reveal-section" style={{ ['--reveal-index' as string]: 3 }}>
        <ReportDetails details={details} recordId={recordId} language={uiReportLanguage} />
      </div>

      {/* 分析模型标记（Issue #528）— 报告末尾 */}
      {shouldShowModel && (
        <div className="report-reveal-section" style={{ ['--reveal-index' as string]: 4 }}>
          <p className="px-1 text-xs text-muted-text">
            {text.analysisModel}: {modelUsed}
          </p>
        </div>
      )}
    </div>
  );
};
