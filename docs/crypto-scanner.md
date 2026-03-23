# Crypto 新币扫描器

## 概述

Crypto 新币扫描器是一个多链加密货币新币发现与分析系统，作为主系统的可选模块运行。支持 Solana、Ethereum、Base 等 EVM 兼容链。

## 架构

```
数据源 (GeckoTerminal / DexScreener)
   ↓
Phase 1: 发现与采集 → 数据库存储
   ↓
Phase 2: 风险评估 + 快照追踪 → 观察列表 + 告警
   ↓
Phase 3: AI 多分析师管线 → 投资建议
   ↓
Phase 4: 可观测性仪表盘 → 运行监控
```

## 启用方式

在 `.env` 中配置：

```bash
CRYPTO_ENABLED=true
CRYPTO_CHAINS=solana,ethereum,base
```

系统将在启动时开启后台扫描线程，默认每 60 秒执行一次。

## 配置参考

### Phase 1: 发现与采集

| 配置项                          | 默认值                 | 说明                                         |
| ------------------------------- | ---------------------- | -------------------------------------------- |
| `CRYPTO_ENABLED`                | `false`                | 是否启用 crypto 扫描器                       |
| `CRYPTO_REFRESH_INTERVAL_SEC`   | `60`                   | 扫描间隔（秒）                               |
| `CRYPTO_CHAINS`                 | `solana,ethereum,base` | 扫描链列表（逗号分隔）                       |
| `CRYPTO_DEFAULT_SORT`           | `newest`               | 默认排序（newest/liquidity/volume/activity） |
| `CRYPTO_MAX_AGE_MINUTES`        | `1440`                 | 最大币龄（分钟）                             |
| `CRYPTO_MIN_LIQUIDITY_USD`      | `0.0`                  | 最低流动性过滤                               |
| `CRYPTO_MIN_VOLUME_USD`         | `0.0`                  | 最低成交量过滤                               |
| `CRYPTO_DISCOVERY_PROVIDER`     | `geckoterminal`        | 发现数据源                                   |
| `CRYPTO_ENRICHMENT_PROVIDER`    | `dexscreener`          | 丰富数据源                                   |
| `CRYPTO_DISCOVERY_TIMEOUT_SEC`  | `5`                    | 发现请求超时                                 |
| `CRYPTO_ENRICHMENT_TIMEOUT_SEC` | `5`                    | 丰富请求超时                                 |
| `CRYPTO_MAX_RETRIES`            | `3`                    | 最大重试次数                                 |
| `CRYPTO_INITIAL_BACKOFF_SEC`    | `1`                    | 初始退避时间                                 |
| `CRYPTO_BACKOFF_MULTIPLIER`     | `2.0`                  | 退避倍率                                     |
| `CRYPTO_DISCOVERY_CACHE_SEC`    | `60`                   | 发现缓存时间                                 |
| `CRYPTO_ENRICHMENT_CACHE_SEC`   | `30`                   | 丰富缓存时间                                 |

### Phase 2: 风险分析与告警

| 配置项                                 | 默认值   | 说明                        |
| -------------------------------------- | -------- | --------------------------- |
| `CRYPTO_RISK_ENABLED`                  | `true`   | 是否启用风险评估            |
| `CRYPTO_RISK_MIN_LIQUIDITY_USD`        | `1000.0` | 风险扫描最低流动性          |
| `CRYPTO_RISK_CACHE_TTL_SEC`            | `300`    | 风险缓存 TTL                |
| `CRYPTO_WATCHLIST_ENABLED`             | `true`   | 是否启用观察列表            |
| `CRYPTO_ALERTS_ENABLED`                | `false`  | 是否启用告警推送            |
| `CRYPTO_ALERT_LIQUIDITY_DROP_PCT`      | `30.0`   | 流动性骤降阈值（%）         |
| `CRYPTO_ALERT_VOLUME_SPIKE_MULTIPLIER` | `5.0`    | 成交量暴涨倍数              |
| `CRYPTO_SNAPSHOT_RETENTION_DAYS`       | `7`      | 快照保留天数                |
| `CRYPTO_SECURITY_PROVIDER`             | `auto`   | 安全数据源（auto 自动选择） |

### Phase 3: AI 分析

| 配置项                         | 默认值               | 说明                  |
| ------------------------------ | -------------------- | --------------------- |
| `CRYPTO_AI_ENRICHMENT_ENABLED` | `false`              | 是否启用 AI 分析      |
| `CRYPTO_AI_QUICK_MODEL`        | _(空，使用全局模型)_ | 快速分析模型          |
| `CRYPTO_AI_DEEP_MODEL`         | _(空，使用全局模型)_ | 深度分析模型          |
| `CRYPTO_AI_RISK_THRESHOLD`     | `80`                 | 风险分数门控阈值      |
| `CRYPTO_AI_CACHE_TTL_SEC`      | `21600`              | AI 结果缓存 TTL（秒） |
| `CRYPTO_AI_PROMPT_VERSION`     | `v1`                 | Prompt 版本号         |

## API 端点

所有端点挂载在 `/api/v1/crypto/` 下。

### 列表

```
GET /api/v1/crypto/launches
  ?chains=solana,ethereum
  &min_liquidity_usd=1000
  &min_volume_usd=100
  &max_age_minutes=720
  &sort=newest
  &cursor=100
  &limit=50
```

### 详情

```
GET /api/v1/crypto/launches/{launch_id}
```

### AI 分析

```
POST /api/v1/crypto/launches/{launch_id}/analyze
```

AI 分析管线：

1. 四个分析师（市场/安全/社交/技术）并发执行
2. 牛熊辩论综合对立观点
3. 研究主管编制最终判定
4. 确定性风险门控覆盖（蜜罐检测、极端风险分数）

### 手动刷新

```
POST /api/v1/crypto/refresh
```

### 状态

```
GET /api/v1/crypto/status
```

### 可观测性

```
GET /api/v1/crypto/metrics/providers   # 供应商指标
GET /api/v1/crypto/metrics/slo         # 扫描 SLO
GET /api/v1/crypto/ai/cost             # AI 成本
GET /api/v1/crypto/ai/prompt-comparison # Prompt 版本对比
```

## 告警系统

当 `CRYPTO_ALERTS_ENABLED=true` 时，系统在每次扫描后对观察列表中的币种进行阈值检查：

- **流动性骤降**：流动性下降超过 `CRYPTO_ALERT_LIQUIDITY_DROP_PCT`%
- **成交量暴涨**：24h 成交量超过基线 `CRYPTO_ALERT_VOLUME_SPIKE_MULTIPLIER` 倍
- **风险等级恶化**：风险等级从低升高（如 low → high）

告警通过系统已配置的通知渠道（企业微信/飞书/Telegram/邮件等）推送。

## 已知限制

- 免费 API 数据源存在速率限制，高频扫描可能触发节流
- AI 分析消耗 LLM token，建议按需启用并关注 `/ai/cost` 端点
- 快照保留受 `CRYPTO_SNAPSHOT_RETENTION_DAYS` 控制，过期数据自动清理
- 告警系统依赖前后两次扫描的对比数据，首次扫描不会触发告警
