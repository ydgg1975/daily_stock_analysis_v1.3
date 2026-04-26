# Market Diagnostic System (大盘全维度诊断系统)

A comprehensive A-share market diagnostic engine that upgrades the existing `daily_stock_analysis` codebase from simple market recap articles to a systematic, quantitative diagnostic framework.

Every trading day after market close, the system automatically produces:
- A **Markdown report** for human analysts (with quantitative evidence)
- A **structured JSON** for strategy systems (with Regime state)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Installation](#installation)
4. [Basic Usage](#basic-usage)
5. [Integration with MarketAnalyzer](#integration-with-marketanalyzer)
6. [Configuration Guide](#configuration-guide)
7. [API Reference](#api-reference)
8. [State Classifications Reference](#state-classifications-reference)
9. [Output Format](#output-format)
10. [Error Handling and Graceful Degradation](#error-handling-and-graceful-degradation)
11. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The system follows a **5-layer architecture**:

```
DataLayer
  ├── IndexDataFetcher        → 9 core index daily series (60-day history)
  ├── BreadthDataFetcher      → Market-wide stock cross-section
  ├── SectorDataFetcher       → 31 Shenwan Level-1 industries
  ├── CapitalFlowFetcher      → North Bound Capital / margin / main force
  └── MacroDataFetcher        → Bond yields / exchange rates
        ↓
FeatureLayer
  ├── TrendFeatures           → MA alignment / MACD / RSRS / ATR
  ├── BreadthFeatures         → Above-MA20 ratio / new-high ratio / AD line
  ├── SentimentFeatures       → Limit-up rate / seal rate / sentiment score
  ├── StyleFeatures           → Large/small-cap RS / growth/value RS
  ├── SectorFeatures          → Sector strength score / persistence / crowding
  ├── CapitalFeatures         → Turnover deviation / North Bound 5-day MA
  └── RiskFeatures            → Realized volatility / drawdown / C-VIX proxy
        ↓
DiagnosticLayer
  ├── IndexDiagnostic         → Trend direction / structural divergence
  ├── BreadthDiagnostic       → Breadth health / diffusion
  ├── SentimentDiagnostic     → Sentiment temperature / money-making effect
  ├── StyleDiagnostic         → Style label / rotation signal
  ├── SectorDiagnostic        → Theme identification / sector classification
  ├── CapitalDiagnostic       → Incremental vs rotational capital
  └── RiskDiagnostic          → Risk level / risk flags
        ↓
StateLayer
  ├── TrendState              → 5 levels: 强趋势上行 → 破位下行
  ├── BreadthState            → 5 levels: 极弱 → 过热
  ├── SentimentState          → 5 levels: 冰点 → 狂热
  ├── StyleState              → 5 levels: 大盘防守 → 风格冲突
  ├── SectorState             → 5 levels: 无主线 → 退潮分化
  ├── RiskState               → 4 levels: 低风险 → 极端风险
  └── CompositeRegime         → 7 composite regimes
        ↓
ReportLayer
  ├── MarkdownRenderer        → Human-readable diagnostic report
  └── JsonExporter            → Structured output for strategy systems
```

### Module Structure

```
src/market_diagnostic/
├── __init__.py
├── engine.py                    # Main entry: MarketDiagnosticEngine
├── config.py                    # Index pool, industry codes, thresholds
├── data/
│   ├── models.py                # IndexDailyData, MarketBreadthData, etc.
│   ├── fetchers.py              # DiagnosticDataFetcher
│   └── cache.py                 # Data caching (60-day retention)
├── features/
│   ├── trend.py                 # TrendFeatures, compute_trend_features()
│   ├── breadth.py               # BreadthFeatures, compute_breadth_features()
│   ├── sentiment.py             # SentimentFeatures
│   ├── style.py                 # StyleFeatures
│   ├── sector.py                # SectorFeatureResult, compute_sector_strength_score()
│   ├── capital.py               # CapitalFeatures
│   ├── risk.py                  # RiskFeatures
│   └── valuation.py             # ValuationFeatures
├── states/
│   ├── enums.py                 # TrendState, BreadthState, etc.
│   └── classifier.py            # MarketStateClassifier, MarketStateResult
├── reports/
│   ├── schema.py                # DiagnosticReport dataclass
│   ├── markdown_renderer.py     # DiagnosticMarkdownRenderer
│   └── strategy_mapper.py       # map_regime_to_strategies()
├── examples/
│   └── run_diagnostic.py        # CLI example script
└── tests/                       # Unit, property, and integration tests
```

---

## Quick Start

```bash
# Run diagnostic for today (prints Markdown to stdout)
cd daily_stock_analysis
python src/market_diagnostic/examples/run_diagnostic.py

# Run for a specific date
python src/market_diagnostic/examples/run_diagnostic.py --date 2024-01-15

# Save both JSON and Markdown reports
python src/market_diagnostic/examples/run_diagnostic.py \
    --date 2024-01-15 \
    --output-json report.json \
    --output-md report.md

# Disable LLM narrative, enable verbose logging
python src/market_diagnostic/examples/run_diagnostic.py --no-llm --verbose
```

---

## Installation

The module is part of the `daily_stock_analysis` package. No separate installation is required.

**Dependencies** (already in the project):
- `numpy` — vectorized indicator calculations
- `pandas` — data manipulation
- `akshare` — A-share market data
- `hypothesis` — property-based testing (dev only)
- `pytest` — test runner (dev only)

---

## Basic Usage

### Using `MarketDiagnosticEngine` directly

```python
from data_provider.base import DataFetcherManager
from src.market_diagnostic.engine import MarketDiagnosticEngine

# Initialize with existing DataFetcherManager
data_manager = DataFetcherManager()

engine = MarketDiagnosticEngine(
    data_manager=data_manager,
    analyzer=None,              # Pass GeminiAnalyzer() to enable LLM narrative
    enable_llm_narrative=False, # Set True when analyzer is provided
)

# Run the full diagnostic workflow
report, markdown = engine.run(date="2024-01-15")

# Access structured data
print(f"Regime: {report.composite_regime}")
print(f"Trend:  {report.trend_state} (score: {report.trend_score:.1f})")
print(f"Breadth: {report.breadth_state} (score: {report.breadth_score:.1f})")
print(f"Confidence: {report.confidence:.0%}")
print(f"Missing data: {report.missing_data}")

# Print the Markdown report
print(markdown)

# Serialize to JSON for downstream systems
json_str = report.to_json()
```

### Accessing specific metrics

```python
# Index data
for idx in report.indices:
    print(f"{idx['name']}: close={idx['close']}, ma20={idx.get('ma20')}")

# Breadth metrics
bm = report.breadth_metrics
print(f"Above MA20: {bm['above_ma20_ratio']:.1%}")
print(f"Limit-up rate: {bm['limit_up_rate']:.2%}")

# Top sectors
for sector in sorted(report.sector_table, key=lambda x: x.get('strength_score', 0), reverse=True)[:5]:
    print(f"{sector['industry_name']}: strength={sector['strength_score']:.2f}, state={sector['state']}")

# Risk flags
if report.risk_flags:
    print(f"⚠️ Risk flags: {', '.join(report.risk_flags)}")

# Strategy mapping
for strategy in report.strategy_mapping:
    print(f"  {strategy['group']} — weight: {strategy.get('weight', 'N/A')}")
```

---

## Integration with MarketAnalyzer

The diagnostic engine integrates seamlessly with the existing `MarketAnalyzer`:

```python
from src.market_analyzer import MarketAnalyzer

# Enable diagnostic mode
analyzer = MarketAnalyzer(
    search_service=None,
    analyzer=None,          # Replace with GeminiAnalyzer() for LLM narrative
    region="cn",
    enable_diagnostic=True, # Key flag
)

# run_full_analysis() returns (DiagnosticReport, markdown_str) in diagnostic mode
report, markdown = analyzer.run_full_analysis()

if report is not None:
    print(f"Regime: {report.composite_regime}")
    print(f"Confidence: {report.confidence:.0%}")
else:
    # Fallback to existing review generation (enable_diagnostic=False)
    print(markdown)
```

When `enable_diagnostic=False` (the default), `run_full_analysis()` falls back to the existing `generate_market_review()` workflow — fully backward compatible.

---

## Configuration Guide

All configuration is in `src/market_diagnostic/config.py`.

### Index Pool

```python
INDEX_POOL = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000016": "上证50",
    "sh000300": "沪深300",   # Primary index for trend classification
    "sh000905": "中证500",
    "sh000852": "中证1000",
    "sh000015": "微盘股指数",
}

PRIMARY_INDEX = "sh000300"  # Used for trend state classification
```

### Style Pairs

```python
STYLE_PAIRS = [
    ("sh000016", "sz399006", "大盘vs创业板"),
    ("sh000300", "sh000852", "沪深300vs中证1000"),
    ("sh000905", "sh000852", "中证500vs中证1000"),
]
```

### Breadth Thresholds

```python
BREADTH_THRESHOLDS = {
    "extreme_weak": 0.20,   # above_ma20_ratio < 20%  → 极弱
    "weak": 0.35,           # 20–35%                  → 偏弱
    "neutral": 0.55,        # 35–55%                  → 中性
    "strong": 0.70,         # 55–70%                  → 偏强
    # >= 70%                                           → 过热
}
```

### Regime Score Weights

```python
REGIME_SCORE_WEIGHTS = {
    "trend":     0.20,
    "breadth":   0.15,
    "sentiment": 0.15,
    "style":     0.15,
    "sector":    0.15,
    "risk":     -0.20,  # Negative: risk reduces the score
}
```

### Sector Strength Score Weights

```python
SECTOR_STRENGTH_WEIGHTS = {
    "ret_5d_excess":    0.25,
    "ret_20d_excess":   0.20,
    "breadth_20":       0.20,
    "new_high_ratio":   0.10,
    "amount_share_delta": 0.10,
    "leadership_score": 0.10,
    "crowding_score":  -0.05,  # Negative: crowding reduces score
}
```

### Confidence Scoring

```python
CONFIDENCE_PARAMS = {
    "base_confidence": 1.0,
    "missing_core_indicator_penalty": 0.15,  # Per missing core indicator
    "signal_consistency_bonus": 0.10,        # When signals align across dimensions
    "extreme_anomaly_penalty": 0.10,         # When extreme anomalies detected
    "estimated_data_penalty": 0.05,          # Per estimated/proxy data item
    "min_confidence": 0.1,
    "max_confidence": 1.0,
}
```

---

## API Reference

### `MarketDiagnosticEngine`

Main orchestrator class.

```python
class MarketDiagnosticEngine:
    def __init__(
        self,
        data_manager: DataFetcherManager,
        analyzer=None,
        enable_llm_narrative: bool = True,
    ): ...

    def run(self, date: str = None) -> Tuple[DiagnosticReport, str]:
        """
        Execute the complete diagnostic workflow.

        Parameters
        ----------
        date : str, optional
            Target trading date in 'YYYY-MM-DD' format. Defaults to today.

        Returns
        -------
        Tuple[DiagnosticReport, str]
            (structured_report, markdown_string)
        """
```

### `DiagnosticReport`

Structured output dataclass.

```python
@dataclass
class DiagnosticReport:
    date: str
    # States
    trend_state: str
    breadth_state: str
    sentiment_state: str
    style_state: str
    sector_state: str
    risk_state: str
    composite_regime: str
    # Scores (0–100)
    trend_score: float
    breadth_score: float
    sentiment_score: float
    risk_score: float
    regime_score: float
    # Detailed data
    indices: List[Dict]           # Index quotes + technical indicators
    breadth_metrics: Dict         # Breadth indicators
    sentiment_metrics: Dict       # Sentiment indicators
    style_metrics: Dict           # Style relative strength
    sector_table: List[Dict]      # Industry diagnostic table
    capital_metrics: Dict         # Capital flow indicators
    risk_flags: List[str]         # Active risk warnings
    # Conclusions
    one_sentence_summary: str
    key_evidence: List[str]
    counter_evidence: List[str]
    strategy_mapping: List[Dict]  # Regime → strategy group mapping
    confidence: float             # 0.1–1.0
    missing_data: List[str]       # Unavailable data items

    def to_json(self) -> str: ...
    @classmethod
    def from_dict(cls, data: dict) -> "DiagnosticReport": ...
```

### `MarketStateResult`

Output of the state classifier.

```python
@dataclass
class MarketStateResult:
    date: str
    trend_state: TrendState
    breadth_state: BreadthState
    sentiment_state: SentimentState
    style_state: StyleState
    sector_state: SectorState
    risk_state: RiskState
    composite_regime: CompositeRegime
    trend_score: float
    breadth_score: float
    sentiment_score: float
    style_score: float
    sector_score: float
    risk_score: float
    regime_score: float
    key_evidence: List[str]       # 3 key supporting evidence items
    counter_evidence: List[str]
    confidence: float             # 0.1–1.0
    risk_flags: List[str]
    missing_data: List[str]
```

### `MarketStateClassifier`

```python
class MarketStateClassifier:
    def classify(
        self,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
        date: str = None,
        missing_data: List[str] = None,
    ) -> MarketStateResult: ...
```

---

## State Classifications Reference

### TrendState (趋势状态)

| Value | Chinese | Condition |
|-------|---------|-----------|
| `强趋势上行` | Strong uptrend | MA5>MA10>MA20>MA60 AND MACD golden cross AND RSRS>0.7 |
| `趋势上行中的回调` | Pullback in uptrend | Bullish MA alignment BUT MA5<MA10 AND MA20 rising |
| `震荡` | Ranging | Tangled MAs AND MACD near zero |
| `趋势转弱` | Weakening trend | MA5<MA10<MA20 OR MACD death cross |
| `破位下行` | Breakdown | Price below MA60 AND RSRS<0.3 |

### BreadthState (广度状态)

| Value | Chinese | above_ma20_ratio |
|-------|---------|-----------------|
| `极弱` | Extreme weak | < 20% |
| `偏弱` | Weak | 20–35% |
| `中性` | Neutral | 35–55% |
| `偏强` | Strong | 55–70% |
| `过热` | Overheated | ≥ 70% |

### SentimentState (情绪状态)

| Value | Chinese | Description |
|-------|---------|-------------|
| `冰点` | Frozen | Very low limit-up rate, high limit-down rate, low seal rate |
| `回暖` | Warming | Recovering limit-up rate, improving seal rate |
| `中性` | Neutral | Moderate limit-up rate and seal rate |
| `活跃` | Active | High limit-up rate, high seal rate, positive next-day premium |
| `狂热` | Euphoric | Extreme limit-up rate, very high seal rate, strong continuous limit-ups |

### StyleState (风格状态)

| Value | Chinese | Description |
|-------|---------|-------------|
| `大盘防守` | Large-cap defensive | Large-cap outperforming small-cap AND dividend > growth |
| `小盘进攻` | Small-cap offensive | Small-cap indices outperforming large-cap |
| `成长主导` | Growth dominant | Growth indices significantly outperforming value |
| `红利防守` | Dividend defensive | Dividend indices outperforming growth |
| `风格冲突` | Style conflict | Conflicting signals across multiple style dimensions |

### SectorState (板块状态)

| Value | Chinese | Condition |
|-------|---------|-----------|
| `无主线` | No theme | No sector with strength_score > 1.5 |
| `单主线` | Single theme | One sector: strength_score > 2.0 AND persistence_score > 0.7 |
| `双主线并行` | Dual theme | Two sectors: strength_score > 1.8 AND persistence_score > 0.6 |
| `高速轮动` | Fast rotation | Top-5 sector rankings changing significantly over 5 days |
| `退潮分化` | Fading | Declining strength scores across previously strong sectors |

### RiskState (风险状态)

| Value | Chinese | Condition |
|-------|---------|-----------|
| `低风险` | Low risk | Low volatility, low drawdown, no risk flags |
| `中性风险` | Neutral risk | Moderate volatility and drawdown |
| `高风险` | High risk | Elevated volatility OR significant drawdown OR 1–2 risk flags |
| `极端风险` | Extreme risk | Extreme volatility OR severe drawdown OR 3+ risk flags |

### CompositeRegime (综合状态)

| Value | Description | Strategy Implication |
|-------|-------------|---------------------|
| `trend_risk_on_growth` | Trend + growth dominant | Trend ETF, sector rotation, small-cap offensive |
| `trend_risk_on_smallcap` | Trend + small-cap dominant | Trend ETF, small-cap offensive |
| `balanced_rotation` | Ranging + neutral breadth | Sector rotation, dividend value, stock-bond balance |
| `defensive_dividend` | Weakening trend + dividend | Dividend value, stock-bond balance, all-weather |
| `high_volatility_warning` | High/extreme risk | Stock-bond balance, all-weather, high cash |
| `panic_bottoming` | Extreme weak breadth + frozen sentiment | Small position probing |
| `broad_weakness_hold` | Breakdown + weak breadth | Stock-bond balance, all-weather, high cash |

### Risk Flags

| Flag | Trigger |
|------|---------|
| `vol_spike` | Realized volatility > 2× historical mean |
| `breadth_collapse` | above_ma20_ratio drops > 10pct in a single day |
| `sector_overcrowding` | Single sector amount_share > mean + 2σ |
| `northbound_outflow` | North Bound Capital net outflow for 3+ consecutive days |
| `leadership_breakdown` | Top-5 sector leaders average drop > 2% |
| `index_break_support` | CSI300 breaks below MA60 |

---

## Output Format

### JSON Output

```json
{
  "date": "2024-01-15",
  "composite_regime": "balanced_rotation",
  "trend_state": "震荡",
  "breadth_state": "中性",
  "sentiment_state": "中性",
  "style_state": "风格冲突",
  "sector_state": "无主线",
  "risk_state": "中性风险",
  "trend_score": 52.3,
  "breadth_score": 48.7,
  "sentiment_score": 50.1,
  "risk_score": 35.2,
  "regime_score": 51.4,
  "indices": [
    {
      "code": "sh000300",
      "name": "沪深300",
      "close": 3521.5,
      "change_pct": 0.35,
      "ma5": 3510.2,
      "ma20": 3480.1,
      "ma60": 3420.5,
      "macd_signal": "中性",
      "rsrs_score": 0.55
    }
  ],
  "breadth_metrics": {
    "above_ma20_ratio": 0.48,
    "limit_up_rate": 0.018,
    "seal_rate": 0.72,
    "new_high_ratio": 0.032
  },
  "sector_table": [
    {
      "industry_name": "电子",
      "strength_score": 1.85,
      "state": "趋势强化",
      "ret_1d": 1.2,
      "ret_5d": 3.8,
      "amount_share": 0.12
    }
  ],
  "risk_flags": [],
  "key_evidence": [
    "沪深300均线缠绕，MACD在零轴附近",
    "广度中性，站上MA20比例48%",
    "情绪中性，涨停率1.8%"
  ],
  "counter_evidence": ["成交额低于5日均值8%"],
  "confidence": 0.82,
  "missing_data": []
}
```

### Markdown Report Structure

```markdown
## 2024-01-15 大盘全维度诊断

### 🎯 一句话结论
当前市场处于【均衡轮动】状态，趋势震荡，广度中性，情绪中性，风险中性风险，综合得分51.4，置信度82%。

### 📊 状态仪表盘
| 维度 | 状态 | 得分 |
|------|------|------|
| 趋势 | 震荡 | 52.3 |
...

### 📈 指数与价格结构
...

### 🌊 市场广度
...

### 🎭 情绪与赚钱效应
...

### 🔄 风格轮动
...

### 🏭 板块主线诊断
...

### 💰 资金流向
...

### ⚠️ 风险警报
...

### 🗺️ 策略映射建议
...

### 📝 证据与置信度
...
```

---

## Error Handling and Graceful Degradation

The system is designed to produce useful output even when data sources are partially unavailable.

### Data Availability Tiers

| Data | Priority | Fallback |
|------|----------|---------|
| 9 core index daily data | P0 (critical) | Use cached previous-day data |
| Market-wide realtime quotes | P0 | Use neutral fallback breadth features |
| 31 Shenwan Level-1 industry data | P1 | Empty sector table |
| North Bound Capital | P1 | Mark as T+1 unavailable, confidence -0.10 |
| Margin balance | P1 | Mark as T+1 unavailable, confidence -0.05 |
| Bond yields / exchange rates | P2 | Skip valuation features |
| C-VIX (option data) | P2 | Use ATR as proxy, mark as estimated |

### Confidence Score Adjustments

The confidence score (0.1–1.0) reflects data completeness:

- **Base**: 1.0
- **Per missing core indicator**: −0.15
- **Consistent signals across dimensions**: +0.10
- **Extreme anomalous values detected**: −0.10
- **Per estimated/proxy data item**: −0.05
- **Minimum**: 0.1 (always produces output)

### Error Logging

All data fetch errors are logged at `ERROR` level with:
- Timestamp
- Data source identifier (e.g., `[DataSource: index_series]`)
- Error message

```python
import logging
logging.basicConfig(level=logging.INFO)

# Errors appear as:
# 2024-01-15 09:30:00 [ERROR] market_diagnostic.engine:
#   [2024-01-15T09:30:00] [DataSource: breadth_data] Failed to fetch breadth data: ...
```

---

## Troubleshooting

### `ImportError: No module named 'akshare'`

Install akshare:
```bash
pip install akshare
```

### `No index data returned for {date}`

- Verify the date is a valid A-share trading day (not a weekend or holiday)
- Check your network connection to AkShare data sources
- The system will continue with cached data or fallback features

### `Failed to fetch sector data` (rate limiting)

AkShare sector APIs have rate limits. The system adds a 3-second delay between sector requests. If you still hit limits:
- Reduce the number of sectors fetched by modifying `SHENWAN_INDUSTRIES` in `config.py`
- Increase the delay in `PERFORMANCE_TARGETS["api_rate_limit_delay_seconds"]`

### Low confidence scores (< 0.5)

Low confidence indicates missing data. Check `report.missing_data` for details:
```python
report, _ = engine.run(date="2024-01-15")
print(f"Confidence: {report.confidence:.0%}")
print(f"Missing: {report.missing_data}")
```

### Tests failing

Run the full test suite:
```bash
cd daily_stock_analysis
python -m pytest src/market_diagnostic/tests/ -v
```

For property-based tests only:
```bash
python -m pytest src/market_diagnostic/tests/ -v -k "properties"
```

For integration tests only:
```bash
python -m pytest src/market_diagnostic/tests/test_comprehensive_integration.py -v
```

### Performance: diagnostic takes > 60 seconds

The main bottleneck is usually sector data fetching (31 API calls with 3-second delays). Options:
- Enable parallel processing (already implemented via `max_workers=4` in sector features)
- Use cached data for sectors that haven't changed
- Reduce the sector list for faster runs during development

---

## Running Tests

```bash
cd daily_stock_analysis

# All tests
python -m pytest src/market_diagnostic/tests/ -v

# Property-based tests (correctness properties)
python -m pytest src/market_diagnostic/tests/ -v -k "properties"

# Integration tests
python -m pytest src/market_diagnostic/tests/test_comprehensive_integration.py -v

# Performance tests
python -m pytest src/market_diagnostic/tests/test_performance.py -v

# With coverage
python -m pytest src/market_diagnostic/tests/ --cov=src/market_diagnostic --cov-report=term-missing
```

---

## Requirements Traceability

| Requirement | Implementation |
|-------------|---------------|
| 1.x Data Acquisition | `data/fetchers.py`, `data/models.py` |
| 2.x Trend Features | `features/trend.py` |
| 3.x Breadth Features | `features/breadth.py` |
| 4.x Sentiment Features | `features/sentiment.py` |
| 5.x Style Features | `features/style.py` |
| 6.x Sector Features | `features/sector.py` |
| 7.x Capital Features | `features/capital.py` |
| 8.x Risk Features | `features/risk.py` |
| 9–16.x State Classification | `states/classifier.py`, `states/enums.py` |
| 17.x Evidence & Confidence | `states/classifier.py` |
| 18.x JSON Output | `reports/schema.py` |
| 19.x Markdown Output | `reports/markdown_renderer.py` |
| 20.x Strategy Mapping | `reports/strategy_mapper.py` |
| 21.x Integration | `engine.py`, `src/market_analyzer.py` |
| 22.x Error Handling | `engine.py` |
| 23.x Performance | `data/cache.py`, `features/sector.py` |
| 24.x Configuration | `config.py` |
| 25.x Documentation | This README |
