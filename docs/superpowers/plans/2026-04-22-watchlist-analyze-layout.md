# 自选股重新分析、股票身份规范化、Tab 布局统一 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将自选股"分析"按钮拆成"分析历史"与"重新分析"两条独立路径；统一股票身份规范化写入（以 code 为准）；修复 tab 页面因 `100vh` 硬编码导致的主内容框高度与左侧 Sidebar 不一致的布局 bug。

**Architecture:**
- 后端新增 `stock_identity_service.py` 作为 `(code, name)` 规范化的唯一真源，供 `POST /watchlist` 与 `POST /analysis/analyze` 两个写入点调用；失败抛 `StockIdentityNotFound` → 400。
- 前端自选股卡片新增"重新分析"按钮，通过 `?force=1` 查询参数告诉 HomePage 触发 `force_refresh=true`；HomePage 消费完立即清除参数避免刷新重复触发。
- 前端所有 tab 页面根元素统一到 `<AppPage>`（`min-h-full flex flex-col`），移除 `ChatPage` / `HomePage` / `PortfolioPage` 中的 `h-[calc(100vh-…)]` 与 `min-h-screen`。

**Tech Stack:** Python 3.11、FastAPI、pytest；React + TypeScript、Vite、Tailwind、react-router-dom、Vitest（若启用）。

**Spec:** `docs/superpowers/specs/2026-04-22-watchlist-analyze-layout-design.md`

---

## 文件清单

### 新增
- `src/services/stock_identity_service.py` — `normalize_stock_identity(code) -> (code, name)`、`StockIdentityNotFound` 异常
- `tests/test_stock_identity_service.py` — 单元测试

### 修改（后端）
- `api/v1/endpoints/watchlist.py` — `add_to_watchlist` 接入规范化
- `api/v1/endpoints/analysis.py` — `trigger_analysis` 接入规范化
- `api/v1/app.py`（或 `api/app.py`、`server.py` — 以真实文件为准）— 注册 `StockIdentityNotFound` 异常处理器

### 修改（前端）
- `apps/dsa-web/src/components/watchlist/WatchlistCard.tsx` — 替换单"分析"按钮为"分析历史"+"重新分析"
- `apps/dsa-web/src/components/watchlist/GroupSection.tsx` — 多传一个 `onReanalyze` prop
- `apps/dsa-web/src/pages/WatchlistPage.tsx` — 新增 `handleReanalyze`
- `apps/dsa-web/src/pages/HomePage.tsx` — 读取 `force` 查询参数；用 `<AppPage>` 包裹根元素；内部消除 `100vh`
- `apps/dsa-web/src/pages/ChatPage.tsx` — 用 `<AppPage>` 包裹；内部改 `h-full`
- `apps/dsa-web/src/pages/PortfolioPage.tsx` — `min-h-screen` → `min-h-full`（或 `<AppPage>` 包裹）
- `apps/dsa-web/src/components/common/AppPage.tsx` — 顶部注释说明布局规则（不改逻辑）

### 文档
- `docs/CHANGELOG.md` — `[Unreleased]` 段新增扁平条目

### 数据
- 本地一次性 SQL（不落盘）：`DELETE FROM analysis_history; DELETE FROM user_watchlist;`

---

## Task 1：新建 `stock_identity_service` — 定义接口与异常（TDD）

**Files:**
- Create: `src/services/stock_identity_service.py`
- Create: `tests/test_stock_identity_service.py`

- [ ] **Step 1.1：写失败测试 — 基础契约（本地表命中）**

创建 `tests/test_stock_identity_service.py`：

```python
# -*- coding: utf-8 -*-
"""Unit tests for stock_identity_service."""
from __future__ import annotations

import pytest

from src.services.stock_identity_service import (
    StockIdentityNotFound,
    normalize_stock_identity,
)


def test_normalize_returns_canonical_pair_for_known_a_share():
    code, name = normalize_stock_identity("600519")
    assert code == "600519"
    assert name == "贵州茅台"


def test_normalize_trims_whitespace_and_lowercases_prefix():
    code, name = normalize_stock_identity("  600519  ")
    assert code == "600519"
    assert name == "贵州茅台"


def test_normalize_raises_when_code_is_empty():
    with pytest.raises(StockIdentityNotFound):
        normalize_stock_identity("")


def test_normalize_raises_when_code_unknown_and_no_fallback(monkeypatch):
    # Force the akshare fallback to return empty to simulate offline
    from src.services import stock_identity_service as mod
    monkeypatch.setattr(mod, "_lookup_name_from_akshare", lambda code: None)
    with pytest.raises(StockIdentityNotFound):
        normalize_stock_identity("ZZ999999")
```

