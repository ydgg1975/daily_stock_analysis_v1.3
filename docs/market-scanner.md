# Market Scanner（A 股 + 美股盘前扫描）

## 产品定位

Market Scanner 是 WolfyStock 的独立产品能力，用于在盘前回答：

> 今天开盘前，当前市场里哪些标的值得优先观察？

它和现有模块的边界如下：

- `Scanner`：主动发现层，输出盘前观察名单、原因、风险与观察触发条件
- `Analysis`：单标的深度分析层，解释一只股票当前值不值得跟踪
- `Ask Stock / Chat`：交互式追问层，用自然语言继续追问逻辑、风险、计划
- `Backtest`：历史验证层，用于验证策略或规则在历史上的表现
- `Execution`：当前阶段**未实现**，Scanner 不直接给出自动交易指令

当前 Web 入口为 `/scanner`，后端 API 为：

- `POST /api/v1/scanner/run`
- `GET /api/v1/scanner/runs`
- `GET /api/v1/scanner/runs/{id}`
- `GET /api/v1/scanner/watchlists/today`
- `GET /api/v1/scanner/watchlists/recent`
- `GET /api/v1/scanner/status`

## 当前实现范围

当前已经落地两个明确分离的 market profile：

- `cn_preopen_v1`：A 股盘前扫描，继续作为默认 profile
- `us_preopen_v1`：美股盘前扫描，面向 pre-open shortlist / watchlist 生成

它们共享 Scanner 的运行面板、持久化、schedule、notification、history/review/quality 设施，但不会被混成一个黑盒统一评分模型。

当前共通能力包括：

- 提供独立运行面板，不复用回测页
- 提供 shortlist 视图，而不是原始表格 dump
- 提供候选详情抽屉，展示原因、特征分项、风险与观察触发条件
- 提供最近扫描历史，便于回看近期 shortlist
- 提供继续动作：
  - 进入首页深度分析
  - 跳转问股
  - 跳转回测并预填代码

A 股仍然保持 A-share-first 的默认体验；美股则作为新增但清晰分离的 Scanner profile 接入，不改变已有 A 股 deterministic ranking 的主导地位。

## A 股 universe 定义

Scanner 不会对“全市场所有标的”做无边界盲扫，而是先构建一个显式、受控、可解释的 A 股候选池。

### Universe 构建步骤

1. 解析可用的 A 股股票列表
2. 读取 A 股全市场实时快照
3. 取两者交集，并只保留常见 A 股股票代码段：
   - `000/001/002/003`
   - `300/301`
   - `600/601/603/605`
   - `688/689`
4. 剔除明显不适合作为盘前 shortlist 的标的
5. 仅保留成交和活跃度较高的一批候选进入详细评估

### Universe 数据依赖与 fallback 顺序

从这次运行时修复开始，Scanner 不再把 `Tushare stock_basic` 权限当成硬前提。

当前 A 股 universe 解析顺序为：

1. 本地 universe cache：`SCANNER_LOCAL_UNIVERSE_PATH`（默认 `./data/scanner_cn_universe_cache.csv`）
2. `TushareFetcher.get_stock_list()`，如果当前 token 具备 `stock_basic` 权限
3. 本地内部 fallback：
   - 本地数据库 `analysis_history / stock_daily`
   - 内置 `STOCK_NAME_MAP` A 股映射
4. `AkshareFetcher.get_stock_list()` 作为最后的在线补充

成功拿到可用 universe 后，Scanner 会回写本地 cache，后续手动/定时运行可直接复用。

### 当前剔除规则

当前 `cn_preopen_v1` profile 默认剔除：

- 北交所代码
- `ST` / 特殊处理股票
- 价格低于 `3.0`
- `volume <= 0` 或 `price <= 0` 的停牌/近似停牌状态
- 成交额低于 `2e8`
- 换手率低于 `0.8%`
- 量比低于 `0.6`

通过上述过滤后，会按成交额和活跃度排序，默认仅保留前 `300` 只进入详细评估。

### Universe 假设

- 当前更偏向“有流动性、有参与度、适合盘前观察”的 A 股主板 / 创业板 / 科创板候选
- 不追求第一版就覆盖全部 A 股细分场景
- 不把低流动性、极低价、明显噪音标的放入默认 shortlist

## A 股打分与排序逻辑

第一版 Scanner 采用**确定性、可解释、规则型**排序，不使用黑盒模型。

### 两阶段流程

#### 第一阶段：全市场预筛

