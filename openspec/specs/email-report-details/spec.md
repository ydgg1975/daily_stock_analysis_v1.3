## ADDED Requirements

### Requirement: Email report includes detailed financial and sector data
邮件报告应当包含与 Web/桌面端 API 相同的详细财务数据、分红指标、板块信息。

#### Scenario: Financial report data included in email
- **WHEN** 分析结果包含 financial_report 数据
- **THEN** 邮件报告中显示财务报告模块，包含营业收入、净利润、ROE 等指标

#### Scenario: Dividend metrics data included in email
- **WHEN** 分析结果包含 dividend_metrics 数据
- **THEN** 邮件报告中显示分红指标模块，包含 TTM 股息率、每股分红等

#### Scenario: Belong boards data included in email
- **WHEN** 分析结果包含 belong_boards 数据
- **THEN** 邮件报告中显示关联板块列表

#### Scenario: Sector rankings data included in email
- **WHEN** 分析结果包含 sector_rankings 数据
- **THEN** 邮件报告中显示板块涨跌榜（领涨/领跌板块）

#### Scenario: Email report includes change_pct for sector data
- **WHEN** belong_boards 包含 change_pct 数据
- **THEN** 报告中显示板块名称和涨跌幅，格式如 "🟢 +2.35%" 或 "🔴 -1.20%"

#### Scenario: Missing change_pct handled gracefully
- **WHEN** belong_boards 存在但 change_pct 为 None/缺失
- **THEN** 报告不显示 NaN，改为仅展示板块名称列表（无表格），或在该行显示 "-"

#### Scenario: Sector price displayed when available
- **WHEN** belong_boards 包含 price 数据
- **THEN** 报告中显示价格列，格式如 "¥128.50"

#### Scenario: Missing price handled gracefully
- **WHEN** belong_boards 存在但 price 为 None/缺失
- **THEN** 报告不显示 NaN，改为仅展示板块名称和涨跌幅，不显示价格列

#### Scenario: Dividend TTM values prioritized from adapter
- **WHEN** dividend_metrics 包含 ttm_dividend_yield_pct 或 ttm_cash_dividend_per_share
- **THEN** 报告直接使用这些预计算值，不重新计算

#### Scenario: Dividend fallback with time filter
- **WHEN** dividend_metrics 不包含 ttm_* 字段，但包含 events
- **THEN** fallback 计算仅使用最近 365 天内的 events
- **AND** cash_dividend_per_share 为 None 时跳过该 event，不抛 TypeError

#### Scenario: Missing data handled gracefully
- **WHEN** 上述任一数据字段不存在
- **THEN** 邮件报告中不显示对应模块，不报错误

#### Scenario: Email content not exceeding reasonable length
- **WHEN** 添加详细数据后
- **THEN** 邮件内容应进行合理截断，确保可读性

## MODIFIED Requirements

### Requirement: Missing data handled gracefully
**Original**: 当字段不存在时，邮件报告中不显示对应模块，不报错误

**Updated**: 当字段不存在时，邮件报告中不显示对应模块，不报错误；
当字段存在但具体值为 None/缺失时，报告显示 "-" 或仅展示可用字段，或显示板块名称列表（无表格），但绝不显示 "NaN" 字符串