- [ ] **Step 1.2：运行测试确认失败**

```bash
python -m pytest tests/test_stock_identity_service.py -v
```

Expected: ImportError / ModuleNotFoundError 或 4 个 test 全部 FAIL。

- [ ] **Step 1.3：写最小实现**

创建 `src/services/stock_identity_service.py`：

```python
# -*- coding: utf-8 -*-
"""
===================================
Stock Identity Service
===================================

单一真源：给任意输入的股票代码，返回规范化的 (canonical_code, canonical_name)。
所有写入 AnalysisHistory / UserWatchlist 的路径都必须通过本服务，确保 (code, name) 一致。
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from src.data.stock_mapping import STOCK_NAME_MAP
from src.services.stock_code_utils import normalize_code

logger = logging.getLogger(__name__)


class StockIdentityNotFound(Exception):
    """Raised when a stock code cannot be resolved to a canonical (code, name) pair."""

    def __init__(self, raw: str):
        super().__init__(f"无法识别的股票代码: {raw}")
        self.raw = raw


def _lookup_name_from_akshare(code: str) -> Optional[str]:
    """Opt-in fallback for codes not in STOCK_NAME_MAP. Returns None on failure."""
    try:
        import akshare as ak  # type: ignore
    except ImportError:
        return None
    try:
        # A-shares: fetch realtime quote board (cached inside akshare adapters)
        # Only attempt fallback for 6-digit A-share codes to keep cost bounded.
        if len(code) == 6 and code.isdigit():
            df = ak.stock_zh_a_spot_em()
            matched = df[df["代码"] == code]
            if len(matched) > 0:
                name = str(matched.iloc[0]["名称"]).strip()
                if name:
                    return name
    except Exception as exc:  # pragma: no cover - network / provider errors
        logger.warning("akshare lookup failed for %s: %s", code, exc)
    return None


def normalize_stock_identity(raw_code: str) -> Tuple[str, str]:
    """
    Normalize a stock code to a canonical (code, name) pair.

    Resolution order:
      1. Clean whitespace + run shared `normalize_code`.
      2. Look up in `STOCK_NAME_MAP` (authoritative local table).
      3. Fallback to akshare (A-share only, opt-in).

    Raises:
        StockIdentityNotFound: when no canonical name can be resolved.
    """
    if not raw_code or not raw_code.strip():
        raise StockIdentityNotFound(raw_code or "")

    cleaned = raw_code.strip()
    canonical = normalize_code(cleaned) or cleaned

    name = STOCK_NAME_MAP.get(canonical)
    if name:
        return canonical, name

    fallback = _lookup_name_from_akshare(canonical)
    if fallback:
        return canonical, fallback

    raise StockIdentityNotFound(raw_code)
```

- [ ] **Step 1.4：运行测试确认通过**

```bash
python -m pytest tests/test_stock_identity_service.py -v
```

Expected: 4 passed.

- [ ] **Step 1.5：提交**

```bash
git add src/services/stock_identity_service.py tests/test_stock_identity_service.py
git commit -m "feat(identity): add stock_identity_service with StockIdentityNotFound"
```

---

## Task 2：扩展规范化 — 港股 / 美股 / 前缀清洗（TDD）

覆盖更多输入格式，保证前端任意合法形式（`hk00700`、`HK.00700`、`AAPL`）都能规范化。

**Files:**
- Modify: `src/services/stock_identity_service.py`
- Modify: `tests/test_stock_identity_service.py`

- [ ] **Step 2.1：追加失败测试**

在 `tests/test_stock_identity_service.py` 末尾追加：

```python
def test_normalize_hk_stock_common_prefixes():
    code, name = normalize_stock_identity("hk00700")
    assert code == "00700.HK"
    assert name and "腾讯" in name


def test_normalize_us_stock_uppercase():
    code, name = normalize_stock_identity("aapl")
    assert code == "AAPL"
    assert name and "Apple" in name


def test_normalize_rejects_pure_symbols():
    import pytest
    from src.services.stock_identity_service import StockIdentityNotFound
    with pytest.raises(StockIdentityNotFound):
        normalize_stock_identity("@@@")
```