使用全市场快照，对候选池做轻量预排序，主要考虑：

- 流动性
- 换手率
- 量比
- 近阶段趋势背景（如 `change_60d`）
- 振幅质量

这一阶段的目标是快速把全市场缩到一个更值得详细评估的子集。

#### 第二阶段：详细评分

对有限候选加载日线历史（本地优先，不足时再补 provider），计算更稳定的盘前特征。

当前总分由以下部分组成：

- `pre_rank`：25 分
- `trend`：20 分
- `momentum`：15 分
- `breakout`：12 分
- `liquidity`：10 分
- `activity`：8 分
- `volatility_quality`：5 分
- `relative_strength`：5 分
- `sector_bonus`：最多 5 分
- `penalties`：过热、波动过大、历史样本退化等扣分

### 主要特征解释

- `trend`：价格是否站稳 MA20 / MA60，MA20 是否继续上行
- `momentum`：近 5 日、20 日收益与最近上涨天数
- `breakout`：距离近 20 日高点的远近，以及量能放大确认
- `liquidity`：近 20 日平均成交额与当前成交额是否足够
- `activity`：换手率、量比、量能扩张情况
- `relative_strength`：候选之间的近期相对强弱排序
- `sector_bonus`：是否与当前较强板块重叠，仅做小幅加分

### 输出结果包含什么

每个 shortlisted 候选至少会包含：

- `symbol / name`
- `rank`
- `scanner score`
- `quality hint`
- `reason summary`
- `reasons`
- `key metrics`
- `feature signals`
- `risk notes`
- `watch context`
- `scan timestamp`
- `run metadata`

## 如何理解结果

Scanner 输出的是“盘前观察名单”，不是自动交易命令。

### 推荐阅读方式

1. 先看 `rank + score`
2. 再看 `reason summary`，理解它为什么入选
3. 再看 `risk notes`，判断是否存在追高、波动、流动性等现实风险
4. 最后看 `watch context`，明确盘中该观察什么，而不是只记住代码

### 质量提示

当前质量提示为：

- `高优先级`
- `优先观察`
- `条件确认`
- `题材跟踪`

它用于帮助阅读顺序，不等同于买入信号强弱标签。

## AI 二次解读层（Phase 1）

在保持 A 股 `cn_preopen_v1` 规则型扫描不变的前提下，Scanner 现在支持一个**可选的 AI 二次解读层**。

它的定位是：

- 只解释 deterministic shortlist 中“为什么今天值得关注”
- 用更接近交易员语言的方式总结机会类型、主要风险与观察计划
- 在盘后 review 数据可用时，补一段轻量复盘点评

它**不会**做的事：

- 不替换原始 `rank / score`
- 不把 AI 作为首轮选股或主排序逻辑
- 不在 AI 不可用时阻断 Scanner
- 不输出自动交易或执行指令

### 当前 AI 输出范围

当前 AI 仅对 shortlist 里的前 N 名候选做解读，默认上限为 `3`，并会在候选详情中追加：

- `AI summary`
- `opportunity type`
- `AI risk interpretation`
- `AI watch plan`
- `AI review commentary`（仅在 review 数据就绪后补充）

规则型字段如 `reason summary / reasons / risk notes / watch context` 会继续原样保留，方便用户并排对照 deterministic 解释与 AI 翻译层。

### AI 降级与可见诊断

AI 只是附加层，不是 Scanner 成功运行的前提：

- 若 `SCANNER_AI_ENABLED=false`，Scanner 继续输出纯规则型 shortlist
- 若 AI provider/model 暂时不可用，候选会显示明确 fallback 文案，而不是模糊失败
- Web `/scanner` 的运行时诊断会显示 AI 是否启用、运行状态、覆盖候选数、使用的模型以及是否发生 fallback

### AI 相关配置

- `SCANNER_AI_ENABLED`
- `SCANNER_AI_TOP_N`

默认建议保持关闭或仅对少量高优先级候选启用，避免把成本和延迟扩散到整个 universe。

## 美股 Scanner Profile（Phase 2）

在不改变 A 股 `cn_preopen_v1` 主排序路径的前提下，Scanner 现在新增了一个独立的 `us_preopen_v1` profile。

它的边界仍然清晰：

- 仍然属于 Scanner，而不是 Backtest 或自动交易模块
- 仍然先由 deterministic score 做 primary shortlist 生成
- AI 若启用，依然只是 secondary interpretation
- 不要求首版美股 profile 与 A 股 feature parity 完全一致，但要求结构清晰、市场语义正确

