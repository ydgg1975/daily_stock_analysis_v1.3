import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import type { ReportDetails as ReportDetailsType, ReportLanguage } from '../../types/analysis';
import { Card } from '../common';
import { DashboardPanelHeader } from '../dashboard';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportDetailsProps {
  details?: ReportDetailsType;
  recordId?: number;
  language?: ReportLanguage;
}

export const ReportDetails: React.FC<ReportDetailsProps> = ({
  details,
  recordId,
  language = 'ko',
}) => {
  type JsonPanel = 'raw' | 'snapshot';
  type CopiedPanelState = Record<JsonPanel, boolean>;

  const reportLanguage = normalizeReportLanguage(language);
  const text = getReportText(reportLanguage);
  const [showRaw, setShowRaw] = useState(false);
  const [showSnapshot, setShowSnapshot] = useState(false);
  const [copiedPanels, setCopiedPanels] = useState<CopiedPanelState>({
    raw: false,
    snapshot: false,
  });
  const copyResetTimerRef = useRef<Partial<Record<JsonPanel, number>>>({});

  useEffect(() => {
    return () => {
      Object.values(copyResetTimerRef.current).forEach((timerId) => {
        if (timerId !== undefined) {
          window.clearTimeout(timerId);
        }
      });
      copyResetTimerRef.current = {};
    };
  }, []);

  const chart = details?.chartAnalysisReport;
  const eventReport = details?.eventMonitoringReport;
  const chartHeading = reportLanguage === 'en' ? 'Chart Analysis' : '차트 분석';
  const chartSupportLabel = reportLanguage === 'en' ? 'Support' : '지지선';
  const chartResistanceLabel = reportLanguage === 'en' ? 'Resistance' : '저항선';
  const chartPatternLabel = reportLanguage === 'en' ? 'Pattern' : '패턴';
  const chartSignalLabel = reportLanguage === 'en' ? 'Signal' : '신호';
  const chartConflictLabel = reportLanguage === 'en' ? 'Conflicts' : '충돌';
  const eventHeading = reportLanguage === 'en' ? 'Event Monitoring' : '이벤트 모니터링';
  const eventPriorityLabel = reportLanguage === 'en' ? 'Priority' : '우선순위';
  const eventThesisBreakLabel = reportLanguage === 'en' ? 'Thesis break risk' : '투자 가설 훼손 위험';
  const eventWatchLabel = reportLanguage === 'en' ? 'Watch items' : '관찰 항목';

  if (!details?.rawResult && !details?.contextSnapshot && !recordId && !chart && !eventReport) {
    return null;
  }

  const copyToClipboard = async (content: string, panel: JsonPanel) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedPanels((prev) => ({
        ...prev,
        [panel]: true,
      }));
      const existingTimer = copyResetTimerRef.current[panel];
      if (existingTimer !== undefined) {
        window.clearTimeout(existingTimer);
      }
      copyResetTimerRef.current[panel] = window.setTimeout(() => {
        setCopiedPanels((prev) => ({
          ...prev,
          [panel]: false,
        }));
        delete copyResetTimerRef.current[panel];
      }, 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const renderJson = (data: unknown, panel: JsonPanel) => {
    const jsonStr = JSON.stringify(data, null, 2);
    return (
      <div className="relative overflow-hidden">
        <span className="absolute top-2 right-2 z-10 inline-flex">
          <button
            type="button"
            onClick={() => copyToClipboard(jsonStr, panel)}
            className="home-accent-link text-xs text-muted-text"
            aria-label={copiedPanels[panel] ? text.copied : text.copy}
          >
            {copiedPanels[panel] ? text.copied : text.copy}
          </button>
        </span>
        <pre className="home-trace-pre home-trace-pre-content text-xs text-foreground font-mono overflow-x-auto p-3 bg-base rounded-lg max-h-80 overflow-y-auto text-left w-0 min-w-full">
          {jsonStr}
        </pre>
      </div>
    );
  };

  return (
    <Card variant="bordered" padding="md" className="home-panel-card text-left">
      <DashboardPanelHeader
        eyebrow={text.transparency}
        title={text.traceability}
        className="mb-3"
      />

      {recordId && (
        <div className="home-divider mb-3 flex items-center gap-2 border-b pb-3 text-xs text-muted-text">
          <span>{text.recordId}:</span>
          <code className="home-accent-chip px-1.5 py-0.5 font-mono text-xs">
            {recordId}
          </code>
        </div>
      )}

      {eventReport && (
        <div className="home-divider mb-3 border-b pb-3">
          <h3 className="mb-2 text-sm font-semibold text-foreground">{eventHeading}</h3>
          {eventReport.status === 'degraded' ? (
            <p className="text-xs text-muted-text">{eventReport.reason || 'Event monitoring is unavailable.'}</p>
          ) : (
            <div className="space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-border bg-surface/40 p-2">
                  <div className="text-muted-text">{eventPriorityLabel}</div>
                  <div className="font-semibold text-foreground">{eventReport.monitoringPriority ?? '--'}</div>
                </div>
                <div className="rounded-lg border border-border bg-surface/40 p-2">
                  <div className="text-muted-text">{eventThesisBreakLabel}</div>
                  <div className="font-semibold text-foreground">{eventReport.thesisBreakRisk ? 'true' : 'false'}</div>
                </div>
              </div>
              {eventReport.watchItems?.length ? (
                <div>
                  <div className="mb-1 text-muted-text">{eventWatchLabel}</div>
                  <ul className="space-y-1 text-foreground">
                    {eventReport.watchItems.slice(0, 3).map((item, index) => (
                      <li key={`${item}-${index}`}>- {item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          )}
        </div>
      )}

      {chart && (
        <div className="home-divider mb-3 border-b pb-3">
          <h3 className="mb-2 text-sm font-semibold text-foreground">{chartHeading}</h3>
          {chart.status === 'ok' ? (
            <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-muted-text">{chartSupportLabel}</div>
                <div className="font-semibold text-foreground">{chart.support ?? '--'}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-muted-text">{chartResistanceLabel}</div>
                <div className="font-semibold text-foreground">{chart.resistance ?? '--'}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-muted-text">{chartPatternLabel}</div>
                <div className="font-semibold text-foreground">{chart.patternLabel ?? '--'}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface/40 p-2">
                <div className="text-muted-text">{chartSignalLabel}</div>
                <div className="font-semibold text-foreground">{chart.visualSignalLabel ?? chart.indicatorSignalLabel ?? '--'}</div>
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-text">{chart.reason || 'Chart analysis is unavailable.'}</p>
          )}
          {chart.conflicts?.length ? (
            <p className="mt-2 text-xs text-warning">
              {chartConflictLabel}: {chart.conflicts.length}
            </p>
          ) : null}
        </div>
      )}

      <div className="space-y-2">
        {details?.rawResult && (
          <div>
            <button
              type="button"
              onClick={() => setShowRaw(!showRaw)}
              className="home-surface-button home-trace-toggle flex w-full items-center justify-between rounded-lg p-2.5"
            >
              <span className="text-xs text-foreground">{text.rawResult}</span>
              <svg
                className={`w-3.5 h-3.5 text-muted-text transition-transform ${showRaw ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {showRaw && (
              <div className="mt-2 animate-fade-in min-w-0 overflow-hidden">
                {renderJson(details.rawResult, 'raw')}
              </div>
            )}
          </div>
        )}

        {details?.contextSnapshot && (
          <div>
            <button
              type="button"
              onClick={() => setShowSnapshot(!showSnapshot)}
              className="home-surface-button home-trace-toggle flex w-full items-center justify-between rounded-lg p-2.5"
            >
              <span className="text-xs text-foreground">{text.analysisSnapshot}</span>
              <svg
                className={`w-3.5 h-3.5 text-muted-text transition-transform ${showSnapshot ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {showSnapshot && (
              <div className="mt-2 animate-fade-in min-w-0 overflow-hidden">
                {renderJson(details.contextSnapshot, 'snapshot')}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
};