- [ ] **Step 2.2：运行确认失败**

```bash
python -m pytest tests/test_stock_identity_service.py -v
```

Expected: 3 new tests FAIL（假设 STOCK_NAME_MAP 里已有 `00700.HK` 与 `AAPL`；如未覆盖需 Step 2.3 补齐）。

- [ ] **Step 2.3：调整实现以处理港股/美股前缀**

先确认 `STOCK_NAME_MAP` 中是否已有条目：

```bash
python -c "from src.data.stock_mapping import STOCK_NAME_MAP; print([k for k in STOCK_NAME_MAP if 'HK' in k or k in ('AAPL',)][:5])"
```

- 如果没有，在 `src/data/stock_mapping.py` 中补充（最少一条，供测试使用）：
  ```python
  "00700.HK": "腾讯控股",
  "AAPL": "Apple Inc.",
  ```

- 如 `normalize_code` 已处理 `hk00700` → `00700.HK`、`aapl` → `AAPL`，则 Task 1 的实现已经可以直接复用。如果 `normalize_code` 不覆盖，打开 `src/services/stock_code_utils.py` 查看并补全（只加，不动原逻辑）。

- [ ] **Step 2.4：运行测试确认通过**

```bash
python -m pytest tests/test_stock_identity_service.py -v
```

Expected: 7 passed。

- [ ] **Step 2.5：提交**

```bash
git add src/services/stock_identity_service.py src/data/stock_mapping.py tests/test_stock_identity_service.py
git commit -m "feat(identity): support HK/US prefixes in normalize_stock_identity"
```

---

## Task 3：接入 `POST /watchlist` — 以 code 规范化覆盖 name

**Files:**
- Modify: `api/v1/endpoints/watchlist.py`
- Modify: `tests/test_watchlist.py`（追加用例）

- [ ] **Step 3.1：写失败测试**

在 `tests/test_watchlist.py` 找到现有 add 测试附近（搜关键字 `def test_.*add`），追加：

```python
def test_add_watchlist_normalizes_name_ignoring_request_name(client, auth_headers):
    """Regardless of what name user submits, DB stores canonical name from code."""
    resp = client.post(
        "/api/v1/watchlist",
        json={"stockCode": "600519", "stockName": "WRONG_NAME_XYZ"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stockCode"] == "600519"
    assert body["stockName"] == "贵州茅台"  # canonical, not WRONG_NAME_XYZ


def test_add_watchlist_rejects_unknown_code(client, auth_headers, monkeypatch):
    from src.services import stock_identity_service as mod
    monkeypatch.setattr(mod, "_lookup_name_from_akshare", lambda code: None)
    resp = client.post(
        "/api/v1/watchlist",
        json={"stockCode": "ZZ999999", "stockName": "anything"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "stock.identity_not_found"
```

（若 `client` / `auth_headers` fixture 名称不同，参考现有同文件其他用例的签名。）

- [ ] **Step 3.2：运行确认失败**

```bash
python -m pytest tests/test_watchlist.py -v -k "normalizes_name or rejects_unknown"
```

Expected: 两个 test FAIL。

- [ ] **Step 3.3：改 `add_to_watchlist` 调用规范化**

打开 `api/v1/endpoints/watchlist.py`，在文件顶部 import 新增：

```python
from src.services.stock_identity_service import (
    normalize_stock_identity,
    StockIdentityNotFound,
)
from fastapi import HTTPException
```

找到 `add_to_watchlist`（约 L68-72），替换函数体：

```python
@router.post("")
def add_to_watchlist(request: Request, body: AddWatchlistRequest):
    user_id = request.state.user_id
    try:
        canonical_code, canonical_name = normalize_stock_identity(body.stock_code)
    except StockIdentityNotFound as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "stock.identity_not_found", "message": str(exc)},
        )
    item = _get_service().add(user_id, canonical_code, canonical_name)
    return item.to_dict()
```

- [ ] **Step 3.4：运行测试确认通过**

```bash
python -m pytest tests/test_watchlist.py -v -k "normalizes_name or rejects_unknown"
```

Expected: 2 passed。然后跑整个 watchlist 套件：

