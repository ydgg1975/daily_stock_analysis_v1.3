# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

> For user-friendly release highlights, see the [GitHub Releases](https://github.com/ZhuLinsen/daily_stock_analysis/releases) page.

## [Unreleased]

<!-- 新条目格式：- [类型] 描述（类型取值：新功能/改进/修复/文档/测试/chore）-->
<!-- 每条独立一行追加到本段末尾，无需分类标题，合并时冲突最小 -->
- [改进] Docker 镜像安全性增强：切换默认运行用户为非 root 用户 `dsa`，降低容器溢出风险。 
- [改进] 实时行情接口安全性增强：升级 Sina 和 Tencent 实时行情接口至 HTTPS 协议，防止敏感金融数据在传输过程中被窃听或篡改。 
- [修复] 修正 `data_provider/akshare_fetcher.py` 中的多处拼写错误及日志文案。 

- [测试] 补齐 AI 配置页与 task_queue 的 LLM 运行时清理/同步回归证据：恢复渠道模型时保留 fallback、编辑模型列表期间不静默清空运行时选择，渠道无可用模型时清理失效 runtime 引用，并覆盖 legacy key 与 `cohere/*`、`google/*`、`xai/*` 直连 provider 保留语义；验收项明确包含 `tests/test_task_queue_config_sync.py`。
- [新功能] 自定义 Webhook 支持 `CUSTOM_WEBHOOK_BODY_TEMPLATE` JSON body 模板，便于适配 AstrBot、NapCat 和自建推送服务。
- [新功能] 大盘复盘结构化区块新增大盘红绿灯结论，基于盘面温度输出 green/yellow/red、核心原因和操作建议。
- [修复] 统一持仓快照输出现价/市值/浮盈亏/收益率与价格元信息，并为 LLM 渠道测试补充结构化诊断与设置页排障提示。
- [文档] 补充 LLM 渠道编辑器的官方来源、依赖兼容窗口、保存时的运行时模型清理规则，以及旧配置回退路径说明。
- [文档] 为 `cohere/*`、`google/*`、`xai/*` 直连语义补充官方 provider/model 说明、`litellm>=1.80.10,<1.82.7` 兼容依据引用，并明确示例模型名仅为配置保留行为说明而非可用性背书。
- [改进] Bot `/status` 展示统一 LLM 主模型、Agent 模型、渠道模式、YAML 配置和更多通知渠道状态。
- [修复] 明确 runtime 清理兼容边界：仅对托管 provider（`gemini`、`vertex_ai`、`anthropic`、`openai`、`deepseek`）触发保存前失效值清理，`cohere/*`、`google/*`、`xai/*` 直连值按 legacy 兼容路径保留，不做无提示迁移或覆写。
- [改进] Web LLM 渠道编辑器补齐 MiniMax 与火山方舟预设，并新增常用服务商 `.env` 模板速查文档。
- [修复] 将 MiniMax 预设调整为官方 OpenAI-compatible Base URL 和当前模型示例，并补充 MiniMax、火山方舟、LiteLLM 兼容来源与回退说明。
- [改进] Web LLM 渠道编辑器补齐 MiniMax 与火山方舟预设，并将常用服务商默认模型示例同步到 OpenAI、Claude、Gemini、Kimi、Qwen、GLM、MiniMax、豆包等官方当前推荐模型。
- [修复] 将 MiniMax 预设调整为官方 OpenAI-compatible Base URL 和当前模型示例，并补充各 LLM 渠道最新模型来源、兼容边界与回退说明。
- [修复] 移除截图识别对 Gemini 3 Vision 模型的过时降级逻辑，默认推断改用当前 Gemini 模型配置。
- [新功能] EventMonitor 支持 `price_change_percent` 涨跌幅阈值规则，可按上涨或下跌方向触发实时告警。
- [文档] 明确 `price_change_percent` 事件告警仅为配置与运行时规则扩展，未变更模型/provider/base URL/LiteLLM 兼容语义；回退路径为关闭/移除 Event Monitor 配置；兼容验证与回归依据见 `tests/test_multi_agent.py`、`tests/test_system_config_service.py`。
- [chore] 抽出 Web LLM provider preset 单一模板数据源，保持现有配置保存语义不变。
- [改进] 补齐 LLM provider channel 在 GitHub Actions 中的显式映射，并同步 `.env` 示例与配置文档。
- [改进] Web LLM 渠道编辑器展示 provider 能力标签、官方来源链接和配置注意事项提示；这些标签仅用于配置参考，不代表运行时能力已验证通过。
- [改进] Docker 镜像安全性增强：切换默认运行用户为非 root 用户 `dsa`，降低容器溢出风险。
- [改进] 实时行情接口安全性增强：升级 Sina 和 Tencent 实时行情接口至 HTTPS 协议，防止敏感金融数据在传输过程中被窃听或篡改。
- [修复] 修正 `data_provider/akshare_fetcher.py` 中的多处拼写错误及日志文案。

## [3.14.2] - 2026-04-30

### 发布亮点

- 大盘复盘扩展到港股，并让 Bot `/market` 与 CLI/调度入口使用一致的交易日过滤语义。
- 问股与 Agent 链路增强配置缺失、决策 fallback 和多策略选择体验。
- LLM 与分析报告链路提升稳定性：非法 JSON 响应会继续尝试备用模型，LiteLLM DEBUG 日志默认降噪。
- 新增只读首次启动配置状态接口，为后续配置向导和 smoke run 奠定基础。

### 新功能

- 大盘复盘支持港股市场：`MARKET_REVIEW_REGION` 新增 `hk` 选项；`both` 扩展为 A股+港股+美股，并新增港股指数（HSI/HSTECH/HSCEI）复盘链路。
- 新增只读首次启动配置状态接口 `GET /api/v1/system/config/setup/status`，用于识别 LLM、Agent、自选股、通知和本地存储配置缺口；该接口不会重载运行时、写入 `.env` 或创建数据库文件。

### 改进

- 问股页面支持组合选择多个 Agent 策略。

### 修复

- Bot `/market` 命令复用 `get_open_markets_today()` / `compute_effective_region()` 做交易日过滤：结果作为 `override_region` 透传给 `run_market_review`；若结果为空字符串则跳过复盘并推送“今日相关市场休市”，与 CLI/调度入口行为一致。
- 问股 Agent 在未配置可用 LLM 时保留后端真实错误原因并维持 `done.success=false` 失败语义，避免前端把配置缺失误当成成功回答。
- Agent 模式未生成有效决策仪表盘时保留本地趋势分析的评分、趋势和操作建议，并将强买/强卖 fallback 归一到兼容的 `buy`/`sell` 决策类型，避免首页结果被 `50 / 观望 / 未知` 缺省值覆盖。
- 持仓快照现价缺失时不再静默回退为持仓成本；当天快照优先使用历史收盘价，仅在缺失时使用实时价 fallback，缺价持仓不再污染市值与未实现盈亏汇总，并为持仓明细返回价格来源、日期、stale 与缺价状态。
- 分析 Prompt 在注入 `trend_analysis` 前按最终 `trend_status` / `ma_alignment` 清洗互斥理由：空头结构移除看多理由、多头结构移除空头结构风险，并在事件/技术冲突与异常放量（>10 倍）时强制提示“事件先行、技术待确认”与量能降权。
- LLM 返回非 JSON 响应时同样触发备用模型切换：主模型成功返回但无法解析 JSON 时，不再立即降级为纯文本 fallback，而是依次尝试 `LITELLM_FALLBACK_MODELS` 中的备用模型；所有模型均无法返回合法 JSON 时，再降级为文本 fallback。
- LiteLLM 内部 DEBUG 日志默认压低到 WARNING，避免流式生成时 token 级日志污染 `stock_analysis_debug_*.log`；如需排查 LiteLLM 内部细节，可临时设置 `LITELLM_LOG_LEVEL=DEBUG`（Fixes #1156）。

### 文档

- 补充 LLM 配置指南与 FAQ，明确问股 Agent 对 `LITELLM_CONFIG` / `LLM_CHANNELS` / legacy `GEMINI_*` `OPENAI_*` `ANTHROPIC_*` 的兼容优先级、回退路径与“不静默迁移旧配置”的结论。

### 测试

- 新增 `tests/test_bot_market_command.py`，覆盖 `MARKET_REVIEW_REGION=both` + open markets `{"cn","us"}` / `{"cn","hk"}` 的 `override_region` 透传断言，并覆盖全市场休市跳过与关闭交易日检查路径；新增 `tests/test_yfinance_hk_indices.py` 覆盖港股指数符号映射与部分/全部失败降级路径。
- 补齐 `task_queue` 轻量导入 stub 的股票代码规范化函数，恢复 `tests/test_task_queue_config_sync.py` 收集与运行。

## [3.14.1] - 2026-04-26
- [测试] 修正大盘复盘 prompt 测试对“明日交易计划”标题的断言，并同步桌面端版本号，恢复发布 gate。

## [3.14.0] - 2026-04-26

### 发布亮点

- 📊 **大盘复盘升级为盘后工作台式结构** — A 股复盘固定输出盘面温度、指数明细、板块 Top 表、新闻催化、明日交易计划和风险提示，减少纯文字复盘的重复与空泛。
- 🖥️ **桌面端新增 GitHub Release 更新提醒** — Windows/macOS 桌面端启动后自动检测新版本，也可从设置页手动检查并跳转下载页。
- 🤖 **Pipeline Agent 数据加载大幅降噪** — K 线工具改为 DB-first 并预热 240 天历史数据，避免同一只股票重复 HTTP 请求.
- 🐳 **Docker 发布链路整理** — 发布工作流收敛为正式发布与手动补发两条路径，官方 Docker Hub 镜像名统一为 `zhulinsen/daily_stock_analysis`。
- 🔧 **LLM 渠道与 DeepSeek V4 配置补强** — GitHub Actions 定时分析补齐多渠道变量透传，DeepSeek 官方渠道预设与示例同步到 V4。
- 🧩 **桌面端静态资源一致性校验** — 打包链路和运行时都能更早发现静态资源错配，降低 Release 包白屏排查成本。

### 新功能

- 🏠 **Web 首页历史报告区新增重新分析入口** — 支持基于原始 prompt 重做同一只股票同日期的分析。
- 🖥️ **Windows/macOS 桌面端新增 GitHub Release 更新提醒** — 启动后自动检测新版本，并支持从设置页手动检查后跳转下载页.

### 改进

- 📊 **A 股大盘复盘报告改为结构化盘后工作台版式** — 固定输出盘面温度、指数明细、板块 Top 表、新闻催化和明日交易计划。
- 🐳 **Docker 发布工作流收敛** — 更清晰地区分正式发布与手动补发链路，并统一官方 Docker Hub 镜像名为 `zhulinsen/daily_stock_analysis`。
- 🤖 **Agent 日线工具优先复用本地缓存** — 同时持久化新获取的日线与新闻情报，减少重复数据源调用.

### 修复

- 🤖 **Pipeline Agent K 线工具 DB-first 加载** — `get_daily_history` / `analyze_trend` / `calculate_ma` / `get_volume_analysis` / `analyze_pattern` 改为优先读取本地 DB，消除同一只股票 9x5=45 次重复 HTTP 请求（Fixes #1066）。
- 🤖 **Pipeline Agent 执行前按需预热 240 天 K 线历史到 DB** — 正常情况下 K 线工具调用无需重复网络请求.
- 🕒 **冻结 `target_date` 并通过 ContextVar 透传到 Pipeline Agent K 线工具线程** — 消除跨收盘边界时间漂移.
- 🪟 **Windows 桌面端后端日志转抄编码修复** — 转抄 stdout/stderr 时优先使用 UTF-8，并兼容本地代码页回退，避免中文日志乱码.
- ⚙️ **GitHub Actions 每日分析工作流补齐 LLM 渠道变量透传** — 支持 `LLM_CHANNELS`、多 Key 与常用 `LLM_<NAME>_*`，避免本地可用的多模型配置在云端定时任务中失效（Fixes #1063, #872）。
- 📈 **历史报告详情接口修正 `change_pct` 取值** — 使用 `is None` 判断避免把 0.0（平盘）当作缺失值丢弃，移除错误的 `change_60d` 兜底，并在缺失时回退到原始实时行情字段（Fixes #1084）。
- 🔧 **DeepSeek 官方渠道预设与示例配置同步到 V4** — 保留 legacy `deepseek-chat` 默认值并增加废弃提示，同时修正模型发现后旧运行时选择导致保存失败的问题（Fixes #1108, #1109）。
- 🧩 **桌面端打包链路新增静态资源一致性检查** — `scripts/check_static_assets.py` 会在源 `static/` 与 PyInstaller 产物中校验 `index.html` 引用的资源是否真实存在，运行时也会在错配时写入明确日志，避免重现 Release 包打开后白屏（Refs #1064 / #1065 / #1050）。
- 🧩 **后端 `/assets/*` 改为显式路由托管** — 资源缺失时返回与请求扩展名匹配的 `text/javascript` / `text/css` 404，减少默认 JSON 错误响应带来的排查误导（Refs #1064）。
- 🌙 **`kimi-k2.6` 自动使用固定温度** — 主分析、大盘复盘和 Agent 调用该模型时自动使用 `temperature=1.0`，避免模型拒绝默认温度请求（Fixes #1102）。

### 文档

- 🐳 **补充官方 Docker 镜像使用说明** — 增加镜像拉取、`docker run` 用法与 `.env` / 数据目录映射说明，不再只覆盖 Compose 部署路径.
- 📨 **修正飞书自定义机器人 Webhook 示例** — `feishu_sender.py` 中的示例改为 interactive card JSON，并补充飞书自动化 Webhook 触发器配置教程.
- 📚 **优化根 README 结构** — 保留首页级功能特性、技术栈、快速开始、推送效果、Web、Agent、赞助商和新闻源入口，将细配置、交易纪律和基本面语义收口到完整指南，并将 Docker 徽章指向官方镜像页.
- 🌐 **同步英文与繁中 README 的精简入口结构** — 同时补齐完整指南中的 LLM 用量 API 与持仓管理说明.
- 🤝 **调整 AI 协作与 PR 模板中的 README 维护规则** — 明确 README 非必要不更新，细节优先进入专题文档.

### 测试

- 🧪 **稳定市场复盘相关测试的 LiteLLM stub 行为** — 避免本机安装的 LiteLLM 在测试收集顺序变化时影响市场复盘单元测试.
- 🧪 **pytest 默认跳过前端依赖目录** — 本地存在 `apps/dsa-web/node_modules` 时不再被后端测试递归扫描，避免发布前 gate 被无关目录拖慢.

## [3.13.0] - 2026-04-21

### 发布亮点

- 🌉 **长桥 OpenAPI 数据源接入** — 美股/港股行情优先使用 Longbridge，YFinance / AkShare 自动兜底；未配置时行为不变.
- 📈 **Tushare 港股全链路扩展** — 港股日线通过 `hk_daily` 获取；筹码分布对港股返回 `None`；换算单位跟随港股口径，不再套用 A 股手/千元规则.
- 🔍 **Anspire Search 语义搜索接入** — 配置 `ANSPIRE_*` 后即可使用 Anspire Search 获取实时行情及资讯，未配置时完全透明.
- 🚀 **普通分析链路支持 LLM 流式生成** — 首页任务 SSE 新增 `task_progress` 事件，进度更细化；不支持流式的 provider 自动回退到非流式调用.
- 🤖 **Web 渠道编辑器支持按需拉取可用模型列表** — `/v1/models` 统一模型发现入口，多选写回 `LLM_{CHANNEL}_MODELS`，拉取失败时保留手动输入降级.
- 🛡️ **Agent 稳定性与预算护栏全面补强** — `AGENT_MAX_STEPS` 语义统一、技能降级不中断管线、SSE 异常透传、技能加载 warning 日志补齐.
- 🛠️ **SQLite 写入链路原子化** — 批量原子 upsert + WAL + `busy_timeout` + 有限写入重试，显著降低批量分析并发锁 competition.

### 新功能

- 🌉 **集成 Longbridge OpenAPI 作为美股/港股可选数据源**（fixes #981）— 配置 `LONGBRIDGE_*` 后优先使用长桥获取日线与实时行情，YFinance / AkShare 兜底；未配置时行为与此前一致. 联调使用 `tests/longbridge_live_smoke.py`（手动脚本，不参与 pytest 收集）.
- 📈 **Tushare 支持港股日线查询** — 配置 Tushare 凭证后调用 `hk_daily` 接口获取港股数据；权限不足时抛出异常，与原流程一致.
- 🔍 **集成 Anspire Search 可选语义搜索后端** — 配置 `ANSPIRE_*` 可使用 Anspire Search 获取实时行情及新闻资讯；未配置时行为与此前一致. 联调使用 `tests/test_anspire_search.py`（手动脚本）.
- 🚀 **普通分析链路支持 LiteLLM 流式生成与更细任务进度** — 股票分析在 LLM 阶段优先尝试 `stream=True` 并在服务端累积 chunk，首页任务 SSE 新增 `task_progress` 事件与更细的 `message/progress` 更新；仅在最终 JSON 解析成功后持久化历史报告；不支持流式的 provider 自动回退到非流式调用.
- 🤖 **Web AI 模型配置支持按渠道获取可用模型列表** — 渠道编辑器支持调用 `/v1/models` 拉取可用模型，并以多选方式写回 `LLM_{CHANNEL}_MODELS`；拉取失败时保留手动输入作为降级路径.

### 改进

- 🔎 **SerpAPI 正文补抓范围收敛** — 自然搜索结果不再逐条同步抓取网页正文；仅对极少数高位且摘要不足的结果做延迟补抓，优先复用 SerpAPI 已返回的结构化摘要，降低搜索链路尾延迟与慢站点放大风险.
- 🤖 **LLM 接入体验简化** — 面向用户的 AI 模型接入文案统一为"主模型 / Agent 主模型 / 备选模型 / 模型渠道"，不再把 LiteLLM 当作普通用户必学概念，现有 `LITELLM_*` / `LLM_CHANNELS` 配置键保持兼容.
- 🧠 **IntelAgent 新增公司公告搜索与主力资金流工具** — 增加上交所/深交所/cninfo 公告搜索维度与 `get_capital_flow` 工具，修复 Agent 模式下公告和资金流数据经常缺失的问题.
- 📦 **后端股票名称解析优先复用 `stocks.index.json`** — 懒加载缓存前端静态索引，纯后端/缺失静态资源场景静默降级回 `STOCK_NAME_MAP` 与原有数据源回退链路.
- 📊 **TushareFetcher 港股单位适配** — `get_chip_distribution` 对港股直接返回 `None`（港股暂不支持筹码分布）；`_normalize_data` 对港股（`hk_daily`）不再做 A 股手→股、千元→元的缩放，与 Tushare 港股字段语义一致.
- ⏱️ **Agent 超步数错误增加 `AGENT_MAX_STEPS` 调整提示** — 帮助用户自助排查步数限制问题.
- ⚙️ **GitHub Actions 分析任务超时支持 `vars` 配置** — `daily_analysis.yml` 任务超时从 repository variables 读取，无需修改代码即可调整运行超时上限（fixes #1014）.

### 修复

- 📣 **大盘复盘链路接入 `REPORT_LANGUAGE`** — `REPORT_LANGUAGE=en` 时，A 股/合并复盘的 Prompt、章节标题、模板兜底文案与通知包装标题统一输出英文，避免英文正文搭配中文标题的混排问题.
- 📈 **EfinanceFetcher 指数开盘价映射兼容**（fixes #1043）— `get_main_indices()` 的开盘价映射改为兼容 `今开 → 开盘 → open`，修复部分 efinance 版本下指数开盘价被读成缺失值的问题.
- 🤖 **AGENT_MAX_STEPS 语义统一**（fixes #1026）— 在 orchestrator 多 Agent 模式下明确为"各子 Agent 步数上限而非硬覆盖"；TechnicalAgent 等高默认值 Agent 会被封顶，低默认值 Agent 保持原值；用户主动调高（>10）时统一覆盖所有子 Agent. 修复了用户设置 12 但 TechnicalAgent 仍以默认 6 步运行并报 "Agent exceeded max steps" 的问题.
- 🛡️ **Specialist（Skill）Agent 失败改为优雅降级** — 技能 Agent 失败不再中断整个分析管线，与 intel/risk 保持相同的降级策略.
- 🔧 **MiniMax-M2.7 连接测试修复** — 修复 LLM 通道连接测试在 MiniMax-M2.7 下返回 "Empty response" 的问题；将 `max_tokens` 上限从 8 提升至 256 以容纳思考过程，并添加 `content_blocks` 格式解析逻辑.
- 📊 **移除 `sentiment_score` 范围约束**（fixes #942）— 移除 `HistoryItem` 与 `ReportSummary` 响应 Schema 中 `sentiment_score` 的 `ge=0/le=100` 约束，历史库中存储的超范围值不再触发 Pydantic ValidationError.
- 🖥️ **WebUI 前端资源缺失时发出明确警告** — `webui_frontend.py` 在 `static/index.html` 存在但 `static/assets/` 缺失时发出 warning，避免 CSS/JS 资源缺失导致页面异常变大却无从排查（fixes #944）.
- 🔗 **分析管线可选服务降级初始化** — `StockAnalysisPipeline` 搜索服务与社交舆情服务任一初始化异常时，记录 warning 并以禁用状态继续运行，避免外部依赖抖动阻塞主分析链路.
- 🖥️ **桌面端版本展示统一读取 `package.json`** — 统一读取 `apps/dsa-desktop/package.json`，移除 preload 中硬编码的 `0.1.0`，设置页展示真实桌面端版本；修复版本号显示错误（fixes #1048）.
- 🐋 **港股名称获取失败修复**（fixes #940）— 修复主数据源字段缺失时无法正确回退到备用字段获取港股名称的问题.
- 🔄 **SSE 任务流断开时 `CancelledError` 正确 re-raise**（fixes #967）— 修复 SSE 流中断时异常被静默吞掉导致故障无日志可查的问题.
- 🔄 **Agent SSE 清理阶段后台任务异常正确上报**（fixes #969）— 流结束时后台执行器异常现在正确记录并上报，避免错误无法感知.
- 🔇 **技能加载异常补充 `logger.warning` 日志**（fixes #970）— 在 `ask.py`、`skills/aggregator.py`、`skills/router.py` 的静默 except 块补充日志，确保技能列表为空时有日志可查.
- 🛠️ **SQLite 写入链路原子化**（fixes #878）— `stock_daily(code,date)` 使用批量原子 upsert；文件型 SQLite 连接默认启用 WAL + `busy_timeout` + 有限写入重试；"新增数"改按本次真正插入窗口计算.
- 💰 **多 Agent / 单 Agent 预算护栏语义统一** — 剩余预算低于最小阈值时主动跳过并降级；已完成阶段可构建降级报告时返回 `success=True` 并携带非空内容，否则返回 `success=False`.
- ⚙️ **GitHub Actions `daily_analysis.yml` 补齐 `REPORT_LANGUAGE` 注入**（fixes #1013）— 修复用户在 Secrets/Variables 中配置 `REPORT_LANGUAGE` 后不生效的问题.
- 📊 **任务状态 API 补齐实时价格字段**（fixes #983）— `GET /api/v1/analysis/status/{task_id}` 从数据库回填已完成任务时补齐 `current_price` / `change_pct`，修复首页报告股票名旁不显示实时价格的问题.
- 📅 **非交易日数据返回最近交易日**（fixes #1009）— 修复非交易日（周末/节假日）筹码分布与板块排行返回倒数第二个交易日数据的问题，现在正常返回最近交易日数据.
- 🔍 **A 股资讯搜索恢复中文优先** — `search_stock_news()` 在首个 provider 主要返回英文资讯时继续尝试后续引擎，并将同批结果中的中文资讯排到前面；非美股查询不再默认沿用 Brave 的 `en/US` 区域语言偏好.
- 📨 **飞书群机器人通知支持签名校验** — 飞书通知现在支持 `FEISHU_WEBHOOK_SECRET` / `FEISHU_WEBHOOK_KEYWORD`；Web 设置与文档明确区分 Webhook 推送模式和 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 应用模式，降低误配风险.
- ⚡ **LLM 适配层新增 `RateLimitError` 和 `ContextWindowExceeded` 检测** — 识别并处理速率限制与上下文窗口超出错误，提升分析链路在高负载或长文本场景下的健壮性（fixes #1002）.

### 测试

- 🧪 **TushareFetcher 港股相关单元测试** — 新增 `get_chip_distribution` 筹码分布获取与 `_normalize_data` 港股/A 股/ETF 单位处理的单元测试，覆盖港股特殊路径.

### 文档

- 📘 **DEPLOY.md 补充 UI 元素异常变大排查步骤** — 新增重建 Docker 镜像或手动执行 `npm run build` 的排查指南；`deploy-webui-cloud.md` 同步更新.
- 📨 **飞书 Webhook 配置说明补全** — 强调 `FEISHU_WEBHOOK_URL` 是群通知必填项、签名校验须两端同时启用或关闭、`FEISHU_APP_SECRET` 仅用于应用/Stream Bot 模式；`.env.example` 补充内联注释；同步英文指南.
- 🤝 **FAQ 补充 Ollama 连接失败排障条目（Q12c）** — 覆盖服务未启动、URL 配置错误、模型前缀缺失、模型未下载、远程防火墙等 5 个检查点（fixes #854）.
- 🌉 **README 补充长桥数据源使用说明** — 中/英/繁 README 明确长桥"首选 / 兜底 / 未配置不调用"边界；`docs/` 内相对路径链接修复；`LONGBRIDGE_PRINT_QUOTE_PACKAGES` 配置与代码及 `.env.example` 对齐.
- 🐋 **Docker 安装场景版本说明** — 补充最小化文档，明确 Docker 安装场景下应以 Git tag / 镜像 tag 判断版本（fixes #1091）.

## [3.12.0] - 2026-04-01

### 发布亮点

- 📊 **回测页新增"次日验证"视图** — 可按股票与日期范围查看 AI 预测 vs 次日实际涨跌，复用历史分析与 1 日回测结果，快速验证分析准确率.
- 🔧 **LLM 接入体验简化** — 用户侧文案统一收口为"主模型 / 备选模型 / 模型渠道"，不再把 LiteLLM 当作普通用户必学概念，现有配置键保持兼容.
- 🐳 **Docker / WebUI 运行时稳态补强** — 修复系统设置保存后配置不生效、启动早期日志缺失、预构建静态资源复用等问题，降低容器化部署的运维摩擦.
- 🔒 **安全与并发稳定性同步增强** — Discord 入站 Webhook 补齐 Ed25519 验签，修复并发执行时共享状态未加锁、单股推送模式通知并发复用等问题.
- 🖥️ **桌面端与定时任务细节打磨** — Windows 安装器支持自选安装目录，内置定时调度器感知运行中 SCHEDULE_TIME 变更，断点续传改按市场时区判断.

### 新功能

- 📊 **回测页新增"次日验证 / 1 日窗口"视图** — 可按股票代码与分析日期范围查看 AI 预测、次日实际涨跌及筛选区间准确率，复用历史分析与 1 日回测结果实现.
- 🏷️ **Web 设置页新增版本信息卡片** — `apps/dsa-web` 现在会在构建时注入 frontend package version and build time; system settings page adds a read-only "Version Info" section showing `WebUI Version / Build ID / Build Time`; when `package.json` is still the placeholder `0.0.0`, it auto-falls back to the build ID, helping users confirm if static assets took effect after a Docker rebuild.
- 🪟 **Windows 桌面安装器支持自选安装目录** — Installation wizard now supports custom directories; persists config/db/logs alongside the executable even when installed on non-default drives. Only supports current-user installs, with UAC elevation disabled and system protection path guards.

### 改进

- 🔎 **SerpAPI 正文补抓范围收敛** — Natural search results no longer crawl full body text synchronously for every entry; only rare high-rank items with insufficient snippets trigger delayed body fetching within a tight timeout budget, prioritizing structured snippets to reduce tail latency.
- 🤖 **LLM 接入体验简化** — User-facing AI terminology consolidated to "Primary / Agent Primary / Fallback / Channel / Advanced Routing"; Web UI, metadata, and docs no longer require LiteLLM knowledge by default while maintaining compatibility for `LITELLM_*` and `LLM_CHANNELS` keys.

### 修复

- 🚀 **启动早期失败时暴露真实根因** — `python main.py` now exposes the true root cause via stderr during bootstrap; delays log file creation until `config.log_dir` is validated to prevent junk log files in unintended paths.
- 🐳 **Docker WebUI 运行时优先复用预构建静态资源** — `prepare_webui_frontend_assets()` checks for pre-existing `static/index.html` within the image; prevents false-positive "frontend project not found" errors in production containers missing `npm` or source code.
- 🐳 **Docker WebUI 系统设置保存后配置生效** — Config now prioritizes reading from the persisted `.env` over initial container environment variables for `STOCK_LIST` and schedule-related toggles.
- 📈 **市场复盘 LLM max_tokens 提升** — Increased market review generation `max_tokens` from `2048` to `8192` to reduce truncation risk for long reports.
- ⏰ **内置定时调度器感知 SCHEDULE_TIME 运行时变更** — Scheduler now detects runtime changes to `SCHEDULE_TIME` from the Web UI and re-binds the daily job on the next tick.
- 🪟 **Windows Release 渠道编辑器保留 MiniMax 模型前缀** — Backend normalization and Web UI lists now preserve `minimax/<model>` verbatim instead of erroneously prefixing with `openai/`.
- 🤖 **Discord 入站 Webhook 补齐 Ed25519 验签** — `DiscordPlatform` now validates Ed25519 signatures and timestamps (±5 min window) for Discord Interactions to prevent replay attacks and unauthorized spoofing.
- ⚙️ **STOCK_GROUP_N / EMAIL_GROUP_N 配置关系明确化** — Clarified relationships with `STOCK_LIST` and added config warnings for email groups exceeding the global stock list.
- 🗓️ **断点续传改按市场时区和交易日历判断**（fixes #880）— Data existence checks now use market-specific timezones (A-share/HK/US) to determine the "latest reusable trading day" instead of generic server wall-clock time.
- 📨 **单股推送模式不再并发复用共享通知实例** — `StockAnalysisPipeline.run()` maintains parallel analysis but serializes result delivery when `SINGLE_STOCK_NOTIFY=true` to ensure notification integrity.
- 🔇 **实时行情降级提示收口为单次告警** — Analysis flow no longer triggers premature realtime lookups just for stock names; only warns about falling back to historical close if all data sources fail.
- 🔍 **A 股中文资讯搜索恢复中文优先** — `search_stock_news()` retries subsequent providers if the first returns primarily English results for non-US stocks; prioritizes Chinese results in grouped batches.
- 🔒 **并发执行时共享状态补齐统一加锁** — Fixed missing synchronization for shared internal state during concurrent analysis runs.

### 测试

- 🧪 **补充设置页版本信息回归测试** — Added assertions for version card rendering and the `0.0.0` fallback logic.
- 🧪 **UI 治理与关键路径回归补强** — Added governance guards against native `title` attributes and old terminal styles; updated smoke tests for `SidebarNav`, `ChatPage`, and `BacktestPage` following the theme upgrade.

## [3.11.0] - 2026-03-27

### 发布亮点

- 🎨 **Web 工作台完成一轮 UI 统一与双主题升级** — 首页、问股、回测、持仓和设置页进一步收口到统一设计 token、输入表面和状态表达；新增完整浅色主题，并支持一键切换。
- 🤖 **Bot / Agent 能力重新补回主分支** — 恢复 `/history`、`/strategies`、`/research` 等命令，`/ask` 继续支持多股对比；Deep Research 与事件监控重回 Web 设置页。
- 🔒 **安全性与运行稳态同步补强** — 修复 IP 伪造限流绕过风险；恢复官方 PyPI 安装路径；Tushare 初始化不再依赖本地 SDK，提升了环境移植性。
- 🖥️ **日常使用细节继续打磨** — 修复首页港股自动补全、登录页主题闪烁、长股票名重叠及 Telegram Markdown 解析兼容性。

### 新功能

- 🎨 **全新浅色主题与双主题切换上线** — Web 工作台新增完整浅色主题, 并支持在侧边栏中一键切换浅色 / 深色模式；主题选择会持久化保存, 刷新页面后仍保持当前偏好. 此次升级不是局部配色微调, 而是对卡片层级、边界对比、输入表面、状态提示和页面背景做了一整套 light theme 重绘.
- 🤖 **补回主分支缺失的 Agent / Bot 能力** — `#648` / `#649` has been backfilled into `main`: Bot restores `/history`, `/strategies`, `/research`, `/ask` keeps multi-stock comparison and portfolio views; Deep Research and Event Monitor config reappears in Web settings and is editable.

### 改进

- 🖥️ **核心页面统一到同一套工作台视觉语言** — `Home / Chat / Backtest / Portfolio / Settings` converged to shared design tokens, `input-surface` input system, and semantic drawers, reducing visual fragmentation.
- 💬 **问股交互可达性与反馈增强** — Chat page enhances message output, notification sends, message copy, history clear, and context follow-up hints; AI response interactions no longer rely heavily on hovering.
- 📊 **回测与持仓页表面和状态表达继续标准化** — Backtest control filters, boolean states, results table, and summary cards unified to shared primitives; portfolio feedback input and alert info further unified.

### 修复

- 🌗 **Web 首屏默认主题预设为深色** — `apps/dsa-web/index.html` now reads locally saved theme preference before React mount; if no saved value, immediately sets `dark` to `<html>` and syncs `color-scheme`, avoiding light theme flash on first screen.
- 🔐 **登录页独立主题层收口** — Login page inputs, labels, toggles, and button text now use independent `--login-*` visual tokens, no longer inheriting global light/dark text colors; login page remains visually stable with dark theme and cyan password input even when browser caches light theme.
- 🖥️ **首页港股代码输入修复** — Web home analysis input now correctly accepts HK stock codes and auto-completes selected HK items, backfilling `00700.HK` / `HK00700` formats.

- 🔒 **认证限流 X-Forwarded-For 取值修复（CWE-345）**（#841 / #842）— `get_client_ip()` changed from leftmost to rightmost `X-Forwarded-For` value to prevent bypass of brute-force protection via header spoofing.
- 📦 **恢复 LiteLLM 官方 PyPI 安装并锁定安全上限** — `requirements.txt` reverts to official `pip install litellm` from PyPI, keeping the minimum `>=1.80.10` while adding `<1.82.7` safety cap to avoid risky yanked versions.
- 📨 **Telegram Markdown 解析失败回退纯文本**（fixes #850）— `src/notification_sender/telegram_sender.py` now automatically drops `parse_mode` and retries with plain text on Telegram `HTTP 400` parse errors.
- 🔢 **A 股同码实时行情保留交易所提示**（fixes #852）— `DataFetcherManager` and `TushareFetcher` now preserve `SZ000001` / `000001.SZ` type exchange indicators to avoid legacy Tushare identification errors.
- 🎯 **多 Agent 次优买点不再盲目复制理想买点**（fixes #851）— When multi-agent results lack independent `secondary_buy`, the dashboard now prefers `N/A` instead of hard-copying `ideal_buy`.
- 🧩 **Tushare 初始化不再强依赖本地 SDK 包** — `TushareFetcher` now directly uses the built-in HTTP client to access Tushare Pro, no longer requiring `import tushare` during early bootstrap.
- ⚙️ **`daily_analysis` 工作流补齐 `DEEPSEEK_API_KEY` 映射** — GitHub Actions daily analysis workflow now correctly passes `DEEPSEEK_API_KEY`.
- 🖥️ **历史列表过长股票名称截断与悬停展示**（fixes #815）— Long stock names in history list now auto-truncate based on char type (EN 15 / CN 8 / Mix 10), defaulting to truncated results with full name on hover.

### 文档

- 🧾 **README 捐赠入口更新为小红书二维码** — README and multilingual instructions updated to Xiaohongshu QR code for consistency.

## [3.10.1] - 2026-03-24

### 新功能

- 🔔 **Web 端分析推送通知开关**（#808）— Home page analysis button now has a "Send Notification" checkbox; API `POST /api/v1/analysis/analyze` adds `notify` field (`bool`, default `true`).

### 改进

- 🖥️ **问股 / 回测页面布局与壳层协同优化** — Unified Chat / Backtest page containers, sharing status UI and follow-up Q&A interaction paths.
- 🎨 **全局视觉与共享组件继续收敛** — Light theme introduces dynamic HSL shadow system; moved scattered inline styles into semantic CSS variables for consistency.

### 修复

- 🖼️ **系统设置智能导入文件选择恢复** — fixed "Choose Photo / Choose File" button in "System Settings > Basic > Smart Import" not responding.
- 🖥️ **移动端滚动与交互层级修复** — resolved z-index conflict where theme switch menu was obscured by main content on mobile.
- 🧾 **Markdown 纯文本复制清洗增强** — improved plain-text export algorithm; copying analysis reports now more reliably removes Markdown artifacts.
- 🧠 **Trading philosophy injection 覆盖 legacy + Agent 全链路**（#810）— `GeminiAnalyzer`, single-agent mode, and skill-aware Prompts now share the same strategy injection state.
- 🛠️ **后端 CI 依赖安装链路稳态化**（#835）— Split backend gate stages and added retries for dependency installation.
- 🪟 **Windows 桌面发版构建恢复 LiteLLM 安装兼容性** — `scripts/build-backend.ps1` now pre-filters GitHub LiteLLM packages and installs locally to bypass Poetry wheel errors.

### 测试

- 🧪 **问股 / 回测 / 智能导入回归覆盖补齐** — Sync'd E2E smoke expectations and related interaction regressions.

## [3.10.0] - 2026-03-24

### 发布亮点

- 🔎 **自动补全与索引工具扩展到三市场** — Indexing chain now covers A-shares, HK stocks, and US stocks, improving the home search experience.
- 🖥️ **Dashboard 与报告查看体验继续收口** — Home Dashboard panels, state boundaries, font hierarchy, and report table density have completed a unification round.
- 🤖 **Agent skill 与市场语义边界更清晰** — Skill bundles, default strategies, backtest summary semantics, and compatibility interfaces further narrowed.
- ⏰ **定时与桌面配置能力更贴近真实使用场景** — Desktop supports `.env` import/export; scheduled tasks now follow the latest saved `STOCK_LIST`.
### 新功能

- 💾 **桌面端 `.env` 备份/恢复入口**（#754）— Desktop settings page adds `Export .env` / `Import .env` buttons.
- 📊 **Tushare 股票列表获取工具** — Added `scripts/fetch_tushare_stock_list.py` to fetch A/HK/US stock lists from Tushare Pro.
- 🔎 **索引生成脚本多市场支持** — `generate_index_from_csv.py` refactored to support Tushare and AkShare dual data sources.
- 🔎 **索引生成脚本增强** — `generate_stock_index.py` adds `--test` mode and detailed export.
- 📋 **首页完整报告支持双模式复制** — History report header adds "Copy Markdown Source" and "Copy Plain Text" buttons.
- 🧩 **个股分析页补齐关联板块展示**（#669）— A-share analysis now records `belong_boards` into `fundamental_context`.

### 改进

- 🖥️ **Dashboard 面板统一化（PR7-2）** — Added `DashboardPanelHeader` and `DashboardStateBlock` as shared components.
- 🖥️ **HomePage 状态边界收口（PR7-2）** — Introduced `useHomeDashboardState` hook, centralizing `stockPoolStore` state selection.
- 🧭 **Agent skill 统一到单一配置语义** — Multi-Agent runtime, API, and metadata unified around a narrowed `skill` concept.
- 🔎 **自动补全索引数据更新** — Re-generated `stocks.index.json`, covering A/HK/US markets.
- 🧾 **Dashboard 字体与完整报告表格密度微调** — Narrowed sidebar font levels and adjusted report table spacing for consistency.

### 修复

- ⏰ **定时模式不再锁定启动时 CLI 股票快照** — Scheduled executions now re-read the latest `STOCK_LIST` before each run.
- 🌍 **LLM Prompt 按股票市场动态注入上下文** — System Prompt identifies A, HK, or US stock codes and injects appropriate role descriptions.
- 🔎 **美股自动补全复用 ticker 去重** — `generate_index_from_csv.py` now merges US tickers by `ts_code` to avoid duplicates.
- 🧾 **Web 报告详情复制交互稳定性修复**（#749）— Fixed copy button visibility and feedback in `ReportDetails`.
- 📊 **Agent skill 回测与兼容接口语义收敛** — `get_skill_backtest_summary` now requires an explicit `skill_id`.
- 🔧 **Skill 默认选择与兼容层行为加固** — Strategy choice no longer stealthily adds bull-trend baselines.

### 测试

- 🧪 **Dashboard 组件测试覆盖率扩展（PR7-2）** — Added `ReportNews` and `TaskPanel` tests.
- 🧪 **多市场索引生成测试补齐** — Added tests for Tushare/AkShare dual source parsing.
- 🧪 **关联板块写入与 API 契约回归** — ensured `belong_boards` / `sector_rankings` extension fails open.
- 🧪 **定时模式股票列表语义回归测试** — Covered scheduled mode's bypass of initial `--stocks` snapshots.

### 文档

- 📘 **新增 Tushare 股票列表工具文档** — Added `docs/TUSHARE_STOCK_LIST_GUIDE.md`.
- 🌍 **补齐定时模式与关联板块的双语说明** — Clarified `STOCK_LIST` hot-reloading in scheduled mode.
- 🧭 **调整 Agent 术语兼容文案** — Backfilled `skill` as internal naming while keeping "Strategy" for users.

## [3.9.0] - 2026-03-20

### 发布亮点

- 🤖 **模型链路与报告语言更灵活** — Agent can choose an independent model chain via `AGENT_LITELLM_MODEL`; `REPORT_LANGUAGE` now covers both regular and Agent reports.
- 🔎 **首页分析体验完成一轮闭环优化** — Added A-share auto-complete; Dashboard state converged to a unified store.
- 💬 **通知与检索能力继续外扩** — Added Slack support; SearXNG auto-discovery for public instances; fixed Tavily time-filtering.
- 💼 **持仓与 market review 链路更稳** — A-share market review connects to TickFlow; portfolio ledger writes are now serialized.

### 新功能

- 🔎 **Web 股票自动补全 MVP** — Home page adds local-index-driven auto-complete.
- 💬 **Slack 一等通知渠道** — Added native Slack support via Bot Token or Incoming Webhook.
- 🌍 **报告输出语言可配置**（Issue #758）— Added `REPORT_LANGUAGE=zh|en`.
- 🚀 **Agent 与普通分析模型解耦**（Issue #692）— Added `AGENT_LITELLM_MODEL`.
- 🔎 **SearXNG 公共实例自动发现与受控轮询**（#752）— Added `SEARXNG_PUBLIC_INSTANCES_ENABLED`.
- 📈 **TickFlow market review enhancement** (#632) — Added optional `TICKFLOW_API_KEY` for index and gain/loss statistics.

### 改进

- **Dashboard state slice and workspace closure** — moved Home / Dashboard state into `stockPoolStore`.
- **Dashboard panel standardization** — unified history, report, news, and markdown presentation.
- **Dashboard-to-chat follow-up bridge** — routed “Ask AI” follow-ups through report-context hydration.
- 💼 **持仓账本并发写入串行化**（#742）— Portfolio trade/delete events now acquire a serialized write lock.
- 💱 **持仓页汇率手动刷新入口补齐**（#748）— Added "Refresh FX" button to Web `/portfolio`.

### 修复

- 🔎 **Web 自动补全 Enter 提交语义修正** — Enter submits original input unless a candidate was explicitly selected.
- 🌍 **补齐 `REPORT_LANGUAGE` 启动解析与历史展示本地化边界** — Localized `sentiment_label` and risk emojis in history views.
- 📰 **Tavily 时效新闻检索发布时间映射修复**（#782）— Fixed accidental filtering of Tavily results.
- 💱 **持仓页汇率刷新禁用语义修正**（#772）— Returns explicit `refresh_enabled=false` if disabled.
- 🤖 **Agent timeout and config hardening** — `AGENT_ORCHESTRATOR_TIMEOUT_S` now protects all Agent loops.
- 🌐 **CORS wildcard + credentials compatibility** — Fixed credentialed request failures in `CORS_ALLOW_ALL` mode.
- 🧭 **Unavailable Agent settings hidden from Web UI** — Removed non-functional Deep Research / Event Monitor toggles.

### 文档

- Added Ollama local model configuration guide (Fixes #690).
- Perfected Ollama configuration instructions.
- Clarified doc sync rules for multi-language and topical docs.

## [3.8.0] - 2026-03-17

### 发布亮点

- 🎨 **Web 界面完成一轮骨架升级** — New App Shell, sidebar, and theme support.
- 📈 **分析上下文继续补强** — Added social sentiment for US stocks; structured finance/dividends for A-shares.
- 🔒 **运行稳定性与配置兼容性提升** — Session invalidation on logout; improved `MAX_WORKERS` adjustment.
- 💼 **持仓纠错链路更完整** — Mis-trades and cash flows can now be deleted with cache invalidation.

### 新功能

- 📱 **美股社交舆情情报** — Added Reddit / X / Polymarket social sentiment sources.
- 📊 **A 股财报与分红结构化增强**（Issue #710）— Added `financial_report` and `dividend` fields to fundamentals.
- 🔍 **接入 Tushare 筹码与行业板块接口** — Added chip distribution and sector gain/loss rankings.
- 🧱 **Web UI 基础骨架升级** — Rebuilt shared design tokens, App Shell, and sidebar.
- 🔐 **登录与系统设置流程重做** — Refactored Login and Settings flows with explicit auth state handling.
- 🧪 **前端回归与冒烟覆盖补强** — Extended Playwright smoke coverage for critical paths.

### 变更

- 🧭 **页面接入新 Shell 布局契约** — Standardized drawer and scroll behavior across core pages.
- 💾 **设置页状态同步更稳** — Refined module-level saving and conflict handling.
- 🎭 **登录页视觉基线回归** — Restored established visual baseline while keeping new auth logic.
- 🏛️ **AI 协作治理资产加固** — Strengthened consistency constraints for governance assets.

### Added

- **Web UI foundation refresh** — rebuilt shared design tokens and primitives.
- **Settings and auth workflow overhaul** — aligned Web UI with runtime auth APIs.
- **UI regression coverage and smoke checks** — expanded targeted frontend tests.

### Changed

- **Shell-driven page integration** — aligned Home, Chat, and Backtest with the new shell layout contract.
- **Settings state consistency** — refined module-level saves and draft preservation.
- **Login visual baseline** — restored visual treatment to branch `006` baseline.

### 修复

- ⏰ **定时启动立即执行兼容旧配置**（Issue #726）— `SCHEDULE_RUN_IMMEDIATELY` falls back to `RUN_IMMEDIATELY`.
- 🧵 **运行期 `MAX_WORKERS` 配置生效与可解释性增强**（#633）— Fixed queue sync with `MAX_WORKERS`.
- 🔐 **退出登录立即失效现有会话** — `POST /api/v1/auth/logout` rotates session secret.
- 🧮 **Tushare 板块/筹码调用限流与跨日缓存修复** — Unified new data chains to `_check_rate_limit()`.
- 💼 **持仓超售拦截与错误流水恢复**（#718）— Verifies sellable quantity before recording trades.
- 📧 **邮件中文发件人名编码**（#708）— Auto-encodes `EMAIL_SENDER_NAME` via RFC 2047.
- 🐛 **港股 Agent 实时行情去重与快速路由** — Unified normalization and routed HK quotes to `akshare_hk`.
- 📰 **新闻时效硬过滤与策略分窗**（#697）— Added strictly filtered news windows.

### 文档

- ☁️ **新增云服务器 Web 界面部署与访问教程**（Fixes #686）.
- 🌍 **补齐英文文档索引与协作文档** — Added EN doc index and CN/EN issue/PR templates.
- 🏷️ **本地化 README 补充 Trendshift badge** — Consistent badges across all languages.

## [3.7.0] - 2026-03-15

### 新功能

- 💼 **持仓管理 P0 全功能上线**（#677，对应 Issue #627）
  - **核心账本与快照闭环**：Added core data models and API endpoints for portfolio management.
  - **券商 CSV 导入**：Initial support for Huatai / CITIC / Merchants.
  - **组合风险报告**：Concentration and historical drawdown monitoring.
  - **Web 持仓页**（`/portfolio`）：Full portfolio dashboard with manual entry and CSV imports.
  - **Agent 持仓工具**：Added `get_portfolio_snapshot` tool.
  - **事件查询 API**：Added trade and ledger history endpoints.
  - **可扩展 Parser Registry**：Shared registry for broker-specific CSV parsers.

- 🎨 **前端设计系统与原子组件库**（#662）
  - Introduced gradual dual-theme architecture and refactored core components.

- ⚡ **分析 API 异步契约与启动优化**（#656）
  - Standardized async return contract and optimized bootstrap logic.

### 修复

- 🔔 **Discord 环境变量向后兼容**（#659）：Added fallback for legacy channel ID keys.
- 🔧 **GitHub Actions Node 24 升级**（#665）：Upgraded official actions for long-term compatibility.
- 📅 **持仓页默认日期本地化**：Fixed date drift for manual entries in different timezones.
- 🔁 **CSV 导入去重逻辑加固**：Enhanced idempotency for legitimate split trades.

### 变更

- `POST /api/v1/portfolio/trades` returns `409` on conflict.
- Analysis API `analyze` interface behavior documented.

### 测试

- Added portfolio core service and CSV import regression tests.
- Added Agent tool call and analysis API contract tests.

## [3.6.0] - 2026-03-14

### Added
- 📊 **Web UI Design System** — implemented dual-theme architecture.
- 🗑️ **History batch deletion** — added batch clear capability in Web UI.
- 🔐 **Auth settings API** — new endpoint to enable/disable auth at runtime.
- openclaw Skill 集成指南 — 新增 [docs/openclaw-skill-integration.md](openclaw-skill-integration.md).
- ⚙️ **LLM channel protocol/test UX** — unified channel config with connection testing.
- 🤖 **Agent architecture Phase 0+1** — established shared agent protocols and loop runner.
- 🔍 **Bot NL routing** — added lightweight NL intent parsing for bot commands.
- 💬 **`/ask` multi-stock analysis** — parallel analysis for up to 5 stocks.
- 📋 **`/history` command** — per-user session isolation and management.
- 📊 **`/strategies` command** — listed available strategy YAML files.
- 🔧 **Backtest summary tools** — registered read-only Agent tools.
- ⚙️ **Agent auto-detection** — auto-detects Agent availability from model string.
- 🏗️ **Multi-Agent orchestrator (Phase 2)** — introduced orchestrated sub-agents for specialized tasks.
- 🧩 **Specialised agents (Phase 2-4)** — Technical, Intel, Decision, and Risk agents.
- 📈 **Strategy system (Phase 3)** — added strategy-specific evaluation and routing.
- 🔬 **Deep Research agent (Phase 5)** — introduced 3-phase ResearchAgent.
- 🧠 **Memory & calibration (Phase 6)** — added accuracy tracking and confidence calibration.
- 📊 **Portfolio Agent (Phase 7)** — added multi-stock portfolio risk analysis.
- 🔔 **Event-driven alerts (Phase 7)** — introduced EventMonitor for rule-based alerts.

### Changed
- 🔐 **Auth password state semantics** — password existence tracked independently of enablement.
- ♻️ **AgentExecutor refactored** — delegated to shared runner loop.
- 📖 **README.md** — expanded Bot command documentation.

### Fixed
- 🐛 **Analysis API blank-code guardrails** — rejects whitespace-only inputs.
- 🎮 **Discord channel env compatibility** — accepted legacy channel ID keys.
- 🔧 **LLM runtime selection guardrails** — fixed protocol prefixing for aliased models.
- 🐛 **Decision dashboard enum compatibility** — normalized outputs before downstream use.
- 🛟 **Multi-Agent partial-result fallback** — preserved minimal dashboards on mid-pipeline failure.
- 🐛 **P0 基本面聚合稳定性修复** (#614) — fixed boards regression and introduced token control.
- 🤖 **Multi-Agent runtime consistency** — propagated `AGENT_MAX_STEPS` to sub-agents.
- 🧪 **Multi-Agent regression coverage** — added orchestrator execution tests.
- 🚦 **Bot async dispatch** — offloaded intent parsing from the event loop.
- 🧵 **Feishu stream ThreadPoolExecutor** — capped thread spawning for message bursts.
- 🐛 **筹码结构 LLM 未填写时兜底补全** (#589).
- ⏱️ **efinance 长调用挂起修复** (#660).
- 🛡️ **runner.py usage None 防护** (#660).

### Notes
- ⚠️ **Multi-worker auth toggles** — deployments must restart workers to sync auth state.

## [3.5.0] - 2026-03-12

### Added
- 📊 **Web UI full report drawer** (Fixes #214).
- 📊 **LLM cost tracking** — recorded all calls in `llm_usage` table.
- 🔍 **SearXNG search provider** (Fixes #550).
- 🤖 **Agent background execution** — allows page switching during analysis.
- 📝 **Report Engine P0** — Pydantic schema validation and Jinja2 templates.
- 📦 **Smart import** — Vision-based extraction from images and clipboards.

### Fixed
- 🐛 **analyze_trend always reports No historical data** (#600).
- 🐛 **Chip structure fallback when LLM omits it** (#589).
- 🐛 **History sniper points show raw text** (#452).
- 🐛 **`.env` save preserves comments and blank lines**.

### Changed
- 🔎 **Fetcher failure observability** — improved error classification in logs.
- ♻️ **Image extract API response extension** — added confidence scores.

### Docs
- 📖 `image-extract-prompt.md` with full documentation.
## [3.4.10] - 2026-03-07

### Fixed
- 🐛 **EfinanceFetcher ETF OHLCV data** (#541, #527).
- 🐛 **tiktoken 0.12.0 Unknown encoding** (#537).
- 🐛 **北交所代码识别失败** (#491, #533).

### Added
- **Markdown-to-image for dashboard report** (#455, #535).
- **Stock name prefetch** — reduces placeholders in reports.

## [3.4.9] - 2026-03-06

### Added
- 🧠 **Structured config validation** — added severity-aware checks.
- 🚀 **CLI init wizard** — interactive bootstrap for new users.

### Fixed
- 🐛 **STOCK_LIST not refreshed on scheduled runs** (#529).
- 🐛 **WebUI fails to load with MIME type error** (#520).

## [3.4.8] - 2026-03-02

### Fixed
- 🐛 **Desktop exe crashes on startup** — bundled litellm data files.

## [3.4.7] - 2026-02-28

### Added
- 🧠 **CN/US Market Strategy Blueprint System** (#395).

### Fixed
- 🐛 **Agent pipeline preserved resolved stock names** (#464).

## [3.4.0] - 2026-02-27

### Added
- 📡 **LiteLLM Direct Integration + Multi API Key Support** (#454).

## [3.3.22] - 2026-02-26

### Added
- 💬 **Chat History Persistence** (Fixes #400).

## [3.3.12] - 2026-02-24

### Added
- 📈 **Intraday Realtime Technical Indicators** (#234).
- 🤖 **Agent Strategy Chat** (#367).

## [3.2.11] - 2026-02-23

### 修复（#patch）
- 🐛 **StockTrendAnalyzer 从未执行** (Issue #357).

## [3.2.10] - 2026-02-22

### 新增
- ⚙️ 支持 `RUN_IMMEDIATELY` 配置项.

## [3.2.9] - 2026-02-22

### 修复
- 🐛 **ETF 分析仅关注指数走势**（Issue #274）.

## [3.2.8] - 2026-02-21

### 修复
- 🐛 **BOT 与 WEB UI 股票代码大小写统一**（Issue #355）.

## [3.2.7] - 2026-02-20

### 新增
- 🔐 **Web 页面密码验证**（Issue #320）.

## [3.2.6] - 2026-02-20
### ⚠️ 破坏性变更（Breaking Changes）

- **历史记录 API 变更 (Issue #322)**.

## [3.2.5] - 2026-02-19

### 新增
- 🌍 **大盘复盘可选区域**（Issue #299）.

## [3.2.4] - 2026-02-18

### 修复
- 🐛 **统一美股数据源为 YFinance**（Issue #311）.

## [3.2.3] - 2026-02-18

### 修复
- 🐛 **标普500实时数据缺失**（Issue #273）.

## [3.2.2] - 2026-02-16

### 新增
- 📊 **PE 指标支持**（Issue #296）.
- 📰 **新闻时效性筛查**（Issue #296）.
- 📈 **强势趋势股乖离率放宽**（Issue #296）.

## [3.2.1] - 2026-02-16

### 新增
- 🔧 **东财接口补丁可配置开关**.

## [3.2.0] - 2026-02-15

### 新增
- 🔒 **CI 门禁统一（P0）**.
- 📦 **发布链路收敛（P0）**.
- 📝 **PR 模板升级（P0）**.
- 🤖 **AI 审查覆盖增强（P0）**.

## [3.1.13] - 2026-02-15

### 新增
- 📊 **仅分析结果摘要**（Issue #262）.

## [3.1.12] - 2026-02-15

### 新增
- 📧 **个股与大盘复盘合并推送**（Issue #190）.

## [3.1.11] - 2026-02-15

### 新增
- 🤖 **Anthropic Claude API 支持**（Issue #257）.
- 📷 **从图片识别股票代码**（Issue #257）.
- ⚙️ **通达信数据源手动配置**（Issue #257）.

## [3.1.10] - 2026-02-15

### 新增
- ⚙️ **立即运行配置**（Issue #332）.

## [3.1.9] - 2026-02-14

### 新增
- Plug **东财接口补丁机制**.

## [3.1.8] - 2026-02-14

### 新增
- 🔐 **Webhook 证书校验开关**（Issue #265）.

## [3.1.7] - 2026-02-14

### 修复
- 🐛 修复包导入错误（package import error）.

## [3.1.6] - 2026-02-13

### 修复
- 🐛 修复 `news_intel` 中 `query_id` 不一致问题.

## [3.1.5] - 2026-02-13

### 新增
- 📷 **Markdown 转图片通知**（Issue #289）.

## [3.1.4] - 2026-02-12

### 新增
- 📧 **股票分组发往不同邮箱**（Issue #268）.

## [3.1.3] - 2026-02-12

### 修复
- 🐛 修复 Docker 内运行时通过页面修改配置报错 `[Errno 16] Device or resource busy` 的问题.

## [3.1.2] - 2026-02-11

### 修复
- 🐛 修复 Docker 一致性问题.

## [3.1.1] - 2026-02-11

### 变更
- ♻️ `API_HOST` → `WEBUI_HOST`.

## [3.1.0] - 2026-02-11

### 新增
- 📊 **ETF 支持增强与代码规范化**.

## [3.0.5] - 2026-02-08

### 修复
- 🐛 修复信号 emoji 与建议不一致的问题.

## [3.0.4] - 2026-02-07

### 新增
- 📈 **回测引擎** (PR #269).

## [3.0.3] - 2026-02-07

### 修复
- 🐛 修复狙击点位数据解析错误问题.

## [3.0.2] - 2026-02-06

### 新增
- ✉️ 可配置邮件发送者名称.

## [3.0.1] - 2026-02-06

### 修复
- 🐛 修复 ETF 实时行情获取.

## [3.0.0] - 2026-02-06

### 移除
- 🗑️ **移除旧版 WebUI**.

## [2.3.0] - 2026-02-01

### 新增
- 🇺🇸 **增强美股支持** (Issue #153).

## [2.2.5] - 2026-02-01

### 新增
- 🤖 **AstrBot 消息推送** (PR #217).

## [2.2.4] - 2026-02-01

### 新增
- ⚙️ **可配置数据源优先级** (PR #215).

## [2.2.3] - 2026-01-31

### 修复
- 📦 更新 requirements.txt.

## [2.2.2] - 2026-01-31

### 修复
- 🐛 修复代理配置区分大小写问题.

## [2.2.1] - 2026-01-31

### 修复
- 🐛 **YFinance 兼容性修复** (PR #210).

## [2.2.0] - 2026-01-31

### 新增
- 🔄 **多源回退策略增强**.

## [2.1.14] - 2026-01-31

### 文档
- 📝 更新 README.

## [2.1.13] - 2026-01-31

### 修复
- 🐛 **Tushare 优先级与实时行情** (Fixed #185).

## [2.1.12] - 2026-01-30

### 修复
- 🌐 修复代理配置区分大小写问题.

## [2.1.11] - 2026-01-30

### 优化
- 🚀 **飞书消息流优化** (PR #192).

## [2.1.10] - 2026-01-30

### 合并
- 📦 合并 PR #154 贡献.

## [2.1.9] - 2026-01-30

### 新增
- 💬 **微信文本消息支持** (PR #137).

## [2.1.8] - 2026-01-30

### 修复
- 🐛 修正日志中 API 提供商显示错误.

## [2.1.7] - 2026-01-30

### 修复
- 🌐 禁用本地环境的代理设置.

## [2.1.6] - 2026-01-29

### 新增
- 📡 **Pytdx 数据源 (Priority 2)**.
- 🏷️ **多源股票名称解析**.
- 🔍 **增强搜索回退**.

## [2.1.5] - 2026-01-29

### 新增
- 📡 新增 Pytdx 数据源.

## [2.1.4] - 2026-01-29

### 文档
- 📝 更新赞助商信息.

## [2.1.3] - 2026-01-28

### 文档
- 📝 重构 README 布局.
- 🌐 新增繁体中文翻译.

## [2.1.2] - 2026-01-27

### 修复
- 🐛 修复个股分析推送失败.

## [2.1.1] - 2026-01-26

### 新增
- 🔧 添加 GitHub Actions auto-tag 工作流.
- 📡 添加 yfinance 兜底数据源.

## [2.1.0] - 2026-01-25

### 新增
- 🇺🇸 **美股分析支持**.
- 📈 **MACD 和 RSI 技术指标**.
- 🎮 **Discord 推送支持**.
- 🤖 **机器人命令交互**.
- 🌡️ **AI 温度参数可配置**.
- 🐳 **Zeabur 部署支持**.

### 重构
- 🏗️ **项目结构优化**.
- 🔄 **数据源架构升级**.
- 🤖 Discord 机器人重构.

### 修复
- 🌐 **网络稳定性增强**.
- 📧 **邮件渲染优化**.
- 📢 **企业微信推送修复**.
- 👷 **CI/CD 修复**.

## [2.0.0] - 2026-01-24

### 新增
- 🇺🇸 **美股分析支持**.
- 🤖 **机器人命令交互** (PR #113).
- 🎮 **Discord 推送支持**.

## [1.6.0] - 2026-01-19

### 新增
- 🖥️ WebUI 管理界面及 API 支持.
- ⚙️ GitHub Actions 配置灵活性增强.

## [1.5.0] - 2026-01-17

### 新增
- 📲 单股推送模式.
- 🔐 自定义 Webhook Bearer Token 认证.

## [1.4.0] - 2026-01-17

### 新增
- 📱 Pushover 推送支持.
- 🔍 博查搜索 API 集成.
- 📊 Efinance 数据源支持.
- 🇭🇰 港股支持.

## [1.3.0] - 2026-01-12

### 新增
- 🔗 自定义 Webhook 支持.

## [1.2.0] - 2026-01-11

### 新增
- 📢 多渠道推送支持.

## [1.1.0] - 2026-01-11

### 新增
- 🤖 OpenAI 兼容 API 支持.

## [1.0.0] - 2026-01-10

### 新增
- 🎯 AI 决策仪表盘分析.
- 📊 大盘复盘功能.
- 🔍 多数据源支持.
- 📰 新闻搜索服务.
- 💬 企业微信机器人推送.
- ⏰ 定时任务调度.
- 🐳 Docker 部署支持.
- 🚀 GitHub Actions 零成本部署.

---

[Unreleased]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.14.2...HEAD
[3.14.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.14.1...v3.14.2
[3.14.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.14.0...v3.14.1
[3.14.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.13.0...v3.14.0
[3.13.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.12.0...v3.13.0
[3.12.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.11.0...v3.12.0
[3.11.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.10.1...v3.11.0
[3.10.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.10.0...v3.10.1
[3.10.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.9.0...v3.10.0
[3.9.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.8.0...v3.9.0
[3.8.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.7.0...v3.8.0
[3.7.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.6.0...v3.7.0
[3.6.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.5.0...v3.6.0
[3.5.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.10...v3.5.0
[3.4.10]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.9...v3.4.10
[3.4.9]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.8...v3.4.9
[3.4.8]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.7...v3.4.8
[3.4.7]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.0...v3.4.7
[3.4.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.3.22...v3.4.0
[3.3.22]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.3.12...v3.3.22
[3.3.12]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.2.11...v3.3.12
[3.2.11]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.2.10...v3.2.11
[2.3.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.5...v2.3.0
[2.2.5]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.4...v2.2.5
[2.2.4]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.3...v2.2.4
[2.2.3]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.2...v2.2.3
[2.2.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.1...v2.2.2
[2.2.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.14...v2.2.0
[2.1.14]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.13...v2.1.14
[2.1.13]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.12...v2.1.13
[2.1.12]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.11...v2.1.12
[2.1.11]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.10...v2.1.11
[2.1.10]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.9...v2.1.10
[2.1.9]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.8...v2.1.9
[2.1.8]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.7...v2.1.8
[2.1.7]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.6...v2.1.7
[2.1.6]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.5...v2.1.6
[2.1.5]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.4...v2.1.5
[2.1.4]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.3...v2.1.4
[2.1.3]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.2...v2.1.3
[2.1.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.6.0...v2.0.0
[1.6.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v1.0.0
