import type React from 'react';
import { useLayoutEffect, useRef } from 'react';
import { Drawer } from '../common/Drawer';
import { ChatPanel } from './ChatPanel';
import { buildChatFollowUpContext } from '../../utils/chatFollowUp';
import { getScopedChatStore } from '../../stores/scopedChatStore';
import type { AnalysisReport } from '../../types/analysis';

interface ChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  report: AnalysisReport | null;
}

const PRESET_PROMPTS = [
  '为什么把止损和买点定在这里？给我解释一下这个点位逻辑',
  '结合我的持仓和自选股，这只有没有冲突或互补？',
  '如果我已经在更高价位买了，现在该怎么办？',
];

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * 报告内联 Chat 抽屉。
 *
 * 隔离策略（v2，修掉 codex review 两条 P1）：
 *  - useMemo 按 sessionId 创建独立 scoped store，不再写全局 useAgentChatStore
 *    → 关掉 drawer 不污染 /chat 页面的 session
 *  - 发送按钮在 store.hydrated 之前 disabled，首条消息不再能和 hydrate 赛跑
 *  - 打开时记录 document.activeElement，关闭时恢复焦点
 *  - Tab / Shift+Tab 在抽屉内环绕，防止键盘焦点逃到被遮挡的主页面
 */
export const ChatDrawer: React.FC<ChatDrawerProps> = ({ isOpen, onClose, report }) => {
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const derived = (() => {
    if (!report) return null;
    const code = report.meta.stockCode;
    const name = report.meta.stockName || null;
    const rid = report.meta.id;
    return {
      sessionId: rid !== undefined ? `report-${rid}` : `report-${code}`,
      context: buildChatFollowUpContext(code, name, report),
      title: name ? `${name}(${code})` : code,
    };
  })();

  // Scoped store comes from a module-level cache keyed by sessionId: same report
  // reopened reuses transcript; different report gets an isolated instance.
  const store = derived?.sessionId ? getScopedChatStore(derived.sessionId) : null;

  // Save/restore focus on open/close. useLayoutEffect in the parent runs BEFORE
  // child useEffect (e.g., ChatPanel's textarea autofocus), so we capture the
  // trigger element the user actually came from, not the textarea that child
  // effects are about to focus.
  useLayoutEffect(() => {
    if (!isOpen) return;
    previouslyFocusedRef.current = (document.activeElement as HTMLElement) ?? null;
    return () => {
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isOpen]);

  // Focus trap: keep Tab navigation inside the drawer
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'Tab') return;
    const root = dialogRef.current;
    if (!root) return;
    const focusables = Array.from(
      root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter((el) => !el.hasAttribute('disabled') && el.offsetParent !== null);
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement as HTMLElement | null;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  };

  if (!isOpen || !derived || !store) return null;

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title={derived.title}
      width="max-w-xl"
      zIndex={110}
      backdropClassName="bg-background/48 backdrop-blur-[2px]"
    >
      <div
        ref={dialogRef}
        onKeyDown={handleKeyDown}
        className="-m-6 flex h-[calc(100%+3rem)] flex-col overflow-hidden"
      >
        <ChatPanel
          store={store}
          context={derived.context}
          presetPrompts={PRESET_PROMPTS}
          autoFocusInput
        />
      </div>
    </Drawer>
  );
};