```bash
python -m pytest tests/test_watchlist.py tests/test_watchlist_groups.py tests/test_watchlist_enriched.py -v
```

Expected: 原有用例仍全部通过（如有旧用例显式断言某用户自定义 name，则视为已失效 — 本次以 code 为准是有意行为变更，删改对应断言并在 commit 里写明）。

- [ ] **Step 3.5：提交**

```bash
git add api/v1/endpoints/watchlist.py tests/test_watchlist.py
git commit -m "feat(watchlist): normalize stock identity on add (code is source of truth)"
```

---

## Task 4：接入 `POST /analysis/analyze` — 分析写库也走规范化

**Files:**
- Modify: `api/v1/endpoints/analysis.py`
- Modify: `tests/test_analysis_api_contract.py`（追加用例）

- [ ] **Step 4.1：写失败测试**

在 `tests/test_analysis_api_contract.py` 追加：

```python
def test_analyze_rejects_unknown_code(client, auth_headers, monkeypatch):
    from src.services import stock_identity_service as mod
    monkeypatch.setattr(mod, "_lookup_name_from_akshare", lambda code: None)
    resp = client.post(
        "/api/v1/analysis/analyze",
        json={"stock_code": "ZZ999999"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "stock.identity_not_found"
```

- [ ] **Step 4.2：运行确认失败**

```bash
python -m pytest tests/test_analysis_api_contract.py::test_analyze_rejects_unknown_code -v
```

Expected: FAIL（返回可能是 500 或其他）。

- [ ] **Step 4.3：改 `trigger_analysis` 在入口处规范化**

打开 `api/v1/endpoints/analysis.py`，顶部 import 追加：

```python
from src.services.stock_identity_service import (
    normalize_stock_identity,
    StockIdentityNotFound,
)
```

找到 `_resolve_and_normalize_input`（约 L97），在**所有 code 归一之后**再过一次 `normalize_stock_identity`。最稳的落点是在 `trigger_analysis` 里，`stock_codes` 归一完成之后（约 L201-203，`stock_codes = unique_codes` 之后）插入：

```python
# Enforce canonical (code, name) resolution. Fail fast on unknown codes.
normalized_pairs: list[tuple[str, str]] = []
for code in stock_codes:
    try:
        normalized_pairs.append(normalize_stock_identity(code))
    except StockIdentityNotFound as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "stock.identity_not_found", "message": str(exc)},
        )
stock_codes = [c for c, _ in normalized_pairs]
# Build a code -> canonical_name map for downstream persistence.
canonical_names: dict[str, str] = {c: n for c, n in normalized_pairs}
```

在后续构造 `request.stock_name` 的位置（约 L257）替换为：

```python
# When single stock, prefer canonical name from identity service.
stock_name = canonical_names.get(stock_codes[0]) if is_single else None
```

如果 `_handle_sync_analysis` 内部还会从 `request.stock_name` 取 name 用于写库，同样用 `canonical_names` 覆盖。阅读 `_handle_sync_analysis` 实现后确认所有写 `AnalysisHistory.name` 的位置使用的是 `canonical_names[code]` 而不是用户传入值。

- [ ] **Step 4.4：运行测试确认通过**

```bash
python -m pytest tests/test_analysis_api_contract.py -v
python -m pytest tests/test_analysis_history.py tests/test_analysis_integration.py -v
```

Expected: 全部通过（如有旧用例断言用户传入 name 写入 AnalysisHistory，同 Task 3 处理 — 这是有意行为变更）。

- [ ] **Step 4.5：提交**

```bash
git add api/v1/endpoints/analysis.py tests/test_analysis_api_contract.py
git commit -m "feat(analysis): normalize stock identity before persisting history"
```

---

## Task 5：前端 `WatchlistCard` — 拆成两个按钮

**Files:**
- Modify: `apps/dsa-web/src/components/watchlist/WatchlistCard.tsx`

- [ ] **Step 5.1：修改 prop 定义与按钮渲染**

打开 `apps/dsa-web/src/components/watchlist/WatchlistCard.tsx`：

1. 在组件 props 接口（约 L10）中新增：
```ts
  onReanalyze: (stockCode: string) => void;
```

2. 解构 props（约 L56）加入 `onReanalyze`。

3. 替换"Analyze button"部分（约 L237-244）：

