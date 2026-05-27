import type React from 'react';
import type {
  ReportDetails as ReportDetailsType,
  ReportMeta,
  ReportSummary as ReportSummaryType,
} from '../../types/analysis';
import { Card, ScoreGauge } from '../common';
import { formatDateTime } from '../../utils/format';
import { localizeLegacyText } from '../../utils/legacyKoreanText';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportOverviewProps {
  meta: ReportMeta;
  summary: ReportSummaryType;
  details?: ReportDetailsType;
  isHistory?: boolean;
}

/**
 */
export const ReportOverview: React.FC<ReportOverviewProps> = ({
  meta,
  summary,
  details,
}) => {
  const reportLanguage = normalizeReportLanguage(meta.reportLanguage);
  const text = getReportText(reportLanguage);
  const displayStockName = localizeLegacyText(meta.stockName || meta.stockCode);
  const displaySummary = localizeLegacyText(summary.analysisSummary);
  const displayAdvice = localizeLegacyText(summary.operationAdvice);
  const displayTrend = localizeLegacyText(summary.trendPrediction);

  const getPriceChangeStyle = (changePct: number | undefined): React.CSSProperties | undefined => {
    if (changePct === undefined || changePct === null) {
      return undefined;
    }

    if (changePct > 0) {
      return { color: 'var(--home-price-up)' };
    }

    if (changePct < 0) {
      return { color: 'var(--home-price-down)' };
    }

    return undefined;
  };

  const normalizeChangePct = (changePct: unknown): number | undefined => {
    if (typeof changePct === 'number' && Number.isFinite(changePct)) {
      return changePct;
    }
    if (typeof changePct === 'string') {
      const parsed = Number.parseFloat(changePct.replace('%', '').trim());
      return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
  };

  const formatChangePct = (changePct: number | undefined): string => {
    if (changePct === undefined || changePct === null) return '--';
    const sign = changePct > 0 ? '+' : '';
    return `${sign}${changePct.toFixed(2)}%`;
  };

  const relatedBoards = (details?.belongBoards ?? [])
    .map((board) => ({
      ...board,
      name: localizeLegacyText((board.name ?? '').trim()),
      type: board.type ? localizeLegacyText(board.type.trim()) : undefined,
    }))
    .filter((board) => board.name);

  const topRankings = Array.isArray(details?.sectorRankings?.top)
    ? details.sectorRankings.top
    : [];
  const bottomRankings = Array.isArray(details?.sectorRankings?.bottom)
    ? details.sectorRankings.bottom
    : [];
  const rankingItems = [
    ...topRankings.map((item) => ({ ...item, tone: 'leading' as const })),
    ...bottomRankings.map((item) => ({ ...item, tone: 'lagging' as const })),
  ].filter((item) => item.name);
  const hasBoardLinkage = relatedBoards.length > 0 || rankingItems.length > 0;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-stretch">
        <div className="lg:col-span-2 space-y-5">
          <Card variant="gradient" padding="md" className="home-report-hero">
            <div className="flex items-start justify-between mb-5">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <h2 className="text-[28px] font-bold leading-tight text-foreground">
                    {displayStockName}
                  </h2>
                  {meta.currentPrice != null && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-bold font-mono" style={getPriceChangeStyle(meta.changePct)}>
                        {meta.currentPrice.toFixed(2)}
                      </span>
                      <span className="text-sm font-semibold font-mono" style={getPriceChangeStyle(meta.changePct)}>
                        {formatChangePct(meta.changePct)}
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="home-accent-chip px-2 py-0.5 font-mono text-xs">
                    {meta.stockCode}
                  </span>
                  <span className="text-xs text-muted-text flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {formatDateTime(meta.createdAt)}
                  </span>
                </div>
              </div>
            </div>

            <div className="home-divider border-t pt-5">
              <span className="label-uppercase">{text.keyInsights}</span>
              <p className="mt-2 max-w-[62ch] whitespace-pre-wrap text-left text-[15px] leading-7 text-foreground">
                {displaySummary || text.noAnalysisSummary}
              </p>
            </div>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card
              variant="bordered"
              padding="sm"
              hoverable
              className="home-panel-card home-insight-card"
              style={{ ['--home-insight-tone' as string]: 'var(--home-strategy-buy)' }}
            >
              <div className="flex items-start gap-3">
                <div className="home-insight-icon w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <div className="space-y-1.5">
                  <h4 className="home-insight-title text-[11px] font-medium uppercase tracking-[0.16em]">{text.actionAdvice}</h4>
                  <p className="home-insight-body text-sm leading-6">
                    {displayAdvice || text.noAdvice}
                  </p>
                </div>
              </div>
            </Card>

            <Card
              variant="bordered"
              padding="sm"
              hoverable
              className="home-panel-card home-insight-card"
              style={{ ['--home-insight-tone' as string]: 'var(--home-strategy-take)' }}
            >
              <div className="flex items-start gap-3">
                <div className="home-insight-icon w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div className="space-y-1.5">
                  <h4 className="home-insight-title text-[11px] font-medium uppercase tracking-[0.16em]">{text.trendPrediction}</h4>
                  <p className="home-insight-body text-sm leading-6">
                    {displayTrend || text.noPrediction}
                  </p>
                </div>
              </div>
            </Card>
          </div>

          {hasBoardLinkage && (
            <Card variant="bordered" padding="md" className="home-panel-card">
              <div className="mb-3 flex items-baseline justify-between gap-3">
                <div>
                  <span className="label-uppercase">{text.boardLinkage}</span>
                  <h3 className="mt-1 text-base font-semibold text-foreground">{text.relatedBoards}</h3>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {relatedBoards.map((board) => (
                  <span
                    key={`${board.name}-${board.type ?? ''}`}
                    className="rounded-lg border border-border bg-surface/50 px-3 py-1.5 text-sm text-foreground"
                  >
                    {board.name}
                    {board.type && (
                      <span className="ml-2 text-xs text-muted-text">{board.type}</span>
                    )}
                  </span>
                ))}
                {rankingItems.map((item) => {
                  const label = item.tone === 'leading' ? text.leadingBoard : text.laggingBoard;
                  const pctValue = normalizeChangePct(item.changePct);
                  const pct = pctValue !== undefined ? formatChangePct(pctValue) : undefined;
                  return (
                    <span
                      key={`${item.tone}-${item.name}-${pct ?? ''}`}
                      className="rounded-lg border border-border bg-surface/50 px-3 py-1.5 text-sm text-foreground"
                    >
                      <span className="font-medium">{localizeLegacyText(item.name.trim())}</span>
                      <span className="ml-2 text-xs text-muted-text">{label}</span>
                      {pct && <span className="ml-2 font-mono text-xs">{pct}</span>}
                    </span>
                  );
                })}
              </div>
            </Card>
          )}
        </div>

        <div className="flex flex-col self-stretch min-h-full">
          <Card variant="bordered" padding="md" className="home-panel-card home-rail-card !overflow-visible flex-1 flex flex-col min-h-0">
            <div className="text-center flex-1 flex flex-col justify-center">
              <h3 className="mb-5 text-sm font-medium tracking-wide text-foreground">{text.marketSentiment}</h3>
              <ScoreGauge score={summary.sentimentScore} size="lg" language={reportLanguage} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
