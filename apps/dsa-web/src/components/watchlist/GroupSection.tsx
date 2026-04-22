import type React from 'react';
import { useCallback, useState } from 'react';
import type { WatchlistGroup } from '../../api/watchlist';
import { cn } from '../../utils/cn';
import { WatchlistCard } from './WatchlistCard';

interface GroupSectionProps {
  group: WatchlistGroup;
  groups: { groupId: string; groupName: string }[];
  onAnalyze: (stockCode: string) => void;
  onReanalyze: (stockCode: string) => void;
  onRemove: (stockCode: string) => void;
  onMoveGroup: (stockCode: string, groupId: string) => void;
  onRenameGroup: (groupId: string, name: string) => void;
  onDeleteGroup: (groupId: string) => void;
  onMoveItem: (stockCode: string, direction: 'up' | 'down') => void;
}

/**
 * Collapsible group container that renders a grid of WatchlistCards.
 */
export const GroupSection: React.FC<GroupSectionProps> = ({
  group,
  groups,
  onAnalyze,
  onReanalyze,
  onRemove,
  onMoveGroup,
  onRenameGroup,
  onDeleteGroup,
  onMoveItem,
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(group.groupName);

  const isDefault = group.groupId === 'default';

  const handleRenameSubmit = useCallback(() => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== group.groupName) {
      onRenameGroup(group.groupId, trimmed);
    }
    setRenaming(false);
  }, [renameValue, group.groupId, group.groupName, onRenameGroup]);

  return (
    <section className="mb-6">
      {/* Group header */}
      <div className="flex items-center gap-2 mb-3">
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          className="flex items-center gap-1.5 text-left transition-colors hover:text-foreground"
        >
          <svg
            className={cn(
              'h-4 w-4 text-muted-text transition-transform duration-200',
              !collapsed && 'rotate-90',
            )}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>

          {renaming ? (
            <input
              type="text"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={handleRenameSubmit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameSubmit();
                if (e.key === 'Escape') {
                  setRenameValue(group.groupName);
                  setRenaming(false);
                }
              }}
              onClick={(e) => e.stopPropagation()}
              autoFocus
              className="rounded border border-cyan/30 bg-transparent px-1.5 py-0.5 text-sm font-semibold text-foreground outline-none focus:border-cyan"
            />
          ) : (
            <span className="text-sm font-semibold text-foreground">
              {group.groupName}
            </span>
          )}

          <span className="text-xs text-muted-text">
            ({group.items.length})
          </span>
        </button>

        {/* Group actions (non-default only) */}
        {!isDefault && !renaming && (
          <div className="flex items-center gap-1 ml-auto">
            <button
              type="button"
              onClick={() => {
                setRenameValue(group.groupName);
                setRenaming(true);
              }}
              className="rounded p-1 text-muted-text transition-colors hover:text-foreground hover:bg-hover"
              aria-label={`Rename ${group.groupName}`}
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => onDeleteGroup(group.groupId)}
              className="rounded p-1 text-muted-text transition-colors hover:text-danger hover:bg-danger/5"
              aria-label={`Delete ${group.groupName}`}
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        )}
      </div>

      {/* Items grid */}
      {!collapsed && (
        group.items.length === 0 ? (
          <p className="text-xs text-muted-text pl-6">
            {'\u8FD9\u4E2A\u5206\u7EC4\u8FD8\u6CA1\u6709\u80A1\u7968'}
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {group.items.map((item) => (
              <WatchlistCard
                key={item.stockCode}
                item={item}
                onAnalyze={onAnalyze}
                onReanalyze={onReanalyze}
                onRemove={onRemove}
                onMoveGroup={onMoveGroup}
                onMoveItem={onMoveItem}
                groups={groups}
              />
            ))}
          </div>
        )
      )}
    </section>
  );
};
