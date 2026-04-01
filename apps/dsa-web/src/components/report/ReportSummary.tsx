import React, { useEffect, useRef } from 'react';
import type { AnalysisResult, AnalysisReport } from '../../types/analysis';
import { ReportOverview } from './ReportOverview';
import { ReportStrategy } from './ReportStrategy';
import { ReportNews } from './ReportNews';
import { ReportDetails } from './ReportDetails';
import { StandardReportPanel } from './StandardReportPanel';
import { SupportPanel } from '../common';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { decideReportRenderPath } from './reportRenderPolicy';

interface ReportSummaryProps {
  data: AnalysisResult | AnalysisReport;
}

interface StandardOnlyCompatibilityPanelProps {
  report: AnalysisReport;
  mode: 'on' | 'off' | 'auto';
}

const StandardOnlyCompatibilityPanel: React.FC<StandardOnlyCompatibilityPanelProps> = ({ report, mode }) => {
  const language = normalizeReportLanguage(report.meta.reportLanguage);
  const isEn = language === 'en';
  const stockLabel = report.meta.stockName || report.meta.stockCode || '--';
  const reportTime = report.meta.createdAt || '--';
  const summary = report.summary.analysisSummary?.trim();
  const advice = report.summary.operationAdvice?.trim();
  const trend = report.summary.trendPrediction?.trim();

  const title = isEn
    ? 'Legacy history record (standard-only mode)'
    : '历史记录兼容提示（标准模式）';
  const body = isEn
    ? 'This record does not contain the standard report structure. The app is currently running in standard-only mode, so full rendering is unavailable for this history entry.'
    : '该历史记录不包含标准报告结构。当前应用运行于标准模式（standard-only），因此此条记录无法完整渲染。';
  const modeText = isEn
    ? `Current mode: ${mode}`
    : `当前模式：${mode}`;
  const note = isEn
    ? 'Use compatibility mode (auto/on) to view this record with legacy fallback when needed.'
    : '如需查看该记录完整内容，请切换到兼容模式（auto/on）并使用 legacy fallback。';

  return (
    <SupportPanel
      title={title}
      body={body}
      role="status"
      className="report-empty-state"
      titleClassName="report-empty-state-title"
      bodyClassName="report-empty-state-body"
      actions={(
        <span className="text-xs text-muted-text">
          {modeText}
        </span>
      )}
    >
      <div data-testid="report-standard-only-degraded" className="space-y-2 text-left text-xs text-secondary-text">
        <p>
          {isEn ? 'Record' : '记录'}: <span className="font-medium text-foreground">{stockLabel}</span>
        </p>
        <p>
          {isEn ? 'Report time' : '报告时间'}: <span className="font-medium text-foreground">{reportTime}</span>
        </p>
        {summary ? (
          <p>
            {isEn ? 'Summary' : '摘要'}: <span className="font-medium text-foreground">{summary}</span>
          </p>
        ) : null}
        {advice ? (
          <p>
            {isEn ? 'Advice' : '建议'}: <span className="font-medium text-foreground">{advice}</span>
          </p>
        ) : null}
        {trend ? (
          <p>
            {isEn ? 'Trend' : '趋势'}: <span className="font-medium text-foreground">{trend}</span>
          </p>
        ) : null}
        <p className="text-muted-text">{note}</p>
      </div>
    </SupportPanel>
  );
};

/**
 * 完整报告展示组件
 * 整合概览、策略、资讯、详情四个区域
 */
export const ReportSummary: React.FC<ReportSummaryProps> = ({ data }) => {
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
  const reportLanguage = normalizeReportLanguage(meta.reportLanguage);
  const text = getReportText(reportLanguage);
  const modelUsed = (meta.modelUsed || '').trim();
  const shouldShowModel = Boolean(
    modelUsed && !['unknown', 'error', 'none', 'null', 'n/a'].includes(modelUsed.toLowerCase()),
  );

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
      {isStandardOnlyNonStandard ? (
        <StandardOnlyCompatibilityPanel report={report} mode={fallbackMode} />
      ) : renderPath === 'standard' ? (
        <StandardReportPanel report={report} />
      ) : (
        <>
          {/* 概览区（首屏） */}
          <ReportOverview meta={meta} summary={summary} />

          {/* 策略点位区 */}
          <ReportStrategy strategy={strategy} language={reportLanguage} />
        </>
      )}

      {/* 资讯区：standard report 已内置终端化新闻面板，避免重复渲染旧资讯块 */}
      {renderPath === 'legacy' ? (
        <ReportNews recordId={recordId} limit={8} language={reportLanguage} />
      ) : null}

      {/* 透明度与追溯区 */}
      <ReportDetails details={details} recordId={recordId} language={reportLanguage} />

      {/* 分析模型标记（Issue #528）— 报告末尾 */}
      {shouldShowModel && (
        <p className="px-1 text-xs text-muted-text">
          {text.analysisModel}: {modelUsed}
        </p>
      )}
    </div>
  );
};
