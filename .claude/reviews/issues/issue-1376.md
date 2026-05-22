# Issue #1376

## Analysis Baseline

- Issue: 新版首页报告缺少“板块联动”展示。
- Confirmed by issue discussion: 用户已用 Docker 对比 `v3.15.0` 与 `v3.16.0`，相同股票在 `v3.16.0` 后稳定缺失该区块。
- Root cause: 部分新版快照把 `fundamental_context` / `realtime_quote` 存在 `context_snapshot` 顶层，但历史详情和任务状态接口只读取 `enhanced_context.fundamental_context` / `realtime_quote_raw`，导致 `belong_boards` / `sector_rankings` 被漏掉，前端按空数据 fail-open 隐藏了“板块联动”。

## Fix Implementation

**Date**: 2026-05-22

### Changes Made

- `src/utils/data_processing.py`: 为 `fundamental_context` 与实时行情字段补充顶层快照兼容提取。
- `api/v1/endpoints/history.py`: 历史详情接口复用统一实时字段提取，恢复 Agent/兼容快照中的价格与板块联动数据。
- `api/v1/endpoints/analysis.py`: 任务状态数据库回退路径补齐 `details`，保持与历史详情接口一致。
- `tests/test_analysis_history.py`: 新增历史详情兼容 Agent 快照结构的回归测试。
- `tests/test_analysis_api_contract.py`: 新增分析状态接口数据库回退路径兼容 Agent 快照结构的回归测试。
- `docs/CHANGELOG.md`: 补充 `[Unreleased]` 修复条目。

### Validation

- 已执行：`uv run --with pytest --with-requirements requirements.txt pytest tests/test_analysis_history.py tests/test_analysis_api_contract.py`
- 已执行：`python3 -m py_compile src/utils/data_processing.py api/v1/endpoints/history.py api/v1/endpoints/analysis.py`
- 未完成：`./scripts/ci_gate.sh`（当前环境缺少 `python` 命令，脚本在 syntax 阶段即退出；已用 `python3 -m py_compile` 与目标回归测试补足本次改动面验证）

### Risks

- 兼容提取逻辑扩大了 `context_snapshot` 支持范围；若未来引入新的同名顶层字段且语义不同，需要同步收敛提取优先级。

### Rollback

- 回滚本次分支中 `src/utils/data_processing.py`、`api/v1/endpoints/history.py`、`api/v1/endpoints/analysis.py`、新增测试与 changelog 条目即可恢复旧行为。
