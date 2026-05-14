## MODIFIED Requirements

### Requirement: Email report includes detailed financial and sector data
邮件报告应当包含与 Web/桌面端 API 相同的详细财务数据、分红指标、板块信息。

#### Scenario: Financial report data included in email
- **WHEN** 分析结果包含 financial_report 数据
- **THEN** 邮件报告中显示财务报告模块，包含营业收入、净利润、ROE 等指标

#### Scenario: Dividend metrics data included in email
- **WHEN** 分析结果包含 dividend_metrics 数据
- **THEN** 邮件报告中显示分红指标模块，包含 TTM 股息率、每股分红等

#### Scenario: Belong boards with metrics displayed in email
- **WHEN** 分析结果包含 belong_boards 数据且包含实时行情指标（price, change_pct）
- **THEN** 邮件报告中以表格形式显示关联板块，包含板块名称、最新价、涨跌幅

#### Scenario: Belong boards without metrics fall back to name-only display
- **WHEN** 分析结果包含 belong_boards 但不包含实时行情指标
- **THEN** 邮件报告中显示板块名称列表（降级展示）

#### Scenario: Sector rankings data included in email
- **WHEN** 分析结果包含 sector_rankings 数据
- **THEN** 邮件报告中显示板块涨跌榜（领涨/领跌板块）

#### Scenario: Missing data handled gracefully
- **WHEN** 上述任一数据字段不存在
- **THEN** 邮件报告中不显示对应模块，不报错误

#### Scenario: Email content not exceeding reasonable length
- **WHEN** 添加详细数据后
- **THEN** 邮件内容应进行合理截断，确保可读性