import { describe, expect, it } from 'vitest';
import {
  getReportControlledValueProfile,
  localizeReportControlledValue,
  localizeReportHeadingLabel,
} from '../reportTerminology';

describe('localizeReportHeadingLabel', () => {
  it('localizes execution/risk headings into English UI chrome', () => {
    expect(localizeReportHeadingLabel('执行计划', 'en')).toBe('Execution plan');
    expect(localizeReportHeadingLabel('当前动作', 'en')).toBe('Current action');
    expect(localizeReportHeadingLabel('新开仓策略', 'en')).toBe('For new positions');
    expect(localizeReportHeadingLabel('已持仓策略', 'en')).toBe('For existing positions');
  });

  it('localizes English headings into Chinese UI chrome', () => {
    expect(localizeReportHeadingLabel('Execution Plan', 'zh')).toBe('执行计划');
    expect(localizeReportHeadingLabel('Current Action', 'zh')).toBe('当前动作');
    expect(localizeReportHeadingLabel('For New Positions', 'zh')).toBe('新开仓策略');
  });

  it('keeps heading suffix content while translating the heading prefix', () => {
    expect(localizeReportHeadingLabel('当前动作: 等待回踩确认', 'en')).toBe('Current action: 等待回踩确认');
    expect(localizeReportHeadingLabel('Execution plan: wait for pullback', 'zh')).toBe('执行计划: wait for pullback');
  });

  it('localizes controlled decision values in both directions', () => {
    expect(localizeReportControlledValue('观望', 'en')).toBe('Watch');
    expect(localizeReportControlledValue('看空', 'en')).toBe('Bearish');
    expect(localizeReportControlledValue('hold', 'zh')).toBe('持有');
    expect(localizeReportControlledValue('short-term range, leaning stronger', 'zh')).toBe('short-term range, leaning stronger');
  });

  it('provides restrained support text for controlled values', () => {
    expect(getReportControlledValueProfile('观望', 'en')).toEqual({
      value: 'Watch',
      support: 'Wait for confirmation',
      matched: true,
    });
    expect(getReportControlledValueProfile('短线震荡偏强', 'en')).toEqual({
      value: 'Bullish',
      support: 'Trend strengthening',
      matched: true,
    });
  });
});
