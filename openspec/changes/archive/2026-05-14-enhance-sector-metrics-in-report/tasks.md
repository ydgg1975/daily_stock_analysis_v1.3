## 1. 数据层增强

- [x] 1.1 在 `data_provider/base.py` 中新增 `get_sector_realtime_quote()` 方法签名
- [x] 1.2 在 `data_provider/efinance_fetcher.py` 中实现板块实时行情查询（复用 `get_realtime_quotes(['行业板块'])` 数据）
- [x] 1.3 在 `data_provider/akshare_fetcher.py` 中实现板块实时行情查询（复用 `stock_board_industry_name_em()` 数据）
- [x] 1.4 在 `data_provider/tushare_fetcher.py` 中实现板块实时行情查询（复用对应接口）
- [x] 1.5 在 `data_provider/base.py` 中添加板块名称模糊匹配逻辑

## 2. 分析层集成

- [x] 2.1 在 `src/analyzer.py` 中添加获取板块实时行情的调用逻辑
- [x] 2.2 在 `src/analyzer.py` 中将行情数据注入到 `belong_boards` 列表
- [x] 2.3 添加降级逻辑：行情获取失败时保持原有 `belong_boards` 数据结构

## 3. 报告渲染更新

- [x] 3.1 在 `src/notification.py` 中更新 Markdown 报告的关联板块渲染逻辑
- [x] 3.2 改为表格形式展示：板块名称 | 涨跌幅 | 最新价
- [x] 3.3 添加涨跌幅颜色标记
- [x] 3.4 处理降级场景
- [x] 3.5 检查其他报告格式

## 4. 测试与验证

- [x] 4.1 本地运行测试，验证关联板块数据正确展示
- [x] 4.2 测试数据源失败时的降级逻辑
- [x] 4.3 运行 `./scripts/ci_gate.sh` 验证后端完整性