## ADDED Requirements

### Requirement: Sector real-time quote can be queried
系统 SHALL 能够根据板块名称查询实时行情数据，包括最新价、涨跌幅、成交额。

#### Scenario: Query sector quote with exact name match
- **WHEN** 调用 `get_sector_realtime_quote(board_names: List[str])` 并传入板块名称列表
- **THEN** 返回每个板块的实时行情，包含 `name`（板块名称）、`price`（最新价）、`change_pct`（涨跌幅）、`volume`（成交额）字段

#### Scenario: Handle sector name mismatch
- **WHEN** 查询的板块名称与数据源返回的名称不完全匹配（如 "白酒概念" vs "白酒")
- **THEN** 使用模糊匹配策略，返回最接近的板块行情

#### Scenario: Handle API failure gracefully
- **WHEN** 数据源调用超时或返回错误
- **THEN** 返回空列表或 None，不抛出异常，调用方执行降级逻辑

### Requirement: Sector quote data is enriched in analysis results
分析阶段 SHALL 将板块实时行情数据注入到 `intelligence['belong_boards']` 中。

#### Scenario: Belong boards enriched with quote data
- **WHEN** 股票有关联板块且板块行情数据获取成功
- **THEN** `belong_boards` 中的每个板块包含 `price`、`change_pct` 字段

#### Scenario: Belong boards fall back when quote unavailable
- **WHEN** 板块行情获取失败（如网络超时、数据源不可用）
- **THEN** `belong_boards` 保持仅包含 `name` 字段，不报错误

## REMOVED Requirements

### Requirement: Belong boards display without metrics
**Reason**: 本需求已被增强，关联板块将展示实时行情指标
**Migration**: 使用新的增强展示格式