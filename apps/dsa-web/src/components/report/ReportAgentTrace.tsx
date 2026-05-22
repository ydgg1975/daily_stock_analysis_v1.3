import type React from 'react';
import { AlertTriangle, BarChart3, BriefcaseBusiness, CheckCircle2, GitBranch, Radar, SearchCheck, ShieldAlert } from 'lucide-react';
import type { AnalysisConfidence, AnalysisMap, ReportDetails } from '../../types/analysis';
import { Badge, Card } from '../common';

interface ReportAgentTraceProps {
  analysisMap?: AnalysisMap;
  analysisConfidence?: AnalysisConfidence;
  details?: ReportDetails;
}

const percent = (value: number | undefined): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return `${Math.round(value * 100)}%`;
};

const confidenceLabel = (label?: string): string => {
  if (label === 'high') return '높음';
  if (label === 'medium') return '보통';
  if (label === 'low') return '낮음';
  return '확인 필요';
};

const statusVariant = (status: string): 'success' | 'warning' | 'default' => {
  if (status === 'completed' || status === 'available') return 'success';
  if (status === 'missing') return 'warning';
  return 'default';
};

const statusLabel = (status: string): string => {
  if (status === 'completed') return '완료';
  if (status === 'available') return '확보';
  if (status === 'missing') return '누락';
  return status;
};

