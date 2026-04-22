# 自选股"重新分析"、股票身份规范化与 Tab 页布局统一 设计文档

- 日期：2026-04-22
- 作者：rex0104 + Claude
- 状态：待评审
- 关联范围：`apps/dsa-web/`、`api/v1/endpoints/`、`src/services/`、`src/storage.py`

## 1. 背景

三项并行需求：

1. 当前 `WatchlistPage` 的"分析"按钮在 commit `76c6e2f` 后只展示已有分析历史，不再触发新的 LLM 分析。用户需要在自选股列表上同时支持"看历史"与"重新跑一次"两种动作。
2. 股票名（`stock_name`）与代码（`stock_code`）由三处独立写入，存在错配风险：用户手动输入、`resolve_name_to_code()` 自动补全、`AnalysisHistory` 分析入库。需要统一规范化，以 `code` 为权威源。
3. 左侧 Sidebar 高度贴齐页面顶部 `top-3`，但 `ChatPage`（问股）等页面根元素使用 `h-[calc(100vh-…)]`，基于视口高度而非父容器高度，导致主内容"顶部铺满页面"，视觉上和左侧框高不一致。所有 tab 页面需要统一到 `<AppPage>` 模式。

昵称功能已端到端实现（`User.nickname` + `PUT /api/v1/auth/nickname` + `ChangeNicknameCard` + `UserMenu` 展示），本次不动。

## 2. 目标与非目标

### 目标

- 自选股行上提供两个清晰分开的动作入口："分析历史"（查看）、"重新分析"（触发新分析）。
- 所有写入股票 `(code, name)` 的路径都必须通过统一的规范化函数，以 `code` 为准推导 `name`。规范化失败直接返回 400 错误。
- 所有 tab 页面根元素统一使用 `<AppPage>` 或等价的 `min-h-full / h-full` 语义，消除所有 `100vh` / `100dvh` / `calc(100vh-…)` 的硬编码。

### 非目标

- 不改 `/api/v1/analysis/analyze` 的入参契约（`force_refresh` 已存在）。
- 不新增昵称相关代码或 UI。
- 不新增或修改认证流程。
- 不改后端自动 tag / 发布流程。
- 不引入新的数据迁移脚本（历史数据清理通过一次性 SQL 在本地执行，不落盘）。

## 3. 改动分解

### 3.1 自选股"分析历史" / "重新分析"

**前端**（`apps/dsa-web/src/pages/WatchlistPage.tsx`）

- 将当前单一"分析"按钮替换为两个按钮或一组连体按钮：
  - `[分析历史]`：`navigate(\`/?q=\${stockCode}\`)`
  - `[重新分析]`：`navigate(\`/?q=\${stockCode}&force=1\`)`
- 按钮顺序：`分析历史` 在前，`重新分析` 在后；桌面端并列，移动端保持可点击区域不小于 44px。
- 图标建议：`分析历史` 用 `History` 图标；`重新分析` 用 `RefreshCw` 图标（lucide-react 或项目现用图标库，以实际现有依赖为准）。
- `WatchlistPage.tsx` 中 `handleAnalyze` 保持，新增 `handleReanalyze` 回调，两者分别触发对应导航。

**前端**（`apps/dsa-web/src/pages/HomePage.tsx`）

- `useSearchParams` 读取已有 `q` 之外，新增读取 `force`：
  - `force=1` 时：以 `force_refresh: true` 调用 `analysisApi.analyze`
  - 否则：保留当前默认行为（命中历史则展示，不触发新分析）
- 分析完成后，新记录由现有 `HistoryList` 订阅机制自动刷新（无需改造 List）。
- 处理完 `force` 后应从 URL 中移除参数（`navigate(pathname, { replace: true })`），避免刷新页面反复强制触发。

**后端**：不修改。`POST /api/v1/analysis/analyze` 已支持 `force_refresh`。

### 3.2 股票身份规范化（以 code 为准）

