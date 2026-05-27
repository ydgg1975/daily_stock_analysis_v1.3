# Changelog

Daily Stock Analysis의 주요 변경 사항을 기록합니다.

형식은 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)를 참고하며, 버전 관리는 [Semantic Versioning](https://semver.org/) 기준을 따릅니다.

사용자 친화적인 릴리스 요약은 [GitHub Releases](https://github.com/robot0971-art/daily_stock_analysis/releases)에서 확인할 수 있습니다.

## [Unreleased]


- [개선] `REPORT_LANGUAGE=ko`를 기본 리포트 언어로 추가하고 Web 리포트 라벨과 AI 분석 프롬프트가 한국어 출력을 우선하도록 정리했습니다.
- [수정] `REPORT_LANGUAGE` 런타임 기본값과 invalid fallback을 설정 스키마와 같은 `ko`/`en`/`zh` 계약에 맞췄습니다.
- [수정] 분석, 알림, 리포트 렌더링의 설정 기반 언어 fallback이 한국어 기본값을 따르도록 맞췄습니다.
- [수정] 한국어 히스토리 Markdown과 단일 종목 알림 리포트의 이벤트/차트 고정 제목이 중국어로 표시되지 않도록 보정했습니다.
- [수정] Web 리포트 컴포넌트가 언어 값이 없을 때 한국어 기본 문구를 사용하고 영어 리포트 언어를 올바르게 정규화하도록 수정했습니다.
- [수정] Web 리포트 개요에서 관련 섹터와 섹터 등락률 섹션이 다시 표시되도록 복구했습니다.
- [수정] 한국어 리포트 모드의 AI 분석 프롬프트, fallback 문구, 설정 주석에 남아 있던 혼합 언어 표현을 자연스러운 한국어로 정리했습니다.
- [수정] 한국어 리포트 언어 확장 중 기존 중국어 리포트 라벨, placeholder, 분석 프롬프트 호환성이 깨지지 않도록 `zh` 동작을 복구했습니다.
- [개선] 분석 기록 전체 초기화 API와 Web 버튼을 추가하고, 현재 KR/US 기본 흐름과 다른 과거 CN/HK 기록을 legacy 배지로 구분할 수 있게 했습니다.
- [수정] Web 분석 입력 예시와 코드 검증을 KR/US 중심으로 조정해 KRX 코드가 중국 A주로 오인되는 일을 줄였습니다.
- [개선] Web 종목 자동완성에서 한국 종목의 `.KS`/`.KQ` suffix와 `KS`/`KQ` prefix 입력을 같은 후보로 매칭하도록 보강했습니다.
- [개선] 기본 분석 흐름을 KR/US 중심으로 전환하고, 6자리 KRX 후보는 `.KS`/`.KQ` 종목으로 yfinance 경로에서 처리하도록 정리했습니다.
- [수정] 리포트 언어 설정의 기본값과 안내를 실제 지원 범위인 `ko`/`en`/`zh` 기준으로 맞췄습니다.
- [수정] Python 3.14 환경에서 백엔드 테스트용 패키지 설치가 tiktoken 0.11.x PyO3 제한으로 실패하지 않도록 tiktoken 0.13.x 대역을 허용했습니다.
- [테스트] A-share, HK, US 종목의 agent history와 chart analysis smoke test를 추가했습니다.
- [테스트] 차트 분석, paper trading, portfolio analysis의 eval fixture와 회귀 검증을 추가했습니다.
- [개선] Agent analysis map에 도구별 호출 수, 성공 수, 실패 수, timeout, cached count, 평균 실행 시간을 집계하는 tool metrics를 추가했습니다.
- [개선] Vision provider가 없거나 Vision 분석이 실패해도 차트 분석 도구가 기존 수치 기반 분석을 유지하고 fallback 사유를 표시하도록 했습니다.
- [개선] Vision 차트 해석에 evidence 블록을 추가해 VLM 근거, confidence, 불확실성, 수치 분석과의 충돌 여부를 구조화했습니다.
- [개선] Web 리포트에 데이터 신뢰도 판단 상태와 통합 리포트 보드를 추가해 confidence, evidence, risk, chart, event, portfolio 상태를 한 화면에서 확인할 수 있게 했습니다.
- [개선] Alert P6에서 관심 종목, 보유 종목, 계좌 연동 규칙 기반 이벤트 알림 범위와 우선순위 처리를 정리했습니다.
- [테스트] 한국어 기준 API, Bot, 로그 메시지와 배포 문서 명령 예시의 회귀 테스트 기본값을 정리했습니다.
- [개선] 종목 리포트에 핵심 근거, 반대 근거, 데이터 한계, 확신도 사유를 표시하는 분석 메타데이터를 추가했습니다.
- [개선] 종목별 이전 분석과 현재 분석을 비교해 투자 가설 상태와 주요 변경점을 리포트에 표시하는 thesis tracking을 추가했습니다.
- [개선] 종목 리포트의 결론, 근거, 반대 근거, 리스크, 데이터 출처를 연결하는 evidence graph 메타데이터를 추가했습니다.
- [개선] 종목별 변동성, 최대 낙폭, 기술적 위험 플래그, 사용자 주의사항을 도출하는 단일 종목 리스크 엔진을 추가했습니다.
- [개선] 백테스트 요약 diagnostics에 confidence bucket별 성과와 리스크 경고 적중률을 추가했습니다.
- [개선] 이벤트 알림 트리거에 우선순위, thesis 훼손 위험, 모니터링 커버리지 메타데이터를 추가했습니다.
- [개선] Agent 도구에 차트 분석 생성과 paper trading 주문 준비 기능을 연결했습니다.
- [개선] 차트 SVG에 가격 날짜 축, 지지와 저항 레이어, RSI 기준선, MACD histogram과 표시 신호 레이어를 추가했습니다.
- [수정] Bot 자연어 라우팅과 플랫폼 어댑터의 사용자 안내 문구에서 중국어 기반 예시와 안내 문구를 줄이고 한국어와 영어 기준으로 정리했습니다.
- [수정] Web 호스트 설정과 API endpoint의 사용자 노출 오류 문구, 로그, Swagger 설명에 남아 있던 중국어 기반 문구를 한국어와 영어 기준으로 정리했습니다.
- [수정] 비동기 분석 작업 서비스와 WebUI 프런트엔드에서 출력물 준비 로그의 깨진 문자열을 한국어로 복구했습니다.
- [수정] Bot 명령 응답과 Agent API 스트리밍 표시명의 깨진 문자열 및 중국어 기반 사용자 노출 문구를 한국어 기준으로 정리했습니다.
- [수정] Web 화면의 깨진 감정 레이어, 구분자, 과거 리포트 표시 문자열을 한국어로 정리했습니다.
- [개선] LLM 채널 추가 화면의 API Key 저장 위치와 연결 테스트의 비저장 동작을 안내했습니다.
- [수정] AI 모델 설정의 Anthropic 관련 설명에 남아 있던 중국어 문구를 한국어로 교체했습니다.
- [수정] 인증 API 오류 문구와 CLI 안내말의 중국어 기반 사용자 노출 문자열을 한국어 기준으로 정리했습니다.
- [수정] 설정 스키마와 안내말의 중국어 문서 링크와 이전 upstream 문서 링크를 현재 저장소의 한국어 기준으로 정리했습니다.
- [문서] LLM 설정 가이드, 테스트 패키징 가이드, provider 운영 가이드, Zeabur 배포 가이드, 문서 인덱스, OpenClaw Skill 연동 가이드를 현재 흐름 기준의 한국어 문서로 정리했습니다.
- [문서] `.env.example`과 LiteLLM YAML 예시의 깨진 주석을 현재 환경 변수 기준 설명으로 정리했습니다.
- [테스트] Windows 환경에서 Docker entrypoint shell 테스트가 `sh` 부재로 실패하지 않도록 건너뛰기 처리를 추가했습니다.
- [테스트] market analyzer 정적 검사에 UTF-8 인코딩을 명시해 Windows 기본 인코딩 오류를 방지했습니다.
- [ci] PR 리뷰 워크플로의 체크 이름과 자동 리뷰 보고서를 한국어로 정리했습니다.
- [ci] 데스크톱 변경 시 `apps/dsa-desktop` 테스트를 실행하는 CI 게이트를 추가했습니다.
- [chore] 언어 아티팩트 검사 스크립트를 추가하고 CI에서 사용자 노출 영역을 검사하도록 연결했습니다.
- [수정] API 오류 메시지와 Bot 명령 응답에 남아 있던 깨진 문구를 한국어로 정리했습니다.
<!-- 新条目格式：- [类型] 描述（类型取值：新功能/改进/修复/文档/测试/chore）-->
<!-- 每条独立一行追加到本段末尾，无需分类标题，合并时冲突最小 -->
- [改进] `scripts/fetch_tushare_stock_list.py` 可对 A 股中带 `XD`/`XR`/`DR`/`N`/`C` 前缀的名称进行回填修正，供自动补全刷新流程默认使用。
- [修复] 股票自动补全索引生成缺少 `pypinyin` 时改为直接失败，避免写出缺失拼音字段的降级索引。
- [修复] 归一腾讯实时行情成交量为股口径，避免量能变化倍数被放大并误导分析报告。
- [文档] 新增 #1391 Phase 0 运行诊断契约文档，明确 trace_id、诊断摘要、关键链路范围与脱敏/fail-open/retention 边界。
- [新功能] 落地 #1391 Phase 1 运行诊断最小链路：任务/SSE 追加 trace_id，并记录日线与实时行情 ProviderRun 快照。
- [改进] Web 路由页面改为按需加载，降低首包体积并增加路由加载失败恢复提示。
- [修复] Docker 默认部署移除 `.env` 单文件挂载，避免 WebUI 保存配置时因 `os.replace` 更新挂载点触发 `Device or resource busy`。
- [修复] 收敛 #1391 Phase 0 A 股代码归属边界：补齐 `SH`/`SZ` 前缀场景的归属一致性，明确 `data_provider/baostock_fetcher.py`、`data_provider/pytdx_fetcher.py`、`data_provider/tushare_fetcher.py` 的本轮修复范围。
- [改进] Web 完整报告 Markdown 抽屉改为按需加载。
- [改进] 新增市场阶段推断基线并明确盘前、盘中、午休、临近收盘、盘后和非交易日语义。
- [新功能] 告警中心新增 P7 大盘红绿灯结构化规则，支持 `market_light_status` 与 `market_light_score_drop` 并复用现有 worker、触发历史、通知和冷却链路。
- [修复] 修复 `STOCK_LIST` 使用裸 A 股代码时 Baostock 等数据源 fallback 的内部格式转换，保持用户配置继续使用 6 位股票编号。
- [文档] 补齐告警中心 P8 文档与配置收口说明，明确 legacy JSON、高级规则、Web/API、Docker、GitHub Actions 与 Desktop 边界。
- [修复] Windows 桌面端自动更新在用户确认重启安装后改为静默执行安装器，并在停止内置后端后清理进程引用，降低安装器提示“每日股票分析无法关闭”的概率。
- [文档] 说明本次桌面修复仅覆盖 Windows NSIS 更新安装链路与后端进程生命周期清理；未改动设置项保存/模型运行时清理语义。移除此前误入的 `docker/Dockerfile` `npm registry` 变更，恢复部署构建与更新修复的职责隔离。
- [修复] macOS 桌面端将运行时配置迁移到用户数据目录，并在旧 `.app` 包内文件仍可访问时迁移 `.env`、数据库和日志，避免后续替换升级后重新配置。
- [改进] 新增运行态市场阶段上下文构造与降级测试。
- [文档] 新增 AnalysisContextPack P0 上下文盘点，明确字段质量状态、现有状态映射和首版 pack 边界。
- [新功能] 落地 #1391 Phase 2 运行诊断摘要：生成用户可读 RunDiagnosticSummary，提供历史报告诊断 API 与脱敏复制文本。
- [文档] 明确 #1391 Phase 2 的结构化检测告警为非配置迁移信号：`agent_max_steps`/`agent_orchestrator_timeout_s` 非法值会 fallback 至默认并产生日志告警，新增诊断链路仅新增 `context_snapshot`/`RunDiagnosticSummary` 读写字段，不改写 `litellm_model`、`agent_litellm_model`、`openai_base_url`、LLM channel 路由或配置迁移语义。
- [新功能] 落地 #1391 Phase 3 运行诊断可见性：报告详情和任务面板默认折叠展示运行状态、trace 与可复制排障信息；后端通过 `api/v1/history/{record_id}/diagnostics` 与 `context_snapshot.diagnostics` 提供历史链路回填。
- [文档] 补充 #1391 Phase 3 兼容性说明：记录后端诊断持久化、历史查询与通知回写链路变更边界与回滚策略，并补齐后端门禁级验证要求。
- [测试] 收敛 #1391 Phase 3 后端/API 与 Web 回归检查：`./scripts/ci_gate.sh`、`test_pipeline_market_phase_context.py`、`test_analysis_api_contract.py`、`test_analysis_history.py`、`npm run lint`、`npm run build`。
- [新功能] 新增 AnalysisContextPack P1 内部契约与脱敏序列化测试。
- [修复] 恢复 Agent/历史兼容快照中的关联板块与板块联动字段提取，修复新版首页报告缺少“板块联动”的回归问题。
- [改进] 设置页配置帮助阶段性补齐 Web 设置页实际展示/可配置字段的中英双语文案，覆盖 Agent、回测、报告、通知路由、系统运行时、AI legacy、数据源和通知高级配置。
- [修复] 修正 Web 设置帮助中 legacy 告警 JSON 字段名与静默时段投递语义说明。
- [修复] 修复 Web 中文设置页在数据源、通知、系统与 Agent 区域的配置标题、说明和关键下拉选项漏翻问题。
- [修复] 修复问股会话切换和首页任务重连后可能残留 Agent/分析任务进行中状态的问题。
- [新功能] 问股新增默认关闭的可见对话上下文压缩，支持 Web 开关、Agent 高级 preset、滚动摘要和最近轮次原文保护，降低长会话 token 消耗。
- [改进] P2-min：LLM Prompt 注入市场阶段上下文。
- [修复] 问股 single-agent 新增 provider-aware trace 分轨，跨轮保留 DeepSeek V4 thinking + tool-call 的 `reasoning_content` 与工具协议材料。

## [3.18.0] - 2026-05-21

### What's Changed

- feat: Add alert-center P2-P6, Web strategy selection, HK/US fundamental context, static-report financial sections, and Finnhub / AlphaVantage US-market fallback.
- improve: Refine LiteLLM parameter recovery, yfinance currency/dividend handling, RSI calculation, market-review presentation, stock-news relevance ranking, and report table rendering.
- fix: Harden desktop packaging/update assets, completed analysis-status responses, AlphaVantage pct_chg routing, portfolio realtime snapshots, alert trigger dedupe, DatabaseManager cold start, and fallback pricing registration.
- docs/tests: Add beginner setup and settings-help docs, document compatibility/rollback boundaries, and extend regression coverage for API, alert, packaging, and release paths.

## [3.17.1] - 2026-05-16

### What's Changed

- fix: Add `--publish never` to the Windows and macOS Electron packaging scripts so tag builds only create local artifacts and GitHub Actions handles release upload and publish.

## Previous Releases

이전 릴리스의 상세 변경 이력은 GitHub Releases에서 확인합니다. 오래된 원문에는 깨진 문자열이 포함되어 있어 현재 문서에서는 사용자에게 필요한 수준의 요약만 유지합니다.

- 3.17.x: Web UI, 데이터 공급망, 분석 안정성 개선
- 3.16.x: 포트폴리오 리포트 표시 개선
- 3.15.x: 분석 워크플로와 배포 경험 개선
- 3.14.x 이하: 기본 분석 기능, 알림, 자동화 문서 개선

[Unreleased]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.18.0...HEAD
[3.18.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.17.1...v3.18.0
[3.17.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.17.0...v3.17.1