export const ReportAgentTrace: React.FC<ReportAgentTraceProps> = ({
  analysisMap,
  analysisConfidence,
  details,
}) => {
  if (!analysisMap && !analysisConfidence && !details?.chartAnalysisReport && !details?.eventMonitoringReport) {
    return null;
  }

  const nodes = Array.isArray(analysisMap?.nodes) ? analysisMap.nodes : [];
  const dataSources = Array.isArray(analysisMap?.dataSources) ? analysisMap.dataSources : [];
  const toolTrace = Array.isArray(analysisMap?.toolTrace) ? analysisMap.toolTrace : [];
  const toolMetrics = analysisMap?.toolMetrics;
  const toolMetricRows = Array.isArray(toolMetrics?.tools) ? toolMetrics.tools : [];
  const warnings = Array.isArray(analysisConfidence?.warnings) ? analysisConfidence.warnings : [];
  const coverageRatio = analysisConfidence?.dataQuality?.coverageRatio ?? analysisMap?.coverage?.ratio;
  const toolSuccessRatio = analysisConfidence?.dataQuality?.toolSuccessRatio;
  const score = analysisConfidence?.score;
  const findNodeStatus = (nodeId: string): string => nodes.find((node) => node.id === nodeId)?.status ?? 'optional';
  const evidenceStatus = nodes.length > 0 ? 'available' : 'missing';
  const riskStatus = findNodeStatus('risk');
  const chartStatus = details?.chartAnalysisReport
    ? details.chartAnalysisReport.status === 'ok' ? 'available' : 'missing'
    : findNodeStatus('chart');
  const eventStatus = details?.eventMonitoringReport
    ? details.eventMonitoringReport.status === 'ok' ? 'available' : 'missing'
    : 'optional';
  const portfolioStatus = findNodeStatus('portfolio');
  const signalTiles = [
    {
      id: 'confidence',
      label: 'Confidence',
      value: percent(score),
      detail: confidenceLabel(analysisConfidence?.label),
      status: analysisConfidence ? 'available' : 'missing',
      icon: CheckCircle2,
    },
    {
      id: 'evidence',
      label: 'Evidence',
      value: `${analysisMap?.coverage?.completedNodes ?? 0}/${analysisMap?.coverage?.totalNodes ?? nodes.length}`,
      detail: 'analysis map',
      status: evidenceStatus,
      icon: GitBranch,
    },
    {
      id: 'risk',
      label: 'Risk',
      value: statusLabel(riskStatus),
      detail: `${analysisConfidence?.dataQuality?.riskFlagCount ?? 0} flags`,
      status: riskStatus,
      icon: ShieldAlert,
    },
    {
      id: 'chart',
      label: 'Chart',
      value: details?.chartAnalysisReport?.patternLabel ?? statusLabel(chartStatus),
      detail: details?.chartAnalysisReport?.visualSignalLabel ?? details?.chartAnalysisReport?.indicatorSignalLabel ?? 'signal',
      status: chartStatus,
      icon: BarChart3,
    },
    {
      id: 'event',
      label: 'Event',
      value: details?.eventMonitoringReport?.monitoringPriority ?? statusLabel(eventStatus),
      detail: details?.eventMonitoringReport?.thesisBreakRisk ? 'thesis break risk' : 'monitoring',
      status: eventStatus,
      icon: Radar,
    },
    {
      id: 'portfolio',
      label: 'Portfolio',
      value: statusLabel(portfolioStatus),
      detail: 'exposure context',
      status: portfolioStatus,
      icon: BriefcaseBusiness,
    },
  ];

  return (
    <Card variant="bordered" padding="md" className="home-panel-card text-left">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <span className="label-uppercase">AGENT TRACE</span>
          <h3 className="mt-1 text-base font-semibold text-foreground">에이전트 판단 상태</h3>
        </div>
        {analysisConfidence && (
          <div className="rounded-lg border border-border/70 px-3 py-2 text-right">
            <div className="text-xs text-muted-text">신뢰도</div>
            <div className="text-lg font-semibold text-foreground">
              {percent(score)}
              <span className="ml-2 text-xs font-medium text-muted-text">
                {confidenceLabel(analysisConfidence.label)}
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="mb-4">
        <div className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-text">통합 리포트 보드</div>
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
          {signalTiles.map((tile) => {
            const Icon = tile.icon;
            return (
              <div key={tile.id} className="rounded-lg border border-border/60 bg-surface/30 p-2.5">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-muted-text">{tile.label}</span>
                  <Icon className="h-3.5 w-3.5 text-primary" />
                </div>
                <div className="truncate text-sm font-semibold text-foreground">{tile.value}</div>
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="truncate text-[11px] text-muted-text">{tile.detail}</span>
                  <Badge variant={statusVariant(tile.status)} className="px-1.5 py-0 text-[10px] shadow-none">
                    {statusLabel(tile.status)}
                  </Badge>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-border/60 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <GitBranch className="h-4 w-4 text-primary" />
            분석 커버리지
          </div>
          <div className="text-2xl font-semibold text-foreground">{percent(coverageRatio)}</div>
          <p className="mt-1 text-xs leading-5 text-muted-text">
            {analysisMap?.coverage?.completedNodes ?? 0}/{analysisMap?.coverage?.totalNodes ?? nodes.length} 단계 완료
          </p>
        </div>

        <div className="rounded-lg border border-border/60 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <SearchCheck className="h-4 w-4 text-primary" />
            도구 성공률
          </div>
          <div className="text-2xl font-semibold text-foreground">{percent(toolMetrics?.successRate ?? toolSuccessRatio)}</div>
          <p className="mt-1 text-xs leading-5 text-muted-text">
            {toolMetrics?.totalCalls ? `${toolMetrics.totalCalls}개 호출 · 평균 ${toolMetrics.avgDuration}s` : toolTrace.length > 0 ? `${toolTrace.length}개 호출 기록` : '호출 기록 없음'}
          </p>
        </div>

        <div className="rounded-lg border border-border/60 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            데이터 출처
          </div>
          <div className="text-2xl font-semibold text-foreground">{dataSources.length}</div>
          <p className="mt-1 text-xs leading-5 text-muted-text">구조화된 입력 기준</p>
        </div>
      </div>

      {nodes.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-text">분석 지도</div>
          <div className="flex flex-wrap gap-2">
            {nodes.map((node) => (
              <Badge key={node.id} variant={statusVariant(node.status)} className="shadow-none">
                {node.label} · {statusLabel(node.status)}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {toolTrace.length > 0 && (
        <div className="mt-4 space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-text">읽은 이유</div>
          {toolTrace.slice(0, 3).map((item, index) => (
            <div key={`${item.tool}-${index}`} className="rounded-lg border border-border/50 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium text-foreground">{item.tool}</span>
                <Badge variant={item.success ? 'success' : 'warning'} className="shadow-none">
                  {item.success ? '성공' : '확인 필요'}
                </Badge>
              </div>
              {item.reason && (
                <p className="mt-1 text-xs leading-5 text-muted-text">{item.reason}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {toolMetricRows.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-text">도구 운영 지표</div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {toolMetricRows.slice(0, 4).map((item) => (
              <div key={item.tool} className="rounded-lg border border-border/50 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-foreground">{item.tool}</span>
                  <Badge variant={item.failure ? 'warning' : 'success'} className="shadow-none">
                    {percent(item.successRate)}
                  </Badge>
                </div>
                <p className="mt-1 text-muted-text">
                  {item.calls} calls · {item.failure} fail · avg {item.avgDuration}s
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="mt-4 rounded-lg border border-warning/30 bg-warning/5 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <AlertTriangle className="h-4 w-4 text-warning" />
            신뢰도 경고
          </div>
          <ul className="space-y-1 text-xs leading-5 text-muted-text">
            {warnings.slice(0, 3).map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};
