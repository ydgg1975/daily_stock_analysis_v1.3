import type React from 'react';
import { AlertTriangle, CheckCircle2, GitBranch, SearchCheck } from 'lucide-react';
import type { AnalysisConfidence, AnalysisMap } from '../../types/analysis';
import { Badge, Card } from '../common';

interface ReportAgentTraceProps {
  analysisMap?: AnalysisMap;
  analysisConfidence?: AnalysisConfidence;
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
}) => {
  if (!analysisMap && !analysisConfidence) {
    return null;
  }

  const nodes = Array.isArray(analysisMap?.nodes) ? analysisMap.nodes : [];
  const dataSources = Array.isArray(analysisMap?.dataSources) ? analysisMap.dataSources : [];
  const toolTrace = Array.isArray(analysisMap?.toolTrace) ? analysisMap.toolTrace : [];
  const warnings = Array.isArray(analysisConfidence?.warnings) ? analysisConfidence.warnings : [];
  const coverageRatio = analysisConfidence?.dataQuality?.coverageRatio ?? analysisMap?.coverage?.ratio;
  const toolSuccessRatio = analysisConfidence?.dataQuality?.toolSuccessRatio;
  const score = analysisConfidence?.score;

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
          <div className="text-2xl font-semibold text-foreground">{percent(toolSuccessRatio)}</div>
          <p className="mt-1 text-xs leading-5 text-muted-text">
            {toolTrace.length > 0 ? `${toolTrace.length}개 호출 기록` : '호출 기록 없음'}
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
