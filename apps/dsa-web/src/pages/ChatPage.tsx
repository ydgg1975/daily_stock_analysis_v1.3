import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { agentApi } from '../api/agent';
import { ApiErrorAlert, Button, ConfirmDialog, ScrollArea } from '../components/common';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type { SkillInfo } from '../api/agent';
import {
  useAgentChatStore,
  type Message,
  type ProgressStep,
} from '../stores/agentChatStore';
import { downloadSession, formatSessionAsMarkdown } from '../utils/chatExport';
import type { ChatFollowUpContext } from '../utils/chatFollowUp';
import { buildFollowUpPrompt, resolveChatFollowUpContext } from '../utils/chatFollowUp';
import { isNearBottom } from '../utils/chatScroll';
import { useShellRail } from '../components/layout/ShellRailContext';

// Quick question examples shown on empty state
const QUICK_QUESTIONS = [
  { label: '用缠论分析茅台', skill: 'chan_theory' },
  { label: '波浪理论看宁德时代', skill: 'wave_theory' },
  { label: '分析比亚迪趋势', skill: 'bull_trend' },
  { label: '箱体震荡技能看中芯国际', skill: 'box_oscillation' },
  { label: '分析腾讯 hk00700', skill: 'bull_trend' },
  { label: '用情绪周期分析东方财富', skill: 'emotion_cycle' },
];

const STARTER_PROMPT_CARDS = [
  {
    title: '开仓执行判断',
    description: '快速判断现在能不能介入，并直接给出买点、止损和目标位。',
    prompt: '请判断 NVDA 现在是否适合介入，并给出买点、止损和目标位',
    skill: 'bull_trend',
  },
  {
    title: '持仓风控复盘',
    description: '适合已有仓位时判断继续持有、减仓还是等待反弹。',
    prompt: '我持有 TSLA，接下来该持有、减仓还是等待回踩确认？请给出风控建议',
    skill: 'bull_trend',
  },
  {
    title: '事件驱动跟踪',
    description: '聚焦财报、催化、风险与情绪，不只停留在泛泛聊天。',
    prompt: 'ORCL 财报后还值得继续跟踪吗？请列出催化、风险和执行计划',
    skill: 'bull_trend',
  },
];

const ChatPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [input, setInput] = useState('');
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<string>('');
  const [showSkillDesc, setShowSkillDesc] = useState<string | null>(null);
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [isFollowUpContextLoading, setIsFollowUpContextLoading] = useState(false);
  const [sendToast, setSendToast] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);
  const [skillsLoadError, setSkillsLoadError] = useState<ParsedApiError | null>(null);
  const messagesViewportRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isMountedRef = useRef(true);
  const followUpHydrationTokenRef = useRef(0);
  const followUpContextRef = useRef<ChatFollowUpContext | null>(null);
  const shouldStickToBottomRef = useRef(true);
  const pendingScrollBehaviorRef = useRef<ScrollBehavior>('auto');
  const { setRailContent, closeMobileRail, isConnected: hasShellRail } = useShellRail();

  // Set page title
  useEffect(() => {
    document.title = '问股 - WolfyStock';
  }, []);

  useEffect(() => () => {
    isMountedRef.current = false;
  }, []);

  const {
    messages,
    loading,
    progressSteps,
    sessionId,
    sessions,
    sessionsLoading,
    sessionLoadError,
    chatError,
    loadSessions,
    loadInitialSession,
    switchSession,
    startStream,
    clearCompletionBadge,
  } = useAgentChatStore();

  const syncScrollState = useCallback(() => {
    const viewport = messagesViewportRef.current;
    if (!viewport) return;
    shouldStickToBottomRef.current = isNearBottom({
      scrollTop: viewport.scrollTop,
      clientHeight: viewport.clientHeight,
      scrollHeight: viewport.scrollHeight,
    });
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  }, []);

  const requestScrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    shouldStickToBottomRef.current = true;
    pendingScrollBehaviorRef.current = behavior;
  }, []);

  const handleMessagesScroll = useCallback(() => {
    syncScrollState();
  }, [syncScrollState]);

  useEffect(() => {
    syncScrollState();
  }, [syncScrollState, sessionId]);

  useEffect(() => {
    const behavior = pendingScrollBehaviorRef.current;
    const shouldAutoScroll = shouldStickToBottomRef.current;
    if (!shouldAutoScroll) return;

    const frame = window.requestAnimationFrame(() => {
      scrollToBottom(behavior);
      pendingScrollBehaviorRef.current = loading ? 'auto' : 'smooth';
    });

    return () => window.cancelAnimationFrame(frame);
  }, [messages, progressSteps, loading, sessionId, scrollToBottom]);

  useEffect(() => {
    if (!loading) {
      pendingScrollBehaviorRef.current = 'smooth';
    }
  }, [loading]);

  useEffect(() => {
    clearCompletionBadge();
  }, [clearCompletionBadge]);

  useEffect(() => {
    loadInitialSession();
  }, [loadInitialSession]);

  const loadSkills = useCallback(async () => {
    try {
      setSkillsLoadError(null);
      const res = await agentApi.getSkills();
      setSkills(res.skills);
      const defaultId =
        res.default_skill_id ||
        res.skills[0]?.id ||
        '';
      setSelectedSkill(defaultId);
    } catch (error: unknown) {
      setSkillsLoadError(getParsedApiError(error));
      setSkills([]);
      setSelectedSkill('');
    }
  }, []);

  useEffect(() => {
    void loadSkills();
  }, [loadSkills]);

  const availableSkillIds = new Set(skills.map((skill) => skill.id));
  const quickQuestions = QUICK_QUESTIONS.filter((question) => availableSkillIds.size === 0 || availableSkillIds.has(question.skill));
  const starterPromptCards = STARTER_PROMPT_CARDS.filter(
    (card) => availableSkillIds.size === 0 || availableSkillIds.has(card.skill),
  );

  const handleStartNewChat = useCallback(() => {
    followUpContextRef.current = null;
    requestScrollToBottom('auto');
    useAgentChatStore.getState().startNewChat();
    if (hasShellRail) {
      closeMobileRail();
    } else {
      setSidebarOpen(false);
    }
  }, [closeMobileRail, hasShellRail, requestScrollToBottom]);

  const handleSwitchSession = useCallback((targetSessionId: string) => {
    requestScrollToBottom('auto');
    switchSession(targetSessionId);
    if (hasShellRail) {
      closeMobileRail();
    } else {
      setSidebarOpen(false);
    }
  }, [closeMobileRail, hasShellRail, requestScrollToBottom, switchSession]);

  const confirmDelete = useCallback(() => {
    if (!deleteConfirmId) return;
    agentApi.deleteChatSession(deleteConfirmId).then(() => {
      loadSessions();
      if (deleteConfirmId === sessionId) {
        handleStartNewChat();
      }
    }).catch(() => {});
    setDeleteConfirmId(null);
  }, [deleteConfirmId, sessionId, loadSessions, handleStartNewChat]);

  // Handle follow-up from report page: ?stock=600519&name=贵州茅台&recordId=xxx
  useEffect(() => {
    const stock = searchParams.get('stock');
    const name = searchParams.get('name');
    const recordId = searchParams.get('recordId');
    if (!stock) {
      return;
    }

    const hydrationToken = ++followUpHydrationTokenRef.current;
    setInput(buildFollowUpPrompt(stock, name));
    followUpContextRef.current = {
      stock_code: stock,
      stock_name: name,
    };
    if (recordId) {
      setIsFollowUpContextLoading(true);
    }
    void resolveChatFollowUpContext({
      stockCode: stock,
      stockName: name,
      recordId: recordId ? Number(recordId) : undefined,
    }).then((context) => {
      if (!isMountedRef.current || followUpHydrationTokenRef.current !== hydrationToken) {
        return;
      }
      followUpContextRef.current = context;
    }).finally(() => {
      if (isMountedRef.current && followUpHydrationTokenRef.current === hydrationToken) {
        setIsFollowUpContextLoading(false);
      }
    });
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  const handleSend = useCallback(
    async (overrideMessage?: string, overrideSkill?: string) => {
      const msgText = overrideMessage || input.trim();
      if (!msgText || loading) return;
      const usedSkill = overrideSkill || selectedSkill;
      const usedSkillName =
        skills.find((s) => s.id === usedSkill)?.name ||
        (usedSkill ? usedSkill : '通用');

      const payload = {
        message: msgText,
        session_id: sessionId,
        skills: usedSkill ? [usedSkill] : undefined,
        context: followUpContextRef.current ?? undefined,
      };
      followUpHydrationTokenRef.current += 1;
      followUpContextRef.current = null;
      setIsFollowUpContextLoading(false);

      setInput('');
      requestScrollToBottom('smooth');
      await startStream(payload, { skillName: usedSkillName });
    },
    [input, loading, requestScrollToBottom, selectedSkill, skills, sessionId, startStream],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickQuestion = (q: (typeof QUICK_QUESTIONS)[0]) => {
    setSelectedSkill(q.skill);
    handleSend(q.label, q.skill);
  };

  const toggleThinking = (msgId: string) => {
    setExpandedThinking((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) next.delete(msgId);
      else next.add(msgId);
      return next;
    });
  };

  const getCurrentStage = (steps: ProgressStep[]): string => {
    if (steps.length === 0) return '正在连接...';
    const last = steps[steps.length - 1];
    if (last.type === 'thinking') return last.message || 'AI 正在思考...';
    if (last.type === 'tool_start')
      return `${last.display_name || last.tool}...`;
    if (last.type === 'tool_done')
      return `${last.display_name || last.tool} 完成`;
    if (last.type === 'generating')
      return last.message || '正在生成最终分析...';
    return '处理中...';
  };

  const renderThinkingBlock = (msg: Message) => {
    if (!msg.thinkingSteps || msg.thinkingSteps.length === 0) return null;
    const isExpanded = expandedThinking.has(msg.id);
    const toolSteps = msg.thinkingSteps.filter((s) => s.type === 'tool_done');
    const totalDuration = toolSteps.reduce(
      (sum, s) => sum + (s.duration || 0),
      0,
    );
    const summary = `${toolSteps.length} 个工具调用 · ${totalDuration.toFixed(1)}s`;

    return (
      <button
        onClick={() => toggleThinking(msg.id)}
        className="flex items-center gap-2 text-xs text-muted-text hover:text-secondary-text transition-colors mb-2 w-full text-left"
      >
        <svg
          className={`w-3 h-3 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        <span className="flex items-center gap-1.5">
          <span className="opacity-60">思考过程</span>
          <span className="text-muted-text/50">·</span>
          <span className="opacity-50">{summary}</span>
        </span>
      </button>
    );
  };

  const renderThinkingDetails = (steps: ProgressStep[]) => (
    <div className="mb-3 pl-5 border-l border-border/40 space-y-0.5 animate-fade-in">
      {steps.map((step, idx) => {
        let icon = '⋯';
        let text = '';
        let colorClass = 'text-muted-text';
        if (step.type === 'thinking') {
          icon = '🤔';
          text = step.message || `第 ${step.step} 步：思考`;
          colorClass = 'text-secondary-text';
        } else if (step.type === 'tool_start') {
          icon = '⚙️';
          text = `${step.display_name || step.tool}...`;
          colorClass = 'text-secondary-text';
        } else if (step.type === 'tool_done') {
          icon = step.success ? '✅' : '❌';
          text = `${step.display_name || step.tool} (${step.duration}s)`;
          colorClass = step.success ? 'text-success' : 'text-danger';
        } else if (step.type === 'generating') {
          icon = '✍️';
          text = step.message || '生成分析';
          colorClass = 'text-[hsl(var(--accent-primary-hsl))]';
        }
        return (
          <div
            key={idx}
            className={`flex items-center gap-2 text-xs py-0.5 ${colorClass}`}
          >
            <span className="w-4 flex-shrink-0 text-center">{icon}</span>
            <span className="leading-relaxed">{text}</span>
          </div>
        );
      })}
    </div>
  );

  const sidebarContent = useMemo(() => (
    <div className="theme-panel-solid flex h-full min-h-0 flex-col overflow-hidden rounded-[1.2rem]">
      <div className="theme-sidebar-divider flex items-center justify-between border-b px-3.5 py-3">
        <h2 className="text-[11px] font-semibold text-[hsl(var(--accent-primary-hsl))] uppercase tracking-[0.2em] flex items-center gap-2">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          历史对话
        </h2>
        <button
          onClick={handleStartNewChat}
          className="theme-panel-subtle rounded-lg p-1.5 text-muted-text transition-all duration-200 ease-out hover:text-foreground"
          title="开启新对话"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
        </button>
      </div>
      {sessionLoadError ? (
        <ApiErrorAlert
          error={sessionLoadError}
          className="m-3"
          actionLabel="重试加载会话"
          onAction={() => {
            void loadSessions();
          }}
        />
      ) : null}
      <ScrollArea testId="chat-session-list-scroll" viewportClassName="p-3">
        {sessionsLoading ? (
          <div className="p-4 text-center text-xs text-muted-text">加载中...</div>
        ) : sessions.length === 0 ? (
          <div className="p-4 text-center text-xs text-muted-text">暂无历史对话</div>
        ) : (
          <div className="space-y-2">
            {sessions.map((s) => (
              <div
                key={s.session_id}
                role="button"
                tabIndex={0}
                onClick={() => handleSwitchSession(s.session_id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleSwitchSession(s.session_id);
                  }
                }}
                data-active={s.session_id === sessionId}
                className="theme-list-item group relative flex w-full cursor-pointer items-start gap-3 overflow-hidden rounded-xl border p-2.5 transition-all duration-200 ease-out"
                aria-label={`切换到对话 ${s.title}`}
              >
                {/* 装饰条 */}
                <div
                  className={`h-10 w-1 rounded-full flex-shrink-0 transition-colors ${
                    s.session_id === sessionId ? 'bg-[hsl(var(--accent-primary-hsl))]' : 'bg-white/10'
                  }`}
                />

                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <span className={`block truncate text-sm font-semibold tracking-tight transition-colors ${
                        s.session_id === sessionId ? 'text-foreground' : 'text-secondary-text group-hover:text-foreground'
                      }`}>
                        {s.title}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteConfirmId(s.session_id);
                      }}
                      className="flex-shrink-0 rounded p-1 text-muted-text opacity-0 transition-all hover:bg-white/10 hover:text-danger group-hover:opacity-100"
                      title="删除"
                    >
                      <svg
                        className="w-3.5 h-3.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[11px] text-muted-text">
                      {s.message_count} 条对话
                    </span>
                    {s.last_active && (
                      <>
                        <span className="h-1 w-1 rounded-full bg-white/10" />
                        <span className="text-[11px] text-muted-text">
                          {new Date(s.last_active).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  ), [handleStartNewChat, handleSwitchSession, loadSessions, sessionId, sessionLoadError, sessions, sessionsLoading]);

  useEffect(() => {
    if (!hasShellRail) {
      return undefined;
    }
    setRailContent(sidebarContent);
    return () => setRailContent(null);
  }, [hasShellRail, setRailContent, sidebarContent]);

  return (
    <div data-testid="chat-workspace" className="workspace-page workspace-page--chat">
      <div className="workspace-chat-layout">
        {!hasShellRail ? (
          <div className="hidden h-full w-[var(--layout-context-rail-width)] flex-shrink-0 flex-col overflow-hidden md:flex">
            {sidebarContent}
          </div>
        ) : null}

        {!hasShellRail && sidebarOpen ? (
          <div
            className="fixed inset-0 z-40 md:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <div className="absolute inset-0 bg-black/60" />
            <div
              className="theme-sidebar-shell absolute bottom-0 left-0 top-0 flex w-[min(var(--layout-context-rail-width),88vw)] flex-col overflow-hidden rounded-none rounded-r-[1.35rem]"
              onClick={(e) => e.stopPropagation()}
            >
              {sidebarContent}
            </div>
          </div>
        ) : null}

        <ConfirmDialog
          isOpen={Boolean(deleteConfirmId)}
          title="删除对话"
          message="删除后，该对话将不可恢复，确认删除吗？"
          confirmText="删除"
          cancelText="取消"
          isDanger
          onConfirm={confirmDelete}
          onCancel={() => setDeleteConfirmId(null)}
        />

        <div className="workspace-chat-main">
          <header className="workspace-header-panel mb-4 flex-shrink-0">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">WolfyStock Quant Research</p>
                <h1 className="mb-2 mt-2 flex items-center gap-2 text-2xl font-bold text-foreground">
                  {!hasShellRail ? (
                    <button
                      onClick={() => setSidebarOpen(true)}
                      className="-ml-1 rounded-lg p-1.5 text-secondary-text transition-colors hover:bg-hover hover:text-foreground md:hidden"
                      title="历史对话"
                    >
                      <svg
                        className="h-5 w-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M4 6h16M4 12h16M4 18h16"
                        />
                      </svg>
                    </button>
                  ) : null}
                  <svg
                    className="h-6 w-6 text-[hsl(var(--accent-primary-hsl))]"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                    />
                  </svg>
                  问股
                </h1>
                <p className="text-sm leading-6 text-secondary-text">
                  把这里当成股票研究助手工作台来用：先问结论，再追问风险、催化、仓位和执行计划。
                </p>
              </div>

              {messages.length > 0 ? (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => downloadSession(messages)}
                    className="flex items-center gap-1.5 rounded-lg border border-border/70 px-3 py-1.5 text-sm text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
                    title="导出会话为 Markdown 文件"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                      />
                    </svg>
                    导出会话
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      if (sending) return;
                      setSending(true);
                      setSendToast(null);
                      try {
                        const content = formatSessionAsMarkdown(messages);
                        await agentApi.sendChat(content);
                        setSendToast({ type: 'success', message: '已发送到通知渠道' });
                        setTimeout(() => setSendToast(null), 3000);
                      } catch (err) {
                        const parsed = getParsedApiError(err);
                        setSendToast({
                          type: 'error',
                          message: parsed.message || '发送失败',
                        });
                        setTimeout(() => setSendToast(null), 5000);
                      } finally {
                        setSending(false);
                      }
                    }}
                    disabled={sending}
                    className="flex items-center gap-1.5 rounded-lg border border-border/70 px-3 py-1.5 text-sm text-secondary-text transition-colors hover:bg-hover hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                    title="发送到已配置的通知机器人/邮箱"
                  >
                    {sending ? (
                      <svg
                        className="h-4 w-4 animate-spin"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                        />
                      </svg>
                    )}
                    发送
                  </button>
                  {sendToast ? (
                    <span className={`text-sm ${sendToast.type === 'success' ? 'text-success' : 'text-danger'}`}>
                      {sendToast.message}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          </header>

          <div className="workspace-surface relative z-10 flex min-h-0 flex-1 flex-col overflow-hidden rounded-[1.4rem]">
          {skillsLoadError ? (
            <div className="px-4 pb-0 pt-4 md:px-6 md:pt-6">
              <ApiErrorAlert
                error={skillsLoadError}
                actionLabel="重试加载策略"
                onAction={() => {
                  void loadSkills();
                }}
              />
            </div>
          ) : null}
          {/* Messages */}
          <ScrollArea
            className="relative z-10 flex-1"
            viewportRef={messagesViewportRef}
            onScroll={handleMessagesScroll}
            viewportClassName="space-y-6 p-4 md:p-6"
            testId="chat-message-scroll"
          >
            {messages.length === 0 && !loading ? (
              <div className="mx-auto flex h-full w-full max-w-5xl flex-col justify-center">
                <div className="theme-panel-glass rounded-[1.35rem] px-5 py-5">
                  <div className="flex items-start gap-4">
                    <div className="theme-panel-subtle flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl">
                      <svg
                        className="h-7 w-7 text-[hsl(var(--accent-primary-hsl))]"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                        />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-lg font-medium text-foreground">从一个高价值问题开始</h3>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-secondary-text">
                        问股页现在更偏向“研究助手工作台”：优先帮你形成交易结论、风险提示、催化判断和执行计划，而不是泛泛聊天。
                      </p>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-3 md:grid-cols-3">
                    {starterPromptCards.map((card) => (
                      <button
                        key={card.title}
                        type="button"
                        onClick={() => handleSend(card.prompt, card.skill)}
                        className="theme-panel-subtle rounded-[1.1rem] px-4 py-4 text-left transition-all duration-200 ease-out hover:-translate-y-[1px]"
                      >
                        <p className="text-sm font-semibold tracking-tight text-foreground">{card.title}</p>
                        <p className="mt-2 text-sm leading-6 text-secondary-text">{card.description}</p>
                        <p className="mt-3 text-xs leading-5 text-muted-text">{card.prompt}</p>
                      </button>
                    ))}
                  </div>

                  {quickQuestions.length > 0 ? (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {quickQuestions.slice(0, 4).map((q, i) => (
                        <button
                          key={i}
                          onClick={() => handleQuickQuestion(q)}
                          className="theme-inline-chip rounded-full px-3 py-1.5 text-sm text-secondary-text transition-all duration-200 ease-out hover:text-foreground"
                        >
                          {q.label}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                      msg.role === 'user'
                        ? 'bg-[hsl(var(--accent-primary-hsl))] text-[hsl(var(--bg-page-hsl))]'
                        : 'bg-elevated text-foreground'
                    }`}
                  >
                    {msg.role === 'user' ? 'U' : 'AI'}
                  </div>
                  <div
                    className={`min-w-0 w-fit max-w-[min(100%,56rem)] overflow-hidden rounded-2xl px-5 py-3.5 ${
                      msg.role === 'user'
                        ? 'bg-[hsl(var(--accent-primary-hsl)/0.12)] text-foreground border border-[hsl(var(--accent-primary-hsl)/0.32)] rounded-tr-sm'
                        : 'theme-panel-subtle text-secondary-text rounded-tl-sm'
                    }`}
                  >
                    {msg.role === 'assistant' && msg.skillName && (
                      <div className="mb-2">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[hsl(var(--accent-primary-hsl)/0.12)] border border-[hsl(var(--accent-primary-hsl)/0.3)] text-xs text-[hsl(var(--accent-primary-hsl))]">
                          <svg
                            className="w-3 h-3"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M13 10V3L4 14h7v7l9-11h-7z"
                            />
                          </svg>
                          {msg.skillName}
                        </span>
                      </div>
                    )}
                    {msg.role === 'assistant' && renderThinkingBlock(msg)}
                    {msg.role === 'assistant' &&
                      expandedThinking.has(msg.id) &&
                      msg.thinkingSteps &&
                      renderThinkingDetails(msg.thinkingSteps)}
                    {msg.role === 'assistant' ? (
                      <div
                        className="prose prose-invert prose-sm max-w-none
                      prose-headings:text-foreground prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1.5
                      prose-h1:text-lg prose-h2:text-base prose-h3:text-sm
                      prose-p:mb-2 prose-p:last:mb-0 prose-p:leading-7 prose-p:break-words
                      prose-strong:text-foreground prose-strong:font-semibold
                      prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-li:break-words
                      prose-code:text-[hsl(var(--accent-primary-hsl))] prose-code:bg-card/70 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:break-all
                      prose-pre:max-w-full prose-pre:overflow-x-auto prose-pre:bg-black/30 prose-pre:border prose-pre:border-border/70 prose-pre:rounded-lg prose-pre:p-3
                      prose-table:w-full prose-table:text-sm
                      prose-th:text-foreground prose-th:font-medium prose-th:border-border prose-th:px-3 prose-th:py-1.5 prose-th:bg-card/70
                      prose-td:border-border/70 prose-td:px-3 prose-td:py-1.5
                      prose-hr:border-border/70 prose-hr:my-3
                      prose-a:text-[hsl(var(--accent-primary-hsl))] prose-a:no-underline hover:prose-a:underline
                      prose-blockquote:border-[hsl(var(--accent-primary-hsl)/0.3)] prose-blockquote:text-secondary-text
                      [&_table]:block [&_table]:overflow-x-auto [&_table]:whitespace-nowrap
                      [&_img]:max-w-full
                    "
                      >
                        <Markdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </Markdown>
                      </div>
                    ) : (
                      msg.content
                        .split('\n')
                        .map((line, i) => (
                          <p
                            key={i}
                            className="mb-1 last:mb-0 leading-relaxed"
                          >
                            {line || '\u00A0'}
                          </p>
                        ))
                    )}
                  </div>
                </div>
              ))
            )}

            {loading && (
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded-full bg-elevated text-foreground flex items-center justify-center flex-shrink-0 text-xs font-bold">
                  AI
                </div>
                <div className="theme-panel-subtle min-w-[200px] max-w-[min(100%,56rem)] overflow-hidden rounded-2xl rounded-tl-sm px-5 py-4">
                  <div className="flex items-center gap-2.5 text-sm text-secondary-text">
                    <div className="relative w-4 h-4 flex-shrink-0">
                      <div className="absolute inset-0 rounded-full border-2 border-[hsl(var(--accent-primary-hsl)/0.2)]" />
                      <div className="absolute inset-0 rounded-full border-2 border-[hsl(var(--accent-primary-hsl))] border-t-transparent animate-spin" />
                    </div>
                    <span className="text-secondary-text">
                      {getCurrentStage(progressSteps)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </ScrollArea>

          {/* Input area */}
          <div className="theme-sidebar-divider relative z-20 border-t p-4 md:p-5">
            {chatError ? (
              <ApiErrorAlert
                error={chatError}
                className="mb-3"
                actionLabel={chatError.category === 'local_connection_failed' ? '刷新页面后重试' : undefined}
                onAction={
                  chatError.category === 'local_connection_failed'
                    ? () => {
                        window.location.reload();
                      }
                    : undefined
                }
              />
            ) : null}
            {skills.length > 0 && (
              <div className="theme-panel-subtle mb-3 rounded-[1rem] p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">研究模式</p>
                    <p className="mt-1 text-sm text-secondary-text">选择一个策略视角，让回答更贴近你的分析框架。</p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedSkill('')}
                    className={`rounded-full border px-3 py-1.5 text-sm transition-all duration-200 ease-out ${
                      selectedSkill === ''
                        ? 'border-[hsl(var(--accent-primary-hsl)/0.3)] bg-[hsl(var(--accent-primary-hsl)/0.08)] text-foreground'
                        : 'theme-inline-chip text-secondary-text hover:text-foreground'
                    }`}
                  >
                    通用分析
                  </button>
                  {skills.map((s) => (
                    <div
                      key={s.id}
                      className="relative"
                      onMouseEnter={() => setShowSkillDesc(s.id)}
                      onMouseLeave={() => setShowSkillDesc(null)}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedSkill(s.id)}
                        className={`rounded-full border px-3 py-1.5 text-sm transition-all duration-200 ease-out ${
                          selectedSkill === s.id
                            ? 'border-[hsl(var(--accent-primary-hsl)/0.3)] bg-[hsl(var(--accent-primary-hsl)/0.08)] text-foreground'
                            : 'theme-inline-chip text-secondary-text hover:text-foreground'
                        }`}
                      >
                        {s.name}
                      </button>
                      {showSkillDesc === s.id && s.description ? (
                        <div className="theme-menu-panel absolute left-0 bottom-full mb-2 z-50 w-64 rounded-lg p-2.5 text-xs leading-relaxed text-secondary-text shadow-xl pointer-events-none animate-fade-in">
                          <p className="mb-1 font-medium text-foreground">{s.name}</p>
                          <p>{s.description}</p>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="theme-panel-subtle rounded-[1rem] p-3">
              <div className="flex items-end gap-3">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="例如：分析 600519 / 茅台现在适合买入吗？ (Enter 发送, Shift+Enter 换行)"
                  disabled={loading}
                  rows={1}
                  className="input-terminal flex-1 min-h-[46px] max-h-[200px] resize-none py-2.5"
                  style={{ height: 'auto' }}
                  onInput={(e) => {
                    const t = e.target as HTMLTextAreaElement;
                    t.style.height = 'auto';
                    t.style.height = `${Math.min(t.scrollHeight, 200)}px`;
                  }}
                />
                <Button
                  variant="primary"
                  onClick={() => handleSend()}
                  disabled={!input.trim() || loading}
                  isLoading={loading}
                  className="h-[46px] flex-shrink-0 px-6"
                >
                  发送
                </Button>
              </div>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-muted-text">优先提问：买点、止损、目标位、风险和催化。</p>
                <span className="text-xs text-secondary-text">
                  当前策略：{selectedSkill ? (skills.find((item) => item.id === selectedSkill)?.name || selectedSkill) : '通用分析'}
                </span>
              </div>
            </div>
            {isFollowUpContextLoading && (
              <p className="mt-2 text-xs text-secondary-text">
                正在加载历史分析上下文；现在可直接发送追问。
              </p>
            )}
          </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