**新增服务**：`src/services/stock_identity_service.py`

```python
class StockIdentityNotFound(Exception):
    """code 无法规范化出合法 (code, name) 时抛出"""

def normalize_stock_identity(code: str) -> tuple[str, str]:
    """
    输入任意用户提交的股票代码，返回规范化的 (canonical_code, canonical_name)。
    - 清洗大小写、前后空白、前缀（hk/HK/SH/SZ 等）
    - 优先查本地映射表（STOCK_NAME_MAP 反向索引）
    - Fallback 到已有数据源（AkShare 等，与 resolve_name_to_code 共享实现）
    - 失败时抛出 StockIdentityNotFound，携带原始输入
    """
```

**调用点改造**（三处写入路径全部接入）：

1. `api/v1/endpoints/watchlist.py`：`add_to_watchlist` 中，忽略请求传入的 `stock_name`，统一用 `normalize_stock_identity(code)` 的结果覆盖。
2. `api/v1/endpoints/analysis.py`：`analyze` 中生成 `AnalysisHistory` 前，将传入 `code` 规范化，用返回的 `(code, name)` 写库；同时供 LLM prompt 使用的 `stock_name` 也以此为准。
3. 如果存在后台调度/批量分析入口（如 `src/core/` 里编排），同样接入。

**异常处理**：

- 新增 API 错误码 `stock.identity_not_found`，HTTP 状态 400：
  ```json
  { "error": "stock.identity_not_found", "message": "无法识别的股票代码: XXX" }
  ```
- FastAPI 层统一用异常处理中间件捕获 `StockIdentityNotFound`。
- 前端在自选股添加、分析触发两个场景展示 toast 错误文案。

**历史数据清理**（本地一次性执行，不落盘 migration）：

```sql
DELETE FROM analysis_history;
DELETE FROM user_watchlist;
```

在实现完成并验证后执行。文档里保留操作说明，但不纳入自动化。

### 3.3 Tab 页布局统一（消除 `100vh` hack）

**规则**（沉淀到 `apps/dsa-web/src/components/layout/AppPage.tsx` 顶部注释）：

- 所有 tab 级别页面的根元素**必须**是 `<AppPage>`，或遵循等价的 `min-h-full flex flex-col` 语义。
- **禁止**在页面根元素使用 `100vh`、`100dvh`、`calc(100vh-…)`、`min-h-screen`、`h-screen` 等视口相关单位。
- 需要"视口撑满 + 内部独立滚动"的页面（如 Chat）：
  - 外层（`<AppPage>` 子元素）用 `h-full overflow-hidden flex flex-col`
  - 滚动区用 `flex-1 min-h-0 overflow-y-auto`

**改动清单**：

| 文件 | 当前问题 | 修改 |
|---|---|---|
| `apps/dsa-web/src/pages/ChatPage.tsx` L535-538 | 根 div 用 `h-[calc(100vh-5rem)] sm:h-[calc(100vh-5.5rem)] lg:h-[calc(100vh-2rem)]` | 外层改 `<AppPage>`；原根 div 改 `h-full w-full min-w-0 flex gap-4 overflow-hidden` |
| `apps/dsa-web/src/pages/HomePage.tsx` L406-409 | 相同 hack | 外层改 `<AppPage>`；保留内部 `flex flex-col overflow-hidden` |
| `apps/dsa-web/src/pages/PortfolioPage.tsx` L756 | `min-h-screen` | 改 `min-h-full` 或使用 `<AppPage>` |
| 已用 `<AppPage>` 的页面（WatchlistPage、Discover、Backtest、Settings） | ✓ | 不动，仅核对没有内部 `100vh` |

**`<AppPage>` 自身**：如当前实现已满足 `min-h-full flex flex-col`，不改代码，仅增加 header 注释说明规则。

## 4. 数据流 / 时序

### 自选股 → 重新分析

