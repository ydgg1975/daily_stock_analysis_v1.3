import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportAgentTrace } from '../ReportAgentTrace';

describe('ReportAgentTrace', () => {
  it('renders analysis map and confidence details', () => {
    render(
      <ReportAgentTrace
        analysisMap={{
          version: 1,
          nodes: [
            {
              id: 'data',
              label: 'Data Collection',
              role: 'input',
              status: 'available',
            },
            {
              id: 'risk',
              label: 'Risk Review',
              role: 'guardrail',
              status: 'missing',
            },
          ],
          edges: [],
          dataSources: [
            {
              id: 'realtime_quote',
              label: 'price',
              available: true,
              reason: 'Used to anchor the analysis to the latest price.',
            },
          ],
          toolTrace: [
            {
              step: 1,
              tool: 'get_realtime_quote',
              node: 'technical',
              reason: 'Checked the latest quote to anchor price, volume, and intraday movement.',
              success: true,
            },
          ],
          toolMetrics: {
            version: 1,
            totalCalls: 2,
            success: 1,
            failure: 1,
            successRate: 0.5,
            avgDuration: 0.35,
            tools: [
              {
                tool: 'get_realtime_quote',
                calls: 2,
                success: 1,
                failure: 1,
                successRate: 0.5,
                failureRate: 0.5,
                avgDuration: 0.35,
              },
            ],
          },
          stageSummary: [],
          coverage: {
            completedNodes: 3,
            totalNodes: 5,
            ratio: 0.6,
            missingNodes: ['risk'],
          },
          reasoningGaps: ['Risk review was not confirmed by a completed risk stage.'],
        }}
        analysisConfidence={{
          version: 1,
          score: 0.68,
          label: 'medium',
          factors: [],
          warnings: ['Risk review was not confirmed by a completed risk stage.'],
          dataQuality: {
            coverageRatio: 0.6,
            toolSuccessRatio: 1,
            dataSourceScore: 0.33,
            missingNodes: ['risk'],
            reasoningGapCount: 1,
            riskFlagCount: 0,
          },
        }}
        details={{
          chartAnalysisReport: {
            status: 'ok',
            patternLabel: '5-bar breakout',
            visualSignalLabel: 'bullish',
          },
          eventMonitoringReport: {
            status: 'ok',
            monitoringPriority: 'critical',
            thesisBreakRisk: true,
          },
        }}
      />,
    );

    expect(screen.getByText('에이전트 판단 상태')).toBeInTheDocument();
    expect(screen.getByText('통합 리포트 보드')).toBeInTheDocument();
    expect(screen.getAllByText('68%')).toHaveLength(2);
    expect(screen.getAllByText('보통').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('60%')).toBeInTheDocument();
    expect(screen.getAllByText('50%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Data Collection · 확보')).toBeInTheDocument();
    expect(screen.getByText('Risk Review · 누락')).toBeInTheDocument();
    expect(screen.getByText('5-bar breakout')).toBeInTheDocument();
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByText('Portfolio')).toBeInTheDocument();
    expect(screen.getAllByText('get_realtime_quote')).toHaveLength(2);
    expect(screen.getByText('도구 운영 지표')).toBeInTheDocument();
    expect(screen.getByText('2 calls · 1 fail · avg 0.35s')).toBeInTheDocument();
    expect(screen.getByText(/latest quote/)).toBeInTheDocument();
    expect(screen.getByText('신뢰도 경고')).toBeInTheDocument();
  });

  it('renders nothing when trace data is absent', () => {
    const { container } = render(<ReportAgentTrace />);

    expect(container).toBeEmptyDOMElement();
  });
});