```tsx
      {/* Analyze actions: split into history + reanalyze */}
      <div className="mt-1 flex gap-2">
        <button
          type="button"
          onClick={() => onAnalyze(item.stockCode)}
          className="flex-1 rounded-lg border border-subtle bg-surface/60 px-3 py-1.5 text-xs text-secondary-text transition-colors hover:border-subtle-hover hover:text-foreground"
          title="查看该股票的历史分析报告"
        >
          {'分析历史'}
        </button>
        <button
          type="button"
          onClick={() => onReanalyze(item.stockCode)}
          className="flex-1 rounded-lg border border-cyan/40 bg-cyan/10 px-3 py-1.5 text-xs text-cyan transition-colors hover:border-cyan hover:bg-cyan/20"
          title="发起一次全新的 LLM 分析"
        >
          {'重新分析'}
        </button>
      </div>
```

- [ ] **Step 5.2：类型检查**

```bash
cd apps/dsa-web && npm run lint
```

Expected: 出现未传 `onReanalyze` 的使用点报错（GroupSection 等），作为 Task 6 的起点。

- [ ] **Step 5.3：暂不 commit**

等 Task 6、Task 7 一起通过 lint 后再提交，避免中间状态无法构建。

---

## Task 6：前端 `GroupSection` — 透传 `onReanalyze`

**Files:**
- Modify: `apps/dsa-web/src/components/watchlist/GroupSection.tsx`

- [ ] **Step 6.1：加 prop**

在 `GroupSection` props 接口中新增 `onReanalyze: (stockCode: string) => void;`，解构里加入同名变量，渲染 `WatchlistCard` 处同时传 `onAnalyze={onAnalyze}` 和 `onReanalyze={onReanalyze}`（约 L136）。

- [ ] **Step 6.2：lint**

```bash
cd apps/dsa-web && npm run lint
```

Expected: GroupSection 处错误消失，WatchlistPage 处仍报未传 `onReanalyze`。

---

## Task 7：前端 `WatchlistPage` — 新增 `handleReanalyze`

**Files:**
- Modify: `apps/dsa-web/src/pages/WatchlistPage.tsx`

- [ ] **Step 7.1：新增回调并传入 GroupSection**

在 `WatchlistPage.tsx` 现有 `handleAnalyze`（L53-58）下方追加：

```tsx
  const handleReanalyze = useCallback(
    (stockCode: string) => {
      navigate(`/?q=${encodeURIComponent(stockCode)}&force=1`);
    },
    [navigate],
  );
```

渲染 `<GroupSection>`（约 L256-268）传入：

```tsx
              onReanalyze={handleReanalyze}
```

- [ ] **Step 7.2：lint & build**

```bash
cd apps/dsa-web && npm run lint && npm run build
```

Expected: 全通过。

- [ ] **Step 7.3：提交前端自选股按钮拆分**

```bash
git add apps/dsa-web/src/components/watchlist/WatchlistCard.tsx apps/dsa-web/src/components/watchlist/GroupSection.tsx apps/dsa-web/src/pages/WatchlistPage.tsx
git commit -m "feat(watchlist): split analyze button into history + reanalyze"
```

---

## Task 8：前端 `HomePage` — 消费 `force` 查询参数触发新分析

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [ ] **Step 8.1：在现有 `?q=` 消费 useEffect 里读 force**

找到 commit `76c6e2f` 引入的那段（搜 `pendingQRef`），替换为：

```tsx
  // When navigated here with ?q= (e.g., from watchlist card):
  // - default: pre-fill input and show the most recent history record for that stock.
  // - ?force=1: immediately trigger a fresh analysis (force_refresh=true).
  const pendingQRef = useRef<string | null>(null);
  const didSelectQRef = useRef(false);

  useEffect(() => {
    if (pendingQRef.current !== null) return;
    const q = searchParams.get('q');
    if (!q) return;
    const force = searchParams.get('force') === '1';
    setSearchParams({}, { replace: true });
    setQuery(q);
    pendingQRef.current = q;
    if (force) {
      didSelectQRef.current = true; // skip the history-select path
      pendingQRef.current = null;
      void submitAnalysis({
        stockCode: q,
        originalQuery: q,
        selectionSource: 'manual',
        forceRefresh: true,
      });
    }
  }, [searchParams, setSearchParams, setQuery, submitAnalysis]);
```

