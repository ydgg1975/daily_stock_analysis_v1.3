# Backtest System

## 服务归属

- 标准历史分析评估接口由 `src/services/backtest_service.py` 负责：
  - `POST /api/v1/backtest/run`
  - `POST /api/v1/backtest/prepare-samples`
  - `GET /api/v1/backtest/results`
  - `GET /api/v1/backtest/sample-status`
  - `GET /api/v1/backtest/runs`
  - `GET /api/v1/backtest/performance`
  - `GET /api/v1/backtest/performance/{code}`
  - `POST /api/v1/backtest/samples/clear`
  - `POST /api/v1/backtest/results/clear`
- 规则回测接口由 `src/services/rule_backtest_service.py` 负责：
  - `POST /api/v1/backtest/rule/parse`
  - `POST /api/v1/backtest/rule/run`
  - `GET /api/v1/backtest/rule/runs`
  - `GET /api/v1/backtest/rule/runs/{run_id}`
  - `GET /api/v1/backtest/rule/runs/{run_id}/status`
  - `POST /api/v1/backtest/rule/runs/{run_id}/cancel`

## 异步 / 后台任务

- `POST /api/v1/backtest/rule/run` 默认异步提交，立即返回 `queued / parsing / running / summarizing / completed / failed / cancelled` 之一。
- 若传入 `wait_for_completion=true`，接口会同步执行并直接返回完整结果。
- `GET /api/v1/backtest/rule/runs/{run_id}/status` 提供轻量状态轮询，不必每次拉取完整详情。
- `POST /api/v1/backtest/rule/runs/{run_id}/cancel` 提供 best-effort cancel：对尚未完成的任务会标记为 `cancelled`；若任务已结束，则返回当前最终状态而不覆盖结果。
- `GET /api/v1/backtest/rule/runs/{run_id}` 继续作为完整详情接口，包含 `execution_trace`、交易明细和审计数据。

## 本地 US parquet 优先级

- 美股日线优先读取 `LOCAL_US_PARQUET_DIR`。
- 若未设置 `LOCAL_US_PARQUET_DIR`，兼容回退到 `US_STOCK_PARQUET_DIR`。
- 若本地 parquet 命中，`resolved_source` 会显示为 `LocalParquet`，不会触发在线抓取。
- 若本地 parquet 缺失或损坏，当前 backtest 流程会沿用既有数据抓取 fallback，并在响应里暴露 `requested_mode / resolved_source / fallback_used`。

## 本地运行 API

```bash
.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
```

可选环境变量：

```bash
export LOCAL_US_PARQUET_DIR=/path/to/local/us/parquet
# 仅兼容旧配置时再使用
export US_STOCK_PARQUET_DIR=/path/to/local/us/parquet
```

## 冒烟脚本

- 新的根目录脚本会自动：
  - 启动临时 uvicorn
  - 关闭管理认证
  - 创建临时数据库
  - 准备本地 `LOCAL_US_PARQUET_DIR` fixture
  - 运行断言并自动清理临时文件

- 标准 backtest API 冒烟：

```bash
python3 test_backtest_basic.py
```

- 规则 backtest API 冒烟：

```bash
python3 test_backtest_rule.py
```

- 合并运行：

```bash
python3 test_backtest_run.py --mode both
```

## 已知假设与限制

- 生产环境真实读取本地 parquet 仍依赖 `pyarrow` 或 `fastparquet`；若环境缺少 parquet engine，仓库内 smoke 脚本会注入测试用 shim 来验证 `LOCAL_US_PARQUET_DIR` 优先路径与异步接口行为。
- 规则回测的同步执行依赖本地数据库中已有行情，或依赖既有数据源 fallback 成功。
- `execution_trace` 的详情、CSV、JSON 导出以持久化 `audit_rows` 为真源；历史旧记录缺少该字段时，会在读取时回补并标记 `trace_rebuilt`。
