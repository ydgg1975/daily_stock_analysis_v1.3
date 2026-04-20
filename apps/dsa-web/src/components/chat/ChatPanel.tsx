import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button, ApiErrorAlert } from '../common';
import { cn } from '../../utils/cn';
import type { ScopedChatStore } from '../../stores/scopedChatStore';
import type { ChatFollowUpContext } from '../../utils/chatFollowUp';

interface ChatPanelProps {
  store: ScopedChatStore;
  context: ChatFollowUpContext;
  presetPrompts?: string[];
  placeholder?: string;
  autoFocusInput?: boolean;
}

/**
 * 轻量对话面板。消息列表 + 输入框 + 空态预置追问。
 *
 * 与全局 `useAgentChatStore` 解耦：由 ChatDrawer 传入一个按 sessionId memo 的
 * scoped store，保证每份报告的会话互相隔离、首帧不会泄露 /chat 页的历史消息。
 */
export const ChatPanel: React.FC<ChatPanelProps> = ({
  store,
  context,
  presetPrompts = [],
  placeholder = '继续追问... (Enter 发送, Shift+Enter 换行)',
  autoFocusInput = false,
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const contextRef = useRef<ChatFollowUpContext>(context);

  const messages = store((s) => s.messages);
  const loading = store((s) => s.loading);
  const progressSteps = store((s) => s.progressSteps);
  const sessionId = store((s) => s.sessionId);
  const chatError = store((s) => s.chatError);
  const hydrated = store((s) => s.hydrated);

  useEffect(() => {
    contextRef.current = context;
  }, [context]);

  // 首次挂载 / store 实例变化时触发 hydrate（幂等：store 内部用 token 守卫去重）
  useEffect(() => {
    void store.getState().hydrate();
  }, [store]);

  // 卸载时中止任何在飞流
  useEffect(() => {
    return () => {
      store.getState().abort();
    };
  }, [store]);

  useEffect(() => {
    if (autoFocusInput && hydrated) {
      textareaRef.current?.focus();
    }
  }, [autoFocusInput, hydrated]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [messages, loading]);

  const handleSend = async (overrideMessage?: string) => {
    const text = (overrideMessage ?? input).trim();
    if (!text || loading || !hydrated) return;

    setInput('');
    await store.getState().startStream(
      {
        message: text,
        session_id: sessionId,
        context: contextRef.current,
      },
      { skillName: '追问' },
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const sendDisabled = !input.trim() || loading || !hydrated;

  const progressHint = progressSteps[progressSteps.length - 1]?.message
    || progressSteps[progressSteps.length - 1]?.display_name
    || '正在思考...';

  // hydrate 完成 + 无消息才算"空态"；hydrate 未完成时显示一个占位，避免首帧闪过去
  const showEmptyState = hydrated && messages.length === 0 && !loading;
  const showHydratingState = !hydrated;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {showHydratingState ? (
          <div className="flex h-full flex-col items-center justify-center text-center text-xs text-secondary-text">
            <span className="relative mb-2 inline-block h-4 w-4">
              <span className="absolute inset-0 rounded-full border-2 border-cyan/20" />
              <span className="absolute inset-0 animate-spin rounded-full border-2 border-cyan border-t-transparent" />
            </span>
            加载历史追问...
          </div>
        ) : showEmptyState ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-3 text-sm text-secondary-text">
              针对当前报告追问 AI — 上下文（买点/止损/目标价、持仓情况）已自动注入
            </div>
            {presetPrompts.length > 0 && (
              <div className="flex w-full flex-col gap-2">
                {presetPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    disabled={loading}
                    onClick={() => void handleSend(prompt)}
                    className="home-surface-button rounded-xl border border-border/60 px-3 py-2 text-left text-xs text-secondary-text transition-colors hover:border-cyan/50 hover:bg-cyan/5 hover:text-foreground disabled:opacity-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  'flex gap-2',
                  msg.role === 'user' ? 'flex-row-reverse' : '',
                )}
              >
                <div
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold shadow-sm',
                    msg.role === 'user' ? 'chat-avatar-user' : 'chat-avatar-ai',
                  )}
                >
                  {msg.role === 'user' ? 'U' : 'AI'}
                </div>
                <div
                  className={cn(
                    'min-w-0 max-w-[85%] overflow-hidden rounded-xl px-3 py-2 text-sm',
                    msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai',
                  )}
                >
                  {msg.role === 'assistant' ? (
                    <div className="chat-prose text-sm">
                      <Markdown remarkPlugins={[remarkGfm]}>{msg.content}</Markdown>
                    </div>
                  ) : (
                    msg.content.split('\n').map((line, i) => (
                      <p key={i} className="mb-1 last:mb-0 leading-relaxed">
                        {line || '\u00A0'}
                      </p>
                    ))
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex gap-2">
                <div className="chat-avatar-ai flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold">
                  AI
                </div>
                <div className="chat-bubble-ai rounded-xl px-3 py-2 text-xs text-secondary-text">
                  <span className="inline-flex items-center gap-2">
                    <span className="relative inline-block h-3 w-3">
                      <span className="absolute inset-0 rounded-full border-2 border-cyan/20" />
                      <span className="absolute inset-0 animate-spin rounded-full border-2 border-cyan border-t-transparent" />
                    </span>
                    {progressHint}
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="border-t border-border/60 bg-card/80 p-3">
        {chatError ? (
          <div className="mb-2">
            <ApiErrorAlert error={chatError} />
          </div>
        ) : null}
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={hydrated ? placeholder : '加载中...'}
            disabled={loading || !hydrated}
            rows={1}
            className="input-surface input-focus-glow flex-1 min-h-[40px] max-h-[160px] resize-none rounded-lg border bg-transparent px-3 py-2 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            onInput={(e) => {
              const t = e.target as HTMLTextAreaElement;
              t.style.height = 'auto';
              t.style.height = `${Math.min(t.scrollHeight, 160)}px`;
            }}
          />
          <Button
            variant="primary"
            size="sm"
            onClick={() => void handleSend()}
            disabled={sendDisabled}
            isLoading={loading}
            className="flex-shrink-0"
          >
            发送
          </Button>
        </div>
      </div>
    </div>
  );
};
