import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ReportDetails } from '../ReportDetails';

describe('ReportDetails', () => {
  const writeTextMock = vi.fn().mockResolvedValue(undefined);
  let originalClipboard: Navigator['clipboard'] | undefined;

  beforeEach(() => {
    vi.useFakeTimers();
    writeTextMock.mockClear();
    originalClipboard = navigator.clipboard;
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
    vi.useRealTimers();
  });

  it('keeps copied feedback scoped to the panel that was copied', async () => {
    const details = {
      rawResult: { score: 82 },
      contextSnapshot: { window: '30d' },
    };

    render(<ReportDetails recordId={7} details={details} />);

    fireEvent.click(screen.getByRole('button', { name: '원본 분석 결과' }));
    fireEvent.click(screen.getByRole('button', { name: '분석 스냅샷' }));

    const [rawCopyButton, snapshotCopyButton] = screen.getAllByRole('button', { name: '복사' });

    await act(async () => {
      fireEvent.click(rawCopyButton);
      await Promise.resolve();
    });

    expect(writeTextMock).toHaveBeenNthCalledWith(1, JSON.stringify(details.rawResult, null, 2));
    expect(screen.getByRole('button', { name: '복사됨' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '복사' })).toHaveLength(1);

    await act(async () => {
      fireEvent.click(snapshotCopyButton);
      await Promise.resolve();
    });

    expect(writeTextMock).toHaveBeenNthCalledWith(2, JSON.stringify(details.contextSnapshot, null, 2));
    expect(screen.getAllByRole('button', { name: '복사됨' })).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getAllByRole('button', { name: '복사' })).toHaveLength(2);
  });

  it('does not render when details and record id are both absent', () => {
    const { container } = render(<ReportDetails />);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders chart analysis summary when provided', () => {
    render(
      <ReportDetails
        details={{
          chartAnalysisReport: {
            status: 'ok',
            support: 100,
            resistance: 120,
            patternLabel: '5-bar breakout',
            visualSignalLabel: 'bullish',
            conflicts: [{ type: 'signal_conflict' }],
          },
        }}
      />,
    );

    expect(screen.getByText('차트 분석')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('5-bar breakout')).toBeInTheDocument();
    expect(screen.getByText('충돌: 1')).toBeInTheDocument();
  });

  it('renders event monitoring summary when provided', () => {
    render(
      <ReportDetails
        details={{
          eventMonitoringReport: {
            status: 'ok',
            monitoringPriority: 'critical',
            thesisBreakRisk: true,
            watchItems: ['Re-check thesis.'],
          },
        }}
      />,
    );

    expect(screen.getByText('이벤트 모니터링')).toBeInTheDocument();
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByText('true')).toBeInTheDocument();
    expect(screen.getByText('- Re-check thesis.')).toBeInTheDocument();
  });
});
