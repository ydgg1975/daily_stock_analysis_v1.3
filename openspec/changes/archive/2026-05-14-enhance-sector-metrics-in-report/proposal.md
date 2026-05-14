## Why

邮件报告中的"关联板块"目前只展示板块名称（如"白酒概念"、"新能源车"），缺少实际市场指标。用户无法直接判断该板块当前是涨是跌、涨幅多少，削弱了报告的参考价值。

## What Changes

- **增强关联板块数据**：在现有板块名称基础上，增加实时行情指标（最新价、涨跌幅、成交额）
- **扩展数据获取层**：在 `data_provider/` 中新增板块实时行情查询能力，支持多数据源 fallback
- **更新报告渲染**：在邮件报告的"关联板块"区域，改为展示板块名称+涨跌幅的表格形式

## Capabilities

### New Capabilities

- `sector-realtime-quote`: 新增板块实时行情数据获取能力，包括最新价、涨跌幅、成交额等核心指标

### Modified Capabilities

- `email-report-details`: 现有邮件报告能力需扩展关联板块的展示格式

## Impact

- **data_provider/base.py**：新增 `get_sector_realtime_quote()` 方法，支持按板块名称查询实时行情
- **data_provider/akshare_fetcher.py** / **tushare_fetcher.py** / **efinance_fetcher.py**：新增板块行情接口适配
- **src/analyzer.py**：在 `belong_boards` 数据中补充实时行情指标
- **src/notification.py**：更新关联板块渲染逻辑，改为表格展示（含价格、涨跌幅）