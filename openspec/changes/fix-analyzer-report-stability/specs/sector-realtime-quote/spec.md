## ADDED Requirements

### Requirement: Sector real-time quote can be queried
系统 SHALL 能够根据板块名称查询实时行情数据，包括最新价、涨跌幅、成交额。

#### Scenario: Query sector quote with exact name match
- **WHEN** 调用 `get_sector_realtime_quote(board_names: List[str])` 并传入板块名称列表
- **THEN** 返回每个板块的实时行情，包含 `name`（板块名称）、`price`（最新价）、`change_pct`（涨跌幅）、`volume`（成交额）字段

#### Scenario: Handle sector name mismatch
- **WHEN** 查询的板块名称与数据源返回的名称不完全匹配（如 "白酒概念" vs "白酒"）
- **THEN** 使用模糊匹配策略，返回最接近的板块行情

#### Scenario: Handle API failure gracefully
- **WHEN** 数据源调用超时或返回错误
- **THEN** 返回空列表或 None，不抛出异常，调用方执行降级逻辑

### Requirement: Sector quote data enrichment happens in pipeline phase
板块实时行情数据 SHALL 在 pipeline 数据获取阶段完成注入，而不是在 analyzer/report 生成阶段。

#### Scenario: Sector quotes enriched during data fetch
- **WHEN** Pipeline 执行数据获取阶段
- **THEN** 在 `fundamental_context` 中已包含 enriched belong_boards（含 price, change_pct）

#### Scenario: Analyzer consumes pre-enriched sector data
- **WHEN** Analyzer 执行 `stabilize_decision_with_structure()`
- **THEN** 不再触发新的外部数据源请求，直接使用 pipeline 传入的 context 数据

#### Scenario: Fail-open when sector quote unavailable
- **WHEN** Pipeline 阶段无法获取板块行情
- **THEN** `belong_boards` 仅包含 `name` 字段，不阻塞后续流程

## REMOVED Requirements

### Requirement: Belong boards display without metrics
**Reason**: 本需求已被增强，关联板块将展示实时行情指标（已在增强 PR 中实现）

**Note**: 删除此需求因为已提供带指标的展示。但在指标缺失时应优雅降级（见下方 ADDED）。