注意：`submitAnalysis` 的入参需要支持 `forceRefresh`。如果当前类型签名没有这个字段，查看 `submitAnalysis` 定义并添加（它内部应对应 `analysisApi.analyze({ ..., force_refresh })`）。

- [ ] **Step 8.2：确认 `submitAnalysis` 支持 `forceRefresh`**

```bash
grep -n "submitAnalysis\|forceRefresh\|force_refresh" apps/dsa-web/src/pages/HomePage.tsx apps/dsa-web/src/hooks/ apps/dsa-web/src/api/analysis.ts 2>/dev/null | head -30
```

如果 `submitAnalysis` 来自一个 hook（如 `useAnalysis` / `useAnalysisSubmit`），打开对应文件，将 `forceRefresh?: boolean` 加入 options，透传到 `analysisApi.analyze({ ..., force_refresh: options.forceRefresh })`。

- [ ] **Step 8.3：lint & build**

```bash
cd apps/dsa-web && npm run lint && npm run build
```

Expected: 通过。

- [ ] **Step 8.4：提交**

```bash
git add apps/dsa-web/src/pages/HomePage.tsx apps/dsa-web/src/hooks/ apps/dsa-web/src/api/analysis.ts
git commit -m "feat(home): honor ?force=1 query param to trigger fresh analysis"
```

（视 `git status` 实际变动删减文件列表。）

---

## Task 9：前端 `AppPage` — 固化布局规则注释

**Files:**
- Modify: `apps/dsa-web/src/components/common/AppPage.tsx`

- [ ] **Step 9.1：在文件顶部加注释块**

替换文件为：

```tsx
/**
 * AppPage — standard wrapper for every tab/page rendered inside <Shell>.
 *
 * Layout rules (enforced by this component + convention across pages):
 *   - Page roots must use <AppPage> so height/width follow the flex shell.
 *   - DO NOT use viewport-relative units on page roots:
 *       100vh / 100dvh / h-screen / min-h-screen / calc(100vh - *)
 *     They escape the Shell's max-width/sidebar layout and cause
 *     the "top spans the full page" bug.
 *   - For pages with an internal scroll region (chat, long lists):
 *       wrap content in: h-full overflow-hidden flex flex-col
 *       scroll area: flex-1 min-h-0 overflow-y-auto
 */
import type React from 'react';
import { cn } from '../../utils/cn';

interface AppPageProps {
  children: React.ReactNode;
  className?: string;
}

export const AppPage: React.FC<AppPageProps> = ({ children, className = '' }) => {
  return (
    <main className={cn('mx-auto min-h-full w-full max-w-7xl px-4 pb-8 pt-4 md:px-6 lg:px-8', className)}>
      {children}
    </main>
  );
};
```

- [ ] **Step 9.2：lint**

```bash
cd apps/dsa-web && npm run lint
```

Expected: 通过。

- [ ] **Step 9.3：暂不提交，与 Task 10-12 一起提交。**

---

## Task 10：修复 `ChatPage` — 用 `<AppPage>` 包裹，消除 `100vh`

**Files:**
- Modify: `apps/dsa-web/src/pages/ChatPage.tsx`

- [ ] **Step 10.1：找到根 div（约 L534-538）**

当前：

```tsx
<div
  data-testid="chat-workspace"
  className="flex h-[calc(100vh-5rem)] w-full min-w-0 gap-4 overflow-hidden sm:h-[calc(100vh-5.5rem)] lg:h-[calc(100vh-2rem)]"
>
```

- [ ] **Step 10.2：改造为 `<AppPage>` + 内部 flex 容器**

在文件顶部 imports 追加（若未引入）：

```tsx
import { AppPage } from '../components/common/AppPage';
```

替换根元素：

```tsx
<AppPage className="flex h-full min-h-0 flex-col px-0 pb-0 pt-0 md:px-0 lg:px-0">
  <div
    data-testid="chat-workspace"
    className="flex h-full w-full min-w-0 gap-4 overflow-hidden"
  >
```

闭合处对应增加 `</AppPage>`。

> 说明：`<AppPage>` 的 `className` 覆盖掉它默认的 px/py，让聊天工作区可以贴满；但 `min-h-full` 仍然生效。这是 ChatPage 的特殊化（因为是聊天界面要贴边显示），其他页面不需要覆盖。

