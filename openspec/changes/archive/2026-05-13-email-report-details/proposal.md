## Why

邮件推送目前缺少 Web/桌面端 API 中包含的详细报告数据（如财务数据、分红指标、板块信息等），导致用户收到的邮件内容与其他端不一致。通过补齐这些数据，可以提升邮件报告的信息量和实用价值。

## What Changes

- 在 `generate_dashboard_report()` 方法中添加财务报告数据展示模块
- 添加分红指标数据到邮件报告
- 添加关联板块信息到邮件报告
- 添加板块涨跌榜数据到邮件报告
- 数据来源：AnalysisResult.dashboard.intelligence 和 context_snapshot

## Capabilities

### New Capabilities
此变更不涉及新增 spec，是对现有报告生成能力的增强补齐。

### Modified Capabilities
无。修改仅影响报告渲染实现方式，不改变功能需求。

## Impact

- 主要修改：`src/notification.py` 中的报告生成方法
- 数据来源：`result.dashboard.get('intelligence', {})` 中的 financial_report、dividend_metrics、belong_boards、sector_rankings
- 风险：需要确保字段可能不存在时的兼容性处理