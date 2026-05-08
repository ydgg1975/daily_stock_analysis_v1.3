import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportStrategy } from '../ReportStrategy';

describe('ReportStrategy', () => {
  it('uses long-short neutral entry labels for futures reports', () => {
    render(
      <ReportStrategy
        assetType="futures"
        language="zh"
        strategy={{
          idealBuy: '空单入场：1200',
          secondaryBuy: '反弹确认后加空：1220',
          stopLoss: '1235',
          takeProfit: '1160',
        }}
      />,
    );

    expect(screen.getByText('理想入场')).toBeInTheDocument();
    expect(screen.getByText('二次入场')).toBeInTheDocument();
    expect(screen.queryByText('理想买入')).not.toBeInTheDocument();
    expect(screen.queryByText('二次买入')).not.toBeInTheDocument();
  });
});
