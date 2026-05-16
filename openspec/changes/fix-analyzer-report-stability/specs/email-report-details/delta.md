## ADDED Requirements

### Requirement: Email report includes change_pct for sector data
关联板块 SHALL 在报告中显示涨跌幅 (change_pct) 指标。

#### Scenario: Belong boards with change_pct displayed
- **WHEN** belong_boards 包含 change_pct 数据
- **THEN** 报告中显示板块名称和涨跌幅，格式如 "🟢 +2.35%" 或 "🔴 -1.20%"

#### Scenario: Missing change_pct handled gracefully
- **WHEN** belong_boards 存在但 change_pct 为 None/缺失
- **THEN** 报告不显示 NaN，改为仅展示板块名称列表（无表格），或在该行显示 "-"

### Requirement: Sector price displayed when available
关联板块 SHALL 在报告中显示最新价 (price) 指标。

#### Scenario: Belong boards with price displayed
- **WHEN** belong_boards 包含 price 数据
- **THEN** 报告中显示价格列，格式如 "¥128.50"

#### Scenario: Missing price handled gracefully
- **WHEN** belong_boards 存在但 price 为 None/缺失
- **THEN** 报告不显示 NaN，改为仅展示板块名称和涨跌幅，不显示价格列

### Requirement: Dividend TTM values prioritized from adapter
分红 TTM 指标 SHALL 优先使用 adapter 预计算值，只有在该值缺失时才使用 fallback 计算。

#### Scenario: Dividend TTM from adapter used
- **WHEN** dividend_metrics 包含 ttm_dividend_yield_pct 或 ttm_cash_dividend_per_share
- **THEN** 报告直接使用这些预计算值，不重新计算

#### Scenario: Dividend fallback with time filter
- **WHEN** dividend_metrics 不包含 ttm_* 字段，但包含 events
- **THEN** fallback 计算仅使用最近 365 天内的 events
- **AND** cash_dividend_per_share 为 None 时跳过该 event，不抛 TypeError

## MODIFIED Requirements

### Requirement: Missing data handled gracefully
**Original**: 当字段不存在时，邮件报告中不显示对应模块，不报错误

**Updated**: 当字段不存在时，邮件报告中不显示对应模块，不报错误；
当字段存在但具体值为 None/缺失时，报告显示 "-" 或仅展示可用字段，或显示板块名称列表（无表格），但绝不显示 "NaN" 字符串