### 美股 universe 与数据假设

首版 `us_preopen_v1` 使用**本地优先**的 bounded universe：

1. 优先从 `LOCAL_US_PARQUET_DIR`
2. 未配置或目录缺失时回退 `US_STOCK_PARQUET_DIR`
3. 若本地 parquet 不可用，再回退本地 `stock_daily` 里已经落库的美股日线

当前默认不会为 universe 做“全网盲扫”，而是仅对本地可用的美股历史样本做解释型 scanner。

同时会先过滤：

- 价格过低标的
- 20 日平均成交额不足
- 20 日平均成交量不足
- 历史样本不够
- 基准 ticker（当前默认 `SPY`）不会进入候选排序本身

### 美股首版关注因素

`us_preopen_v1` 当前强调：

- liquidity
- recent trend / momentum continuation
- volatility / tradability
- benchmark-relative behavior（默认相对 `SPY`）
- optional live quote / gap context

如果 live quote 不可用，Scanner 仍会继续输出 shortlist，只是会在 risk notes 和运行时诊断里明确提示当前更偏历史视角。

### 美股结果如何展示

Web `/scanner` 现在可以显式切换：

- 市场：`A股` / `美股`
- 对应 profile：`cn_preopen_v1` / `us_preopen_v1`

同时在以下位置保留 market/profile 上下文：

- 当前 run badge
- recent watchlists 历史项
- status / quality / review 结果
- 导出摘要

美股候选的 reasons / risk notes / watch context 也改为使用更贴近 pre-open / gap / liquidity / open-check 的措辞，避免直接复用 A 股语义。

## 风险提示与观察触发条件

第一版已经内置一些 A 股现实约束：

- 主板 / 创业板 / 科创板的涨跌停制度差异
- 短线过热与题材追高风险
- 流动性不足时的承接风险
- 高振幅下的事件驱动波动风险
- 历史样本不足或降级时的二次核验提示

观察触发条件会给出轻量但结构化的上下文，例如：

- 观察是否上破近 20 日高点
- 观察量比是否维持在阈值以上
- 弱开并跌回关键均线时应放弃追踪
- 同步确认板块联动是否仍然成立

## P9：日常运营层

Scanner 现在不仅能“跑一次”，还可以支撑盘前日常工作流：

- 支持独立的盘前定时运行，不和主分析 schedule 混在一起
- 按交易日持久化 daily watchlist，方便打开“今日观察名单”
- 支持查看 recent watchlists，做轻量回看
- 支持通过现有通知渠道推送盘前 shortlist 摘要
- 支持查看最近定时运行、通知状态与失败原因

### 当前运营入口

- Web：`/scanner`
  - 今日 watchlist 默认前置展示
  - 近期 watchlist 以按日聚合的方式展示
  - 运营状态区展示 schedule、最近定时运行、通知状态与最近失败
- CLI：
  - `python main.py --scanner`：手动运行一次 Scanner
  - `python main.py --scanner-schedule`：启动 Scanner 定时任务
- API：
  - `POST /api/v1/scanner/run`
  - `GET /api/v1/scanner/watchlists/today`
  - `GET /api/v1/scanner/watchlists/recent`
  - `GET /api/v1/scanner/status`

### 调度与配置

Scanner 使用独立配置，不复用普通分析的调度语义：

- `SCANNER_PROFILE`（当前支持 `cn_preopen_v1` / `us_preopen_v1`）
- `SCANNER_SCHEDULE_ENABLED`
- `SCANNER_SCHEDULE_TIME`
- `SCANNER_SCHEDULE_RUN_IMMEDIATELY`
- `SCANNER_NOTIFICATION_ENABLED`
- `SCANNER_LOCAL_UNIVERSE_PATH`
- `LOCAL_US_PARQUET_DIR`
- `US_STOCK_PARQUET_DIR`（兼容旧变量名）
- `SCANNER_AI_ENABLED`
- `SCANNER_AI_TOP_N`

默认建议把 A 股盘前 schedule 设在开盘前，例如 `08:40`。普通分析任务和 Scanner 可以在同一进程里并存调度，但仍然各自保持独立职责。

### 每日 watchlist 如何持久化

当前不会额外引入新的迁移层，而是继续复用现有 Scanner 持久化表：

- `market_scanner_runs`
- `market_scanner_candidates`

P9 相关运营元数据继续写入已有 JSON 字段，当前会额外保留：

