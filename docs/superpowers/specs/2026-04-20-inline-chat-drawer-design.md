# 报告内联 Chat 抽屉（Inline Chat Drawer）Design

> Date: 2026-04-20
> Status: Draft
> Scope: 把 HomePage 的 "追问 AI" 按钮从跳转 /chat 改成打开右侧内联 Chat 抽屉，预注入当前报告上下文，降低分析→追问的决策成本

## 1. Background

### User Value

现在用户在 HomePage 看到一份分析报告后，想问"为什么止损定这里？"或"和我持仓有没有冲突？"时，只能点 "追问 AI" 跳转到 `/chat` 页面 —— 即便 context 已经通过 query params 传递，页面切换本身就会打断阅读节奏，用户需要重新寻找自己刚才看的哪一条。

**本次改动把追问能力搬到报告旁边**，用户点击 "追问 AI" 打开右侧抽屉，主页报告仍可见，上下文自动注入。

### Current State

- `HomePage.tsx:510` 按钮 `handleAskFollowUp` 执行 `navigate('/chat?stock=…&name=…&recordId=…')`
- `ChatPage.tsx:216-250` 通过 query params 还原 context，调用 `resolveChatFollowUpContext` 获取历史报告详情注入 `followUpContextRef`
- 后端 `api/v1/endpoints/agent.py:43-57` `ChatRequest.context: Optional[Dict[str, Any]]` 已支持任意上下文
- `useAgentChatStore` 是全局 Zustand store，已管理 session/messages/streaming；可在多组件间复用

## 2. Design Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 抽屉位置 | 右侧独立 Drawer，不嵌入 ReportMarkdown | 保持报告与对话解耦；markdown 抽屉聚焦完整文本 |
| 与 ReportMarkdown 关系 | 互相独立，zIndex 错开（Chat=110, ReportMarkdown=100） | 允许用户同时开启，但优先层级为 Chat |
| 抽屉宽度 | `max-w-xl` (36rem) | 对话场景比报告窄；配合主页 3 列布局不至于全屏覆盖 |
| 后端改动 | 无 | context schema 已支持，复用现有 `chatStream` API |
| 会话策略 | 每份报告首次打开新建隔离 session（`session_id = report-{recordId}-{uuid}` 存内存），再次打开延续 | 避免跨报告串话；关闭抽屉不销毁，重开可继续 |
| Chat 组件 | 新建轻量 `ChatPanel`，不复用整个 `ChatPage` | ChatPage 带 sidebar/skill 选择，不适合窄抽屉 |
| 上下文注入 | 沿用 `buildChatFollowUpContext` 产出的 `ChatFollowUpContext` | 避免重复实现，后端已认这个 shape |
| 预置追问 | 3 个硬编码 prompt chips | MVP 固定；后续可按报告内容动态生成 |
| 配额/付费 | **不在 MVP 内** | 免费 vs 付费限制是独立工作流 |

## 3. Component Structure

```
apps/dsa-web/src/
  components/chat/                       ← 新目录
    ChatPanel.tsx                        ← 新：轻量对话面板（消息列表 + 输入框 + preset chips）
    ChatDrawer.tsx                       ← 新：包一层 Drawer，带 header
  pages/HomePage.tsx                     ← 改：handleAskFollowUp 改为打开 drawer
  stores/agentChatStore.ts               ← 不改
  utils/chatFollowUp.ts                  ← 不改，直接复用 buildChatFollowUpContext
api/                                     ← 不改
```

### ChatPanel 责任

- props: `context?: ChatFollowUpContext`, `sessionIdOverride?: string`, `presetPrompts?: string[]`, `onSendStart?: () => void`
- 内部:
  - 挂载时若 `sessionIdOverride` 与 store 当前 `sessionId` 不同，调用 `switchSession(sessionIdOverride)`
  - context 通过一个本地 ref 注入到下一次 `startStream` payload，与 ChatPage 的模式一致
  - 渲染消息列表（复用 ChatPage 的 markdown 渲染与 copy/thinking 交互 —— 抽成 `ChatMessageBubble` 小组件）
  - 空态显示 3 个 `presetPrompts` 作为可点击的 chips
  - 输入框固定在底部

### ChatDrawer 责任

- props: `isOpen: boolean`, `onClose: () => void`, `report: AnalysisReport | null`
- 内部：
  - Drawer 标题显示 `{stockName}({stockCode}) · 追问 AI`
  - 从 `report` 构建 context，派生 stable `sessionId = report-${recordId}`
  - 透传 context + sessionId + presetPrompts 给 `ChatPanel`
  - `presetPrompts`（MVP 固定）：
    - "解释这个止损点为什么定在这里"
    - "结合我的持仓和自选股，这只有没有冲突或互补"
    - "如果我已经在更高价位买了，现在该怎么办"

## 4. Flow

1. User 点击 HomePage 报告区的 "追问 AI" 按钮
2. HomePage 设置 `chatDrawerOpen=true`，保留 `selectedReport`
3. `ChatDrawer` 挂载 → 从 `selectedReport.meta.id` 派生 `sessionId = report-${id}` → 调用 `switchSession`（store 自动拉历史消息）
4. 若 session 没有历史消息（首次），空态显示 preset chips
5. User 点击 chip 或输入 → `ChatPanel` 把 `context = buildChatFollowUpContext(…, selectedReport)` 注入 payload → `startStream` SSE 流式返回
6. User 关闭 drawer → `chatDrawerOpen=false`，store 不清空（保留历史供下次打开）

## 5. Non-Goals (MVP)

- 付费 quota / 免费次数限制（独立工作流）
- 动态 preset prompts（根据报告内容生成）
- 拖拽调整抽屉宽度
- 在抽屉内同时显示报告全文（需要 split pane，v2 再说）
- 跨报告合并记忆
- 持久化 `session_id → recordId` 绑定到 DB（内存映射即可，刷新后丢失新消息是可接受的）

## 6. Testing

- 单元测试（vitest）：
  - `ChatPanel` 在空态渲染 presets
  - `ChatPanel` 点击 preset 触发 `startStream` 且 payload 含正确 context
  - `ChatDrawer` 根据 `selectedReport.meta.id` 派生 sessionId
- 回归：现有 `ChatPage` 行为不变（不改 store 逻辑）
- 手测：desktop 宽屏 + 移动窄屏开合行为、ESC 关闭、同时打开 ReportMarkdown 抽屉时层级正确

## 7. Rollout

- 不需要 feature flag：改动仅前端，未改 API，未改数据库
- 用户感知：`追问 AI` 按钮行为改变（不再跳转到 /chat）
- 回滚：`handleAskFollowUp` 恢复为 navigate 即可

## 8. Open Questions

- **延续性**：抽屉关闭后消息是否持久？MVP 方案是 store 保留（刷新页面丢失）。若日后需要持久，把 `session_id = report-${recordId}` 作为服务端 key 写入 DB 即可复用现有 session storage。
- **免费配额**：暂不做。未来可在 `startStream` 发起前加一个本地限流（如每报告最多 5 轮），或后端按 plan 判断。

---

Status: Approved for implementation (MVP).