```
User clicks [重新分析] on WatchlistPage row
  → navigate(`/?q=600519&force=1`)
  → HomePage mounts, reads searchParams: q=600519, force=1
  → call analysisApi.analyze({ stock_code: '600519', force_refresh: true })
  → loading UI
  → navigate('/', { replace: true })  // 清除 force，防止刷新重复触发
  → onSuccess: new AnalysisHistory record persisted
  → HistoryList re-fetches and renders new record at top
```

### 规范化写入

```
Frontend submits { code: 'hk700', name: '中国腾讯' }
  → watchlist endpoint calls normalize_stock_identity('hk700')
    → cleans → '00700' (项目当前规范化后的形式：HK 代码不含后缀)
    → looks up canonical_name = '腾讯控股'
  → DB stores (user_id, '00700', '腾讯控股')
  → AnalysisHistory on analyze 同样使用上述 (code, name)
```

## 5. 错误处理

| 场景 | 行为 |
|---|---|
| `normalize_stock_identity` 失败（代码非法 / 查无此股） | 抛 `StockIdentityNotFound`，HTTP 400，前端 toast |
| `analyze` 时已有同日分析但传 `force_refresh=true` | 正常生成新记录（`created_at` 精确到秒，不会主键冲突；若未来发现冲突需在 `AnalysisHistory` 表主键策略上单独评审） |
| HomePage 未携带 `q` 或 `q` 为空 | 不触发任何分析，保持当前首页默认视图 |
| 用户在移动端宽屏切换 | `<AppPage>` 规则 + flex 自适应，不依赖视口单位 |

## 6. 测试计划

### 后端

- 新增 `tests/services/test_stock_identity_service.py`：
  - 本地映射命中（A 股、港股、美股至少各一例）
  - AkShare fallback 命中（用 monkeypatch 模拟）
  - 非法输入抛 `StockIdentityNotFound`
  - 大小写/前缀清洗
- `tests/api/test_watchlist.py`、`tests/api/test_analysis.py`：
  - 提交故意错配的 `(code, wrong_name)` → DB 里落的是 canonical name
  - 提交非法 code → 400 响应结构正确
- 运行：`./scripts/ci_gate.sh`；涉及网络数据源的走 `pytest -m "not network"` 默认不跑，本地可手动 `-m network` 验证。

### 前端

- 手动验证：
  - 自选股点"分析历史" → HomePage 显示已有；不调用 `/analyze`（DevTools Network 观测）
  - 自选股点"重新分析" → HomePage 调用 `/analyze` 且 `force_refresh=true`；完成后历史列表新增一条；URL 回退到 `/`
  - 错误 code 添加 → toast 错误
  - 依次点每个 tab，目视中间主内容框顶部/底部与左侧 Sidebar 对齐
  - 问股页消息多/少时输入框吸底，消息区独立滚动
- `cd apps/dsa-web && npm run lint && npm run build`

### 回归

- 登录、注册、昵称修改、修改密码、自选股分组等无影响
- 首页正常触发历史分析（无 `force` 参数时）仍然命中缓存行为

## 7. 不纳入范围（显式）

- 不做任何 UI 视觉重设计，仅修复布局 bug 与加按钮。
- 不引入新的动画 / 交互。
- 不对数据库表结构做迁移。
- 不对 `resolve_name_to_code` 的实现做大改；`stock_identity_service` 复用其核心能力。
- 不处理"用户希望自定义股票昵称"这类需求（本次以 code 为权威，显式放弃用户自定义 name）。

## 8. 回滚方式

- 所有改动限定在前端页面、一个新后端 service、三个 endpoint 调用点、两处 React 页面根元素。按 commit 维度回滚即可。
- 历史数据清理是破坏性的但仅本地执行，不影响线上；如需恢复，从本地 SQLite 备份拷回。
- 规范化服务如出现大面积误判，短期 fallback：在调用点加环境变量开关 `STOCK_IDENTITY_STRICT=0`，不启用拒绝写入（本次默认启用）。