- `watchlist_date`
- `trigger_mode`（`manual` / `scheduled`）
- `request_source`
- `notification` 结果
- `failure` 原因

这样可以在不重构现有 Scanner 存储结构的前提下，直接支持 today / recent watchlist 查询与运营状态展示。

### 通知如何工作

首版通知层复用现有 `NotificationService`，不依赖用户打开 Web 页面。

当 `SCANNER_NOTIFICATION_ENABLED=true` 且定时运行产生结果时，系统会：

1. 生成一份简洁 Markdown watchlist 摘要
2. 保存本地报告文件，便于追溯
3. 向已配置通知渠道发送盘前 shortlist
4. 在运行元数据里记录通知是否成功

通知摘要默认包含：

- rank
- symbol / name
- score
- concise reason
- primary risk note
- primary watch / trigger context

### 失败与空结果语义

P9 强调“可见失败”，而不是静默跳过：

- `completed`：正常产出 shortlist
- `empty`：运行成功，但当日没有候选满足阈值
- `failed`：运行失败，已保留失败原因
- `skipped`：仅用于调度层返回值，例如非交易日跳过；不会伪装成成功运行

这意味着“今天没有 shortlist”会被明确保存成一个可查看的 daily watchlist 结果，而不是被误解为系统没有工作。

## 本地优先与运行留痕

Scanner 尽量复用仓库已有的 local-first 模式：

- 股票列表优先读本地 universe cache，不足时再走 provider / 本地 fallback
- 实时快照复用现有 market data loader，并保留多 fetcher 尝试链路
- 日线历史优先读本地 `stock_daily`
- 本地不足时再按标的补抓，并回写本地缓存
- 扫描结果会持久化 run 与 shortlisted candidates

当前会保存的 run 元数据包括：

- 扫描时间
- market / profile
- universe 名称
- universe 大小、预筛大小、详细评估大小
- source summary
- scoring notes
- shortlist 结果
- watchlist_date / trigger_mode / request_source
- notification 状态
- failure reason（若失败）

### A 股 snapshot fallback 与降级模式

当前 realtime snapshot 解析顺序为：

1. `AkshareFetcher`
   - 优先 `ak.stock_zh_a_spot_em`
   - 失败后再尝试 `ak.stock_zh_a_spot`（新浪兜底）
2. `EfinanceFetcher`
3. 若两者都不可用，则尝试 `local_history_degraded`

`local_history_degraded` 只会在本地 `stock_daily` 有足够历史样本时启用，并会在结果里明确标记：

- `source_summary` 中显示 `snapshot=local_history_degraded`
- `diagnostics.scanner_data.degraded_mode_used=true`
- universe notes 中提示当前结果更适合作为盘前参考，而不是高确信度 shortlist

如果连降级模式也无法成立，Scanner 会返回更明确的失败语义，而不再只给一个模糊的 `no_supported_fetcher`。

### 可见失败原因与诊断

当前会在运行元数据、失败记录和 `/scanner` 页面二级诊断区保留：

- universe 来源
- snapshot 来源
- fetcher 尝试链路
- 是否启用了 degraded mode

常见 reason code 包括：

- `tushare_permission_denied`
- `universe_source_unavailable`
- `akshare_snapshot_fetch_failed`
- `efinance_snapshot_fetch_failed`
- `no_realtime_snapshot_available`

建议排查顺序：

1. 先看 universe 是否来自 `local_universe_cache / db_local_fallback / builtin_stock_mapping`
2. 再看 snapshot attempts 是 AkShare 失败、efinance 失败，还是都失败
3. 如果启用了 `local_history_degraded`，确认本地 `stock_daily` 是否足够新、样本是否足够
4. 若失败记录里仍为 `no_realtime_snapshot_available`，说明全量快照与降级模式都不可用，需要补本地历史或恢复免费实时源

## Route A：日常复盘与质量评估工作流

在 P9 让 Scanner 具备“能定时跑、能保留 watchlist、能推送”之后，当前阶段继续把它补成一个更完整的每日工作流：

- `today / recent watchlists` 仍是默认入口，但现在更强调“今天和前几天相比发生了什么”
- `/scanner` 会把当前 watchlist 与上一交易日做轻量对比
- shortlist 候选会展示后续表现，而不是只停留在晨会名单
- 页面会提供一层轻量 quality summary，用来判断 Scanner 最近是否仍在稳定产出有用候选
- 支持导出紧凑的日评摘要，便于手工复盘与分享

### 今日 / 近期 watchlist 如何查看

