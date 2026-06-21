# PR #1734 Review 反馈修复说明

## Scope of Change（实际）

本次修改实际包含 11 个文件（含数据库候选查询层）：

- `api/v1/endpoints/backtest.py`
- `api/v1/schemas/backtest.py`
- `apps/dsa-web/src/api/backtest.ts`
- `apps/dsa-web/src/index.css`
- `apps/dsa-web/src/pages/BacktestPage.tsx`
- `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx`
- `apps/dsa-web/src/types/backtest.ts`
- `docs/CHANGELOG.md`
- `src/repositories/backtest_repo.py`
- `src/services/backtest_service.py`
- `tests/test_backtest_service.py`

## Web 页面可视证据

已在 Web 侧改动 `BacktestPage` 后端测结果展示样式与诊断 message 呈现行为。若无法在仓库内提交截图，请在 PR 描述/评论补充运行后页面截图链接作为最终证据；可复核替代证据可见：

- `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx`（回测页面诊断信息渲染与结果态断言）
- `apps/dsa-web/src/index.css` / `apps/dsa-web/src/pages/BacktestPage.tsx`（结果区域与诊断 message UI 样式与文案）
- `tests/test_backtest_service.py`（后端空候选与行情不足的诊断返回覆盖）
