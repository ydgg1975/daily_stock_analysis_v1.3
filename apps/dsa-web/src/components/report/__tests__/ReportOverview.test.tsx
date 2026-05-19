import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportOverview } from '../ReportOverview';

const baseMeta = {
  queryId: 'q-1',
  stockCode: '600519',
  stockName: 'guizhoumaotai',
  reportType: 'detailed' as const,
  reportLanguage: 'zh' as const,
  createdAt: '2026-03-21T08:00:00Z',
};

const baseSummary = {
  analysisSummary: 'qushiweichiqiangshi',
  operationAdvice: 'jixuguanchamaidian',
  trendPrediction: 'duanxianzhendangpianqiang',
  sentimentScore: 78,
};

describe('ReportOverview', () => {
  it('renders related boards with leading and lagging markers', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: ' baijiu ', type: 'hangye' },
            { name: 'xiaofei', type: 'gainian' },
            { name: 'xinnengyuan' },
          ],
          sectorRankings: {
            top: [{ name: 'baijiu', changePct: 2.31 }],
            bottom: [{ name: 'xiaofei', changePct: -1.2 }],
          },
        }}
      />,
    );

    expect(screen.getByText('guanlianbankuai')).toBeInTheDocument();
    expect(screen.getByText('baijiu')).toBeInTheDocument();
    expect(screen.getByText('hangye')).toBeInTheDocument();
    expect(screen.getByText('lingzhang')).toBeInTheDocument();
    expect(screen.getByText('+2.31%')).toBeInTheDocument();
    expect(screen.getByText('lingdie')).toBeInTheDocument();
    expect(screen.getByText('-1.20%')).toBeInTheDocument();
    expect(screen.queryByText('zhongxing')).not.toBeInTheDocument();
  });

  it('shows board list when rankings are unavailable', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: 'bandaoti', type: 'hangye' }],
        }}
      />,
    );

    expect(screen.getByText('guanlianbankuai')).toBeInTheDocument();
    expect(screen.getByText('bandaoti')).toBeInTheDocument();
    expect(screen.queryByText('zhongxing')).not.toBeInTheDocument();
    expect(screen.queryByText('lingzhang')).not.toBeInTheDocument();
    expect(screen.queryByText('lingdie')).not.toBeInTheDocument();
  });

  it('hides related boards section when no boards are available', () => {
    render(<ReportOverview meta={baseMeta} summary={baseSummary} details={{ belongBoards: [] }} />);

    expect(screen.queryByText('guanlianbankuai')).not.toBeInTheDocument();
  });

  it('fails open on malformed ranking payloads', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: ' baijiu ' }],
          sectorRankings: {
            top: {} as unknown as never[],
            bottom: [{ name: 'baijiu', changePct: '-2.5%' as unknown as number }],
          },
        }}
      />,
    );

    expect(screen.getByText('guanlianbankuai')).toBeInTheDocument();
    expect(screen.getByText('baijiu')).toBeInTheDocument();
    expect(screen.getByText('lingdie')).toBeInTheDocument();
    expect(screen.getByText('-2.50%')).toBeInTheDocument();
  });
});
