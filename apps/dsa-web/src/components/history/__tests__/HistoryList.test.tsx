import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HistoryList } from '../HistoryList';
import type { HistoryItem } from '../../../types/analysis';

const baseProps = {
  isLoading: false,
  isLoadingMore: false,
  hasMore: false,
  selectedIds: new Set<number>(),
  onItemClick: vi.fn(),
  onLoadMore: vi.fn(),
  onToggleItemSelection: vi.fn(),
  onToggleSelectAll: vi.fn(),
  onDeleteSelected: vi.fn(),
  onResetHistory: vi.fn(),
};

const items: HistoryItem[] = [
  {
    id: 1,
    queryId: 'q-1',
    stockCode: 'KR005930',
    stockName: '삼성전자',
    sentimentScore: 82,
    operationAdvice: '매수',
    createdAt: '2026-03-15T08:00:00Z',
  },
];

const longNameItem: HistoryItem = {
  id: 2,
  queryId: 'q-2',
  stockCode: 'KR005930',
  stockName: '삼성전자우선주장기테스트장기',
  sentimentScore: 75,
  operationAdvice: '관망',
  createdAt: '2026-03-16T08:00:00Z',
};

describe('HistoryList', () => {
  it('shows the empty state copy when no history exists', () => {
    const { container } = render(<HistoryList {...baseProps} items={[]} />);

    expect(screen.getByText('아직 분석 기록이 없습니다')).toBeInTheDocument();
    expect(screen.getByText('한국/미국 관심 종목을 분석하면 이곳에 기록이 표시됩니다.')).toBeInTheDocument();
    expect(screen.getByText('분석 기록')).toBeInTheDocument();
    expect(container.querySelector('.glass-card')).toBeTruthy();
  });

  it('renders selected count and forwards item interactions', () => {
    const onItemClick = vi.fn();
    const onToggleItemSelection = vi.fn();

    render(
      <HistoryList
        {...baseProps}
        items={items}
        selectedIds={new Set([1])}
        selectedId={1}
        onItemClick={onItemClick}
        onToggleItemSelection={onToggleItemSelection}
      />,
    );

    expect(screen.getByText('선택 1')).toBeInTheDocument();
    expect(screen.getByText('매수 82')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /삼성전자/i }));
    expect(onItemClick).toHaveBeenCalledWith(1);

    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    expect(onToggleItemSelection).toHaveBeenCalledWith(1);
  });

  it('toggles select-all when clicking the label text', () => {
    const onToggleSelectAll = vi.fn();

    render(
      <HistoryList
        {...baseProps}
        items={items}
        onToggleSelectAll={onToggleSelectAll}
      />,
    );

    fireEvent.click(screen.getByText('전체 선택'));

    expect(onToggleSelectAll).toHaveBeenCalledTimes(1);
  });

  it('disables delete when nothing is selected', () => {
    render(<HistoryList {...baseProps} items={items} />);

    expect(screen.getByRole('button', { name: '선택 삭제' })).toBeDisabled();
  });

  it('shows a reset action and legacy badge for old reports', () => {
    const onResetHistory = vi.fn();

    render(
      <HistoryList
        {...baseProps}
        items={[{ ...items[0], isLegacy: true }]}
        onResetHistory={onResetHistory}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '전체 초기화' }));

    expect(screen.getByText('legacy')).toBeInTheDocument();
    expect(onResetHistory).toHaveBeenCalledTimes(1);
  });

  it('keeps Korean stock names readable', () => {
    render(
      <HistoryList
        {...baseProps}
        items={[longNameItem]}
      />,
    );

    expect(screen.getAllByText('삼성전자우선주장기테스트장기').length).toBeGreaterThan(0);
  });

  it('generates unique select-all ids across multiple instances', () => {
    const { container } = render(
      <>
        <HistoryList {...baseProps} items={items} />
        <HistoryList {...baseProps} items={items} />
      </>,
    );

    const labels = container.querySelectorAll('label[for]');
    const ids = Array.from(labels).map((label) => label.getAttribute('for'));

    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