当前页面会把“今日观察名单”和“近期 watchlists”分层展示：

- 今日或当前选中的 watchlist 仍然是主视图
- 近期 watchlists 则更像一个 review 入口，而不再只是归档列表
- 历史项会直接显示：
  - 通知状态
  - top symbols
  - 与上一观察日相比的新入选 / 连续入选 / 掉出名单
  - 该日 shortlist 的轻量复盘摘要（若本地日线足够）

这让用户可以先看今天，再快速回看前几天 shortlist 的变化节奏。

### 跨日对比现在怎么看

当前对比仍然保持轻量和可解释：

- `新入选`：今天首次进入 shortlist 的标的
- `连续入选`：前一观察日仍在名单里的标的
- `掉出名单`：前一观察日有、今天已不在名单的标的
- 对连续入选标的，还会显示 rank 变化，帮助判断关注度是在上升还是下滑

这不是复杂的因子归因，只是为了让用户更快看懂“watchlist 在怎么变化”。

### 盘后复盘与候选结果跟踪

当前版本使用本地 `stock_daily` 做确定性、可解释的候选后续表现跟踪，不新增新表、不引入黑盒评价。

默认做法是：

1. 以 Scanner 运行时已知的最近交易日收盘价作为锚点
2. 统计其后默认 `3` 个交易日窗口的表现
3. 对每个 shortlisted 候选给出：
   - `same_day_close_return_pct`
   - `next_day_return_pct`
   - `review_window_return_pct`
   - `max_favorable_move_pct`
   - `max_adverse_move_pct`
   - 是否跑赢本地可用 benchmark（当前优先 `000300`）

页面会把这些结果收敛成更适合产品阅读的标签：

- `兑现较强`
- `表现一般`
- `后续偏弱`
- `逻辑已验证 / 部分验证 / 未验证`

这层复盘的目标是回答“晨会 shortlist 后来怎么样了”，而不是替代 Backtest 做长期历史验证。

### 质量指标代表什么

当前 quality summary 只提供轻量、可解释的最近表现统计，主要回答：

- 平均 shortlist 收益如何
- 候选命中率如何
- 跑赢 benchmark 的比例如何
- 每次 run 通常能筛出多少可复盘候选
- 兑现候选与未兑现候选的平均分有没有明显差异

这些指标的作用是帮助判断 Scanner 最近“有没有持续产出可用候选”，而不是把 Scanner 变成一套完整量化评估平台。

### 与 Backtest 的边界

当前 Route A 继续保持和 Backtest 的边界：

- `Scanner review`：看最近真实 shortlist 的后续表现
- `Backtest`：验证规则/策略在更长历史样本上的表现

也就是说，复盘能帮助判断 Scanner 最近几天是否实用，但它不等同于“这套规则长期有效”的结论。

### 导出摘要

`/scanner` 当前支持导出紧凑 Markdown 日评摘要，默认包含：

- watchlist 日期
- shortlist 候选
- concise reason / risk / watch context
- 当前 run 的跨日变化摘要
- 当前 run 的轻量复盘摘要

这更适合手工复盘、分享或留档，不等同于正式研究报告。

## 已知限制

当前版本**有意不做**以下能力：

- 不做自动交易或下单
- 不做黑盒机器学习评分
- 不做无边界全市场盲扫
- 不把 Scanner 合并进 Backtest 产品
- 不做 tick 级别或盘口级别的成交归因复盘
- 不把新闻/公告/事件作为第一版硬依赖
- 不做完整策略调参或信号编排引擎
- 不做可视化调度编排中心
- 不做复杂的多租户通知编排
- 不做 paper trading 或自动执行

当前复盘还存在几个明确限制：

- 结果跟踪依赖本地 `stock_daily` 完整度；若数据未更新，会显示为待复盘或部分复盘
- benchmark 对比只在本地存在对应指数日线时启用，不会伪造结果
- 当前主要基于日线 close/high/low 做 follow-through 统计，不判断竞价细节、分时路径或真实可成交性

## 面向未来的美股扩展路径

当前代码已保留 `us_preopen_v1` profile 作为架构扩展点，但尚未实现具体 scanner 逻辑。未来若增加美股支持，建议沿以下方向扩展：

- 新增独立的 `ScannerMarketProfile`
- 使用适合美股盘前的 universe 构建规则
- 替换 A 股特有的涨跌停 / 板块语义
- 引入更适合美股的 pre-market / news / earnings / gap 特征
- 保持 Scanner / Analysis / Backtest / Execution 的边界不变
