import { create, type StoreApi, type UseBoundStore } from 'zustand';
import { agentApi, type ChatStreamRequest } from '../api/agent';
import {
  createParsedApiError,
  getParsedApiError,
  isApiRequestError,
  isParsedApiError,
  type ParsedApiError,
} from '../api/error';
import type { Message, ProgressStep, StreamMeta } from './agentChatStore';

/**
 * Per-drawer isolated chat store.
 *
 * Why separate from `useAgentChatStore`:
 *  - The global store persists its sessionId to localStorage as the /chat page default.
 *    Mutating it from a report drawer would steal the user's main /chat conversation.
 *  - The global store shares one `messages` array across callers. An inline drawer
 *    mounted while hydrating can flash stale transcripts and race the hydrate response
 *    into overwriting messages the user just sent.
 *
 * This store:
 *  - Is created per sessionId (memoized by ChatDrawer).
 *  - Never touches localStorage.
 *  - Gates send on `hydrated` so the first user message cannot race the initial
 *    `getChatSessionMessages()` fetch.
 *  - Uses a hydration token so stale fetches are dropped if the session changes.
 */

export interface ScopedChatState {
  sessionId: string;
  messages: Message[];
  loading: boolean;
  progressSteps: ProgressStep[];
  chatError: ParsedApiError | null;
  /** True once the initial history fetch has settled (success or failure). */
  hydrated: boolean;
  abortController: AbortController | null;
}

export interface ScopedChatActions {
  /** Load historical messages for this session. Safe to call more than once; only
   *  the latest invocation's response is applied. */
  hydrate: () => Promise<void>;
  startStream: (payload: ChatStreamRequest, meta?: StreamMeta) => Promise<void>;
  /** Abort any in-flight stream. Used on unmount. */
  abort: () => void;
}

export type ScopedChatStore = UseBoundStore<
  StoreApi<ScopedChatState & ScopedChatActions>
>;

/**
 * Module-level cache so reopening the same report drawer reuses its transcript
 * and so React-Compiler-friendly call sites (no useMemo needed) still get a
 * stable store instance per sessionId.
 *
 * Cache growth is bounded in practice — one entry per distinct report ever
 * opened in the session. If this becomes material we can switch to an LRU.
 */
const scopedStoreCache = new Map<string, ScopedChatStore>();

export function getScopedChatStore(sessionId: string): ScopedChatStore {
  let store = scopedStoreCache.get(sessionId);
  if (!store) {
    store = createScopedChatStore(sessionId);
    scopedStoreCache.set(sessionId, store);
  }
  return store;
}

/** Test-only: clear the module cache between tests. */
export function __resetScopedChatStoreCache() {
  scopedStoreCache.clear();
}

export function createScopedChatStore(sessionId: string): ScopedChatStore {
  let hydrationToken = 0;

  return create<ScopedChatState & ScopedChatActions>((set, get) => ({
    sessionId,
    messages: [],
    loading: false,
    progressSteps: [],
    chatError: null,
    hydrated: false,
    abortController: null,

    hydrate: async () => {
      hydrationToken += 1;
      const myToken = hydrationToken;
      try {
        const msgs = await agentApi.getChatSessionMessages(sessionId);
        if (myToken !== hydrationToken) return;
        set((s) => {
          // Never overwrite messages that arrived after hydration started.
          // (In practice the send button is gated on `hydrated`, so this is
          //  belt-and-suspenders — but keep it correct regardless.)
          if (s.messages.length > 0) {
            return { hydrated: true };
          }
          return {
            hydrated: true,
            messages: msgs.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
            })),
          };
        });
      } catch {
        if (myToken !== hydrationToken) return;
        set({ hydrated: true });
      }
    },

    abort: () => {
      const ac = get().abortController;
      ac?.abort();
      set({ abortController: null, loading: false, progressSteps: [] });
    },

    startStream: async (payload, meta) => {
      if (get().loading) return;
      if (!get().hydrated) return;

      const { abortController: prevAc } = get();
      prevAc?.abort();

      const ac = new AbortController();
      set({ abortController: ac });

      const streamSessionId = payload.session_id || get().sessionId;
      const skillName = meta?.skillName ?? '追问';

      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: payload.message,
        skill: payload.skills?.[0],
        skillName,
      };

      set((s) => ({
        messages: [...s.messages, userMessage],
        loading: true,
        progressSteps: [],
        chatError: null,
      }));

      try {
        const response = await agentApi.chatStream(
          { ...payload, session_id: streamSessionId },
          { signal: ac.signal },
        );
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        let finalContent: string | null = null;
        const currentProgressSteps: ProgressStep[] = [];

        const processLine = (line: string) => {
          if (!line.startsWith('data: ')) return;
          const event = JSON.parse(line.slice(6)) as ProgressStep;
          if (event.type === 'done') {
            const doneEvent = event as unknown as {
              success: boolean;
              content?: string;
              error?: string;
            };
            if (doneEvent.success === false) {
              const parsed = getParsedApiError(
                doneEvent.error || doneEvent.content || '大模型调用出错，请检查 API Key 配置',
              );
              throw createParsedApiError({
                title: '追问执行失败',
                message: parsed.message,
                rawMessage: parsed.rawMessage,
                status: parsed.status,
                category: parsed.category,
              });
            }
            finalContent = doneEvent.content ?? '';
            return;
          }
          if (event.type === 'error') {
            throw getParsedApiError(event.message || '分析出错');
          }
          currentProgressSteps.push(event);
          set((s) => ({ progressSteps: [...s.progressSteps, event] }));
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split('\n');
          buf = lines.pop() ?? '';
          for (const line of lines) {
            try {
              processLine(line);
            } catch (parseErr: unknown) {
              if (isParsedApiError(parseErr) || isApiRequestError(parseErr)) {
                throw parseErr;
              }
            }
          }
        }
        if (buf.trim().startsWith('data: ')) {
          try {
            processLine(buf.trim());
          } catch (parseErr: unknown) {
            if (isParsedApiError(parseErr) || isApiRequestError(parseErr)) {
              throw parseErr;
            }
          }
        }

        if (!ac.signal.aborted) {
          set((s) => ({
            messages: [
              ...s.messages,
              {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: finalContent || '（无内容）',
                skill: payload.skills?.[0],
                skillName,
                thinkingSteps: [...currentProgressSteps],
              },
            ],
          }));
        }
      } catch (error: unknown) {
        if (error instanceof Error && error.name === 'AbortError') {
          // silent abort
        } else {
          set({ chatError: getParsedApiError(error) });
        }
      } finally {
        const { abortController: currentAc } = get();
        if (currentAc === ac) {
          set({ loading: false, progressSteps: [], abortController: null });
        }
      }
    },
  }));
}
