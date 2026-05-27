import { render, screen } from '@testing-library/react';

import { describe, expect, it } from 'vitest';

import { ReportOverview } from '../ReportOverview';



const baseMeta = {

  queryId: 'q-1',

  stockCode: '600519',

  stockName: '구이저우마오타이',

  reportType: 'detailed' as const,

  reportLanguage: 'zh' as const,

  createdAt: '2026-03-21T08:00:00Z',

};



const baseSummary = {

  analysisSummary: '추세가 강세를 유지합니다',

  operationAdvice: '매수 지점을 계속 관찰합니다',

  trendPrediction: '단기 박스권 강세',

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

            { name: ' 백주 ', type: '업종' },

            { name: '소비', type: '테마' },

            { name: '신에너지' },

          ],

          sectorRankings: {

            top: [{ name: '백주', changePct: 2.31 }],

            bottom: [{ name: '소비', changePct: -1.2 }],

          },

        }}

      />,

    );



    expect(screen.getByText('관련 섹터')).toBeInTheDocument();

    expect(screen.getAllByText('백주').length).toBeGreaterThan(0);

    expect(screen.getByText('업종')).toBeInTheDocument();

    expect(screen.getAllByText('강세').length).toBeGreaterThan(0);

    expect(screen.getByText('+2.31%')).toBeInTheDocument();

    expect(screen.getByText('약세')).toBeInTheDocument();

    expect(screen.getByText('-1.20%')).toBeInTheDocument();

    expect(screen.queryByText('중립')).not.toBeInTheDocument();

  });



  it('shows board list when rankings are unavailable', () => {

    render(

      <ReportOverview

        meta={baseMeta}

        summary={baseSummary}

        details={{

          belongBoards: [{ name: '반도체', type: '업종' }],

        }}

      />,

    );



    expect(screen.getByText('관련 섹터')).toBeInTheDocument();

    expect(screen.getByText('반도체')).toBeInTheDocument();

    expect(screen.queryByText('중립')).not.toBeInTheDocument();

  });



  it('hides related boards section when no boards are available', () => {

    render(<ReportOverview meta={baseMeta} summary={baseSummary} details={{ belongBoards: [] }} />);



    expect(screen.queryByText('관련 섹터')).not.toBeInTheDocument();

  });



  it('fails open on malformed ranking payloads', () => {

    render(

      <ReportOverview

        meta={baseMeta}

        summary={baseSummary}

        details={{

          belongBoards: [{ name: ' 백주 ' }],

          sectorRankings: {

            top: {} as unknown as never[],

            bottom: [{ name: '백주', changePct: '-2.5%' as unknown as number }],

          },

        }}

      />,

    );



    expect(screen.getByText('관련 섹터')).toBeInTheDocument();

    expect(screen.getAllByText('백주').length).toBeGreaterThan(0);

    expect(screen.getByText('약세')).toBeInTheDocument();

    expect(screen.getByText('-2.50%')).toBeInTheDocument();

  });

});
