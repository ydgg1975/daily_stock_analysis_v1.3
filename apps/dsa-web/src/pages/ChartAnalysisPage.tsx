import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { stocksApi, type StockChartAnalysisResponse } from '../api/stocks';
import type { ParsedApiError } from '../api/error';
import { createParsedApiError, getParsedApiError } from '../api/error';
import { ApiErrorAlert, AppPage, Badge, Card, EmptyState, InlineAlert, PageHeader } from '../components/common';

const INPUT_CLASS =
  'input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

const signalLabel: Record<string, string> = {
  bullish: '상승',
  bearish: '하락',
  neutral: '중립',
  bullish_overextended: '상승 과열',
  bearish_oversold: '하락 과매도',
};

const patternLabel: Record<string, string> = {
  five_bar_breakout: '5봉 돌파',
  five_bar_breakdown: '5봉 이탈',
  short_uptrend: '단기 상승',
  short_downtrend: '단기 하락',
  range_bound: '박스권',
  insufficient_data: '데이터 부족',
};

function formatNumber(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function formatSignal(value?: string): string {
  if (!value) return '--';
  return signalLabel[value] ?? value;
}

function formatDisplayLabel(value?: string, fallback?: string): string {
  if (value) return value;
  return fallback ?? '--';
}

function signalVariant(value?: string): 'success' | 'warning' | 'danger' | 'default' {
  if (!value) return 'default';
  if (value.includes('bullish')) return value.includes('overextended') ? 'warning' : 'success';
  if (value.includes('bearish')) return 'danger';
  return 'default';
}

const Metric: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="rounded-xl border border-border/70 bg-card/45 px-4 py-3">
    <p className="label-uppercase">{label}</p>
    <p className="mt-1 text-base font-semibold text-foreground">{value}</p>
  </div>
);

const ChartAnalysisPage: React.FC = () => {
  useEffect(() => {
    document.title = '차트 분석 - DSA';
  }, []);

  const [stockCode, setStockCode] = useState('AAPL');
  const [days, setDays] = useState('60');
  const [result, setResult] = useState<StockChartAnalysisResponse | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [loading, setLoading] = useState(false);

  const metadata = result?.metadata;
  const patternName = metadata?.pattern?.name;
  const conflictCount = metadata?.conflicts?.length ?? 0;
  const sanitizedSvg = useMemo(() => result?.svg ?? '', [result?.svg]);

  const runAnalysis = async () => {
    const trimmedCode = stockCode.trim();
    if (!trimmedCode) {
      setError(createParsedApiError({
        title: '입력 확인',
        message: '종목 코드를 입력하세요.',
        category: 'missing_params',
      }));
      return;
    }
    const parsedDays = Number.parseInt(days, 10);
    const effectiveDays = Number.isFinite(parsedDays) ? Math.min(Math.max(parsedDays, 30), 240) : 90;
    setLoading(true);
    setError(null);
    try {
      const data = await stocksApi.getChartAnalysis(trimmedCode, effectiveDays, true);
      setResult(data);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void runAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppPage>
      <PageHeader
        title="차트 분석"
        description="캔들, 이동평균, 거래량, RSI, MACD 기반의 차트 프리뷰입니다."
      />

      <div className="grid gap-5 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card title="분석 입력" subtitle="Chart Preview" padding="md">
            <div className="space-y-4">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-muted-text">종목 코드</span>
                <input
                  className={INPUT_CLASS}
                  value={stockCode}
                  onChange={(event) => setStockCode(event.target.value)}
                  placeholder="AAPL"
                  disabled={loading}
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-muted-text">기간</span>
                <input
                  className={INPUT_CLASS}
                  type="number"
                  min={30}
                  max={240}
                  value={days}
                  onChange={(event) => setDays(event.target.value)}
                  disabled={loading}
                />
              </label>
              <button
                type="button"
                className="btn-primary flex h-11 w-full items-center justify-center gap-2"
                disabled={loading}
                onClick={() => void runAnalysis()}
              >
                <Search className="h-4 w-4" />
                {loading ? '분석 중...' : '차트 분석'}
              </button>
            </div>
          </Card>

          {result ? (
            <Card title="신호 요약" subtitle={result.source ?? 'Data'} padding="md">
              <div className="flex flex-wrap gap-2">
                <Badge variant={signalVariant(metadata?.visualSignal)}>
                  차트 {formatDisplayLabel(metadata?.displayLabels?.visualSignal, formatSignal(metadata?.visualSignal))}
                </Badge>
                <Badge variant={signalVariant(metadata?.indicatorSignal)}>
                  지표 {formatDisplayLabel(metadata?.displayLabels?.indicatorSignal, formatSignal(metadata?.indicatorSignal))}
                </Badge>
                <Badge variant={conflictCount > 0 ? 'warning' : 'success'}>
                  충돌 {conflictCount}
                </Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <Metric label="종가" value={formatNumber(metadata?.latestClose)} />
                <Metric label="지지" value={formatNumber(metadata?.support)} />
                <Metric label="저항" value={formatNumber(metadata?.resistance)} />
                <Metric label="패턴" value={formatDisplayLabel(metadata?.displayLabels?.pattern, patternLabel[patternName ?? ''] ?? patternName)} />
              </div>
            </Card>
          ) : null}
        </div>

        <div className="space-y-5">
          {error ? <ApiErrorAlert error={error} /> : null}
          {result?.status === 'degraded' ? (
            <InlineAlert
              variant="warning"
              title="차트 분석 제한"
              message={result.reason ?? '차트 분석에 필요한 데이터가 부족합니다.'}
            />
          ) : null}

          <Card title={result ? `${result.stockCode} 차트` : '차트'} subtitle="SVG Preview" padding="md">
            {loading ? (
              <div className="flex min-h-[28rem] items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
              </div>
            ) : sanitizedSvg ? (
              <div
                className="overflow-auto rounded-xl border border-border/70 bg-white p-3"
                data-testid="chart-svg-preview"
                dangerouslySetInnerHTML={{ __html: sanitizedSvg }}
              />
            ) : (
              <EmptyState
                title="차트 없음"
                description="종목 코드를 입력하고 차트 분석을 실행하세요."
              />
            )}
          </Card>

          {metadata?.conflicts?.length ? (
            <Card title="충돌 신호" subtitle="Conflict" padding="md">
              <div className="space-y-3">
                {metadata.conflicts.map((item, index) => (
                  <div key={`${item.type ?? 'conflict'}-${index}`} className="rounded-xl border border-warning/30 bg-warning/8 px-4 py-3">
                    <p className="text-sm font-medium text-foreground">
                      {formatSignal(item.visualSignal)} vs {formatSignal(item.indicatorSignal)}
                    </p>
                    <p className="mt-1 text-sm text-muted-text">
                      {item.message ?? '차트 구조와 수치 지표가 서로 다른 방향을 가리킵니다.'}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          ) : null}
        </div>
      </div>
    </AppPage>
  );
};

export default ChartAnalysisPage;
