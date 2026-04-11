# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

> For user-friendly release highlights, see the [GitHub Releases](https://github.com/ZhuLinsen/daily_stock_analysis/releases) page.

## [Unreleased]

### 修复

- 🧩 **Deterministic strategy_spec 归一化改为优先保留显式结构化字段** — 自然语言策略解析后，周期定投与已支持的指标型策略在再次归一化时，现在会优先沿用已有 `strategy_spec` 中明确给出的 `signal / capital / order / schedule / costs` 等结构化字段，而不是被旧的 `setup` 默认值静默覆盖。同时规范化后的 `strategy_spec` 会附带统一的 `support` 元信息与 `strategy_family / max_lookback`，让 NLP 解释结果与后续 deterministic 执行之间的契约更可检查、更稳定。
- 🕰️ **Deterministic 历史回放改为 stored-first replay，legacy fallback 显式隔离** — 规则回测历史详情与历史列表现在会优先从已持久化的 `summary.metrics`、`summary.visualization.audit_rows`、`summary.visualization.comparison` 以及已存储的日级序列中重建结果，不再让旧的 row columns 或隐式重算路径覆盖已有存储结果。只有旧运行缺少这些持久化字段时，才会进入明确命名的 legacy fallback 分支补建 audit / daily / exposure 数据，缩小 freshly completed run 与 reopened historical run 之间的口径漂移。
- 📈 **Deterministic benchmark / buy-hold 对比口径改为单一持久化 comparison payload** — 规则回测现在会把 `benchmark_curve / benchmark_summary / buy_and_hold_curve / buy_and_hold_summary` 与对应 KPI returns 一起收口到 `summary.visualization.comparison` 作为持久化真源。结果详情与历史读取在该 payload 存在时会优先使用它，避免 KPI、图表与历史回放各自从不同字段重新推导。对于外部基准不可用的场景，系统会显式持久化 `unavailable_reason` 并返回 `null` 的 benchmark KPI，而不是伪造收益值；同标的 buy-hold 仍按同一 run window、同一 close 口径保留。
- 🔌 **Deterministic 结果详情 API 统一公开 `auditRows` 字段名** — 规则回测服务内部仍以存储载荷里的 `summary.visualization.audit_rows` 作为审计台账真源，但 `/api/v1/backtest/rule/runs/{run_id}` 等 API 响应现在会把该字段稳定序列化为公开契约 `auditRows`，避免新运行在原始 JSON 中只能看到 `audit_rows`、前端再被动 camelCase 转换的隐式差异。CSV 导出与结果详情继续共用同一份已持久化 ledger。
- ⚙️ **Deterministic backtest 执行模型收口为结构化配置** — 规则回测现在会把执行语义持久化为结构化 `execution_model`，明确记录 `signal_evaluation_timing / entry_timing / exit_timing / entry_fill_price_basis / exit_fill_price_basis / fee_model / slippage_model / market_rules`，并继续派生旧的 `execution_assumptions` 兼容视图。引擎内部也改为优先围绕这份结构化配置执行与持久化，历史运行若还没有新字段则会从旧的 assumptions 回推兼容配置，避免结果解释口径漂移。
- 🧾 **Deterministic backtest audit ledger 持久化收口为单一真源** — 规则回测完成后现在会把日级 audit ledger 作为结构化结果的一部分持久化保存，字段口径统一收口为 `date / symbol_close / benchmark_close / position / shares / cash / holdings_value / total_portfolio_value / daily_pnl / daily_return / cumulative_return / benchmark_cumulative_return / buy_hold_cumulative_return / action / fill_price`，并继续保留信号摘要、手续费、滑点、drawdown 与 unavailable 原因等可审计字段。结果页读取与 CSV 导出在存在存储 ledger 时会直接复用这份持久化数据，不再走另一条临时重建路径；历史结果回放也保持与当前运行一致的 stored-ledger 读取语义。
- 🗂️ **Deterministic 结果页改为“首屏看图 + 深信息入 tabs/collapse”** — `/backtest/results/:runId` 不再把日级详情、审计表、交易表、参数快照、benchmark 说明、执行假设和历史列表继续纵向常驻堆叠在默认页面流里。结果页首屏现在只保留顶部摘要 / 操作、KPI 和统一 chart workspace；日级详情改为跟随 hover 的浮动明细卡，`审计明细 / 交易记录 / 参数与假设 / 历史结果` 则收进专门标签页，首屏回到以图表分析为中心的 JoinQuant 风格。
- 📊 **Deterministic 结果页首屏进一步压缩为 compact dashboard hero** — 结果页这次继续从“几个独立高 section 纵向堆叠”收敛为“一个紧凑主舞台”：顶部说明换成更薄的 top bar，KPI 改成更低高度的关键指标摘要（总收益 / 年化 / 最大回撤 / 夏普 / 基准 / 超额），统一 chart workspace 也把主图 / 日盈亏 / 仓位 / brush 一路压到更紧的 `220 / 72 / 56 / 40px` dense 比例，并同步缩短 panel 间距，首屏更像一个协调的 dashboard，而不是继续依赖长滚动阅读。
- 🎯 **Deterministic hover 明细改为真实跟随型 tooltip** — 结果图里的当日详情不再固定钉在右上角角落，而是继续复用同一个 `hoverIndex / hoveredRow`，并额外根据当前 hover 的图表几何实时计算 tooltip 的 `left/top`：默认贴近 hover 点右下侧，接近边缘时再左右 / 上下翻转，在 chart workspace 内以真正跟随 cursor / crosshair 的浮层展示。
- 📐 **Deterministic 结果页引入共享 density 比例系统** — `/backtest/results/:runId` 现在显式使用 `comfortable / compact / dense` 三档 density 统一驱动 header、KPI、chart panel、legend、brush、tooltip 和间距，不再让图表高度、文字大小和 tooltip 尺寸各自独立收缩，缩放到更小浏览器时也能保持整页比例协调。
- 🧾 **Deterministic hover tooltip 改成稳定的 compact chart tooltip 布局** — hover 明细不再复用通用 audit-grid，而是切到专门的 label/value 双列 tooltip 布局：主字段稳定对齐、日期与数值避免尴尬断行，长文本进入可换行的全文区，并用固定 max width / max height + 内部滚动避免内容继续溢出卡片。
- 🧭 **Deterministic Backtest 正式切成两页式产品流** — `/backtest` 不再同时长期承载参数输入、策略确认和 full-width 结果分析，而是收口为确定性回测配置页：负责普通/专业两种配置体验、策略解析确认、提交运行和历史入口。完整结果分析现统一迁到新路由 `/backtest/results/:runId`，并由结果页负责 run status / polling、KPI、全宽 chart workspace、审计表、交易表、参数快照与基准说明。
- 🔁 **Deterministic 运行与历史统一走同一个结果页路径** — 从 `/backtest` 发起 deterministic run 后会直接导航到 `/backtest/results/:runId`；配置页里的历史记录点击后也不再把大图分析回放在当前页，而是打开同一个结果页路由。当前运行和历史运行因此真正复用同一条 `fetch run -> normalize result -> render workspace` 链路，不再保留旧的 config-page chart glue。
- 🧱 **`/backtest` 确定性结果页改为 normalized-result 单一渲染架构** — Deterministic Backtest 的结果查看链路这次不再继续叠补旧 viewer，而是直接重写为 `normalizeDeterministicBacktestResult -> DeterministicBacktestChartWorkspace -> KPI / audit / trade-event tables` 的单向数据流。当前结果与历史结果共用同一个 workspace，主图、每日盈亏、仓位和底部 brush 都只读统一 `normalized rows`，避免旧 deterministic chart glue 在 hover、visible window 和空图状态之间继续漂移。
- 🧭 **`/backtest` 确定性结果图改为统一多 panel viewer** — Deterministic Backtest 的结果区不再直接挂三张独立 chart card，而是改成单一联动图表容器：内部纵向堆叠 `累计收益率 / 每日盈亏 / 仓位·买卖行为` 三个 panel，并由同一个 hover 状态、可见区间和底部 range brush 统一驱动。当前结果与历史回测记录也继续共用同一套 viewer，从存储的结构化 timeseries 与 audit rows 动态重建，而不是走分散的图表实现或静态图像。
- 🔎 **`/backtest` 结果区升级为可核查 / 可联动 / 可复盘的单一结果系统** — Deterministic Backtest 现在把日级审计账本持久化进结果记录，并用同一份结果数据驱动 KPI、联动三图、悬停当日详情、日级审计表与历史记录重建。结果区固定为 `累计收益率 / 每日盈亏 / 仓位·买卖行为` 三张联动图，新增共享 hover 检查、范围选择器（全部 / 近3个月 / 近1个月 / 自定义拖动）和 CSV 审计导出；打开历史回测记录时，也会直接从存储的结构化 timeseries 与 audit rows 动态重建图表和对账视图，而不是依赖静态图像或分散重算。
- 📊 **`/backtest` 确定性回测新增可配置基准与更清晰的三图结果区** — Deterministic Backtest 现在支持 `无基准 / 当前标的买入并持有 / 沪深300 / 中证500 / 纳指100 / QQQ / 标普500 / SPY / 自定义代码` 的基准选择，并按市场默认自动回退为更合适的对照线；结果区也固定收口为 `累计收益率 / 每日盈亏 / 仓位·买卖行为` 三张图，统一按容器宽度调整高度、刻度、marker 密度和终点标签，减少右侧结果面板在桌面缩放下的文字重叠与图表拥挤。
- 🧭 **`/backtest` 普通模式改为弹性双栏引导工作区** — Deterministic Backtest 的 `Normal Mode` 不再是旧版窄侧栏，也不再是居中的窄单栏，而是改成吃满内容区的弹性双栏：左侧是更宽的引导式主工作窗口，右侧是随步骤变化的预览 / 状态 / 结果窗口；图表与结果区会跟随右侧容器宽度自适应，基础参数、策略确认和运行阶段也重新对齐到这一套 split workspace 模型。
- 🧭 **`/backtest` 新增 Normal / Professional 双交互模式** — `/backtest` 现在默认使用 `Normal Mode`：左侧控制面板按步骤只显示一个主步骤卡片，减少一次性暴露的复杂度；切换到 `Professional Mode` 后则展开完整控制面板，保留高级用户所需的全部控制。Deterministic Backtest 与 Historical Evaluation 都沿用同一套模式切换与右侧显示板设计。
- 🧭 **`/backtest` 统一为单一 left-control / right-display 交互模型** — Deterministic Backtest 与 Historical Evaluation 现在共享同一套 Backtest V1 设计系统：左侧固定控制面板负责参数、确认与执行，右侧显示板负责解析预览、结果、图表、表格与历史。原先残留的 workbench/IDE 式分区语言被进一步收口，stepper 也改为真实驱动左侧工作流，不再只是装饰。
- 🧭 **`/backtest` 简化为更清晰的 Backtest V1 result-first 页面** — 移除过重的 rail/workbench chrome、上下文条和多区域 shell，把 `/backtest` 收口为单一主页面流：`Header -> Base Params -> Strategy Input -> Result Metrics -> 主图 -> Daily Return -> Exposure -> Inspection -> Trade Log -> History`。新的布局默认以确定性策略回测为主，图表保持全宽且不再与 summary 侧摆混排，页面整体更像一张严肃的研究/回测页，而不是半完成的 IDE。
- 🧭 **`/backtest` 重构为响应式 workstation 框架** — Backtest 路由现在使用真正的 route-scoped rail / stage workbench shell，并把 authoring、results、audit 接入可重排的响应式布局；同时移除此前主要依赖 centered max-width 的页面行为，让结果区在桌面端随视口真实扩展与重排，而不是整体像居中页面一样被浏览器缩放。
- 🧭 **`/backtest` 打磨为更完整的 in-app Backtest Workbench** — 在保留现有功能和执行语义不变的前提下，`/backtest` 继续沿用 route-scoped workbench shell，并把页面层级明确收口为 `authoring/setup -> results workspace -> audit/history`。这轮主要不是加功能，而是让结果区成为视觉中心：历史评估与确定性策略回测都新增了更清晰的 workbench section hierarchy、状态 telemetry、结果区强调和次级审计区；确定性 flow 的 step panel、改写提示和结果刷新也改为更平滑的轻量过渡，减少此前“很多卡片机械堆叠、状态硬切换”的感觉。
- 🧭 **修正 `/backtest` 的真实桌面宽度瓶颈** — 这次不再继续堆叠 Backtest 自身的 max-width hack，而是直接放宽了上层 `Shell` 中真正限制内容宽度的 `shell-content-frame`，并只对 `/backtest` 路由加上专用 modifier。此前许多 backtest 页内的“加宽”规则之所以视觉效果有限，是因为父层内容框先被 `layout-page-max` 截断；修正后，Backtest workbench 的更宽画布和下方结果区终于能够真正继承到可用桌面宽度。
- 📏 **Backtest workbench 画布与分析区进一步放宽** — `/backtest` 的专用 workbench shell 继续扩大了 desktop 下的实际可用画布，`backtest-workbench-main`、结果卡与历史卡都采用了更激进的宽度策略和更紧的横向 padding。setup/authoring 仍保持相对克制，而结果、图表、检视、trade log 和 history 明显获得更多横向空间，使页面更少像中间内容条，更接近真正的回测分析画布。
- 🧪 **`/backtest` 切换到专用 workbench page shell** — Backtest 不再继承普通页面的 `workspace-page` 文档式内容壳层，而是使用 route-scoped 的专用 workbench page shell。该 shell 为 `/backtest` 单独定义了更宽的 page-level canvas、header 区和 main workspace 区，同时保留 setup/authoring 区的可读宽度与结果区更宽的研究视图，使桌面端更接近独立回测工作站，而不会影响应用中的其他页面。
- 🛠️ **Backtest 页面回退为稳定的连续页流，并保留更宽的结果区** — 修复了此前桌面 workbench 实验带来的 step 按钮拥挤、setup 区不稳定和 boxed zones 互相抢宽度的问题。Backtest 页面现在重新使用单一连续页面流；上方 guided flow / confirmation / run 卡片回到更稳的标准宽度，而结果、图表、检视和历史区继续使用更宽的 section 级宽度策略，在不破坏控件布局的前提下保留研究工作区的横向空间。
- 📊 **确定性策略结果区升级为 full-width research layout** — Deterministic Strategy Backtest 现在把结果区重排为更接近研究终端的全宽布局：先显示核心指标，再用全宽主图展示策略 vs 同标的 buy-and-hold 的归一化净值对比，并补充两张辅助子图用于检查 `Daily Return` 与 `Exposure`。策略摘要、执行 / 基准检视和结果解读则下沉到图表下方，避免继续压缩主图宽度；Trade log 仍保留为底部审计区。
- 🎯 **确定性对比图强化策略 / 基准层级可读性** — Deterministic Strategy Backtest 的主对比图现在把 `Strategy` 线提升为更亮、更粗的主视觉层，而 `Buy & Hold` 基准线则改成更暗、更细的次级虚线；同时把图例收口为 `Strategy / Buy & Hold / Buy / Sell` 四个短标签，并为买卖点使用更容易区分的形状与终点标签，降低暗色背景下两条主线过于接近的问题。
- 🖥️ **Backtest 页面切换到更宽的 desktop research workspace** — Backtest 页面现在使用更积极的 desktop 宽度策略，明显减少大屏下两侧空白带；Deterministic result 区的 card 也单独采用更宽的 workbench 布局，让主图和子图不再像嵌在保守居中列里的“小卡片”，而更接近真正的量化研究工作区。
- 🧠 **确定性策略确认页更少退化成 generic fallback** — Deterministic Strategy Backtest 现在会优先保留已识别的核心策略意图，即使整条自然语言还不能执行，也会把 `detected_strategy_family / core_intent_summary / unsupported_extensions / interpretation_confidence` 作为结构化确认信息返回。像“均线交叉 + 止损扩展”“MACD + 参数优化”“RSI + 分批建仓”这类输入，不再主要显示成空的 `rule_conditions` 回退，而会更明确地区分“已理解的主策略”与“当前不支持的附加约束”，并据此生成当前可执行的改写建议。
- 🧭 **确定性策略确认步骤层级与改写交互进一步收口** — Deterministic Strategy Backtest 的确认页现按 `状态 -> 解析策略 -> 改写建议 -> 默认值 -> Warnings` 收口展示，减少重复解释层；当输入当前不支持时，系统会以更紧凑的方式显示 supported portion、rewrite suggestions 与 grouped assumptions。点击建议改写后会直接回填策略文本、返回策略步骤，并显示轻量“已应用建议改写”提示，方便用户重新解析继续。
- 📐 **确定性策略回测扩展到首批技术策略家族** — Deterministic Strategy Backtest 现在通过同一条 `natural language -> normalized strategy_spec -> deterministic execution` 链路正式支持 `均线交叉 / MACD 交叉 / RSI 阈值` 三类单标的、多头、单持仓策略。解析确认区会显式区分 `可执行 / 含默认假设 / 当前不支持`，并把默认参数与执行假设以结构化方式返回；后端 deterministic engine 则在不新增第二套执行管线的前提下，复用现有结果 contract 输出真实指标、权益曲线与交易明细。
- 🧭 **确定性策略确认页补齐 unsupported 诊断与改写建议** — Deterministic Strategy Backtest 的 parse/confirmation payload 现在会额外返回更清晰的 `unsupported_reason / unsupported_details / supported_portion_summary / rewrite_suggestions / assumption_groups / parse_warnings`，用于说明系统已识别了什么、当前哪一部分不支持、以及如何把自然语言改写成当前可执行的 deterministic form。前端确认步骤同步改为紧凑展示这些信息，并支持一键把改写建议回填到策略输入框中继续解析。
- 🧭 **确定性策略回测重构为 guided step flow** — Backtest 页面中的 Deterministic Strategy Backtest 现改为默认的分步工作流：`Symbol -> Capital & Date -> Strategy -> Confirmation -> Run`。确认步骤会基于归一化 `strategy_spec` 展示更紧凑的结构化摘要，并显式区分 `可执行 / 含默认假设 / 当前不支持 / 结果已过期` 等状态；结果区则收口为指标摘要、策略规格、权益曲线和交易明细，运行历史下沉为次级区域。页面同时保留低强调的 `Advanced mode` 入口，用于后续扩展更专业的编辑路径。
- 🧩 **确定性策略回测引入首版受限策略规格（strategy spec）管线** — 中文自然语言定投策略不再直接依赖零散 `setup` 字段进入执行层，而是先归一为受限的 `strategy_spec` / 规则规格对象，再经过显式校验与默认值补齐后复用原有 deterministic backtest 执行链路。当前首版规格重点覆盖单标的区间定投家族（固定股数 / 固定金额、起止日期、执行频率、成交价格基准、现金不足处理、期末平仓、手续费 / 滑点），前端解析预览与执行说明也同步改为优先展示归一化后的策略规格，减少 one-off hardcoded 模板继续外溢为长期执行契约。
- 🧠 **确定性策略回测新增中文自然语言定投 MVP** — Deterministic Strategy Backtest 现在支持把一小类中文定投指令解析成结构化草稿，并在用户确认后复用原有 deterministic backtest 执行链路返回真实汇总、权益曲线和交易明细。当前优先支持“固定股数 / 固定金额、给定起止日期、按交易日买入、现金不足时停止”的单标的区间定投表达，例如“资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止”。
- 📈 **确定性策略回测 MVP 补齐日期区间驱动的真实结果链路** — Deterministic Strategy Backtest 现在支持显式 `开始日期 / 结束日期` 输入，并把日期区间贯穿到后端规则执行、结果 contract、前端汇总区、权益曲线和交易明细中。页面不再只依赖“最近 N 根 bars”近似窗口来回答策略盈亏问题，而是可以更直接地验证“在指定区间内，这套规则到底赚了还是亏了”。
- 🔎 **Historical backtest 补齐样本日期与定价来源透明度** — Historical Analysis Evaluation 相关响应现在会额外暴露 `latest_prepared_sample_date / latest_eligible_sample_date / excluded_recent_reason / excluded_recent_message / pricing_resolved_source / pricing_fallback_used`，用于解释“为什么样本只停在更早日期”以及“本次定价究竟用了 LocalParquet 还是回退到了 Yfinance/API”。Web 回测页同步在历史评估参数区增加一条轻量说明，直接展示最新已准备样本、最新可评估样本、未纳入较新日期的原因和实际定价来源。
- 🧭 **Backtest 历史评估页做第二轮中文化与减层** — 历史分析评估页改为更直接的 5 段流程：定位说明、参数与执行、运行概览、评估结果、运行历史。页面移除了单独的 `Methodology / Definitions` 解释层，运行时数据源元数据收口到参数区轻量 chips，概览区只保留一组主 KPI；同时把主要区块标题与关键指标统一成中文，减少中英混杂与重复说明带来的视觉负担。
- 🧾 **Backtest 历史评估页改为直接消费后端数据源元数据** — Historical Analysis Evaluation 现在直接读取后端返回的 `requested_mode / resolved_source / fallback_used` 并映射到页面中的 `Requested Mode / Resolved Source / Fallback Used`，不再把结果表行级 `marketDataSources` 聚合作为 summary-level 主来源；结果表本身仍保留行级 source 展示，便于审计单条样本。
- 🧪 **Backtest 页面信息架构拆分为两条清晰模块** — Web `Backtesting` 页面现严格拆为 `Historical Analysis Evaluation` 与 `Deterministic Strategy Backtest` 两个顶层 tab：历史分析评估区新增独立的 Header、Control Panel、Methodology / Definitions、Summary Strip、Result Table、Run History，并显式声明“不是完整组合/账户回测”；确定性策略区则重排为自然语言输入、解析预览、执行控制、结果区、历史区的 MVP 骨架。历史评估页同时新增数据源透明度占位与 best-effort 标签归一化，前端会优先把运行结果中的原始 source 映射为 `LocalParquet / DatabaseCache / YfinanceFetcher / ProviderAPI / MixedFallback`，在后端尚未把 runtime source metadata 注入所有 summary/run 接口前，先保证页面上可见且不打断现有流程。
- 🧾 **研究报告生成改为渐进式草稿体验** — 首页在异步分析启动后不再停留在泛化阻塞 loading，而是立即进入结构化“研究报告草稿”状态：后端任务队列通过 SSE 新增 `task_updated` 阶段事件并透出实时 `result`/执行摘要，前端据此按 `初始化 → 市场数据 → 信号分析 → 报告组装 → 收尾` 渐进填充报告章节，在失败时保留已呈现内容并提供重试入口，最终平滑切换到正式报告视图。
- 📱 **Web 工作区响应式与抽屉交互进一步收口** — 首页移动端不再保留会挤压主内容的历史侧区预览，档案抽屉改为更高效的纵向层级与主滚动区，首页主操作按钮统一高度/宽度策略并移除重复档案入口；同时补齐移动端与桌面端断点切换时的抽屉/档案状态复位，避免 viewport 来回切换后残留遮挡层或错位框架。
- 🚀 **Web 壳层切换为严格 SpaceX 设计纪律的研究工作区** — `dsa-web` 本轮不再保留“旧 dashboard 壳层 + 新皮肤”的混搭方案：主导航改为顶部极简 masthead + 移动端抽屉，历史分析从密集侧栏列表重构为独立档案抽屉与首页轻量工作区摘要，首页首屏改成面向研究流程的 command / archive / report 布局，登录页、启动加载页、报告生成态和共享按钮/输入/抽屉统一收口到黑底 + spectral white + ghost control 的受控极简语言；同时新增本地持久化“红跌绿涨 / 红涨绿跌”市场颜色约定，并同步应用到价格、涨跌幅与图表相关指标。
- 🛰️ **Web 产品体验重构为统一设计系统** — Web 端现在以统一的 SpaceX-inspired 产品设计语言驱动整个体验：Shell、侧边导航、登录/认证入口、启动加载、状态横幅、按钮/输入/表格/弹窗等共享原语统一改为克制的黑白谱系、DIN 风格排版和低噪声交互；首页、回测、持仓、管理员日志以及共用历史/任务/报告表面同步对齐，移动端抽屉和首屏节奏也一起收口，避免“局部页面重做、整体仍然混搭”的问题。
- 🧭 **回测域语义与工作区统一收口** — Backtest 现明确拆分为“历史分析评估”和“确定性规则策略回测”两套语义：历史评估统一把 `eval_window` 解释为 trading bars、`min_age` 解释为 calendar days；规则回测新增显式执行假设、buy-and-hold / excess return、交易审计字段与异步任务状态（`parsing / queued / running / summarizing / completed / failed`）。同时新增共享的本地美股 parquet helper，`stock_service`、历史评估 warmup / fill 路径和规则回测历史加载都统一优先读取 `US_STOCK_PARQUET_DIR`，缺失或异常时保留原有 API fallback 并输出明确日志。
- 📚 **Backtest 工作区补齐历史与重置操作** — Backtest 页新增可配置的样本准备范围（支持更大的历史样本数）、回测运行历史列表、按 symbol 查看历史结果的回放入口，以及样本清理 / 结果清理 / 样本重建的显式控制。页面现在能区分“准备样本”“重跑结果”和“清空存量记录”，不再把这些动作混成一个模糊的 force rerun。
- 📦 **Backtest sample warmup flow** — Settings/Backtest 页面新增显式“准备回测样本”动作：当历史分析不足以满足成熟窗口时，可先按股票代码补写可回测的历史分析样本到 `analysis_history`，再重新运行回测。该准备动作复用本地可用的历史行情数据作为输入，并保持回测主流程仍然只读取 `analysis_history` 作为候选源。
- 📊 **Backtest run diagnostics** — `POST /api/v1/backtest/run` now returns an explicit `no_result_reason` / `no_result_message` when it writes no rows, so a 200 response no longer looks like a silent success when the candidate set is empty. The existing optional `performance` 404 handling remains unchanged; the page can now explain empty runs as “no analysis history” or “insufficient historical data” instead of showing an unexplained blank state.
- 🧭 **AI Task Routing 行式收紧 + Data Source Library 校验状态显性化** — Settings 的 AI Task Routing 由“主卡 + 右侧卡组 + 内嵌多卡”进一步收紧为单一 surface 内的 3 条任务行，Analysis 行内直接展示主路由/备用路由和 Provider 覆盖，Stock Chat / Backtesting 以更短的次级行展示继承/覆盖状态与当前生效路由，减少大块空白和 card-in-card 视觉负担。Data Source Library 卡片保留能力标签，并把状态文案拆成“未配置 / 已配置待验证 / 内置可用”；当前没有复用现成后端连通性探活接口，因此第三方数据源先展示真实的 status-only“已配置，未做连通性验证”，不伪装成网络校验成功。
- 🧭 **Settings Task Routing 压缩布局 + Data Source Library 可用性表达增强** — AI Task Routing 调整为左侧 Analysis 主卡 + 右侧 Stock Chat / Backtesting 次卡的同屏布局，减少纵向空白并保留“编辑任务路由”主入口；Data Source Library 卡片补充能力标签（行情/基本面/新闻/情绪）和状态检查行，明确区分内置可用、凭据已配置可用于当前路由、等待凭据配置三类状态。数据源状态当前为基于现有配置/内置源能力的状态检查，不伪装成真实网络连通性探活。
- 🧭 **Settings AI/Data 信息架构对齐** — AI 区域移除独立“当前生效 AI 配置”顶层摘要块，把 Analysis / Backup / Stock Chat / Backtesting 的当前生效路由直接并入“任务路由”卡片，减少“先看摘要再滚去编辑”的重复路径；数据源设置同步重排为“数据路由 + 数据源库”两层结构，上层继续编辑 market/fundamentals/news/sentiment 的主备源顺序，下层以卡片展示 Alpha Vantage / Finnhub / Yahoo / FMP / GNews / Tavily / Local Inference 等源的凭据状态、内置可用状态和当前路由使用情况，让 Data Sources 与 AI Provider Library + Task Routing 保持一致的心智模型。
- 🧭 **AI Settings 摘要可读性与 Provider 级高级配置作用域收口** — “当前生效 AI 配置”从偏表格化的三列硬布局调整为更易扫读的紧凑摘要行，保留 Analysis / Backup / Stock Chat / Backtesting 与 Provider 覆盖信息但减少机械表格感；Provider 卡片的“管理高级配置”现在会以 provider scope 打开高级渠道编辑器，只显示当前 Provider 的渠道行并锁定新增预设，避免在单 Provider 编辑时继续看到其他 Provider 的无关渠道与全局 runtime 区块。全局“打开高级设置”入口保留为低优先级全量管理入口。
- 🧭 **GLM/Zhipu 路由保存与 AI 设置渐进式编辑收口** — 前后端模型校验新增统一 canonical identity 比较：`glm-4`、`openai/glm-4` 这类“完整 ID / 后缀 ID”会先归一到同一模型身份再做渠道声明校验，修复 GLM 渠道已显式声明 `glm-4` 且测试成功，但主任务路由保存仍被最终校验误拒的问题；同时 AI Settings 主页面改成“摘要卡片 + 抽屉编辑”的渐进式交互，任务路由与 Quick Provider API Key 均默认只展示状态/当前模型，编辑操作进入侧边抽屉，高级 Provider / Channel 配置继续下沉到独立抽屉，减少长表单在主页面直接铺开造成的视觉负担。
- 🧭 **AI Settings 主页面去重降噪** — 压缩 AI 主页面的说明性文案和重复区块，移除“高级配置”卡片里的逐 Provider 汇总网格与主页面重复提示，只保留一个低优先级的“打开高级设置”入口；高级渠道数量改由各 Provider 卡片直接展示，让页面主层级更明确地收敛为 `Task Routing -> Provider Library -> Advanced Config`。
- 🧭 **AI 路由模型来源收口 + Provider 默认/显式模型模式拆分** — 任务路由模型选项改为单一可信来源规则：`Provider 预设模型 + 已启用高级渠道显式声明模型 + 仍与前两类匹配的已保存路由模型`，不再从旧 `LITELLM_*` / 全局模型集合反向回填下拉选项，避免 GLM/Zhipu 仅声明 `glm-4` 时仍出现 `glm-5` 这类 phantom model。Analysis / Stock Chat / Backtesting 的路由编辑器新增“Provider 默认 / 自动”和“显式模型 ID”两层模式，Quick Provider 仅配置 API Key 时可先走 Provider 默认模式；高级渠道声明、自定义 Base URL/协议、runtime 参数继续保留在下沉的高级配置层。
- 🧭 **AI 测试与 fallback 语义对齐（GLM/Zhipu）** — 快速 Provider 测试现在会优先复用同 Provider 的高级渠道测试模板（协议/Base URL/首个声明模型），并补充“quick test 直连路径 vs advanced channel 测试路径”说明；GLM/Zhipu 快测失败时会给出引导到高级渠道测试的可执行提示。`LLMChannelEditor` 同步收口 fallback 校验语义：该字段仅接受当前运行时可访问模型（已启用渠道或可用直连 key），跨 Provider 容灾应配置在任务层备用路由。后端 `test_llm_channel` 对 `Empty response` 增加可操作诊断（模型权限/协议不匹配/解析失败等），不再只返回泛化错误。
- 🧭 **AI 设置改为任务优先工作流（Analysis / Stock Chat / Backtesting）** — 设置页 AI 区域新增“按任务配置模型”：Analysis 继续维护主/备路由；Stock Chat 与 Backtesting 默认继承 Analysis，并支持独立覆盖保存（分别写入 `AGENT_LITELLM_MODEL` 与 `BACKTEST_LITELLM_MODEL`）。同时“快速 Provider API Key 配置”升级为 Provider Library 卡片视图（Gemini / AIHubMix / OpenAI / Anthropic / DeepSeek / GLM/Zhipu），凭据就绪后即可进入任务模型选择，不强制先建渠道；高级 Provider/Channel 配置保留为可选层并下沉。
- 🔁 **直连 API Key 兼容链路补齐（最终校验层）** — 修复 Gemini 直连 API Key 模式在“备用路由保存”阶段仍被后端按“仅渠道声明”拒绝的问题。`SystemConfigService` 现已在最终运行时模型校验中统一接受“已启用渠道模型”或“匹配的 legacy 直连 API Key”两类能力来源（适用于 `LITELLM_MODEL / LITELLM_FALLBACK_MODELS / AGENT_LITELLM_MODEL / VISION_MODEL`），从而恢复“仅配置 `GEMINI_API_KEY` 也可保存 Gemini 主/备路由”的向后兼容行为；同时前端 AI 路由保存不再保留陈旧 fallback 列表，避免历史无效模型残留导致误报。
- 🔧 **AI 路由编辑器可选网关回归修复（凭据就绪作为唯一来源）** — 修复 Settings 中主/备网关下拉被错误禁用或无可选项的问题：网关选择器可用性与选项来源改为严格基于凭据检测结果（`AIHUBMIX_KEY(S)`、`GEMINI_API_KEY(S)`、`OPENAI_API_KEY(S)`、`DEEPSEEK_API_KEY(S)`、`ANTHROPIC_API_KEY(S)`），不再依赖 `LLM_CHANNELS`。当前行为为：已就绪 provider ≥1 时主路由可选，≥2 时备用路由可选；仅有 legacy `LLM_CHANNELS` 而无凭据时保持禁用并给出明确原因。此前 primary-only 保存修复（不向 `LLM_CHANNELS` 自动注入网关）保持不变。
- 🧭 **AIHubMix 路由可用性与问股路由说明增强** — AI 路由凭据识别补充 `AIHUBMIX_API_KEY(S)`，确保 AIHubMix 在凭据就绪时可直接进入主/备路由选择；模型编辑器补充 AIHubMix 专用提示与示例（支持手动模型 ID，如 `openai/gpt-4.1-free`、`openai/gpt-4.1-mini`），并保留预设 + 自定义双模式。设置页“当前生效 AI 配置”与“默认 AI 路由”区域新增问股路由说明，明确展示问股是“与分析共用”还是“使用 AGENT_LITELLM_MODEL 独立模型路由”。
- ♻️ **AI 备用路由可清空（primary-only 回归可用）** — AI 路由编辑器新增显式“清空备用路由”操作，支持将 `Backup Gateway/Model` 一次性重置为空；清空后保存会一致写入 `AI_BACKUP_GATEWAY=''`、`AI_BACKUP_MODEL=''` 并清空 `LITELLM_FALLBACK_MODELS`，避免残留 fallback 导致 primary-only 配置被校验拦截。
- 🧪 **AI 备用路由前置兼容性校验 + 渠道配置入口增强** — AI 路由编辑器在填写备用路由时新增前置兼容性检查：若备用模型未在“已启用渠道模型声明”中出现，会在保存前显示可执行错误并提供“前往配置渠道模型”入口，同时禁用保存按钮，避免提交后才被后端拒绝。AI 路由区也新增“配置 Provider/渠道 API”直达入口，并在高级区补充“渠道/API 层 vs 路由层”说明，降低“渠道配置入口隐藏”带来的排障成本。
- 🛠️ **AI 路由保存失败修复（primary-only 合法场景）** — Settings 的 `Save routing` 不再把“仅网关选择”自动注入 `LLM_CHANNELS`，避免触发后端 `LLM_<channel>_*` 完整渠道校验导致 `System configuration validation failed`。同时新增前端路由完整性校验：主路由必须“网关+模型”同时存在，备用路由必须“同时填写或同时留空”；当保存失败时会在 AI 路由区域展示可执行错误信息。primary-only（如 `AI_PRIMARY_GATEWAY=gemini` + `AI_PRIMARY_MODEL=gemini/...`，`AI_BACKUP_*` 为空）现在可稳定保存，并保持 `AI_PRIMARY_* / AI_BACKUP_* / LITELLM_*` 兼容同步。
- 🧭 **AI 路由设置可用性收口（网关-模型一致性 + 显式模式）** — Settings 的 `Default AI Routing` 继续做聚焦修复：当主/备网关未选择时不再展示残留模型值，避免“网关未配置但模型有值”的误导；主/备两侧模型输入改为显式双模式（`预设选择` / `自定义 ID`），并补充模式优先级与网关前置提示。Gemini 与 AIHubMix 路由均保持“网关特定预设 + 始终允许手输模型 ID”（例如 `gemini/gemini-3-flash-preview` 或 AIHubMix 目录模型）。保存后成功提示会明确回显 `Primary route / Backup route / Scope`，并保持 `AI_PRIMARY_* / AI_BACKUP_* / LITELLM_*` 兼容持久化。
- 🧠 **AI 设置信息架构重排（仅 AI 区域）** — Settings 的 AI 区域重构为四层：`Current Effective AI Route`（生效主/备网关与模型、配置状态）、`Default AI Routing`（唯一主工作流，主/备网关+模型可编辑）、`Provider Readiness`（凭据状态、预设模型、推断模型、自定义模型能力）和 `Advanced / Raw Compatibility`（折叠展示 legacy/raw 字段）。同时新增“网关-模型联动 + 手动模型 ID 输入”能力，支持 AIHubMix/Gemini 等场景下按网关快速选模型并自由输入自定义模型 ID，且保持 `AI_PRIMARY_* / AI_BACKUP_* / LITELLM_*` 兼容持久化不变。
- 🛰️ **新增管理员执行日志中心（D2）** — 后端新增结构化执行日志会话与事件存储（AI/数据源/通知分层），并提供管理员解锁后可访问的 `/api/v1/admin/logs/sessions` 与 `/api/v1/admin/logs/sessions/{session_id}` 接口；Web 端新增 `/admin/logs` 管理员页面与设置页入口，可按会话查看时间线，区分 `success / partial_success / timeout_unknown / failed / not_configured` 通知终态，并保持用户侧任务/报告页面简洁不暴露原始调试细节。
- 📚 **管理员日志可读层 + AI 默认路由选择（D2.1 / D3）** — 管理员日志列表与详情新增“执行摘要 + 叙述段落 + 关键徽标”，在保留原始事件时间线的同时，提升可读性（最终模型、数据源、回退、通知终态、主要失败原因一目了然）。设置页 AI 区域补齐“主/备网关 + 主/备模型”双层路由选择并持久化 `AI_PRIMARY_* / AI_BACKUP_*`，同时兼容同步到 `LITELLM_MODEL / LITELLM_FALLBACK_MODELS / LLM_CHANNELS`，避免“API 已配置但仍显示未配置”的误导。
- 🧭 **首页执行摘要可控 + 管理员系统动作链日志（D2.2）** — 新增系统配置 `SHOW_RUNTIME_EXECUTION_SUMMARY`（设置页“系统/高级”可视化开关），用于控制首页是否显示运行时执行摘要卡片；管理员日志中心新增“系统动作时间线”语义层，事件按 `category/action/target/status` 展示网关调用、模型尝试、数据源尝试与回退切换、通知通道尝试与终态分类，提升 Aihubmix→模型、GNews→Tavily 等链路排障可读性，同时保持管理员日志页独立可见、不受首页开关影响。

- 🧾 **完整 Markdown 报告结构去重与审计升级** — `report_markdown` 渲染改为严格四层：`Decision Summary -> Execution Plan -> Evidence -> Coverage / Audit`。决策层只保留“评分/建议/趋势 + 一句话结论”，执行信息合并到单一 `Execution Plan`，`Risks & Catalysts` 收敛为四组：`Bullish Factors`、`Risk Factors`、`Catalysts / Watch Conditions`、`Market Sentiment`，移除重复的 bullish/bearish/mixed 独立块。缺失字段展示同步改造为“表格内关键字段仅显示 `NA`、非关键缺失下沉到审计区”，并在审计区提供四类归因（`integrated_unavailable / not_integrated_yet / source_not_provided / not_applicable`）与 `High/Medium/Low` 接入优先级分组，提升 API 接入排期可执行性。

- 🧭 **报告页信息架构重排为“四层决策流”并下沉冗余指标** — `StandardReportPanel` 调整为 `决策摘要 -> 图表/会话指标 -> 执行与风险 -> 深度附录`：首屏仅保留股票名/代码、最新价与涨跌、综合评分、操作建议、趋势判断和一句话结论；执行区收敛为“关键动作/关键风险/观察 Checklist”三块；大体量技术/财务表、评分拆解、催化与情绪等信息下沉到默认折叠的附录 disclosure，减少重复结论与首屏噪音，同时保持 `VITE_REPORT_LEGACY_FALLBACK=auto` 兼容路径不变。

- 🛡️ **B3 受控弃用准备：报告渲染新增 legacy fallback 开关与契约观测** — Web 报告分支新增 `VITE_REPORT_LEGACY_FALLBACK`（`on/off/auto`）受控策略，`standard_report` 作为主路径，legacy 分支降级为兼容回退；同时补齐 `legacy_only` 契约测试、switch 分支测试与 fallback 观测日志（含 `payloadVariant / standardReportSource / mode`），为后续最终移除 legacy 路径提供可回滚保障。

- 🧭 **三主题侧栏语言重构 + 壳层间距与交互动效再抛光** — Web 端新增侧栏专用 token（nav 几何、icon 容器、激活指示、分隔线、品牌块边框/阴影、rail framing），并在 `Dark Terminal / Cyberpunk / Geek(DOS)` 里分别落地为交易终端、赛博控制轨、单色 DOS 控制台三种侧栏语言，不再是同构侧栏仅换色。`Shell` 与 workspace split/chat 布局同时改为独立 `layout-shell-gap/layout-content-gap`，提高侧栏与主内容之间的结构间距，减少“贴边拥挤”感；导航项/图标容器/激活条与主区卡片的 hover/active 过渡也统一到 motion token，交互更平滑而不拖慢响应。

- 📱 **移动端问股加载失败与侧栏遮挡问题修复（含主题/交互动效细化）** — `dsa-web` 的问股链路新增流式请求兼容处理：`chatStream` 统一携带 `credentials`/SSE header，移动端不支持 `ReadableStream` 或流式端点不可用时自动回退到标准 `/agent/chat`，并在会话加载失败、策略加载失败、网络失败时给出可执行的错误指引与重试入口。首页移动端侧栏移除了重复任务队列，只保留历史面板，避免遮挡历史分析列表。交互层补充了 Drawer/ConfirmDialog 的平滑开关场动画，Cyberpunk 主题进一步压暗并降低高亮粉色占比，保持三主题在背景、圆角、字体与控件语言上的差异化。

- 🧱 **主题系统升级为“独立家族皮肤”并清理残留硬编码颜色** — Web 端进一步把 `Dark Terminal / Cyberpunk / Geek(DOS)` 收口为真正的全局主题家族：Cyberpunk 仅保留黑 + 粉 + 紫（去除可见 cyan/teal/green 残留），Geek / DOS 收敛为黑白灰单色终端。新增并对齐 `chart-toolbar / input / focus-ring` 等全局 token，状态条、历史选择框、任务队列、自动补全 market/match badge、分页、确认弹窗、内联告警、通用按钮与 loading 图标等组件全部改为 token 驱动，不再依赖 `bg-cyan` / `text-green-*` / `border-rose-*` 这类硬编码 Tailwind 色值。

- 🌌 **Cyberpunk / Geek(DOS) 主题再次重绘 + 品牌化启动加载页落地** — `dsa-web` 赛博主题不再以青色为主，而是切换为黑底 + 霓虹粉/紫主导的高对比视觉（按钮、激活 pill、导航、进度条、图表 chrome 与卡片边缘发光同步偏向 pink/purple）；Geek / DOS 主题则从绿黑终端改为近黑白灰的单色复古样式（低饱和、平面化、弱发光、mono 字体主导）。同时新增品牌化首屏加载体验：`index.html` 提供预挂载 splash fallback，React 挂载后由 `BrandedLoadingScreen` 接管，中心使用 `/image.png` logo 动画并在关键初始加载完成后平滑淡出，避免慢网环境先看到半成品页面。

- 🎨 **Web 主题系统重构为硬约束 token contract + 图表/历史滚动隔离加固** — `dsa-web` 主题切换不再依赖零散颜色覆写，新增并落地 `--bg-page / --bg-sidebar / --bg-card / --accent-* / --chart-* / --font-* / --progress-*` 等核心 token，并让 Sidebar、Hero、卡片、按钮、badge、dropdown、设置面板、任务队列、图表 toolbar/legend/candle 配色统一走 token 渲染；`Dark Terminal / Cyberpunk / Geek(DOS)` 的背景、边框、发光强度、字体与图表语义已显式拉开。History rail 与 K 线区同时加固 wheel/touch 事件消费、`passive` 监听、`overscroll-behavior` 与 `touch-action`，滚轮/拖拽在局部容器内交互时不再串联到整页滚动。

- 🧩 **History rail 在无任务场景下的真实滚动可达性修复** — Home 侧栏现在只在存在活动任务时渲染任务卡，避免空任务卡继续占用第二行并压缩历史区高度；历史卡容器同时固定为 `h-full + min-h-0` 的 bounded 区，确保 8+ 条历史记录可在同一卡片内继续滚动访问，而不是被 rail 裁剪后只显示前几条。

- 🧱 **历史分析滚动根因、字号设置与 K 线语义对齐修复** — 侧栏历史分析现在使用独立 card + 独立 viewport（`min-h-0` + bounded grid row），滚轮在历史卡内部只驱动历史列表本身，离开卡片后页面滚动恢复默认；并在列表底部继续保持 nested-scroll 场景下的 load-more 触发。设置页基础配置新增“字体大小”用户偏好（小/默认/大），持久化到本地并通过全局 CSS 变量受控生效。图表区的 range 语义也已重新对齐为 `1M=1分钟K`、`5M=5分钟K`、`1D=日K`，并补齐 `周K/月K/年K`，前后端周期参数与聚合规则保持一致，默认仍只开启 Candles + Volume。

- 🧭 **品牌位填充、独立历史卡、Key Action 提醒合并与 broker-style range defaults 再收口** — Sidebar 顶部 `WolfyStock` logo 现在会真正填满品牌图标位，避免小图悬在中间；首页左侧历史分析区重构为独立 card + 独立 viewport，鼠标滚轮进入历史卡后只驱动历史列表本身，older records 可以在 rail 内继续向下访问而不把主页面一起带动。任务队列则维持更紧凑的扫描式卡片，仅保留名称、代码、阶段、状态和创建时间，减少每个任务的垂直占用。Key Action 卡本身继续增密，并把 `Execution Reminder` 合并进同一卡片下半区，不再额外占一块竖向空间。图表默认态只显示 `Candles + Volume`，range 控件同步收敛为券商风格语义，并给 reset/zoom 控件单独留出右侧间距。

- 📈 **历史 rail 与 broker-style K 线继续收口** — 首页历史请求不再默认限制在最近 30 天，左侧 `HistoryList` 同时增加滚动阈值触发的分页加载兜底，避免在固定 rail 内滚到底后仍拿不到 Oracle 更早的记录。报告页 `ReportPriceChart` 现在把周线/月线历史拉长到 2~3 年范围，并把非分时视图的默认视窗从固定 64 根调整为整段历史，日/周/月 K 不再默认只剩约两个月；蜡烛体也改为实心填充，并降低长周期视图的最小 candle 宽度，减少密集重叠。

- 🐺 **品牌块、侧边历史 rail 与移动端密度继续收口** — Web 左上角导航品牌块改为使用新的 `WolfyStock` 图形资产与 `QUANTITATIVE SYSTEM` 副标题，替换旧的 `DSA` 名称与图标；Home 侧边 rail 继续压缩任务面板高度、收紧历史条目与列表头部间距，并移除历史请求层的 30 天截断，让更早的分析记录可以在固定高度侧栏里继续纵向滚动访问。与此同时，报告页和图表的移动端间距、时间框按钮、指标 pill、footer metrics 与 disclosure padding 继续压缩，减少空白和换行，保持 broker-style 的紧凑信息密度而不牺牲可读性。

- 🧭 **历史滚动、作战计划占位与 K 线交互继续收口** — 首页左侧 `HistoryList` 现在在 shell rail 中使用真实可收缩滚动容器，历史分析记录可以上下滚动到更早条目，不再因父层高度锁死而截断；标准报告页移除了“来源与覆盖 / 透明度”面板，让作战计划独占整行，并把顶部“关键动作”重排成左侧 bullet plan、右侧 3 条关键利好 + 3 条关键风险，减少空卡片与竖向浪费。市场图表则去掉了与十字光标重复的行情 KPI 卡片，只保留固定 inspector 与指标标线，并通过 `wheel preventDefault + stopPropagation` 配合 `overscroll-behavior: contain` / `touch-action: none` 阻止滚轮缩放时同时带动页面上下滑动，使 K 线交互更接近交易终端。

- 🧩 **统一报告 schema、UI 语言切换、任务队列与交互图表继续收口** — `report_renderer` 现在会在 `standard_report` 中额外产出 `channel_summary`，让完整 Markdown、Discord 精简通知和 brief/homepage 摘要都从同一份结构化对象读取评分、建议、趋势、结论、价格、执行位、风险/利好、最新更新与 checklist，而不是各自拼接字段；`NotificationService.generate_dashboard_report()` 也会在返回 Markdown 前预热 Discord 专用缓存，修复 Discord 明明有数据却仍回退成 `NA` 或继续发送整份长 Markdown 的问题。Web 前端新增全局中英 i18n provider 与语言切换器（默认中文并持久化），并把首页、侧栏、设置页、主题菜单、任务状态、历史列表、图表标题/按钮等首路径文本抽到资源文件；首页任务区改成保留最近任务的队列面板，支持 `queued / analyzing / generating / notifying / completed / failed` 阶段、刷新后恢复与最近完成任务保留。图表侧则修复月线 `days=730` 越界问题，移除多余说明文案，新增指标显隐、缩放、拖拽平移、tooltip 跟踪与更清晰的价格/时间/成交量分区，并让主题菜单、报告面板和测试基线与新的本地默认语言保持一致。

- 🧭 **报告顶部价格语义、金融图表与全局工作区壳层继续收口** — `report_renderer` 现在会把顶部主价明确标成 `Analysis Price`，并用 `Intraday snapshot / Last close / Regular-session close` 区分盘中快照、已收盘与扩展时段基准，避免把分析基准价误导性写成“实时当前价”；同一 bundle 内的 `Prev Close / Open / High / Low / Change` 会一起落盘，盘中场景不再额外展示语义暧昧的 `Reference Close`。Web 报告页的主摘要下方同步改为 API 驱动的金融图表：`1D / 1M / 3M / 1Y / W / M` 视图、真正按价格坐标绘制的 K 线 / 日内图、成交量副图、MA5/10/20 与支撑/压力/买点/止损/目标位标线，替代原先的大面积空白和弱线图；桌面端 Hero 改成“宽主价格区 + 紧凑状态栏”的双栏终端布局，移动端则把次级元信息折叠、让 chart 与 market stats 更早进入首屏。分析完成后的“最新报告已打开”提示则改为自动消失的 toast，不再长期占用主页面。`Shell` / `ChatPage` / `HomePage` 同步统一 desktop rail 宽度、workspace max-width 与断点间距，继续修复 Home / Query / Holdings / Backtest / Settings 路由切换时的缩进与壳层不一致问题；本轮还补上 `workspace-split-layout--main-only` 与基于实际内容宽度触发的 Hero 桌面模式，避免历史 rail 已外置到 shell 后，浏览器放大/全屏时主报告仍误落进窄 rail 列而被挤扁。Cyberpunk / Geek(DOS) 也继续在 badge、卡片、按钮、侧栏和图表上呈现明显不同的视觉语言。
- 🧭 **报告自动打开、交易计划结构化重算、移动端滚动与主题分化同步落地** — `report_renderer` 不再机械复用松散 sniper point，而是按 recent support / resistance、MA5/10/20/60、日内波动与 52 周语境重算 `理想买点 / 次优买点 / 止损 / 目标一区 / 目标二区 / 目标区间 / 仓位建议`，并把 quiet-news 场景下的 risk / catalyst / sentiment 自动补齐为“公司级 → 行业/市场级 → 技术语境”三层摘要；Web 首页在分析任务完成后会重试拉取并自动打开最新历史报告，失败时给出 `View latest report` CTA，同时把当前选中的报告 ID 持久化以便刷新后恢复；Home / Holdings / Backtest 共用统一 workspace 宽度与间距体系，移动端移除固定高度与嵌套滚动陷阱，恢复正常纵向浏览；`cyber / hacker(Geek / DOS)` 主题则升级为真正的 design-token 级切换，连同字体、圆角、按钮、输入框、卡片、历史列表和壳层背景一起改变，避免主题只剩轻微色差。
- 🎯 **分析状态自动聚焦、移动端滚动与主题表面继续收口** — Web 前端本轮没有再改后端数据逻辑，而是围绕实际产品体验补齐三处关键缺口：分析任务完成后，首页会自动定位并选中同股票的最新历史报告、滚动到结果区，并对刚生成的记录做短时高亮，避免用户手动去历史列表里寻找结果；Home/Ask 的根容器同时修正为移动端可正常纵向滚动、桌面端才使用受控滚动，不再因固定高度与 `overflow-hidden` 造成手机端下拉失效；主题系统也继续从“技术上能切换”推进到“关键表面真实响应主题”，历史列表、任务区、问股侧栏、主题菜单、实体卡片与列表项全部改为基于 theme token 渲染，配合 `terminal / cyber / hacker` 的字体、panel 和 surface token，让三套主题在实际工作台里有可读、克制但明确的视觉差异。
- 🎛️ **中段信息密度与主题系统落地继续收口** — `StandardReportPanel` 中部的“风险与催化 / Checklist 与评分”不再保留高而空的大黑块：风险、利好、最新动态、情绪摘要改成更紧凑的 2x2 信息卡，动态去重展示 2~4 条真实催化/风险和 1~3 条真实更新；Checklist 行高、状态 pill 和评分拆解也同步压缩，评分说明改成更短的 definition-grid，减少纵向空耗。与此同时，Web 主题切换不再只是菜单占位：`ThemeProvider` 现在会把主题 preset 真正写入 `document.documentElement` / `body` 和 localStorage，并通过新的 shell/sidebar/report surface token 驱动深黑终端、赛博朋克、Geek Hacker 三套可读暗色预设，让 Shell、导航、Hero、报告卡片和主要表面在切换后有真实可见差异，而不是只有按钮变色。
- 🌒 **分析状态条、主题系统与全站工作区一致性继续收口** — Web 前端本轮继续只做当前本地产品态 polish：首页在提交分析后会立即显示结构化状态条，用统一阶段映射展示“已提交 / 排队中 / 拉取数据 / 生成分析 / 已完成 / 失败”，并对 FMP 403、Gemini 503、409 重复任务等异常给出更产品化的提示；主题切换器从占位按钮升级为可持久化的深黑终端 / 赛博朋克 / Geek Hacker 三套暗色预设；Home、Ask、Portfolio、Backtest、Settings 统一改用共享 workspace header / surface / spacing 体系，减少页面之间的缩放和密度割裂；标准报告页则继续去掉设计草稿式文案，强化综合评分 / 操作建议 / 趋势判断的视觉层级，并让缺失值、source、status 在首页更克制、在完整报告里更集中。后端同时补上健壮 `.env` 加载器，兼容本地 `.env` 首行 `source ...` 这类 shell 前导语句，不再触发 `python-dotenv could not parse statement starting at line 1` 的解析报错。
- 🧭 **首页决策优先、完整报告 canonical 结构与问股工作台继续收口** — `report_renderer` 新增统一的 `decision_panel / reason_layer / coverage_notes` 结构，用同一套结论顺序同时驱动首页 structured view、完整 Markdown 报告、history detail 和 Discord compact digest：先输出评分/建议/趋势、一句话结论、当前价与涨跌，再给出买点/止损/目标/仓位、核心风险、核心利好、最新关键更新和 checklist 摘要。Web `StandardReportPanel` 也同步把首页结构改成“Hero 总览 -> 决策执行面板 -> 理由层 -> 证据层 -> 覆盖说明”，把执行位和风险/催化提前，把技术/基本面表下沉为 evidence layer；`ChatPage` 则继续收口成研究助手工作台，补齐高价值起手问题卡、结构化研究模式区和更紧凑的输入编排，减少空白与工程噪音。
- 🧩 **前端工作栏整合 + Hero 压缩 + 策略面板继续收口** — Web `Shell / SidebarNav / HomePage / HistoryList / TaskPanel / StandardReportPanel` 本轮不再推翻骨架，而是继续做版面收口：Shell 新增统一 rail 上下文，把左侧 DSA 导航、历史分析和任务列表整合成同一深黑工作栏；首页主内容最大宽度明显放开，减少桌面端左右黑边；Hero Summary 压缩成更紧凑的两列布局，把时间信息改成紧凑 row，减少评分区空白；下层模块按“行情/技术、基本面/财报、新闻/作战计划、Checklist/评分拆解”的阅读节奏重新平衡；作战计划改成真正的横向策略面板，上层四格展示关键价位，下层两列展示仓位、建仓与风控说明，并统一列表项、按钮和卡片的轻量过渡，形成更顺滑但不花哨的终端式交互。
- 🖥️ **整站壳层改成深黑 Web3 terminal，并把标准报告页重排成大矩形纵向模块** — Web `Shell / SidebarNav / HomePage / HistoryList / TaskPanel / StandardReportPanel` 继续从旧黑蓝 dashboard 骨架收口到统一的深黑石墨主题：左侧 DSA 导航、历史列表、任务面板和报告工作区全部去掉蓝色 glow 外壳，改成近黑实体面板 + 低亮边框 + 少量 cyan 强调；标准报告页也不再保留 tabs/chips/窄侧栏，而是直接重排为“顶部 Hero 总览 -> 行情/技术并排 -> 基本面/财报并排 -> 新闻/作战计划并排 -> Checklist/评分拆解/风险摘要宽卡片”的大矩形卡片序列，桌面端允许纵向滚动浏览，平板端优先主内容，手机端则按总览、行情、技术、基本面、财报、新闻/情绪、作战计划、checklist 的固定顺序单列展开，避免横向滚动和窄长条阅读。
- 🧱 **NVDA 关键口径继续收口 + Web 报告页改成大矩形终端布局** — `pipeline` / `us_fundamentals_provider` 继续把 `freeCashflow / operatingCashflow / returnOnEquity / returnOnAssets` 的来源与时间窗显式下沉到 `_meta.field_sources / field_periods`，并在汇总基本面时把 `latest_quarter`、`provider_reported_total`、`overview/context` 这类高风险口径打成 `TTM待复核`，由 `report_renderer` 统一展示为 `NA（口径冲突，待校正）`，避免把可疑 ROE/ROA/FCF 直接暴露给用户。新闻 highlights 也继续修正语义：陈旧财报复盘归入催化/业绩预期，媒体解读类内容优先路由到风险/情绪，而非伪装成“最新动态”。Web 标准报告页则进一步抛弃窄条与碎卡片，改成更接近交易终端的“左历史窄栏 + 中间大矩形主内容 + 右侧辅助栏”结构：中间主内容按总览、行情/技术、基本面/财报、新闻/作战计划纵向分层，整体去掉黑蓝外壳、弱化来源胶囊与蓝色 glow，统一成深黑石墨终端主题。
- 🎛️ **同 session 评分稳定器改为分项合成 + Web 报告页重构为深黑终端布局** — `pipeline` 不再只对 LLM 黑箱总分做事后限幅，而是显式拆成“行情/趋势分、技术分、基本面分、新闻/情绪分、风险修正项”后再合成总分，并在 `last_completed_session` 下优先锚定同一交易日/同一 session 的历史基线：当核心输入未变时严格限制单次漂移，技术指标补齐、新闻新增、provider 口径切换等场景则通过 `change_reason` 与 `score_breakdown` 解释来源。Web `StandardReportPanel` 同步放弃旧的黑蓝卡片堆叠骨架，改成更接近 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 的深黑 exchange terminal：顶部 summary strip、一级 tabs、二级 chips、左中右 dense table/rail 布局，以及底部新闻/作战计划区，整体减少 glow、卡片数和无效留白。
- 🧮 **NVDA 基本面 TTM 口径与新闻时效语义继续收口** — `pipeline` 对美股基本面字段新增更细的 source priority：`freeCashflow / operatingCashflow` 优先使用 statement-derived TTM（FMP quarterly statements 优先，其次 Yahoo quarterly），`returnOnEquity / returnOnAssets` 优先使用 FMP/Finnhub 的 TTM ratios，再回退其他 overview 源，避免现金流总额和 ROE/ROA 混用不同时间窗。`report_renderer` 会把这些字段的 `来源 + 口径` 一并带进基本面/财报表，并在新闻 highlights 中将“陈旧财报复盘”从 `最新动态` 降级为催化/业绩语境，避免把 2026-02-25 的财报解读伪装成 2026-03-28 的新公告。Web `StandardReportPanel` 继续去卡片化：表格来源/口径改为终端式细文本列，右侧侧栏精简为评分/风险/情绪/checklist，整体进一步靠近 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 的深黑 terminal 风格。
- 📉 **已收盘场景行情主口径修正 + Web 终端式结构继续收口** — `report_renderer` 不再把 `close` 当作 `prev_close` 的兜底来源；当美股处于 `last_completed_session` 且上游昨收缺失、被错误平盘化，或 `close / prev_close / change / pct` 出现互相打架时，会优先按同一套 regular close 口径重建昨收并重算涨跌，避免 NVDA 这类已收盘场景出现“收跌但昨收等于收盘、涨跌额/幅却是 0”的假平盘。`history_service` 同步在历史详情重建时修复这类污染快照，`pipeline` 的美股 fallback 也补充识别 `regularMarketPreviousClose / chartPreviousClose`。Web `StandardReportPanel` 则继续参考 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 收口为更像终端的结构：顶部 summary strip、一级 tabs、二级 chips、左侧高密度表格、右侧评分/风险/checklist 侧栏，减少卡片堆叠、压缩留白，并统一 badge / chip / checklist 的黑灰基调与尺寸。
- 🧭 **评分稳定器与深黑终端式报告页重做** — `pipeline` 新增分析结果稳定器：把“短线技术趋势”和“综合操作建议”显式分层，降低空头排列、MA20 下方、放量下跌、RSI 偏弱等单一技术因子对综合评分的瞬时压制；当近期历史分数存在时会对单次评分变动做限幅，并在“强基本面 + 短线偏弱”的场景下保留基本面缓冲，避免 NVDA 这类大票因补齐技术字段后直接从中性/观望跳到强烈看空。`report_renderer` 同步输出 `decision_context`（短线视角 / 综合建议 / 调整说明 / 分数变化），Web `StandardReportPanel` 则按 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 的信息架构重排为更克制的深黑 terminal 风格：顶部 summary strip、一级 tabs、二级 chips、左侧高密度表格、右侧评分/趋势/风险/checklist/结论框架，并统一 badge / checklist pill / 表格行高与卡片边框层级，去掉过强 cyan glow 与多余 icon 底框。
- 📡 **技术指标改为 API 优先 + Web 报告改成 OKX 风格终端布局** — `pipeline` / `us_fundamentals_provider` 新增 FMP technical indicator 接入，`MA5 / MA10 / MA20 / MA60 / RSI14` 现在优先取 FMP technical API，`VWAP` 优先取 FMP historical price；FMP 缺失时再回退 Alpha Vantage 或本地历史 OHLC 计算，避免 NVDA / TSLA / ORCL 这类大票长期落在“样本不足”。`report_renderer` 会把技术字段的 `source / status` 一并写入 `standard_report`，Web `StandardReportPanel` 同步改成更接近 OKX markets/prices 的深黑终端式布局：顶部 Hero 总览、一级 tabs、二级 chips、左侧紧凑表格、右侧信号/风险/checklist，并统一 badge / checklist / 表格视觉。
- 🛡️ **多源 fallback 防回归与历史详情保真** — `pipeline` / `history_service` / `report_renderer` 继续收紧美股行情与基本面合并规则：已有有效 quote / fundamentals 不再被 `None`、空字符串、占位 `0` 或 `0.0` 污染；`market_timestamp` 会随 fallback quote 继续透传；历史详情重建会把 `trend_score=0`、`volume_ratio=0.0`、`turnover_rate=0.0`、占位均线等假零值替换为 `context_snapshot` 中的真实值。渲染层同步把量比、换手率、趋势强度等缺失指标恢复为 `NA（原因）`，避免 TSLA 等美股报告出现“字段还在但几乎全部退化成 NA / 0.00”的回归。
- 🌑 **Web 报告页 dark terminal 质感继续收口** — `StandardReportPanel` / `Badge` 继续沿用统一 `standard_report` 数据，但把页面层级调整为更成熟的黑色 trading terminal 风格：去掉重复标题，弱化过度 glow，统一 badge / checklist pill 尺寸与居中对齐，把“时效性 / 市场时间 / 交易日 / session”下沉为次级 chip 信息，并让 Hero 区优先突出股票名、当前价、涨跌幅、评分、建议与趋势，减少“半成品 demo 感”。

- 🌌 **TSLA 等美股标准报告口径校正 + Web3 Dark Dashboard 改版** — `report_renderer` / `history_service` / `pipeline` 进一步统一行情、基本面、财报三类字段语义：常规时段涨跌额/幅继续优先按当前价与昨收重算；`market_session_date` 改为优先从真实 `market_timestamp` 推导，避免美东交易日被本地时区误写；扩展时段时间不再误复用常规时段时间；基本面表去除与财报表混口径的增长字段，并通过 `TTM / 最新值 / 一致预期 / 最新季度同比/环比` 标签显式标注口径；MA5 / MA10 / MA20 / MA60 / VWAP 缺失时继续输出 `NA（原因）`，样本不足不再伪装成 `0.00`。Web 报告详情页则改为更紧凑的 web3 dark / terminal 风格 Hero + 双栏 dashboard 布局，统一 checklist pill、badge、半透明深色卡片、紧凑表格和评分/趋势/均线位置条，同时补齐 `standard_report` snake_case -> camelCase 归一化，确保 Web 与 Discord 继续共用同一 `standard_report` 结构。
- 📘 **标准报告升级为紧凑投资简报视图** — `standard_report` 在服务层新增 `summary_panel / table_sections / visual_blocks / highlights / battle_plan_compact / checklist_items` 等结构化块，Web 端首屏改为摘要卡片、紧凑指标表、评分/价格位置条、风险机会摘要、紧凑作战计划和状态化 checklist，Discord 端则从统一 markdown 中抽取短版摘要，只保留顶部结论、核心行情、技术定位、风险/利好和作战计划，避免继续推送超长字段转储。
- 🇨🇳 **标准报告用户可见字段统一中文化，并接入美股/新闻补数 fallback** — `standard_report` 的 market / technical / fundamental / earnings / sentiment 用户可见字段标签统一由后端渲染层输出中文，避免 Web、Discord 与 history markdown 各自翻译导致口径漂移；同时为美股补充 Finnhub `quote + basic metrics + company news`、FMP `quote + profile + ratios + quarterly statements + historical price`、GNews 通用新闻兜底，优先在现有数据源缺失时补齐昨收、涨跌额/幅、振幅、成交量、52 周高低、MA5/10/20/60、VWAP、Beta、PE/PB、marketCap、shares/float、营收/净利润及新闻发布时间等字段，并继续保持 regular / extended session 分离与 `NA（原因）` 语义。
- 🧾 **标准报告字段映射补全与 Discord 推送稳态修复** — `report_renderer` 会继续沿用统一 `standard_report` 结构，但现在会补消费 `market_snapshot`、`structured_analysis`、`realtime_context`、`market_context`、`fundamental_context`、`earnings_analysis` 中已存在的行情/技术面/基本面字段，减少“上游已有数据却仍显示 `NA`”的情况，并保持 regular / extended session 分离；history 详情重建会合并 `context_snapshot` 补全 `details.standard_report`，Web 端同步兼容 `standardReport` / `standard_report` 回退；Discord 推送改为优先基于统一标准报告内容，补齐配置判定、稳定分块、逐块日志与失败原因输出，并接受任意 2xx 响应为成功，避免静默失败。
- 🧱 **标准报告数据结构下沉到服务层** — `report_renderer` 现在先构建单一 `standard_report` 数据结构，再由 Web Markdown/Discord 消息共用渲染；历史详情 API `details.standard_report` 同步暴露该结构，避免网站、通知和客户端各自重复拼字段导致口径漂移。
- 📣 **Discord 完整报告可读性与资讯价值分级修复** — 在不删字段前提下将 Discord 中的大表格转换为紧凑列表展示；重要信息区新增高价值关键词优先与低价值资讯降权，缺少高价值催化/动态时明确提示“未发现高价值新增催化/动态”。
- 🧮 **报告口径一致性与交易位校验补齐** — 在报告渲染层新增行情口径一致性重算与告警（涨跌额/涨跌幅按当前价与昨收校验），并在作战计划中新增买点类型标注（突破买点/回踩买点）及止损位风险提示，避免 Discord/Web 完整报告出现交易语义自相矛盾。
- 🧾 **Discord/Web 完整报告语义统一（NA 原因 + 北京时间 + 一致格式化）** — 报告渲染统一走同一模板链路，Discord 不再做内容压缩删减，仅按长度分块；Web 与 Discord 共享字段与 section 语义。缺失字段统一展示为 `NA（原因）`，并补齐“报告生成时间（北京时间）/市场时间（原始+北京时间）/交易日/会话类型”显示；价格与比例统一两位小数，成交量/成交额按可读单位输出。
- 🧩 **Web 报告链路缺失字段兜底语义收敛** — 前端在解析分析/任务状态/历史详情报告时新增统一归一化：当 `summary` 必填字段缺失时回填安全默认值（含 `sentiment_score=50`），并优先用顶层响应元信息补齐 `meta` 关键字段，避免因后端局部缺字段导致报告渲染异常或语义漂移。
- 🕒 **统一时间字段契约与诊断可观测性补齐** — Pipeline/API/Renderer 统一追加 `market_timestamp`、`market_session_date`、`news_published_at`、`report_generated_at`（均为 ISO 8601 且保留原始市场时区），并新增 `session_type` 标记（`intraday_snapshot` / `last_completed_session`）；`data_quality.provider_notes` 现在持续输出 provider 失败链路与时间契约快照，`diagnostic_mode` 开启时会输出完整诊断块，关闭时保持兼容默认行为。
- 🧠 **Sentiment 公司相关性过滤升级（规则版）** — 在不引入重模型前提下新增 relevance gating 与分类（`company_specific` / `industry_general` / `regulatory` / `low_relevance`），输出 `relevance_type`/`relevance_score`，并确保 `industry_general` 默认不进入个股核心结论；无高相关信息时统一降级 `no_reliable_news + low confidence`。
- 🧭 **多维分析数据质量与来源可追溯增强（美股优先）** — 新增技术指标来源追踪（`local_from_ohlcv` / `alpha_vantage_fallback`）、`data_quality` 结构化状态与告警注入（含 provider failure warnings）；当基本面/财报/情绪缺失时，报告与提示词将显式说明 partial/no_reliable_news，避免“隐性默认值”伪完整结论。
- 🇺🇸 **美股分析链路闭环修复** — 美股实时行情链路改为明确标记 `yfinance`（仅真实降级时显示“降级兜底”），并在 pipeline 统一补算 `volume_ratio`（当日成交量 / 5 日均量）；新增 Alpha Vantage `OVERVIEW` 的 `SharesOutstanding` 缓存读取并据此计算 `turnover_rate`，缺失时不再错误展示 `0%`，统一显示“数据缺失”；通知与 Markdown 报告中美股筹码改为固定文案“美股暂不支持该指标”，不再显示 A 股筹码占位缺失信息。
- 🧾 **Web 报告透明度区复制按钮层级修复**（#749）— `ReportDetails` 中“原始分析结果 / 分析快照”的复制按钮补齐可点击层级，避免被下方 JSON 内容覆盖后出现按钮可见但无法点击的问题。
- 🧾 **Web 报告详情复制提示按面板独立** — `ReportDetails` 中“原始分析结果”和“分析快照”的复制提示不再共享同一个 `copied` 状态；当两个面板同时展开时，复制其中一个只会更新对应按钮文案，避免两个按钮同时显示“已复制”的误导反馈。
- 📊 **Agent backtest tool semantics** — `get_skill_backtest_summary` 现在要求显式传入 `skill_id`，缺失时会返回明确的校验提示；当仓库尚未持久化真实 skill 级汇总时会返回明确的 unsupported/info 响应，而不再复用 overall 指标。成功返回路径会同时保留 normalized 指标和 `*_pct` 兼容字段，相关工具错误返回也改为稳定通用文案，避免向 agent 或用户暴露底层异常细节。

## [3.9.0] - 2026-03-20

### 发布亮点

- 🤖 **模型链路与报告语言更灵活** — Agent 现在可以通过 `AGENT_LITELLM_MODEL` 独立选择模型链路，普通分析与 Agent 报告也可通过 `REPORT_LANGUAGE=zh|en` 输出统一语言，减少“英文内容 + 中文壳子”这类混排问题，并允许团队分别权衡主分析与 Agent 的成本、速度和能力。
- 🔎 **首页分析体验完成一轮闭环优化** — 首页新增 A 股自动补全，支持代码、中文名、拼音和别名检索；同时 Dashboard 状态收口到统一 store，历史、报告、新闻与 Markdown 抽屉的交互更稳定，“Ask AI” 追问也会优先携带当前报告上下文。
- 💬 **通知与检索能力继续外扩** — 新增 Slack 一等通知渠道；SearXNG 在未配置自建实例时可以自动发现公共实例并按受控轮询降级；Tavily 时效新闻链路修复后，严格时效过滤不再错误丢光有效结果。
- 💼 **持仓与市场复盘链路更稳** — A 股 market review 可选接入 TickFlow 强化指数与涨跌统计；持仓账本写入改为串行化以缩小并发超卖窗口；汇率刷新入口和禁用态提示也更加清晰，减少用户误判。

### 新功能

- 🔎 **Web 股票自动补全 MVP** — 首页分析输入框新增本地索引驱动的自动补全，支持股票代码、中文名、拼音和别名匹配；选中候选后会提交 canonical code，并透传 `stock_name`、`original_query`、`selection_source` 到分析请求、任务状态和 SSE 事件；索引加载失败时自动退回旧输入模式，不阻断原有提交流程。同步补充了静态索引加载器、索引生成脚本和前后端契约测试。分阶段进行开发，第一阶段仅支持 A 股。
- 💬 **Slack 一等通知渠道** — 新增 Slack 原生通知支持，同时支持 Bot Token 和 Incoming Webhook 两种接入方式；同时配置时优先使用 Bot API，确保文本与图片发送到同一频道；Bot Token 模式支持图片上传（raw body POST，不使用 multipart）；新增 `SLACK_BOT_TOKEN`、`SLACK_CHANNEL_ID`、`SLACK_WEBHOOK_URL` 配置项，GitHub Actions 工作流同步补齐对应 Secrets 传递。
- 🌍 **报告输出语言可配置**（Issue #758）— 新增 `REPORT_LANGUAGE=zh|en`，默认 `zh`；语言设置会同步注入普通分析与 Agent Prompt，并覆盖 Markdown/Jinja 模板、通知 fallback、历史/API `report_language` 元数据及 Web 报告页固定文案，避免“英文内容 + 中文壳子”的混合输出。
- 🚀 **Agent 与普通分析模型解耦**（Issue #692）— 新增 `AGENT_LITELLM_MODEL`（留空继承 `LITELLM_MODEL`，无前缀按 `openai/<model>` 归一）；Agent 执行链路与 `/api/v1/agent/models` 的 `is_primary/is_fallback` 标记改为基于 Agent 实际模型链路；系统配置与启动期校验补齐 `AGENT_LITELLM_MODEL` 的 `unknown_model/missing_runtime_source` 检查；Web 设置页新增 Agent 主模型选择并与渠道模式运行时配置同步。
- 🔎 **SearXNG 公共实例自动发现与受控轮询**（#752）— 新增 `SEARXNG_PUBLIC_INSTANCES_ENABLED`，在未配置 `SEARXNG_BASE_URLS` 时默认从 `searx.space` 拉取公共实例列表，并按受控轮询顺序选择实例；同次请求内遇到超时、连接错误、HTTP 非 200 或无效 JSON 会自动切换到下一个实例。已配置自建实例的用户保持原有优先级与语义不变；`daily_analysis` GitHub Actions 工作流也已支持显式透传该开关并在启动日志中展示当前状态。
- 📈 **TickFlow market review enhancement** (#632) — 新增可选 `TICKFLOW_API_KEY`；配置后，A 股大盘复盘的主要指数行情优先尝试 TickFlow；若当前 TickFlow 套餐支持标的池查询，市场涨跌统计也会优先尝试 TickFlow。失败或权限不足时立即回退到现有 `AkShare / Tushare / efinance` 链路；板块涨跌榜回退顺序保持不变。接入层同时适配了真实 SDK 契约：主指数查询按单次请求上限分批拉取，并将 TickFlow 返回的比例型 `change_pct` / `amplitude` 统一转换为项目内部的百分比口径。

### 改进

- **Dashboard state slice and workspace closure** — moved Home / Dashboard state into `stockPoolStore`, consolidated history selection, report loading, task syncing, polling refresh, and markdown drawer handling under a single state slice.
- **Dashboard panel standardization** — kept the current dashboard layout contract stable while unifying history, report, news, and markdown presentation with shared tokens, standardized states, and bounded in-panel scrolling for the history list.
- **Dashboard-to-chat follow-up bridge** — routed “Ask AI” follow-ups through report-context hydration instead of direct cross-page state coupling, while keeping chat sends usable when enriched history context is still loading.
- 🧩 **Agent skill unification**（#779）— Multi-Agent runtime, API, Web chat, and config metadata now treat YAML trading profiles as a single `skill` concept; `/api/v1/agent/skills` becomes the primary discovery endpoint, `AGENT_SKILL_*` becomes the primary config surface, and legacy `strategy` names remain only as compatibility aliases.
- 🗂️ **Skill bundle alignment** — `SkillManager` now supports mainstream `SKILL.md` bundles with YAML frontmatter and supporting files, while the multi-agent runtime’s optional forked execution path is renamed to `specialist` mode to keep “skills” and “specialist sub-agents” as separate concepts.
- 🧭 **Skill metadata drives defaults** — built-in skill YAML files now declare their own aliases, default activation flags, router fallback participation, ordering priority, and market-regime tags; factory/router/Bot `/ask`/Web chat default selection no longer hardcode `bull_trend`-centric behavior in code.
- 💼 **持仓账本并发写入串行化**（#742）— 持仓源事件写入/删除现在会在 SQLite 下先获取串行化写锁，减少并发卖出把超售流水写入账本的窗口；直接持仓写接口在锁竞争时返回 `409 portfolio_busy`，CSV 导入保持逐条提交并把 busy 计入 `failed_count`。
- 💱 **持仓页汇率手动刷新入口补齐**（#748）— Web `/portfolio` 页面现在会在“汇率状态”卡片中展示“刷新汇率”按钮，直接调用现有 `POST /api/v1/portfolio/fx/refresh` 接口；刷新后会仅重载快照与风险数据，并以内联摘要反馈“已更新 / 仍 stale / 刷新失败”的结果，减少用户对 `fxStale` 长时间停留的误解。

### 修复

- 🔎 **Web 自动补全 Enter 提交语义修正** — 股票自动补全在搜索命中候选时不再默认高亮第一项；候选列表展开但用户尚未用方向键或鼠标明确选中时，按 Enter 会继续提交原始输入，避免手动输入被第一条候选静默覆盖。
- 🌍 **补齐 `REPORT_LANGUAGE` 启动解析与历史展示本地化边界** — `Config` 在启动时继续遵循“真实环境变量优先、`.env` 兜底”的既有语义，并在两者冲突时输出显式告警，减少 `REPORT_LANGUAGE` 来源不清带来的误判；同时 `/api/v1/history/{id}` 英文详情响应会同步本地化 `sentiment_label`，历史 Markdown 也会正确识别英文 `bias_status` 的风险等级 emoji，避免出现 `乐观` 或 `🚨Safe` 这类中英混排/误报展示。
- 📰 **Tavily 时效新闻检索发布时间映射修复**（#782）— Tavily 在股票新闻和严格时效的情报维度中现在会显式使用 `topic="news"`，并兼容 `published_date` / `publishedDate` 两种发布时间字段；修复了 Tavily 明明返回结果却在后续硬过滤阶段被全部记为 `drop_unknown` 丢弃的问题，同时将机构分析、业绩预期、行业分析等分析型维度恢复为宽源搜索，不再被统一压缩成新闻模式。
- 💱 **持仓页汇率刷新禁用语义修正**（#772）— 当 `PORTFOLIO_FX_UPDATE_ENABLED=false` 时，`POST /api/v1/portfolio/fx/refresh` 现在会返回显式 `refresh_enabled=false` 与 `disabled_reason`，Web `/portfolio` 页面会明确提示“汇率在线刷新已被禁用”，不再误报“当前范围无可刷新的汇率对”。
- 🤖 **Agent timeout and config hardening** — `AGENT_ORCHESTRATOR_TIMEOUT_S` now also protects the legacy single-agent ReAct loop, parallel tool batches stop waiting once the remaining budget is exhausted, and invalid numeric `.env` values fall back to safe defaults with warnings instead of crashing startup.
- 🌐 **CORS wildcard + credentials compatibility** — `CORS_ALLOW_ALL=true` no longer combines `allow_origins=["*"]` with credentialed requests, avoiding browser-side cross-origin failures in demo/development setups.
- 🧭 **Unavailable Agent settings hidden from Web UI** — Deep Research / Event Monitor controls are now treated as compatibility-only metadata in the current branch and are removed from the Settings page to avoid exposing non-functional toggles.
- 🔧 **Skill compatibility hardening** — `allowed-tools` from `SKILL.md` now stays as bundle metadata instead of leaking into runtime tool selection, `/api/v1/agent/strategies` again preserves the legacy `strategies` payload shape, explicit `skills: []` clears stale chat context, and skill-level backtest rollups stay neutral until real per-skill stats exist.
- 🎯 **显式策略选择不再叠加默认多头基线** — Agent 仅在未显式选择策略时才注入默认趋势交易基线；当用户或配置明确指定某个策略 skill 时，分析将只遵循所选策略，不再偷偷附带旧的 bull-trend 默认哲学。
- 🧭 **隐式默认策略收敛为单一多头默认值** — 当 `AGENT_SKILLS` 留空且请求未显式传入策略时，后端不再同时激活多个 `default_active=true` 的 skill，而是统一回落到主默认策略 skill（当前为 `bull_trend`），让 API / Bot / Web 对“默认策略”的理解保持一致。

### 文档

- 新增 Ollama 本地模型配置说明，同步更新 `README.md` 与 `docs/README_EN.md`（Fixes #690）
- 完善 Ollama 配置说明：`docs/full-guide.md` / `docs/full-guide_EN.md` 环境变量表与 Note 补充 `OLLAMA_API_BASE`，避免英文用户误以为 Ollama 不能作为独立配置入口；合并重复的 `OLLAMA_API_BASE` 条目为单一条目
- 明确文档同步治理边界：补充 `README.md`、专题文档、双语文档与交付说明之间的默认同步规则，减少后续文档漂移
- 调整 Agent 术语兼容文案：用户入口继续以“策略”为主称呼，README、双语文档、设置页与问股界面补充 `skill` 作为内部统一命名，降低迁移期理解成本

## [3.8.0] - 2026-03-17

### 发布亮点

- 🎨 **Web 界面完成一轮骨架升级** — 新的 App Shell、侧边导航、主题能力、登录与系统设置流程已经串成统一体验，桌面端加载背景也完成对齐。
- 📈 **分析上下文继续补强** — 美股新增社交舆情情报，A 股补齐财报与分红结构化上下文，Tushare 新接入筹码分布和行业板块涨跌数据。
- 🔒 **运行稳定性与配置兼容性提升** — 退出登录会立即让旧会话失效，定时启动兼容旧配置，运行中的 `MAX_WORKERS` 调整和新闻时效窗口反馈更清晰。
- 💼 **持仓纠错链路更完整** — 超售会被前置拦截，错误交易/资金流水/公司行为可以直接删除回滚，便于修复脏数据。

### 新功能

- 📱 **美股社交舆情情报** — 新增 Reddit / X / Polymarket 社交媒体情绪数据源，为美股分析提供实时社交热度、情绪评分和提及量等补充指标；完全可选，仅在配置 `SOCIAL_SENTIMENT_API_KEY` 后对美股生效。
- 📊 **A 股财报与分红结构化增强**（Issue #710）— `fundamental_context.earnings.data` 新增 `financial_report` 与 `dividend` 字段；分红统一按“仅现金分红、税前口径”计算，并补充 `ttm_cash_dividend_per_share` 与 `ttm_dividend_yield_pct`；分析/历史 API 的 `details` 追加 `financial_report`、`dividend_metrics` 可选字段，保持 fail-open 与向后兼容。
- 🔍 **接入 Tushare 筹码与行业板块接口** — 新增筹码分布、行业板块涨跌数据获取能力，并统一纳入配置化数据源优先级；默认按上海时间区分盘中/盘后交易日取数，优先使用 Tushare 同花顺接口，必要时降级到东财。
- 🧱 **Web UI 基础骨架升级** — 重建共享设计令牌与通用组件，新增 App Shell、Theme Provider、侧边导航，并同步调整 Electron 加载背景，为 Web / Desktop 的统一体验打底。
- 🔐 **登录与系统设置流程重做** — 重构 Login、Settings 与 Auth 管理流程，补上显式的认证 setup-state 处理，并让 Web 端与运行时认证配置 API 行为对齐。
- 🧪 **前端回归与冒烟覆盖补强** — 新增并扩展登录、首页、聊天、移动端 Shell、设置页、回测入口等关键路径的组件测试与 Playwright smoke coverage。

### 变更

- 🧭 **页面接入新 Shell 布局契约** — Home、Chat、Settings、Backtest 已统一接入新的页面容器、抽屉和滚动约定，降低 UI 迁移期间的页面行为不一致。
- 💾 **设置页状态同步更稳** — 优化草稿保留、直接保存同步与冲突处理，减少模块级保存后前后端配置状态不一致的问题。
- 🎭 **登录页视觉基线回归** — 登录页恢复到既有 `006` 分支的视觉基线，同时保留新的认证状态逻辑和统一表单交互模型。
- 🏛️ **AI 协作治理资产加固** — 收敛并加强 `AGENTS.md`、`CLAUDE.md`、Copilot 指令和校验脚本的一致性约束，降低治理资产长期漂移风险。

### Added

- **Web UI foundation refresh** — rebuilt shared design tokens and common primitives, introduced the app shell, theme provider, sidebar navigation, and Electron loading background alignment for the upgraded desktop/web experience
- **Settings and auth workflow overhaul** — rebuilt the Login, Settings, and Auth management flows, added explicit auth setup-state handling, and aligned the Web UI with the runtime auth configuration APIs
- **UI regression coverage and smoke checks** — expanded targeted frontend tests and added Playwright smoke coverage for login, home, chat, mobile shell, settings, and backtest entry flows

### Changed

- **Shell-driven page integration** — aligned Home, Chat, Settings, and Backtest with the new shell layout contract so routing, drawer behavior, and page-level scrolling are consistent during the UI migration
- **Settings state consistency** — refined draft preservation, direct-save synchronization, and conflict handling so module-level saves no longer leave the page out of sync with backend config state
- **Login visual baseline** — restored the login page visual treatment to the established `006` branch baseline while keeping the newer auth-state logic and unified form interaction model

### 修复

- ⏰ **定时启动立即执行兼容旧配置**（Issue #726）— `SCHEDULE_RUN_IMMEDIATELY` 未设置时会回退读取 `RUN_IMMEDIATELY`，修复升级后旧 `.env` 在定时模式下的兼容性问题；同时澄清 `.env.example` / README 中两个配置项的适用范围，并注明 Outlook / Exchange 强制 OAuth2 暂不支持。
- 🧵 **运行期 `MAX_WORKERS` 配置生效与可解释性增强**（#633）— 修复异步分析队列未按 `MAX_WORKERS` 同步的问题；新增任务队列并发 in-place 同步机制（空闲即时生效、繁忙延后），并在设置保存反馈与运行日志中明确输出 `profile/max/effective`，减少“参数未生效”误解。
- 🔐 **退出登录立即失效现有会话** — `POST /api/v1/auth/logout` 现在会轮换 session secret，避免旧 cookie 在退出后仍可继续访问受保护接口；同浏览器标签页和并发页面会被同步登出。认证开启时，该接口也不再属于匿名白名单，未登录请求会返回 `401`，避免匿名请求触发全局 session 失效。
- 🧮 **Tushare 板块/筹码调用限流与跨日缓存修复** — 新增的 `trade_cal`、行业板块排行、筹码分布链路统一接入 `_check_rate_limit()`；交易日历缓存改为按自然日刷新，避免服务跨天运行后继续沿用旧交易日判断取数日期。
- 💼 **持仓超售拦截与错误流水恢复**（#718）— `POST /api/v1/portfolio/trades` 现在会在写入前校验可卖数量，超售返回 `409 portfolio_oversell`；持仓页新增交易 / 资金流水 / 公司行为删除能力，删除后会同步失效仓位缓存与未来快照，便于从错误流水中直接恢复。
- 📧 **邮件中文发件人名编码**（#708）— 邮件通知现在会对包含中文的 `EMAIL_SENDER_NAME` 自动做 RFC 2047 编码，并在异常路径补充 SMTP 连接清理，修复 GitHub Actions / QQ SMTP 下 `'ascii' codec can't encode characters` 导致的发送失败。
- 🐛 **港股 Agent 实时行情去重与快速路由** — 统一 `HK01810` / `1810.HK` / `01810` 等港股代码归一规则；港股实时行情改为直接走单次 `akshare_hk` 路径，避免按 A 股 source priority 重复触发同一失败接口；Agent 运行期对显式 `retriable=false` 的工具失败增加短路缓存，减少同轮分析中的重复失败调用。
- 📰 **新闻时效硬过滤与策略分窗**（#697）— 新增 `NEWS_STRATEGY_PROFILE`（`ultra_short/short/medium/long`）并与 `NEWS_MAX_AGE_DAYS` 统一计算有效窗口；搜索结果在返回后执行发布时间硬过滤（时间未知剔除、超窗剔除、未来仅容忍 1 天），并在历史 fallback 链路追加相同约束，避免旧闻再次进入“最新动态/风险警报”。

### 文档

- ☁️ **新增云服务器 Web 界面部署与访问教程**（Fixes #686）— 补充从云端部署到外部访问的落地说明，降低远程自托管门槛。
- 🌍 **补齐英文文档索引与协作文档** — 新增英文文档索引、贡献指南、Bot 命令文档，并补充中英双语 issue / PR 模板，方便中英文协作与外部贡献者理解项目入口。
- 🏷️ **本地化 README 补充 Trendshift badge** — 在多语言 README 中同步补上新版能力入口标识，减少中英文说明面不一致。

## [3.7.0] - 2026-03-15

### 新功能

- 💼 **持仓管理 P0 全功能上线**（#677，对应 Issue #627）
  - **核心账本与快照闭环**：新增账户、交易、现金流水、企业行为、持仓缓存、每日快照等核心数据模型与 API 端点；支持 FIFO / AVG 双成本法回放；同日事件顺序固定为 `现金 → 企业行为 → 交易`；持仓快照写入采用原子事务。
  - **券商 CSV 导入**：支持华泰 / 中信 / 招商首批适配，含列名别名兼容；两阶段接口（解析预览 + 确认提交）；`trade_uid` 优先、key-field hash 兜底的幂等去重；前导零股票代码完整保留。
  - **组合风险报告**：集中度风险（Top Positions + A 股板块口径）、历史回撤监控（支持回填缺失快照）、止损接近预警；多币种统一换算 CNY 口径；汲取失败时回退最近成功汇率并标记 stale。
  - **Web 持仓页**（`/portfolio`）：组合总览、持仓明细、集中度饼图、风险摘要、全组合 / 单账户切换；手工录入交易 / 资金流水 / 企业行为；内嵌账户创建入口；CSV 解析 + 提交闭环与券商选择器。
  - **Agent 持仓工具**：新增 `get_portfolio_snapshot` 数据工具，默认紧凑摘要，可选持仓明细与风险数据。
  - **事件查询 API**：新增 `GET /portfolio/trades`、`GET /portfolio/cash-ledger`、`GET /portfolio/corporate-actions`，支持日期过滤与分页。
  - **可扩展 Parser Registry**：应用级共享注册，支持运行时注册新券商；新增 `GET /portfolio/imports/csv/brokers` 发现接口。

- 🎨 **前端设计系统与原子组件库**（#662）
  - 引入渐进式双主题架构（HSL 变量化设计令牌），清理历史 Legacy CSS；重构 Button / Card / Badge / Collapsible / Input / Select 等 20+ 核心组件；新增 `clsx` + `tailwind-merge` 类名合并工具；提升历史记录、LLM 配置等页面可读性。

- ⚡ **分析 API 异步契约与启动优化**（#656）
  - 规范 `POST /api/v1/analysis/analyze` 异步请求的返回契约；优化服务启动辅助逻辑；修复前端报告类型联合定义与后端响应对齐问题。

### 修复

- 🔔 **Discord 环境变量向后兼容**（#659）：运行时新增 `DISCORD_CHANNEL_ID` → `DISCORD_MAIN_CHANNEL_ID` 的 fallback 读取；历史配置用户无需修改即可恢复 Discord Bot 通知；全部相关文档与 `.env.example` 对齐。
- 🔧 **GitHub Actions Node 24 升级**（#665）：将所有 GitHub 官方 actions 升级至 Node 24 兼容版本，消除 CI 日志中的 Node.js 20 deprecation warning（影响 2026-06-02 强制升级窗口）。
- 📅 **持仓页默认日期本地化**：手工录入表单默认日期改用本地时间（`getFullYear/Month/Date`），修复 UTC-N 时区用户在当天晚间出现日期偏移的问题。
- 🔁 **CSV 导入去重逻辑加固**：dedup hash 纳入行序号作为区分因子，确保同字段合法分笔成交不被误折叠；同时在 `trade_uid` 存在时也持久化 hash，防止混合来源重复写入。

### 变更

- `POST /api/v1/portfolio/trades` 在同账户内 `trade_uid` 冲突时返回 `409`。
- 持仓风险响应新增 `sector_concentration` 字段（增量扩展），原有 `concentration` 字段保持不变。
- 分析 API `analyze` 接口异步行为契约文档化；前端报告类型联合更新。

### 测试

- 新增持仓核心服务测试（FIFO / AVG 部分卖出、同日事件顺序、重复 `trade_uid` 返回 409、快照 API 契约）。
- 新增 CSV 导入幂等性、合法分笔成交不误去重、去重边界、风险阈值边界、汇率降级行为测试。
- 新增 Agent `get_portfolio_snapshot` 工具调用测试。
- 新增分析 API 异步契约回归测试。

## [3.6.0] - 2026-03-14

### Added
- 📊 **Web UI Design System** — implemented dual-theme architecture and terminal-inspired atomic UI components
- 📊 **UI Components Refactoring** — integrated `clsx` and `tailwind-merge` for robust class composition across Web UI

- 🗑️ **History batch deletion** — Web UI now supports multi-selection and batch deletion of analysis history; added `POST /api/v1/history/batch-delete` endpoint and `ConfirmDialog` component.
- 🔐 **Auth settings API** — new `POST /api/v1/auth/settings` endpoint to enable or disable Web authentication at runtime and set the initial admin password when needed
- openclaw Skill 集成指南 — 新增 [docs/openclaw-skill-integration.md](openclaw-skill-integration.md)，说明如何通过 openclaw Skill 调用 DSA API
- ⚙️ **LLM channel protocol/test UX** — `.env` and Web settings now share the same channel shape (`LLM_CHANNELS` + `LLM_<NAME>_PROTOCOL/BASE_URL/API_KEY/MODELS/ENABLED`); settings page adds per-channel connection testing, primary/fallback/vision model selection, and protocol-aware model prefixing
- 🤖 **Agent architecture Phase 0+1** — shared protocols (`AgentContext`, `AgentOpinion`, `StageResult`), extracted `run_agent_loop()` runner, `AGENT_ARCH` switch (`single`/`multi`), config registry entries
- 🔍 **Bot NL routing** — two-layer natural-language routing: cheap regex pre-filter (stock codes + finance keywords) → lightweight LLM intent parsing; controlled by `AGENT_NL_ROUTING=true`; supports multi-stock and strategy extraction
- 💬 **`/ask` multi-stock analysis** — comma or `vs` separated codes (max 5), parallel thread execution with 150s timeout (preserves partial results), Markdown comparison summary table at top
- 📋 **`/history` command** — per-user session isolation via `{platform}_{user_id}:{scope}` format (colon delimiter prevents prefix collision); lists both `/chat` and `/ask` sessions; view detail or clear
- 📊 **`/strategies` command** — lists available strategy YAML files grouped by category (趋势/形态/反转/框架) with ✅/⬜ activation status
- 🔧 **Backtest summary tools** — `get_strategy_backtest_summary` and `get_stock_backtest_summary` registered as read-only Agent tools
- ⚙️ **Agent auto-detection** — `is_agent_available()` auto-detects from `LITELLM_MODEL`; explicit `AGENT_MODE=true/false` takes full precedence
- 🏗️ **Multi-Agent orchestrator (Phase 2)** — `AgentOrchestrator` with 4 modes (`quick`/`standard`/`full`/`strategy`); drop-in replacement for `AgentExecutor` via `AGENT_ARCH=multi`; `BaseAgent` ABC with tool subset filtering, cached data injection, and structured `AgentOpinion` output
- 🧩 **Specialised agents (Phase 2-4)** — `TechnicalAgent` (8 tools, trend/MA/MACD/volume/pattern analysis), `IntelAgent` (news & sentiment, risk flag propagation), `DecisionAgent` (synthesis into Decision Dashboard JSON), `RiskAgent` (7 risk categories, two-level severity with soft/hard override)
- 📈 **Strategy system (Phase 3)** — `StrategyAgent` (per-strategy evaluation from YAML skills), `StrategyRouter` (rule-based regime detection → strategy selection), `StrategyAggregator` (weighted consensus with backtest performance factor)
- 🔬 **Deep Research agent (Phase 5)** — `ResearchAgent` with 3-phase approach (decompose → research sub-questions → synthesise report); token budget tracking; new `/research` bot command with aliases (`/深研`, `/deepsearch`)
- 🧠 **Memory & calibration (Phase 6)** — `AgentMemory` with prediction accuracy tracking, confidence calibration (activates after minimum sample threshold), strategy auto-weighting based on historical win rate
- 📊 **Portfolio Agent (Phase 7)** — `PortfolioAgent` for multi-stock portfolio analysis (position sizing, sector concentration, correlation risk, cross-market linkage, rebalance suggestions)
- 🔔 **Event-driven alerts (Phase 7)** — `EventMonitor` with `PriceAlert`, `VolumeAlert`, `SentimentAlert` rules; async checking, callback notifications, serializable persistence
- ⚙️ **New config entries** — `AGENT_ORCHESTRATOR_MODE`, `AGENT_RISK_OVERRIDE`, `AGENT_DEEP_RESEARCH_BUDGET`, `AGENT_MEMORY_ENABLED`, `AGENT_STRATEGY_AUTOWEIGHT`, `AGENT_STRATEGY_ROUTING` — all registered in `config.py` + `config_registry.py` (WebUI-configurable)

### Changed
- 🔐 **Auth password state semantics** — stored password existence is now tracked independently from auth enablement; when auth is disabled, `/api/v1/auth/status` returns `passwordSet=false` while preserving the saved password for future re-enable
- 🔐 **Auth settings re-enable hardening** — re-enabling auth with a stored password now requires `currentPassword`, and failed session creation rolls back the auth toggle to avoid lockout
- ♻️ **AgentExecutor refactored** — `_run_loop` delegates to shared `runner.run_agent_loop()`; removed duplicated serialization/parsing/thinking-label code
- ♻️ **Unified agent switch** — Bot, API, and Pipeline all use `config.is_agent_available()` instead of divergent `config.agent_mode` checks
- 📖 **README.md** — expanded Bot commands section (ask/chat/strategies/history), added NL routing note, updated agent mode description
- 📖 **.env.example** — added `AGENT_ARCH` and `AGENT_NL_ROUTING` configuration documentation
- 🔌 **Analysis API async contract** — `POST /api/v1/analysis/analyze` now documents distinct async `202` payloads for single-stock vs batch requests, and `report_type=full` is treated consistently with the existing full-report behavior

### Fixed
- 🐛 **Analysis API blank-code guardrails** — `POST /api/v1/analysis/analyze` now drops whitespace-only entries before batch enqueue and returns `400` when no valid stock code remains
- 🐛 **Bare `/api` SPA fallback** — unknown API paths now return JSON `404` consistently for both `/api/...` and the exact `/api` path
- 🎮 **Discord channel env compatibility** — runtime now accepts legacy `DISCORD_CHANNEL_ID` as a fallback for `DISCORD_MAIN_CHANNEL_ID`, and the docs/examples now use the same variable name as the actual workflow/config implementation
- 🐛 **Session secret rotation on Windows** — use atomic replace so auth toggles invalidate existing sessions even when `.session_secret` already exists
- 🐛 **Auth toggle atomicity** — persist `ADMIN_AUTH_ENABLED` before rotating session secret; on rotation failure, roll back to the previous auth state
- 🔧 **LLM runtime selection guardrails** — YAML 模式下渠道编辑器不再覆盖 `LITELLM_MODEL` / fallback / Vision；系统配置校验补上全部渠道禁用后的运行时来源检查，并修复 `vertexai/...` 这类协议别名模型被重复加前缀的问题
- 🐛 **Multi-stock `/ask` follow-up regressions** — portfolio overlay now shares the same timeout budget as the per-stock phase and is skipped on timeout instead of blocking the bot reply; `/history` now stores the readable per-stock summary instead of raw dashboard JSON; condensed multi-stock output now renders numeric `sniper_points` values
- 🐛 **Decision dashboard enum compatibility** — multi-agent `DecisionAgent` now keeps `decision_type` within the legacy `buy|hold|sell` contract and normalizes stray `strong_*` outputs before risk override, pipeline conversion, and downstream统计/通知汇总
- 🛟 **Multi-Agent partial-result fallback** — `IntelAgent` now caches parsed intel for downstream reuse, shared JSON parsing tolerates lightly malformed model output, and the orchestrator preserves/synthesizes a minimal dashboard on timeout or mid-pipeline parse failure instead of always collapsing to `50/观望/未知`
- 🐛 **Shared LiteLLM routing restored** — bot NL intent parsing and `ResearchAgent` planning/synthesis now reuse the same LiteLLM adapter / Router / fallback / `api_base` injection path as the main Agent flow, so `LLM_CHANNELS` / `LITELLM_CONFIG` / OpenAI-compatible deployments behave consistently
- 🐛 **Bot chat session backward compatibility** — `/chat` now keeps using the legacy `{platform}_{user_id}` session id when old history already exists, and `/history` can still list / view / clear those pre-migration sessions alongside the new `{platform}_{user_id}:chat` format
- 🐛 **EventMonitor unsupported rule rejection** — config validation/runtime loading now reject or skip alert types the monitor cannot actually evaluate yet, so schedule mode no longer silently accepts permanent no-op rules
- 🐛 **P0 基本面聚合稳定性修复** (#614) — 修复 `get_stock_info` 板块语义回归（新增 `belong_boards` 并保留 `boards` 兼容别名）、引入基本面上下文精简返回以控制 token、为基本面缓存增加最大条目淘汰，并补齐 ETF 总体状态聚合与 NaN 板块字段过滤，保证 fail-open 与最小入侵。
- 🔧 **GitHub Actions 搜索引擎环境变量补充** — 工作流新增 `MINIMAX_API_KEYS`、`BRAVE_API_KEYS`、`SEARXNG_BASE_URLS` 环境变量映射，使 GitHub Actions 用户可配置 MiniMax、Brave、SearXNG 搜索服务（此前 v3.5.0 已添加 provider 实现但缺少工作流配置）
- 🤖 **Multi-Agent runtime consistency** — `AGENT_MAX_STEPS` now propagates to each orchestrated sub-agent; added cooperative `AGENT_ORCHESTRATOR_TIMEOUT_S` budget to stop overlong pipelines before they cascade further
- 🔌 **Multi-Agent feature wiring** — `AGENT_RISK_OVERRIDE` now actively downgrades final dashboards on hard risk findings; `AGENT_MEMORY_ENABLED` now injects recent analysis memory + confidence calibration into specialised agents; multi-stock `/ask` now runs `PortfolioAgent` to add portfolio-level allocation and concentration guidance
- 🔔 **EventMonitor runtime wiring** — schedule mode can now load alert rules from `AGENT_EVENT_ALERT_RULES_JSON`, poll them at `AGENT_EVENT_MONITOR_INTERVAL_MINUTES`, and send triggered alerts through the existing notification service
- 🛠️ **Follow-up stability fixes** — multi-stock `/ask` now falls back to usable text output when dashboard JSON parsing fails; EventMonitor skips semantically invalid rules instead of aborting schedule startup; background alert polling now runs independently of the main scheduled analysis loop
- 🧪 **Multi-Agent regression coverage** — added orchestrator execution tests for `run()`, `chat()`, critical-stage failure, graceful degradation, and timeout handling
- 🧹 **PortfolioAgent cleanup** — `post_process()` now reuses shared JSON parsing and removed stale unused imports
- 🚦 **Bot async dispatch** — `CommandDispatcher` now exposes `dispatch_async()`; NL intent parsing and default command execution are offloaded from the event loop, DingTalk stream awaits async handlers directly, and Feishu stream processing is moved off the SDK callback thread
- 🌐 **Async webhook handler** — new `handle_webhook_async()` function in `bot/handler.py` for use from async contexts (e.g. FastAPI); calls `dispatch_async()` directly without thread bridging
- 🧵 **Feishu stream ThreadPoolExecutor** — replaced unbounded per-message `Thread` spawning with a capped `ThreadPoolExecutor(max_workers=8)` to prevent thread explosion under message bursts
- 🔒 **EventMonitor safety** — `_check_volume()` now safely handles `get_daily_data` returning `None` (no tuple-unpacking crash); `on_trigger` callbacks support both sync and async callables via `asyncio.to_thread`/`await`
- 🧹 **ResearchAgent dedup** — `_filtered_registry()` now delegates to `BaseAgent._filtered_registry()` instead of duplicating the filtering logic
- 🧹 **Bot trailing whitespace cleanup** — removed W291/W293 whitespace issues across `bot/handler.py`, `bot/dispatcher.py`, `bot/commands/base.py`, `bot/platforms/feishu_stream.py`, `bot/platforms/dingtalk_stream.py`
- 🐛 **Dispatcher `_parse_intent_via_llm` safety** — replaced fragile `'raw' in dir()` with `'raw' in locals()` for undefined-variable guard in `JSONDecodeError` handler
- 🐛 **筹码结构 LLM 未填写时兜底补全** (#589) — DeepSeek 等模型未正确填写 `chip_structure` 时，自动用数据源已获取的筹码数据补全，保证各模型展示一致；普通分析与 Agent 模式均生效
- 🐛 **历史报告狙击点位显示原始文本** (#452) — 历史详情页现优先展示 `raw_result.dashboard.battle_plan.sniper_points` 中的原始字符串，避免 `analysis_history` 数值列把区间、说明文字或复杂点位压缩成单个数字；保留原有数值列作为回退
- 🐛 **Session prefix collision** — user ID `123` could see sessions of user `1234` via `startswith`; fixed with colon delimiter in session_id format
- 🐛 **NL pre-filter false positives** — `re.IGNORECASE` caused `[A-Z]{2,5}` to match common English words like "hello"; removed global flag, use inline `(?i:...)` only for English finance keywords
- 🐛 **Dotted ticker in strategy args** — `_get_strategy_args()` didn't recognize `BRK.B` as a stock code, leaving it in strategy text; now accepts `TICKER.CLASS` format
- ⏱️ **efinance 长调用挂起修复** (#660) — 为所有 efinance API 调用引入 `_ef_call_with_timeout()` 包装（默认 30 秒，可通过 `EFINANCE_CALL_TIMEOUT` 配置）；使用 `executor.shutdown(wait=False)` 确保超时后不再阻塞主线程，彻底消除 81 分钟挂起问题
- 🛡️ **类型安全内容完整性检查** (#660) — `check_content_integrity()` 现在将非字符串类型的 `operation_advice` / `analysis_summary` 视为缺失字段，避免下游 `get_emoji()` 因 `dict.strip()` 崩溃
- 📄 **报告保存与通知解耦** (#660) — `_save_local_report()` 不再依赖 `send_notification` 标志触发，`--no-notify` 模式下本地报告照常保存
- 🔄 **operation_advice 字典归一化** (#660) — Pipeline 和 BacktestEngine 现在将 LLM 返回的 `dict` 格式 `operation_advice` 通过 `decision_type`（不区分大小写）映射为标准字符串，防止因模型输出格式变化导致崩溃
- 🛡️ **runner.py usage None 防护** (#660) — `response.usage` 为 `None` 时不再抛出 `AttributeError`，回退为 0 token 计数
- 📋 **orchestrator 静默失败改为日志警告** (#660) — `IntelAgent` / `RiskAgent` 阶段失败现在记录 `WARNING` 而非静默跳过，便于诊断

### Notes
- ⚠️ **Multi-worker auth toggles** — runtime auth updates are process-local; multi-worker deployments must restart/roll workers to keep auth state consistent

## [3.5.0] - 2026-03-12

### Added
- 📊 **Web UI full report drawer** (Fixes #214) — history page adds "Full Report" button to display the complete Markdown analysis report in a side drawer; new `GET /api/v1/history/{record_id}/markdown` endpoint
- 📊 **LLM cost tracking** — all LLM calls (analysis, agent, market review) recorded in `llm_usage` table; new `GET /api/v1/usage/summary?period=today|month|all` endpoint returns aggregated token usage by call type and model
- 🔍 **SearXNG search provider** (Fixes #550) — quota-free self-hosted search fallback; priority: Bocha > Tavily > Brave > SerpAPI > MiniMax > SearXNG
- 🔍 **MiniMax web search provider** — `MiniMaxSearchProvider` with circuit breaker (3 failures → 300s cooldown) and dual time-filtering; configured via `MINIMAX_API_KEYS`
- 🤖 **Agent models discovery API** — `GET /api/v1/agent/models` returns available model deployments (primary/fallback/source/api_base) for Web UI model selector
- 🤖 **Agent chat export & send** (#495) — export conversation to .md file; send to configured notification channels; new `POST /api/v1/agent/chat/send`
- 🤖 **Agent background execution** (#495) — analysis continues when switching pages; badge notification on completion; auto-cancel in-progress stream on session switch
- 📝 **Report Engine P0** — Pydantic schema validation for LLM JSON; Jinja2 templates (markdown/wechat/brief) with legacy fallback; content integrity checks with retry; brief mode (`REPORT_TYPE=brief`); history signal comparison
- 📦 **Smart import** — multi-source import from image/CSV/Excel/clipboard; Vision LLM extracts code+name+confidence; name→code resolver (local map + pinyin + AkShare); confidence-tiered confirmation
- ⚙️ **GitHub Actions LiteLLM config** — workflow supports `LITELLM_CONFIG`/`LITELLM_CONFIG_YAML` for flexible AI provider configuration
- ⚙️ **Config engine refactor & system API** (#602) — unified config registry, validation and API exposure
- 📖 **LLM configuration guide** — new `docs/LLM_CONFIG_GUIDE.md` covering 3-tier config, quick start, Vision/Agent/troubleshooting

### Fixed
- 🐛 **analyze_trend always reports No historical data** (#600) — now fetches from DB/DataFetcher instead of broken `get_analysis_context`
- 🐛 **Chip structure fallback when LLM omits it** (#589) — auto-fills from data source chip data for consistent display across models
- 🐛 **History sniper points show raw text** (#452) — prioritizes original strings over compressed numeric values
- 🐛 **GitHub Actions ENABLE_CHIP_DISTRIBUTION configurable** (#617) — no longer hardcoded, supports vars/secrets override
- 🐛 **`.env` save preserves comments and blank lines** — Web settings no longer destroys `.env` formatting
- 🐛 **Agent model discovery fixes** — legacy mode includes LiteLLM-native providers; source detection aligned with runtime; fallback deployments no longer expanded per-key
- 🐛 **Stooq US stock previous close semantics** — no longer misuses open price as previous close
- 🐛 **Stock name prefetch regression** — prioritizes local `STOCK_NAME_MAP` before remote queries
- 🐛 **AkShare limit-up/down calculation** (#555) — fixed market analysis statistics
- 🐛 **AkShare Tencent source field index & ETF quote mapping** (#579)
- 🐛 **Pytdx stock name cache pagination** (#573) — prevents cache overflow
- 🐛 **PushPlus oversized report chunking** (#489) — auto-segments long content
- 🐛 **Agent chat cancel & switch** (#495) — cancel no longer misreports as failure; fast switch no longer overwrites stream state
- 🐛 **MiniMax search status in `/status` command** (#587)
- 🐛 **config_registry duplicate BOCHA_API_KEYS** — removed duplicate dict entry that silently overwrote config

### Changed
- 🔎 **Fetcher failure observability** — logs record start/success/failure with elapsed time, failover transitions; Efinance/Akshare include upstream endpoint and classified failure categories
- ♻️ **Data source resilience & cleanup** (#602) — fallback chain optimization
- ♻️ **Image extract API response extension** — new `items` field (code/name/confidence); `codes` preserved for backward compatibility
- ♻️ **Import parse error messages** — specific failure reasons for Excel/CSV; improved logging with file type and size

### Docs
- 📖 LLM config guide refactored for clarity (#583)
- 📖 `image-extract-prompt.md` with full prompt documentation
- 📖 AkShare fallback cache TTL documentation
## [3.4.10] - 2026-03-07

### Fixed
- 🐛 **EfinanceFetcher ETF OHLCV data** (#541, #527) — switch `_fetch_etf_data` from `ef.fund.get_quote_history` (NAV-only, no OHLCV, no `beg`/`end` params) to `ef.stock.get_quote_history`; ETFs now return proper open/high/low/close/volume/amount instead of zeros; remove obsolete NAV column mappings from `_normalize_data`
- 🐛 **tiktoken 0.12.0 `Unknown encoding cl100k_base`** (#537) — pin `tiktoken>=0.8.0,<0.12.0` in requirements.txt to avoid plugin-registration regression introduced in 0.12.0
- 🐛 **Web UI API error classification** (#540) — frontend no longer treats every HTTP 400 as the same "server/network" failure; now distinguishes Agent disabled / missing params / model-tool incompatibility / upstream LLM errors / local connection failures
- 🐛 **北交所代码识别失败** (#491, #533) — 8/4/92 开头的 6 位代码现正确识别为北交所；Tushare/Akshare/Yfinance 等数据源支持 .BJ 或 bj 前缀；Baostock/Pytdx 对北交所代码显式切换数据源；避免误判上海 B 股 900xxx
- 🐛 **狙击点位解析错误** (#488, #532) — 理想买入/二次买入等字段在无「元」字时误提取括号内技术指标数字；现先截去第一个括号后内容再提取

### Added
- **Markdown-to-image for dashboard report** (#455, #535) — 个股日报汇总支持 markdown 转图片推送（Telegram、WeChat、Custom、Email），与大盘复盘行为一致
- **markdown-to-file engine** (#455) — `MD2IMG_ENGINE=markdown-to-file` 可选，对 emoji 支持更好，需 `npm i -g markdown-to-file`
- **PREFETCH_REALTIME_QUOTES** (#455) — 设为 `false` 可禁用实时行情预取，避免 efinance/akshare_em 全市场拉取
- **Stock name prefetch** (#455) — 分析前预取股票名称，减少报告中「股票xxxxx」占位符
- 📊 **分析报告模型标记** (#528, #534) — 在分析报告 meta、报告末尾、推送内容中展示 `model_used`（完整 LLM 模型名）；Agent 多轮调用时记录并展示每轮实际使用的模型（支持 fallback 切换）

### Changed
- **Enhanced markdown-to-image failure warning** (#455) — 转图失败时提示具体依赖（wkhtmltopdf 或 m2f）
- **WeChat-only image routing optimization** (#455) — 仅配置企业微信图片时，不再对完整报告做冗余转图，避免误导性失败日志
- **Stock name prefetch lightweight mode** (#455) — 名称预取阶段跳过 realtime quote 查询，减少额外网络开销

## [3.4.9] - 2026-03-06

### Added
- 🧠 **Structured config validation** — `ConfigIssue` dataclass and `validate_structured()` with severity-aware logging; `CONFIG_VALIDATE_MODE=strict` aborts startup on errors
- 🖼️ **Vision model config** — `VISION_MODEL` and `VISION_PROVIDER_PRIORITY` for image stock extraction; provider fallback (Gemini → Anthropic → OpenAI → DeepSeek) when primary fails
- 🚀 **CLI init wizard** — `python -m dsa init` 3-step interactive bootstrap (model → data source → notification), 9 provider presets, incremental merge by default
- 🔧 **Multi-channel LLM support** with visual channel editor (#494)

### Changed
- ♻️ **Vision extraction** — migrated from gemini-3 hardcode to `litellm.completion()` with configurable model and provider fallback; `OPENAI_VISION_MODEL` deprecated in favor of `VISION_MODEL`
- ♻️ **Market analyzer** — uses `Analyzer.generate_text()` for LLM calls; fixes bypass and Anthropic `AttributeError` when using non-Router path
- ♻️ **Config validation refinements** — test_env output format syncs with `validate_structured` (severity-aware ✓/✗/⚠/·); Vision key warning when `VISION_MODEL` set but no provider API key; market_analyzer test covers `generate_market_review` fallback when `generate_text` returns None
- ⚙️ **Auto-tag workflow defaults to NO tag** — only tags when commit message explicitly contains `#patch`, `#minor`, or `#major`
- ♻️ **Formatter and notification refactor** (#516)

### Fixed
- 🐛 **STOCK_LIST not refreshed on scheduled runs** — `.env` or WebUI changes to `STOCK_LIST` now hot-reload before each scheduled analysis (#529)
- 🐛 **WebUI fails to load with MIME type error** — SPA fallback route now resolves correct `Content-Type` for JS/CSS files (#520)
- 🐛 **AstrBot sender docstring misplaced** — `import time` placed before docstring in `_send_astrbot`, causing it to become dead code
- 🐛 **Telegram Markdown link escaping** — `_convert_to_telegram_markdown` escaped `[]()` characters, breaking all Markdown links in reports
- 🐛 **Duplicate `discord_bot_status` field** in Config dataclass — second declaration silently shadowed the first
- 🧹 **Unused imports** — removed `shutil`/`subprocess` from `main.py`
- 🔧 **Config validation and Vision key check** (#525)

### Docs
- 📝 Clarified GitHub Actions non-trading-day manual run controls (`TRADING_DAY_CHECK_ENABLED` + `force_run`) for Issue #461 / PR #466

## [3.4.8] - 2026-03-02

### Fixed
- 🐛 **Desktop exe crashes on startup with `FileNotFoundError`** — PyInstaller build was missing litellm's JSON data files (e.g. `model_prices_and_context_window_backup.json`). Added `--collect-data litellm` to both Windows and macOS build scripts so the files are correctly bundled in the executable.

### CI
- 🔧 Cache Electron binaries on macOS CI runners to prevent intermittent EOF download failures when fetching `electron-vX.Y.Z-darwin-*.zip` from GitHub CDN
- 🔧 Fix macOS DMG `hdiutil Resource busy` error during desktop packaging

### Docs
- 📝 Clarify non-trading-day manual run controls for GitHub Actions (`TRADING_DAY_CHECK_ENABLED` + `force_run`) (#474)

## [3.4.7] - 2026-02-28

### Added
- 🧠 **CN/US Market Strategy Blueprint System** (#395) — market review prompt injects region-specific strategy blueprints with position sizing and risk trigger recommendations

### Fixed
- 🐛 **`TRADING_DAY_CHECK_ENABLED` env var and `--force-run` for GitHub Actions** (#466)
- 🐛 **Agent pipeline preserved resolved stock names** (#464) — placeholder names no longer leak into reports
- 🐛 **Code cleanup** (#462, Fixes #422)
- 🐛 **WebUI auto-build on startup** (#460)
- 🐛 **ARCH_ARGS unbound variable** (#458)
- 🐛 **Time zone inconsistency & right panel flash** (#439)

### Docs
- 📝 Clarify potential ambiguities in code (#343)
- 📝 ENABLE_EASTMONEY_PATCH guidance for Issue #453 (#456)

## [3.4.0] - 2026-02-27

### Added
- 📡 **LiteLLM Direct Integration + Multi API Key Support** (#454, Fixes #421 #428)
  - Removed native SDKs (google-generativeai, google-genai, anthropic); unified through `litellm>=1.80.10`
  - New config: `LITELLM_MODEL`, `LITELLM_FALLBACK_MODELS`, `GEMINI_API_KEYS`, `ANTHROPIC_API_KEYS`, `OPENAI_API_KEYS`
  - Multi-key auto-builds LiteLLM Router (simple-shuffle) with 429 cooldown
  - **Breaking**: `.env` `GEMINI_MODEL` (no prefix) only for fallback; explicit config must include provider prefix

### Changed
- ♻️ **Notification Refactoring** (#435) — extracted 10 sender classes into `src/notification_sender/`

### Fixed
- 🐛 LLM NoneType crash, history API 422, sniper points extraction
- 🐛 Auto-build frontend on WebUI startup — `WEBUI_AUTO_BUILD` env var (default `true`)
- 🐛 Docker explicit project name (#448)
- 🐛 Bocha search SSL retry (#445, #446) — transient errors retry up to 3 times
- 🐛 Gemini google-genai SDK migration (Fixes #440, #444)
- 🐛 Mobile home page scrolling (Fixes #419, #433)
- 🐛 History list scroll reset (#431)
- 🐛 Settings save button false positive (fixes #417, #430)

## [3.3.22] - 2026-02-26

### Added
- 💬 **Chat History Persistence** (Fixes #400, #414) — `/chat` page survives refresh, sidebar session list
- 🎨 Project VI Assets — logo icon set, PSD, vector, banner (#425)
- 🚀 Desktop CI Auto-Release (#426) — Windows + macOS parallel builds

### Fixed
- 🐛 Agent Reasoning 400 & LiteLLM Proxy (fixes #409, #427)
- 🐛 Discord chunked sending (#413) — `DISCORD_MAX_WORDS` config
- 🐛 yfinance shared DataFrame (#412)
- 🐛 sniper_points parsing (#408)
- 🐛 Agent framework category missing (#406)
- 🐛 Date inconsistency & query id (fixes #322, #363)

## [3.3.12] - 2026-02-24

### Added
- 📈 **Intraday Realtime Technical Indicators** (Issue #234, #397) — MA calculated from realtime price, config: `ENABLE_REALTIME_TECHNICAL_INDICATORS`
- 🤖 **Agent Strategy Chat** (#367) — full ReAct pipeline, 11 YAML strategies, SSE streaming, multi-turn chat
- 📢 PushPlus Group Push — `PUSHPLUS_TOPIC` (#402)
- 📅 Trading Day Check (Issue #373, #375) — `TRADING_DAY_CHECK_ENABLED`, `--force-run`

### Fixed
- 🐛 DeepSeek reasoning mode (Issue #379, #386)
- 🐛 Agent news intel persistence (Fixes #396, #405)
- 🐛 Bare except clauses replaced with `except Exception` (#398)
- 🐛 UUID fallback for HTTP non-secure context (fixes #377, #381)
- 🐛 Docker DNS resolution (Fixes #372, #374)
- 🐛 Agent session/strategy bugs — multiple follow-up fixes for #367
- 🐛 yfinance parallel download data filtering

### Changed
- Market review strategy consistency — unified cn/us template
- Agent test assertions updated (`6 -> 11`)


## [3.2.11] - 2026-02-23

### 修复（#patch）
- 🐛 **StockTrendAnalyzer 从未执行** (Issue #357)
  - 根因：`get_analysis_context` 仅返回 2 天数据且无 `raw_data`，pipeline 中 `raw_data in context` 始终为 False
  - 修复：Step 3 直接调用 `get_data_range` 获取 90 日历天（约 60 交易日）历史数据用于趋势分析
  - 改善：趋势分析失败时用 `logger.warning(..., exc_info=True)` 记录完整 traceback

## [3.2.10] - 2026-02-22

### 新增
- ⚙️ 支持 `RUN_IMMEDIATELY` 配置项，设为 `true` 时定时任务触发后立即执行一次分析，无需等待首个定时点

### 修复
- 🐛 修复 Web UI 页面居中问题
- 🐛 修复 Settings 返回 500 错误

## [3.2.9] - 2026-02-22

### 修复
- 🐛 **ETF 分析仅关注指数走势**（Issue #274）
  - 美股/港股 ETF（如 VOO、QQQ）与 A 股 ETF 不再纳入基金公司层面风险（诉讼、声誉等）
  - 搜索维度：ETF/指数专用 risk_check、earnings、industry 查询，避免命中基金管理人新闻
  - AI 提示：指数型标的分析约束，`risk_alerts` 不得出现基金管理人公司经营风险

## [3.2.8] - 2026-02-21

### 修复
- 🐛 **BOT 与 WEB UI 股票代码大小写统一**（Issue #355）
  - BOT `/analyze` 与 WEB UI 触发分析的股票代码统一为大写（如 `aapl` → `AAPL`）
  - 新增 `canonical_stock_code()`，在 BOT、API、Config、CLI、task_queue 入口处规范化
  - 历史记录与任务去重逻辑可正确识别同一股票（大小写不再影响）

## [3.2.7] - 2026-02-20

### 新增
- 🔐 **Web 页面密码验证**（Issue #320, #349）
  - 支持 `ADMIN_AUTH_ENABLED=true` 启用 Web 登录保护
  - 首次访问在网页设置初始密码；支持「系统设置 > 修改密码」和 CLI `python -m src.auth reset_password` 重置

## [3.2.6] - 2026-02-20
### ⚠️ 破坏性变更（Breaking Changes）

- **历史记录 API 变更 (Issue #322)**
  - 路由变更：`GET /api/v1/history/{query_id}` → `GET /api/v1/history/{record_id}`
  - 参数变更：`query_id` (字符串) → `record_id` (整数)
  - 新闻接口变更：`GET /api/v1/history/{query_id}/news` → `GET /api/v1/history/{record_id}/news`
  - 原因：`query_id` 在批量分析时可能重复，无法唯一标识单条历史记录。改用数据库主键 `id` 确保唯一性
  - 影响范围：使用旧版历史详情 API 的所有客户端需同步更新

### 修复
- 修复美股（如 ADBE）技术指标矛盾：akshare 美股复权数据异常，统一美股历史数据源为 YFinance（Issue #311）
- 🐛 **历史记录查询和显示问题 (Issue #322)**
  - 修复历史记录列表查询中日期不一致问题：使用明天作为 endDate，确保包含今天全天的数据
  - 修复服务器 UI 报告选择问题：原因是多条记录共享同一 `query_id`，导致总是显示第一条。现改用 `analysis_history.id` 作为唯一标识
  - 历史详情、新闻接口及前端组件已全面适配 `record_id`
  - 新增后台轮询（每 30s）与页面可见性变更时静默刷新历史列表，确保 CLI 发起的分析完成后前端能及时同步，使用 `silent` 模式避免触发 loading 状态
- 🐛 **美股指数实时行情与日线数据** (Issue #273)
  - 修复 SPX、DJI、IXIC、NDX、VIX、RUT 等美股指数无法获取实时行情的问题
  - 新增 `us_index_mapping` 模块，将用户输入（如 SPX）映射为 Yahoo Finance 符号（如 ^GSPC）
  - 美股指数与美股股票日线数据直接路由至 YfinanceFetcher，避免遍历不支持的数据源
  - 消除重复的美股识别逻辑，统一使用 `is_us_stock_code()` 函数

### 优化
- 🎨 **首页输入栏与 Market Sentiment 布局对齐优化**
  - 股票代码输入框左缘与历史记录 glass-card 框左对齐
  - 分析按钮右缘与 Market Sentiment 外框右对齐
  - Market Sentiment 卡片向下拉伸填满格子，消除与 STRATEGY POINTS 之间的空隙
  - 窄屏时输入栏填满宽度，响应式对齐保持一致

## [3.2.5] - 2026-02-19

### 新增
- 🌍 **大盘复盘可选区域**（Issue #299）
  - 支持 `MARKET_REVIEW_REGION` 环境变量：`cn`（A股）、`us`（美股）、`both`（两者）
  - us 模式使用 SPX/纳斯达克/道指/VIX 等指数；both 模式可同时复盘 A 股与美股
  - 默认 `cn`，保持向后兼容

## [3.2.4] - 2026-02-18

### 修复
- 🐛 **统一美股数据源为 YFinance**（Issue #311）
  - akshare 美股复权数据异常，统一美股历史数据源为 YFinance
  - 修复 ADBE 等美股股票技术指标矛盾问题

## [3.2.3] - 2026-02-18

### 修复
- 🐛 **标普500实时数据缺失**（Issue #273）
  - 修复 SPX、DJI、IXIC、NDX、VIX、RUT 等美股指数无法获取实时行情的问题
  - 新增 `us_index_mapping` 模块，将用户输入（如 SPX）映射为 Yahoo Finance 符号（如 `^GSPC`）
  - 美股指数与美股股票日线数据直接路由至 YfinanceFetcher，避免遍历不支持的数据源

## [3.2.2] - 2026-02-16

### 新增
- 📊 **PE 指标支持**（Issue #296）
  - AI System Prompt 增加 PE 估值关注
- 📰 **新闻时效性筛查**（Issue #296）
  - `NEWS_MAX_AGE_DAYS`：新闻最大时效（天），默认 3，避免使用过时信息
- 📈 **强势趋势股乖离率放宽**（Issue #296）
  - `BIAS_THRESHOLD`：乖离率阈值（%），默认 5.0，可配置
  - 强势趋势股（多头排列且趋势强度 ≥70）自动放宽乖离率到 1.5 倍

## [3.2.1] - 2026-02-16

### 新增
- 🔧 **东财接口补丁可配置开关**
  - 支持 `EFINANCE_PATCH_ENABLED` 环境变量开关东财接口补丁（默认 `true`）
  - 补丁不可用时可降级关闭，避免影响主流程

## [3.2.0] - 2026-02-15

### 新增
- 🔒 **CI 门禁统一（P0）**
  - 新增 `scripts/ci_gate.sh` 作为后端门禁单一入口
  - 主 CI 改为 `backend-gate`、`docker-build`、`web-gate` 三段式
  - CI 触发改为所有 PR，避免 Required Checks 因路径过滤缺失而卡住合并
  - `web-gate` 支持前端路径变更按需触发
  - 新增 `network-smoke` 工作流承载非阻断网络场景回归
- 📦 **发布链路收敛（P0）**
  - `docker-publish` 调整为 tag 主触发，并增加发布前门禁校验
  - 手动发布增加 `release_tag` 输入与 semver/changelog 强校验
  - 发布前新增 Docker smoke（关键模块导入）
- 📝 **PR 模板升级（P0）**
  - 增加背景、范围、验证命令与结果、回滚方案、Issue 关联等必填项
- 🤖 **AI 审查覆盖增强（P0）**
  - `pr-review` 纳入 `.github/workflows/**` 范围
  - 新增 `AI_REVIEW_STRICT` 开关，可选将 AI 审查失败升级为阻断

## [3.1.13] - 2026-02-15

### 新增
- 📊 **仅分析结果摘要**（Issue #262）
  - 支持 `REPORT_SUMMARY_ONLY` 环境变量，设为 `true` 时只推送汇总，不含个股详情
  - 默认 `false`，多股时适合快速浏览

## [3.1.12] - 2026-02-15

### 新增
- 📧 **个股与大盘复盘合并推送**（Issue #190）
  - 支持 `MERGE_EMAIL_NOTIFICATION` 环境变量，设为 `true` 时将个股分析与大盘复盘合并为一次推送
  - 默认 `false`，减少邮件数量、降低被识别为垃圾邮件的风险

## [3.1.11] - 2026-02-15

### 新增
- 🤖 **Anthropic Claude API 支持**（Issue #257）
  - 支持 `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、`ANTHROPIC_TEMPERATURE`、`ANTHROPIC_MAX_TOKENS`
  - AI 分析优先级：Gemini > Anthropic > OpenAI
- 📷 **从图片识别股票代码**（Issue #257）
  - 上传自选股截图，通过 Vision LLM 自动提取股票代码
  - API: `POST /api/v1/stocks/extract-from-image`；支持 JPEG/PNG/WebP/GIF，最大 5MB
  - 支持 `OPENAI_VISION_MODEL` 单独配置图片识别模型
- ⚙️ **通达信数据源手动配置**（Issue #257）
  - 支持 `PYTDX_HOST`、`PYTDX_PORT` 或 `PYTDX_SERVERS` 配置自建通达信服务器

## [3.1.10] - 2026-02-15

### 新增
- ⚙️ **立即运行配置**（Issue #332）
  - 支持 `RUN_IMMEDIATELY` 环境变量，`true` 时定时任务启动后立即执行一次
- 🐛 修复 Docker 构建问题

## [3.1.9] - 2026-02-14

### 新增
- 🔌 **东财接口补丁机制**
  - 新增 `patch/eastmoney_patch.py` 修复 efinance 上游接口变更
  - 不影响其他数据源的正常运行

## [3.1.8] - 2026-02-14

### 新增
- 🔐 **Webhook 证书校验开关**（Issue #265）
  - 支持 `WEBHOOK_VERIFY_SSL` 环境变量，可关闭 HTTPS 证书校验以支持自签名证书
  - 默认保持校验，关闭存在 MITM 风险，仅建议在可信内网使用

## [3.1.7] - 2026-02-14

### 修复
- 🐛 修复包导入错误（package import error）

## [3.1.6] - 2026-02-13

### 修复
- 🐛 修复 `news_intel` 中 `query_id` 不一致问题

## [3.1.5] - 2026-02-13

### 新增
- 📷 **Markdown 转图片通知**（Issue #289）
  - 支持 `MARKDOWN_TO_IMAGE_CHANNELS` 配置，对 Telegram、企业微信、自定义 Webhook（Discord）、邮件发送图片格式报告
  - 邮件为内联附件，增强对不支持 HTML 客户端的兼容性
  - 需安装 `wkhtmltopdf` 和 `imgkit`

## [3.1.4] - 2026-02-12

### 新增
- 📧 **股票分组发往不同邮箱**（Issue #268）
  - 支持 `STOCK_GROUP_N` + `EMAIL_GROUP_N` 配置，不同股票组报告发送到对应邮箱
  - 大盘复盘发往所有配置的邮箱

## [3.1.3] - 2026-02-12

### 修复
- 🐛 修复 Docker 内运行时通过页面修改配置报错 `[Errno 16] Device or resource busy` 的问题

## [3.1.2] - 2026-02-11

### 修复
- 🐛 修复 Docker 一致性问题，解决关键批次处理与通知 Bug

## [3.1.1] - 2026-02-11

### 变更
- ♻️ `API_HOST` → `WEBUI_HOST`：Docker Compose 配置项统一

## [3.1.0] - 2026-02-11

### 新增
- 📊 **ETF 支持增强与代码规范化**
  - 统一各数据源 ETF 代码处理逻辑
  - 新增 `canonical_stock_code()` 统一代码格式，确保数据源路由正确

## [3.0.5] - 2026-02-08

### 修复
- 🐛 修复信号 emoji 与建议不一致的问题（复合建议如"卖出/观望"未正确映射）
- 🐛 修复 `*ST` 股票名在微信/Dashboard 中 markdown 转义问题
- 🐛 修复 `idx.amount` 为 None 时大盘复盘 TypeError
- 🐛 修复分析 API 返回 `report=None` 及 ReportStrategy 类型不一致问题
- 🐛 修复 Tushare 返回类型错误（dict → UnifiedRealtimeQuote）及 API 端点指向

### 新增
- 📊 大盘复盘报告注入结构化数据（涨跌统计、指数表格、板块排名）
- 🔍 搜索结果 TTL 缓存（500 条上限，FIFO 淘汰）
- 🔧 Tushare Token 存在时自动注入实时行情优先级
- 📰 新闻摘要截断长度 50→200 字

### 优化
- ⚡ 补充行情字段请求限制为最多 1 次，减少无效请求

## [3.0.4] - 2026-02-07

### 新增
- 📈 **回测引擎** (PR #269)
  - 新增基于历史分析记录的回测系统，支持收益率、胜率、最大回撤等指标评估
  - WebUI 集成回测结果展示

## [3.0.3] - 2026-02-07

### 修复
- 🐛 修复狙击点位数据解析错误问题 (PR #271)

## [3.0.2] - 2026-02-06

### 新增
- ✉️ 可配置邮件发送者名称 (PR #272)
- 🌐 外国股票支持英文关键词搜索

## [3.0.1] - 2026-02-06

### 修复
- 🐛 修复 ETF 实时行情获取、市场数据回退、企业微信消息分块问题
- 🔧 CI 流程简化

## [3.0.0] - 2026-02-06

### 移除
- 🗑️ **移除旧版 WebUI**
  - 删除基于 `http.server.ThreadingHTTPServer` 的旧版 WebUI（`web/` 包）
  - 旧版 WebUI 的功能已完全被 FastAPI（`api/`）+ React 前端替代
  - `--webui` / `--webui-only` 命令行参数标记为弃用，自动重定向到 `--serve` / `--serve-only`
  - `WEBUI_ENABLED` / `WEBUI_HOST` / `WEBUI_PORT` 环境变量保持兼容，自动转发到 FastAPI 服务
  - `webui.py` 保留为兼容入口，启动时直接调用 FastAPI 后端
  - Docker Compose 中移除 `webui` 服务定义，统一使用 `server` 服务

### 变更
- ♻️ **服务层重构**
  - 将 `web/services.py` 中的异步任务服务迁移至 `src/services/task_service.py`
  - Bot 分析命令（`bot/commands/analyze.py`）改为使用 `src.services.task_service`
  - Docker 环境变量 `WEBUI_HOST`/`WEBUI_PORT` 更名为 `API_HOST`/`API_PORT`（旧名仍兼容）

## [2.3.0] - 2026-02-01

### 新增
- 🇺🇸 **增强美股支持** (Issue #153)
  - 实现基于 Akshare 的美股历史数据获取 (`ak.stock_us_daily()`)
  - 实现基于 Yfinance 的美股实时行情获取（优先策略）
  - 增加对不支持数据源（Tushare/Baostock/Pytdx/Efinance）的美股代码过滤和快速降级

### 修复
- 🐛 修复 AMD 等美股代码被误识别为 A 股的问题 (Issue #153)

## [2.2.5] - 2026-02-01

### 新增
- 🤖 **AstrBot 消息推送** (PR #217)
  - 新增 AstrBot 通知渠道，支持推送到 QQ 和微信
  - 支持 HMAC SHA256 签名验证，确保通信安全
  - 通过 `ASTRBOT_URL` 和 `ASTRBOT_TOKEN` 配置

## [2.2.4] - 2026-02-01

### 新增
- ⚙️ **可配置数据源优先级** (PR #215)
  - 支持通过环境变量（如 `YFINANCE_PRIORITY=0`）动态调整数据源优先级
  - 无需修改代码即可优先使用特定数据源（如 Yahoo Finance）

## [2.2.3] - 2026-01-31

### 修复
- 📦 更新 requirements.txt，增加 `lxml_html_clean` 依赖以解决兼容性问题

## [2.2.2] - 2026-01-31

### 修复
- 🐛 修复代理配置区分大小写问题 (fixes #211)

## [2.2.1] - 2026-01-31

### 修复
- 🐛 **YFinance 兼容性修复** (PR #210, fixes #209)
  - 修复新版 yfinance 返回 MultiIndex 列名导致的数据解析错误

## [2.2.0] - 2026-01-31

### 新增
- 🔄 **多源回退策略增强**
  - 实现了更健壮的数据获取回退机制 (feat: multi-source fallback strategy)
  - 优化了数据源故障时的自动切换逻辑

### 修复
- 🐛 修复 analyzer 运行后无法通过改 .env 文件的 stock_list 内容调整跟踪的股票

## [2.1.14] - 2026-01-31

### 文档
- 📝 更新 README 和优化 auto-tag 规则

## [2.1.13] - 2026-01-31

### 修复
- 🐛 **Tushare 优先级与实时行情** (Fixed #185)
  - 修复 Tushare 数据源优先级设置问题
  - 修复 Tushare 实时行情获取功能

## [2.1.12] - 2026-01-30

### 修复
- 🌐 修复代理配置在某些情况下的区分大小写问题
- 🌐 修复本地环境禁用代理的逻辑

## [2.1.11] - 2026-01-30

### 优化
- 🚀 **飞书消息流优化** (PR #192)
  - 优化飞书 Stream 模式的消息类型处理
  - 修改 Stream 消息模式默认为关闭，防止配置错误运行时报错

## [2.1.10] - 2026-01-30

### 合并
- 📦 合并 PR #154 贡献

## [2.1.9] - 2026-01-30

### 新增
- 💬 **微信文本消息支持** (PR #137)
  - 新增微信推送的纯文本消息类型支持
  - 添加 `WECHAT_MSG_TYPE` 配置项

## [2.1.8] - 2026-01-30

### 修复
- 🐛 修正日志中 API 提供商显示错误 (PR #197)

## [2.1.7] - 2026-01-30

### 修复
- 🌐 禁用本地环境的代理设置，避免网络连接问题

## [2.1.6] - 2026-01-29

### 新增
- 📡 **Pytdx 数据源 (Priority 2)**
  - 新增通达信数据源，免费无需注册
  - 多服务器自动切换
  - 支持实时行情和历史数据
- 🏷️ **多源股票名称解析**
  - DataFetcherManager 新增 `get_stock_name()` 方法
  - 新增 `batch_get_stock_names()` 批量查询
  - 自动在多数据源间回退
  - Tushare 和 Baostock 新增股票名称/列表方法
- 🔍 **增强搜索回退**
  - 新增 `search_stock_price_fallback()` 用于数据源全部失败时
  - 新增搜索维度：市场分析、行业分析
  - 最大搜索次数从 3 增加到 5
  - 改进搜索结果格式（每维度 4 条结果）

### 改进
- 更新搜索查询模板以提高相关性
- 增强 `format_intel_report()` 输出结构

## [2.1.5] - 2026-01-29

### 新增
- 📡 新增 Pytdx 数据源和多源股票名称解析功能

## [2.1.4] - 2026-01-29

### 文档
- 📝 更新赞助商信息

## [2.1.3] - 2026-01-28

### 文档
- 📝 重构 README 布局
- 🌐 新增繁体中文翻译 (README_CHT.md)

### 修复
- 🐛 修复 WebUI 无法输入美股代码问题
  - 输入框逻辑改成所有字母都转换成大写
  - 支持 `.` 的输入（如 `BRK.B`）

## [2.1.2] - 2026-01-27

### 修复
- 🐛 修复个股分析推送失败和报告路径问题 (fixes #166)
- 🐛 修改 CR 错误，确保微信消息最大字节配置生效

## [2.1.1] - 2026-01-26

### 新增
- 🔧 添加 GitHub Actions auto-tag 工作流
- 📡 添加 yfinance 兜底数据源及数据缺失警告

### 修复
- 🐳 修复 docker-compose 路径和文档命令
- 🐳 Dockerfile 补充 copy src 文件夹 (fixes #145)

## [2.1.0] - 2026-01-25

### 新增
- 🇺🇸 **美股分析支持**
  - 支持美股代码直接输入（如 `AAPL`, `TSLA`）
  - 使用 YFinance 作为美股数据源
- 📈 **MACD 和 RSI 技术指标**
  - MACD：趋势确认、金叉死叉信号（零轴上金叉⭐、金叉✅、死叉❌）
  - RSI：超买超卖判断（超卖⭐、强势✅、超买⚠️）
  - 指标信号纳入综合评分系统
- 🎮 **Discord 推送支持** (PR #124, #125, #144)
  - 支持 Discord Webhook 和 Bot API 两种方式
  - 通过 `DISCORD_WEBHOOK_URL` 或 `DISCORD_BOT_TOKEN` + `DISCORD_MAIN_CHANNEL_ID` 配置
- 🤖 **机器人命令交互**
  - 钉钉机器人支持 `/分析 股票代码` 命令触发分析
  - 支持 Stream 长连接模式
- 🌡️ **AI 温度参数可配置** (PR #142)
  - 支持自定义 AI 模型温度参数
- 🐳 **Zeabur 部署支持**
  - 添加 Zeabur 镜像部署工作流
  - 支持 commit hash 和 latest 双标签

### 重构
- 🏗️ **项目结构优化**
  - 核心代码移至 `src/` 目录，根目录更清爽
  - 文档移至 `docs/` 目录
  - Docker 配置移至 `docker/` 目录
  - 修复所有 import 路径，保持向后兼容
- 🔄 **数据源架构升级**
  - 新增数据源熔断机制，单数据源连续失败自动切换
  - 实时行情缓存优化，批量预取减少 API 调用
  - 网络代理智能分流，国内接口自动直连
- 🤖 Discord 机器人重构为平台适配器架构

### 修复
- 🌐 **网络稳定性增强**
  - 自动检测代理配置，对国内行情接口强制直连
  - 修复 EfinanceFetcher 偶发的 `ProtocolError`
  - 增加对底层网络错误的捕获和重试机制
- 📧 **邮件渲染优化**
  - 修复邮件中表格不渲染问题 (#134)
  - 优化邮件排版，更紧凑美观
- 📢 **企业微信推送修复**
  - 修复大盘复盘推送不完整问题
  - 增强消息分割逻辑，支持更多标题格式
  - 增加分批发送间隔，避免限流丢失
- 👷 **CI/CD 修复**
  - 修复 GitHub Actions 中路径引用的错误

## [2.0.0] - 2026-01-24

### 新增
- 🇺🇸 **美股分析支持**
  - 支持美股代码直接输入（如 `AAPL`, `TSLA`）
  - 使用 YFinance 作为美股数据源
- 🤖 **机器人命令交互** (PR #113)
  - 钉钉机器人支持 `/分析 股票代码` 命令触发分析
  - 支持 Stream 长连接模式
  - 支持选择精简报告或完整报告
- 🎮 **Discord 推送支持** (PR #124)
  - 支持 Discord Webhook 推送
  - 添加 Discord 环境变量到工作流

### 修复
- 🐳 修复 WebUI 在 Docker 中绑定 0.0.0.0 (fixed #118)
- 🔔 修复飞书长连接通知问题
- 🐛 修复 `analysis_delay` 未定义错误
- 🔧 启动时 config.py 检测通知渠道，修复已配置自定义渠道情况下仍然提示未配置问题

### 改进
- 🔧 优化 Tushare 优先级判断逻辑，提升封装性
- 🔧 修复 Tushare 优先级提升后仍排在 Efinance 之后的问题
- ⚙️ 配置 TUSHARE_TOKEN 时自动提升 Tushare 数据源优先级
- ⚙️ 实现 4 个用户反馈 issue (#112, #128, #38, #119)

## [1.6.0] - 2026-01-19

### 新增
- 🖥️ WebUI 管理界面及 API 支持（PR #72）
  - 全新 Web 架构：分层设计（Server/Router/Handler/Service）
  - 核心 API：支持 `/analysis` (触发分析), `/tasks` (查询进度), `/health` (健康检查)
  - 交互界面：支持页面直接输入代码并触发分析，实时展示进度
  - 运行模式：新增 `--webui-only` 模式，仅启动 Web 服务
  - 解决了 [#70](https://github.com/ZhuLinsen/daily_stock_analysis/issues/70) 的核心需求（提供触发分析的接口）
- ⚙️ GitHub Actions 配置灵活性增强（[#79](https://github.com/ZhuLinsen/daily_stock_analysis/issues/79)）
  - 支持从 Repository Variables 读取非敏感配置（如 STOCK_LIST, GEMINI_MODEL）
  - 保持对 Secrets 的向下兼容

### 修复
- 🐛 修复企业微信/飞书报告截断问题（[#73](https://github.com/ZhuLinsen/daily_stock_analysis/issues/73)）
  - 移除 notification.py 中不必要的长度硬截断逻辑
  - 依赖底层自动分片机制处理长消息
- 🐛 修复 GitHub Workflow 环境变量缺失（[#80](https://github.com/ZhuLinsen/daily_stock_analysis/issues/80)）
  - 修复 `CUSTOM_WEBHOOK_BEARER_TOKEN` 未正确传递到 Runner 的问题

## [1.5.0] - 2026-01-17

### 新增
- 📲 单股推送模式（[#55](https://github.com/ZhuLinsen/daily_stock_analysis/issues/55)）
  - 每分析完一只股票立即推送，不用等全部分析完
  - 命令行参数：`--single-notify`
  - 环境变量：`SINGLE_STOCK_NOTIFY=true`
- 🔐 自定义 Webhook Bearer Token 认证（[#51](https://github.com/ZhuLinsen/daily_stock_analysis/issues/51)）
  - 支持需要 Token 认证的 Webhook 端点
  - 环境变量：`CUSTOM_WEBHOOK_BEARER_TOKEN`

## [1.4.0] - 2026-01-17

### 新增
- 📱 Pushover 推送支持（PR #26）
  - 支持 iOS/Android 跨平台推送
  - 通过 `PUSHOVER_USER_KEY` 和 `PUSHOVER_API_TOKEN` 配置
- 🔍 博查搜索 API 集成（PR #27）
  - 中文搜索优化，支持 AI 摘要
  - 通过 `BOCHA_API_KEYS` 配置
- 📊 Efinance 数据源支持（PR #59）
  - 新增 efinance 作为数据源选项
- 🇭🇰 港股支持（PR #17）
  - 支持 5 位代码或 HK 前缀（如 `hk00700`、`hk1810`）

### 修复
- 🔧 飞书 Markdown 渲染优化（PR #34）
  - 使用交互卡片和格式化器修复渲染问题
- ♻️ 股票列表热重载（PR #42 修复）
  - 分析前自动重载 `STOCK_LIST` 配置
- 🐛 钉钉 Webhook 20KB 限制处理
  - 长消息自动分块发送，避免被截断
- 🔄 AkShare API 重试机制增强
  - 添加失败缓存，避免重复请求失败接口

### 改进
- 📝 README 精简优化
  - 高级配置移至 `docs/full-guide.md`


## [1.3.0] - 2026-01-12

### 新增
- 🔗 自定义 Webhook 支持
  - 支持任意 POST JSON 的 Webhook 端点
  - 自动识别钉钉、Discord、Slack、Bark 等常见服务格式
  - 支持配置多个 Webhook（逗号分隔）
  - 通过 `CUSTOM_WEBHOOK_URLS` 环境变量配置

### 修复
- 📝 企业微信长消息分批发送
  - 解决自选股过多时内容超过 4096 字符限制导致推送失败的问题
  - 智能按股票分析块分割，每批添加分页标记（如 1/3, 2/3）
  - 批次间隔 1 秒，避免触发频率限制

## [1.2.0] - 2026-01-11

### 新增
- 📢 多渠道推送支持
  - 企业微信 Webhook
  - 飞书 Webhook（新增）
  - 邮件 SMTP（新增）
  - 自动识别渠道类型，配置更简单

### 改进
- 统一使用 `NOTIFICATION_URL` 配置，兼容旧的 `WECHAT_WEBHOOK_URL`
- 邮件支持 Markdown 转 HTML 渲染

## [1.1.0] - 2026-01-11

### 新增
- 🤖 OpenAI 兼容 API 支持
  - 支持 DeepSeek、通义千问、Moonshot、智谱 GLM 等
  - Gemini 和 OpenAI 格式二选一
  - 自动降级重试机制

## [Unreleased]

### 修复
- 收口 `last_completed_session` 的美股已收盘口径：常规字段会优先锁定单一 EOD bundle，避免 `close / prev_close / change / pct` 被多源 fallback 混写。
- 报告评分新增显式拆解与同 session 稳定约束，减少同一交易日重复生成报告时的无解释大幅漂移。

### Web
- 重构标准报告详情页为更接近 [OKX Markets/Prices](https://www.okx.com/en-us/markets/prices) 的深黑终端布局：顶部 summary strip、表格主区、右侧信号栏、移动端紧凑 definition-list。
- 移除 standard report 页面下方重复的旧资讯区，并放宽首页报告容器，减少桌面端无效留白与顶层横向滚动。
- 主题系统增强为明显分层：`Dark Terminal` 保持克制终端风格，`Cyberpunk` 提升霓虹边界与高对比发光，`Geek / DOS` 切换为低饱和复古终端面板与方角控制。
- 新增 5 档全局字号系统（XS/S/M/L/XL），并分别控制桌面与移动端缩放比例，设置持久化到本地存储。
- 移动端密度优化：收紧页面间距、标题与图表工具条字号/间距，提升同屏信息量。
- 修复移动端 K 线交互滚动串扰：在图表内部触摸拖拽/缩放时隔离页面滚动，图表外区域保持正常页面滚动。

## [1.0.0] - 2026-01-10

### 新增
- 🎯 AI 决策仪表盘分析
  - 一句话核心结论
  - 精确买入/止损/目标点位
  - 检查清单（✅⚠️❌）
  - 分持仓建议（空仓者 vs 持仓者）
- 📊 大盘复盘功能
  - 主要指数行情
  - 涨跌统计
  - 板块涨跌榜
  - AI 生成复盘报告
- 🔍 多数据源支持
  - AkShare（主数据源，免费）
  - Tushare Pro
  - Baostock
  - YFinance
- 📰 新闻搜索服务
  - Tavily API
  - SerpAPI
- 💬 企业微信机器人推送
- ⏰ 定时任务调度
- 🐳 Docker 部署支持
- 🚀 GitHub Actions 零成本部署

### 技术特性
- Gemini AI 模型（gemini-3-flash-preview）
- 429 限流自动重试 + 模型切换
- 请求间延时防封禁
- 多 API Key 负载均衡
- SQLite 本地数据存储

---

[Unreleased]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.9.0...HEAD
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
