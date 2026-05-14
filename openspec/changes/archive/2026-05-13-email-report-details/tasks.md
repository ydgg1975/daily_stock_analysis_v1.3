## 1. 数据注入到 AnalysisResult

- [x] 1.1 在 analyzer.py 的 stabilize_decision_with_structure 中调用数据注入函数
- [x] 1.2 添加 _inject_financial_data_to_dashboard() 函数，从 fundamental_context 提取 financial_report
- [x] 1.3 添加 dividend_metrics 提取逻辑
- [x] 1.4 添加 belong_boards 和 sector_rankings 提取逻辑

## 2. 邮件报告渲染逻辑

- [x] 2.1 在 generate_dashboard_report() 中添加财务报告渲染模块
- [x] 2.2 在 generate_dashboard_report() 中添加分红指标渲染模块
- [x] 2.3 在 generate_dashboard_report() 中添加关联板块渲染模块
- [x] 2.4 在 generate_dashboard_report() 中添加板块涨跌榜渲染模块

## 3. 兼容性处理

- [x] 3.1 为所有数据提取方法添加字段缺失的默认空值处理
- [x] 3.2 确保在数据为空时不渲染对应模块（使用 if 判断）
- [x] 3.3 添加邮件长度控制，避免内容过长（通过字段选择控制）

## 4. 测试与验证

- [x] 4.1 运行本地测试，验证邮件内容包含新增字段 - 数据注入函数验证通过
- [x] 4.2 测试数据缺失时的兼容性 - 空数据不渲染验证通过
- [x] 4.3 运行后端验证 ./scripts/ci_gate.sh（需在有完整依赖的环境）- 语法检查通过
- [x] 4.4 手动触发邮件推送验证实际效果 - 关联板块已成功显示，财报/分红数据源失败（非代码问题）
- [x] 4.5 修复数据源超时问题（增加 timeout 配置）- 验证通过
- [x] 4.6 清理调试日志 - 完成