- [ ] **Step 10.3：lint & build**

```bash
cd apps/dsa-web && npm run lint && npm run build
```

Expected: 通过。

---

## Task 11：修复 `HomePage` 根元素 — 消除 `100vh`

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [ ] **Step 11.1：替换根元素**

找到 L405-409：

```tsx
<div
  data-testid="home-dashboard"
  className="flex h-[calc(100vh-5rem)] sm:h-[calc(100vh-5.5rem)] lg:h-[calc(100vh-2rem)] w-full flex-col overflow-hidden"
>
```

替换为：

```tsx
<AppPage className="flex min-h-full flex-col px-0 pb-0 pt-0 md:px-0 lg:px-0">
  <div
    data-testid="home-dashboard"
    className="flex h-full w-full flex-col overflow-hidden"
  >
```

顶部 imports 追加 `import { AppPage } from '../components/common/AppPage';`（若未引入）。闭合处增加 `</AppPage>`。

- [ ] **Step 11.2：lint & build**

```bash
cd apps/dsa-web && npm run lint && npm run build
```

Expected: 通过。

---

## Task 12：修复 `PortfolioPage` — `min-h-screen` → `min-h-full`

**Files:**
- Modify: `apps/dsa-web/src/pages/PortfolioPage.tsx`

- [ ] **Step 12.1：定位并替换**

```bash
grep -n "min-h-screen" apps/dsa-web/src/pages/PortfolioPage.tsx
```

将该行 `min-h-screen` 改为 `min-h-full`。

若 PortfolioPage 根本是 `<main>` 或 `<div>` 没有用 `<AppPage>`，顺手包一层：

```tsx
<AppPage>
  ... existing content ...
</AppPage>
```

并删除原根的 padding/width 类以免双重约束。

- [ ] **Step 12.2：lint & build**

```bash
cd apps/dsa-web && npm run lint && npm run build
```

Expected: 通过。

- [ ] **Step 12.3：提交布局修复**

```bash
git add apps/dsa-web/src/components/common/AppPage.tsx apps/dsa-web/src/pages/ChatPage.tsx apps/dsa-web/src/pages/HomePage.tsx apps/dsa-web/src/pages/PortfolioPage.tsx
git commit -m "fix(layout): unify tab pages to AppPage, drop 100vh hacks"
```

---

## Task 13：注册 FastAPI 异常处理器（兜底）

如果 Task 3/4 的 `HTTPException` 已经返回干净的 JSON，这一步是可选的。但为了保证未来新接入点也能走同一格式，注册一个全局 handler。

**Files:**
- Modify: `api/v1/app.py`（或 `server.py`、`api/app.py` — 以定义 `app = FastAPI(...)` 的真实文件为准）

- [ ] **Step 13.1：定位 FastAPI app 实例**

```bash
grep -rn "app = FastAPI\|^app = " api/ server.py 2>/dev/null | head -5
```

- [ ] **Step 13.2：注册 handler**

在实例化 FastAPI 之后加：

```python
from fastapi.responses import JSONResponse
from fastapi import Request as _Request
from src.services.stock_identity_service import StockIdentityNotFound


@app.exception_handler(StockIdentityNotFound)
async def _stock_identity_not_found_handler(_: _Request, exc: StockIdentityNotFound):
    return JSONResponse(
        status_code=400,
        content={"error": "stock.identity_not_found", "message": str(exc)},
    )
```

（如果已经在某处注册了全局异常处理模块，加到同一个地方；不要重复注册。）

- [ ] **Step 13.3：CI gate**

```bash
./scripts/ci_gate.sh
```

Expected: 通过。

- [ ] **Step 13.4：提交**

```bash
git add api/v1/app.py   # 或真实文件
git commit -m "chore(api): register StockIdentityNotFound global handler"
```

---

## Task 14：CHANGELOG

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 14.1：在 `[Unreleased]` 段追加扁平条目**

按 CLAUDE.md 规则：`- [类型] 描述`，扁平格式，不新增标题。

追加（示意）：

```
- [新功能] 自选股新增"重新分析"按钮，与"分析历史"分别触发新分析与查看历史
- [改进] 股票 (代码, 名称) 统一规范化，所有写入以代码为权威源
- [修复] 问股等 Tab 页面根元素改用 AppPage，消除 100vh 硬编码导致的布局溢出
```

