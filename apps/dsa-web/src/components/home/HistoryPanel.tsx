/**
 * SpaceX live refactor: preserves the embedded history list behavior and
 * selection/load-more interactions while anchoring the archive column inside a
 * dedicated scrollable surface aligned with the top workspace row.
 */
import type React from 'react';
import type { HistoryItem } from '../../types/analysis';
import { HistoryList } from '../history';

type HistoryPanelProps = {
  items: HistoryItem[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  selectedId?: number;
  highlightedId?: number | null;
  selectedIds: Set<number>;
  isDeleting?: boolean;
  onItemClick: (recordId: number) => void;
  onLoadMore: () => void;
  onToggleItemSelection: (recordId: number) => void;
  onToggleSelectAll: () => void;
  onDeleteSelected: () => void;
};

export const HistoryPanel: React.FC<HistoryPanelProps> = (props) => {
  return (
    <HistoryList
      {...props}
      className="home-history-panel home-history-panel--spacex"
      embedded
    />
  );
};

export default HistoryPanel;
