# Changelog

이 문서는 Daily Stock Analysis 프로젝트의 주요 변경 사항을 기록합니다.

형식은 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)를 따르며, 버전 관리는 [Semantic Versioning](https://semver.org/)을 기준으로 합니다.

사용자 친화적인 릴리스 요약은 [GitHub Releases](https://github.com/ZhuLinsen/daily_stock_analysis/releases)를 참고하세요.

## [Unreleased]

- [수정] Web 홈/채팅/알림 화면의 깨진 한국어 문구와 관련 테스트 기대값을 정리했습니다.
- [수정] 데스크톱 업데이트 확인과 설치 흐름의 깨진 문구 및 JavaScript 문법 오류를 복구했습니다.
- [ci] PR 리뷰 워크플로의 체크 이름과 자동 리뷰 보고서를 한국어로 정리했습니다.
- [ci] 데스크톱 앱 변경 시 `apps/dsa-desktop` 테스트를 실행하는 CI 게이트를 추가했습니다.
- [문서] README, 문서 인덱스, FAQ, Bot 명령 가이드를 한국어 기준 문서로 정리했습니다.
- [문서] 전체 운영 가이드, 배포 가이드, LLM 설정, 알림, 경고, 설정 도움말 문서를 한국어 기준 문서로 정리했습니다.
- [개선] 리포트 언어 매핑의 사용자 표시값을 한국어로 정리했습니다.
- [chore] 언어 아티팩트 검사 스크립트를 추가하고 CI에서 사용자 노출 영역을 검사하도록 연결했습니다.
- [수정] Windows에서 symlink가 일반 파일로 체크아웃되는 환경에서도 AI 작업 자산 검사가 Git 인덱스의 symlink 상태를 확인하도록 보강했습니다.
- [수정] API 오류 메시지와 Bot 명령 응답에 남아 있던 깨진 문구를 한국어로 정리했습니다.
<!-- 新条目格式：- [类型] 描述（类型取值：新功能/改进/修复/文档/测试/chore）-->
<!-- 每条独立一行追加到本段末尾，无需分类标题，合并时冲突最小 -->
- [修复] 抽出 LiteLLM 生成参数适配层，对严格 temperature 模型按请求临时固定或省略参数，避免 GPT-5 / o 系列与 Kimi K2.6 拒绝默认温度请求。
- [改进] LiteLLM 参数错误支持一次请求内自动修正重试，并在成功后进程内缓存策略，降低新模型参数兼容问题的人工配置成本。
- [文档] 补充 Issue #1316 参数自愈改动的外部兼容依据、运行时配置清理边界与回滚证据；并在 `tests/test_system_config_service.py` 增加清理路径下 `LLM_TEMPERATURE` 保持不变的回归用例。
- [文档] 补充严格 temperature 兼容语义的官方来源、运行时依赖约束与 `LLM_TEMPERATURE` 回退/不回写路径说明。
- [改进] 告警中心 P2 新增后台评估 worker，schedule 模式可同时评估持久化 active rules 与 legacy JSON 规则，并记录 `triggered` / `skipped` / `degraded` / `failed` 最小评估历史。
- [修复] 统一 Windows 桌面安装包与自动更新元数据文件名，避免 Release 中出现重复安装包并阻断 `latest.yml` 指向不存在附件。
- [修复] 桌面端启动 WebUI 时为入口页增加 no-cache 响应头和版本化 cache-busting URL，避免安装新版后 Electron 继续复用旧 WebUI 缓存。
- [文档] 扩展 Web 设置页帮助信息，补充 Agent 模型、LiteLLM fallback/config/temperature 与 LLM 渠道编辑器字段说明。
- [新功能] 新增 Finnhub / AlphaVantage 美股数据源适配器，扩展美股日线 failover 链至 Finnhub(P2) -> AlphaVantage(P3) -> Yfinance(P4) -> Longbridge(P5)。
- [修复] AlphaVantage 适配器在 newest-first 原始数据下 pct_chg 计算错误：改为先按日期升序排序再计算涨跌幅。
- [修复] 美股日线路由未包含 Finnhub / AlphaVantage：扩展 `get_daily_data()` 美股分支的 source_order 以覆盖新增数据源。
- [文档] 新增小白客户端安装与配置指南，说明桌面客户端下载、基础模型配置、新闻源配置和常见问题。
- [新功能] Web 首页个股分析支持选择策略。
- [新功能] 新增热点题材、事件驱动、成长质量和预期重估策略。
- [新功能] Web 新增告警中心 MVP，支持现有三类告警规则的创建、列表、启停、删除、dry-run 测试和触发历史查看。
- [新功能] 告警中心 P4 记录真实通知尝试结果，并为持久化规则新增可查询的业务冷却状态。
- [修复] 持仓快照在当天刷新时优先使用实时行情重算当前价、市值与未实现盈亏，避免复用旧收盘价导致页面刷新后盈亏不变。
- [新功能] 告警中心 P5 支持 MA、RSI、MACD、KDJ、CCI 日线技术指标规则，并复用现有触发历史、通知结果和持久化冷却链路。
- [改进] 将 RSI 计算口径从 SMA 调整为 Wilder's EMA / SMMA，统一分析报告与告警阈值口径。
- [改进] 大盘复盘将红绿灯与盘面温度合并为终端友好的盘面信号分数，移除色块进度条与重复温度行。
- [改进] 大盘复盘近三日市场线索改为标题与来源链接列表，移除摘要片段，降低中英混排和误读风险。

## 이전 릴리스

이전 릴리스의 상세 변경 이력은 GitHub Releases에서 확인할 수 있습니다.

주요 릴리스 흐름:

- 3.17.x: Web UI, 데이터 공급자, 분석 안정성 개선
- 3.16.x: 포트폴리오 리포트 표시 개선
- 3.15.x: 분석 워크플로와 배포 편의성 개선
- 3.14.x 이하: 기본 분석 기능, 알림, 자동화 문서 개선

과거 변경 로그 원문에는 중국어와 깨진 표기가 포함되어 있어, 한국어 전용 프로젝트 맥락에 맞춰 이 문서에서는 요약 형태로 유지합니다.
