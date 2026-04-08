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
};

const items: HistoryItem[] = [
  {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: '贵州茅台',
    sentimentScore: 82,
    operationAdvice: '买入',
    createdAt: '2026-03-15T08:00:00Z',
  },
];

describe('HistoryList', () => {
  it('shows the empty state copy when no history exists', () => {
    render(<HistoryList {...baseProps} items={[]} />);

    expect(screen.getByText('暂无历史分析记录')).toBeInTheDocument();
    expect(screen.getByText('完成首次分析后，这里会保留最近结果。')).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole('button', { name: '管理' }));

    expect(screen.getByText('已选 1')).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.textContent === '建议 82')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /贵州茅台/i }));
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

    fireEvent.click(screen.getByRole('button', { name: '管理' }));
    fireEvent.click(screen.getByText('全选当前'));

    expect(onToggleSelectAll).toHaveBeenCalledTimes(1);
  });

  it('generates unique select-all ids across multiple instances', () => {
    const { container } = render(
      <>
        <HistoryList {...baseProps} items={items} />
        <HistoryList {...baseProps} items={items} />
      </>,
    );

    const manageButtons = screen.getAllByRole('button', { name: '管理' });
    fireEvent.click(manageButtons[0]);
    fireEvent.click(manageButtons[1]);

    const labels = container.querySelectorAll('label[for]');
    const ids = Array.from(labels).map((label) => label.getAttribute('for'));

    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('loads more when the scroll viewport reaches the bottom threshold', () => {
    const onLoadMore = vi.fn();

    render(
      <HistoryList
        {...baseProps}
        items={Array.from({ length: 6 }, (_, index) => ({
          ...items[0],
          id: index + 1,
          queryId: `q-${index + 1}`,
        }))}
        hasMore
        onLoadMore={onLoadMore}
      />,
    );

    const viewport = screen.getByTestId('home-history-list-scroll');
    Object.defineProperty(viewport, 'scrollHeight', { value: 1200, configurable: true });
    Object.defineProperty(viewport, 'clientHeight', { value: 400, configurable: true });
    Object.defineProperty(viewport, 'scrollTop', { value: 730, configurable: true });

    fireEvent.scroll(viewport);

    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });

  it('captures mouse wheel inside history viewport and scrolls list itself', () => {
    render(
      <HistoryList
        {...baseProps}
        items={Array.from({ length: 8 }, (_, index) => ({
          ...items[0],
          id: index + 1,
          queryId: `q-${index + 1}`,
        }))}
        embedded
      />,
    );

    const viewport = screen.getByTestId('home-history-list-scroll');
    Object.defineProperty(viewport, 'scrollHeight', { value: 1600, configurable: true });
    Object.defineProperty(viewport, 'clientHeight', { value: 320, configurable: true });
    Object.defineProperty(viewport, 'scrollTop', {
      value: 0,
      writable: true,
      configurable: true,
    });

    fireEvent.wheel(viewport, { deltaY: 240 });

    expect(viewport.scrollTop).toBe(240);
  });
});
