## Context

当前邮件推送使用 `generate_dashboard_report()` 方法生成报告，但该方法仅使用了 `dashboard` 中的部分字段（intelligence、core_conclusion、data_perspective、battle_plan）。

缺少的数据：
1. **financial_report**: 结构化财报摘要（来自 fundamental_context）
2. **dividend_metrics**: 分红指标（TTM 股息率等）
3. **belong_boards**: 关联板块列表
4. **sector_rankings**: 板块涨跌榜（领涨/领跌板块）

这些数据在 API 端已通过 `extract_fundamental_detail_fields()` 和 `extract_board_detail_fields()` 提取并返回给 Web/桌面端。

## Goals / Non-Goals

**Goals:**
- 在邮件报告模板中添加财务报告数据模块
- 在邮件报告模板中添加分红指标数据模块
- 在邮件报告模板中添加关联板块信息
- 在邮件报告模板中添加板块涨跌榜
- 确保字段不存在时的兼容处理

**Non-Goals:**
- 不修改数据库结构
- 不修改 API 响应格式
- 不增加新的配置项

## Decisions

1. **数据来源**: 从 `result.dashboard.get('intelligence', {})` 中提取已有数据，而非新增数据采集
   - intelligence 中已包含 financial_report、dividend_metrics
   - belong_boards 和 sector_rankings 需要额外获取

2. **展示位置**: 在现有报告结构中添加新的 Section
   - 财务/分红数据：放在"基本面分析"之后
   - 板块信息：单独新建 Section

3. **兼容性处理**: 使用 `getattr()` 和默认值确保字段缺失时不报错

## Risks / Trade-offs

- **数据缺失风险**: 部分股票可能没有财务数据或板块信息
  -  mitigation: 仅在数据存在时渲染对应模块
  
- **邮件长度风险**: 添加更多内容可能导致邮件过长
  - mitigation: 每个模块添加数据时控制展示行数，重要字段优先

- **实现复杂度**: 需要在 notification.py 中添加数据提取逻辑
  - mitigation: 复用已有的数据处理函数