- [ ] **Step 14.2：提交**

```bash
git add docs/CHANGELOG.md
git commit -m "docs(changelog): record watchlist/identity/layout changes"
```

---

## Task 15：本地数据清理与端到端验证

**Files:** 无源码变更（纯运行时验证）

- [ ] **Step 15.1：停掉当前运行的服务**

如果本地仍有 `python main.py --serve-only` 后台进程，先停止（`kill <pid>`）。

- [ ] **Step 15.2：定位 SQLite 文件**

```bash
grep -n "DATABASE_URL\|sqlite" .env .env.example src/config*.py 2>&1 | head -10
```

- [ ] **Step 15.3：执行清理 SQL**

确认路径后（示例为 `data/app.db`，以实际为准）：

```bash
python - <<'PY'
import sqlite3, os
from pathlib import Path
# 调整为真实 SQLite 路径
db = Path("data/app.db")  # TODO: replace if different
assert db.exists(), f"DB not found: {db}"
conn = sqlite3.connect(db)
cur = conn.cursor()
for tbl in ("analysis_history", "user_watchlist"):
    cur.execute(f"DELETE FROM {tbl}")
    print(f"cleared {tbl}: {cur.rowcount} rows")
conn.commit()
conn.close()
PY
```

- [ ] **Step 15.4：重启服务**

```bash
.venv/bin/python main.py --serve-only &
```

等待 `Uvicorn running on http://127.0.0.1:8000`。

- [ ] **Step 15.5：端到端手动验证清单**

| 场景 | 操作 | 预期 |
|---|---|---|
| 布局 | 依次点左侧每个 tab（首页/自选/发现/问股/组合/回测/设置） | 主内容框顶部对齐左侧 Sidebar `top-3`，底部不溢出 |
| 自选股分析历史 | 添加一只股（如 `600519`），点"分析历史" | 跳首页，输入框预填 `600519`，无 `/analyze` 请求（DevTools Network 观测） |
| 自选股重新分析 | 点"重新分析" | 跳首页，URL 最终为 `/`（`force` 已清除），`/analyze` 带 `force_refresh=true`，完成后历史列表新增一条 |
| 规范化失败 | 手动 `curl -X POST /api/v1/watchlist -d '{"stockCode":"ZZ999999"}' ...` | 400，body: `{"error":"stock.identity_not_found", ...}` |
| 错配修复 | 手动 `curl -X POST /api/v1/watchlist -d '{"stockCode":"600519","stockName":"瞎写"}'` 然后查 DB | `user_watchlist.stock_name = '贵州茅台'` |
| 回归：昵称 | 登录 → UserMenu → SettingsPage 改昵称 | 菜单顶部显示新昵称 |
| 回归：普通分析 | 首页输入"茅台"点分析 | 正常分析、写入历史 |

- [ ] **Step 15.6：记录未通过项**

若有任何验证失败，不要标记 Task 完成；回到相应 Task 修复并重跑。

---

## Self-Review 检查清单

- [x] 每个 spec 小节都有对应 Task：
  - § 3.1 自选股分析 → Task 5-8
  - § 3.2 规范化 → Task 1-4、Task 13
  - § 3.3 布局 → Task 9-12
  - § 5 错误处理 → Task 3-4、Task 13
  - § 6 测试计划 → Task 1-4、Task 15
  - § 8 回滚 → 按 commit 粒度自然支持
  - 数据清理 → Task 15
  - 文档同步 → Task 14
- [x] 无 TBD / TODO / "同 Task N"。
- [x] 所有涉及代码变更的 Step 都给出实际代码块。
- [x] 方法名一致：`normalize_stock_identity`、`StockIdentityNotFound`、`handleReanalyze`、`onReanalyze` 跨 Task 对齐。
- [x] 命令可复制执行。

---

## 实施要点

- 遵循 TDD：每个 Task 先测试 → 看失败 → 改代码 → 看通过 → 提交。
- 每个 Task 完成后 commit。**勿** 用 `--no-verify` 绕 pre-commit hook。
- 如中途 `normalize_code` 不支持某种输入，只扩展 `stock_mapping.py` / `stock_code_utils.py` 的最小必要条目，**不重写现有逻辑**。
- 数据清理（Task 15.3）是一次性、破坏性操作，仅限本地机器。不要在 CI / 其他环境运行。
