# 市场诊断系统 - 合并报告使用指南

## 概述

市场诊断系统现在支持**两种模式**：

1. **独立模式**：仅生成诊断报告
2. **合并模式**（新增）：将诊断报告与原有大盘复盘合并

## 使用方式

### 方式1：独立诊断报告

```python
from src.market_analyzer import MarketAnalyzer

# 创建分析器，启用诊断模式
analyzer = MarketAnalyzer(enable_diagnostic=True)

# 运行分析，不合并（仅返回诊断报告）
diagnostic_report, markdown = analyzer.run_full_analysis(merge_with_original=False)

print(markdown)
```

### 方式2：合并报告（推荐）

```python
from src.market_analyzer import MarketAnalyzer

# 创建分析器，启用诊断模式
analyzer = MarketAnalyzer(enable_diagnostic=True)

# 运行分析，合并原有复盘和诊断报告（默认行为）
diagnostic_report, merged_markdown = analyzer.run_full_analysis(merge_with_original=True)

# 或者简写（默认就是True）
diagnostic_report, merged_markdown = analyzer.run_full_analysis()

print(merged_markdown)
```

### 方式3：传统复盘（不启用诊断）

```python
from src.market_analyzer import MarketAnalyzer

# 不启用诊断模式
analyzer = MarketAnalyzer(enable_diagnostic=False)

# 运行传统复盘
_, traditional_review = analyzer.run_full_analysis()

print(traditional_review)
```

## 合并报告结构

合并后的报告包含以下部分：

```markdown
# 2026-04-26 A股市场复盘

## 🎯 市场诊断总结
- 一句话总结
- 综合状态、趋势、广度、情绪、风险等级
- 置信度

---

## 📰 市场新闻与热点
（从原有复盘中提取）
- 政策动态
- 行业热点
- 重要事件

---

## 📊 全维度量化诊断
（完整的诊断系统报告）
- 状态仪表盘
- 指数与价格结构
- 市场广度
- 情绪与赚钱效应
- 风格轮动
- 板块主线诊断
- 资金流向
- 风险警报
- 策略映射建议
- 证据与置信度
```

## 数据源问题与解决方案

### 当前问题

从运行日志看到以下问题：

1. **网络代理问题**
   - 东方财富接口被代理阻断
   - 错误：`ProxyError('Unable to connect to proxy')`

2. **部分指数数据缺失**
   - 深证成指（sz399001）
   - 创业板指（sz399006）
   - 沪深300（sh000300）
   - 微盘股指数（sh000015）

3. **数据源限流**
   - Yahoo Finance: `YFRateLimitError`
   - 新浪财经：部分接口返回空数据

### 解决方案

#### 方案1：配置Tushare（推荐）

Tushare是最稳定的数据源，但需要Token：

```bash
# 1. 注册Tushare账号
# 访问 https://tushare.pro/register

# 2. 获取Token
# 登录后在个人中心获取Token

# 3. 配置环境变量
export TUSHARE_TOKEN="your_token_here"

# 或在代码中配置
# 编辑 .env 文件
TUSHARE_TOKEN=your_token_here
```

#### 方案2：安装额外数据源

```bash
# 安装efinance（东方财富）
pip install efinance

# 安装pytdx（通达信）
pip install pytdx

# 安装baostock
pip install baostock
```

#### 方案3：禁用代理

如果你的网络环境有代理问题：

```bash
# 临时禁用代理
unset http_proxy
unset https_proxy
unset HTTP_PROXY
unset HTTPS_PROXY

# 然后运行程序
python3 src/market_diagnostic/examples/run_diagnostic.py
```

#### 方案4：使用优雅降级（已实现）

系统已经实现了优雅降级机制：

- 当某个指数数据获取失败时，会标记为缺失数据
- 继续处理其他可用数据
- 在报告中明确标注缺失的数据项
- 根据数据完整性调整置信度

**示例**：即使只获取到5/9个指数，系统仍会生成报告，并在报告中说明：

```
**缺失数据**: 深证成指, 创业板指, 沪深300, 微盘股指数
**置信度**: 55% (因数据不完整而降低)
```

## 性能优化建议

### 1. 使用缓存

系统已实现缓存机制，相同日期的数据会被缓存：

```python
# 第一次运行：从API获取数据（较慢）
analyzer.run_full_analysis()

# 第二次运行：使用缓存（很快）
analyzer.run_full_analysis()
```

### 2. 减少API调用

如果只需要部分功能，可以修改配置：

```python
# 编辑 src/market_diagnostic/config.py
# 减少指数池
INDEX_POOL = {
    "sh000001": "上证指数",
    "sh000016": "上证50",
    "sh000300": "沪深300",
    # 注释掉不需要的指数
}
```

### 3. 异步获取（未来优化）

当前数据获取是串行的，未来可以改为并行：

```python
# 未来版本可能支持
analyzer = MarketAnalyzer(
    enable_diagnostic=True,
    parallel_fetch=True  # 并行获取数据
)
```

## 测试与验证

### 测试合并功能

```bash
cd daily_stock_analysis
python3 test_merge_simple.py
```

这会生成一个演示文件 `merged_report_demo.md`，展示合并效果。

### 测试完整流程（需要网络）

```bash
cd daily_stock_analysis

# 测试独立诊断
python3 src/market_diagnostic/examples/run_diagnostic.py --no-llm --date 2024-01-15

# 测试合并报告（需要修改示例脚本）
# 编辑 run_diagnostic.py，使用 MarketAnalyzer 而不是直接使用 engine
```

## 常见问题

### Q1: 为什么有些指数获取不到？

**A**: 可能的原因：
1. 网络代理问题
2. 数据源API限流
3. 指数代码格式不对
4. 数据源不支持该指数

**解决**：配置Tushare或安装更多数据源。

### Q2: 报告生成很慢怎么办？

**A**: 
1. 第一次运行会慢（需要获取60天历史数据）
2. 后续运行会使用缓存，速度快很多
3. 可以减少指数池和行业数量

### Q3: 如何只看诊断报告，不要原有复盘？

**A**: 
```python
analyzer.run_full_analysis(merge_with_original=False)
```

### Q4: 如何自定义合并策略？

**A**: 修改 `src/market_analyzer.py` 中的 `_merge_reports()` 方法。

## 下一步计划

1. **数据源优化**
   - 添加更多备用数据源
   - 实现智能数据源选择
   - 支持自定义数据源优先级

2. **性能优化**
   - 并行数据获取
   - 更智能的缓存策略
   - 增量更新机制

3. **报告增强**
   - 支持更多报告格式（HTML、PDF）
   - 可视化图表
   - 历史对比分析

4. **集成优化**
   - 与现有工作流更深度集成
   - 支持定时任务
   - 支持消息推送

## 总结

✅ **已实现**：
- 诊断系统与原有复盘的合并
- 优雅降级机制
- 数据缓存
- 多数据源支持

⚠️ **需要注意**：
- 首次运行需要良好的网络环境
- 建议配置Tushare Token
- 部分指数可能获取失败（会标注）

🎯 **推荐使用方式**：
```python
analyzer = MarketAnalyzer(enable_diagnostic=True)
report, markdown = analyzer.run_full_analysis()  # 默认合并模式
```

这样可以同时获得：
- 原有复盘的新闻和热点分析
- 诊断系统的量化指标和状态分类
- 完整的策略建议
