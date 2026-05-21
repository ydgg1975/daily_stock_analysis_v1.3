# 문서 센터

이 문서는 프로젝트 문서의 진입점입니다. README는 프로젝트 소개와 빠른 시작만 담고, 세부 설정과 운영 문서는 아래 항목에서 확인합니다.

## 상황별 바로가기

| 하고 싶은 일 | 먼저 볼 문서 | 이어서 볼 문서 |
| --- | --- | --- |
| 프로젝트를 빠르게 이해하기 | [README](../README.md) | [전체 설정과 운영 가이드](full-guide.md) |
| 처음 실행하기 | [초보자 클라이언트 설정](beginner-client-setup.md) | [FAQ](FAQ.md) |
| LLM 설정하기 | [LLM 설정 가이드](LLM_CONFIG_GUIDE.md) | [LLM provider 운영 가이드](llm-providers.md) |
| 알림 설정하기 | [알림 기능 기준](notifications.md) | [Bot 명령과 연동](bot-command.md) |
| 서버나 클라우드에 배포하기 | [배포 가이드](DEPLOY.md) | [Zeabur 배포](docker/zeabur-deployment.md) |
| 데스크톱 앱 패키징하기 | [데스크톱 앱 패키징 가이드](desktop-package.md) | [배포 가이드](DEPLOY.md) |
| 오류를 해결하기 | [FAQ](FAQ.md) | [변경 로그](CHANGELOG.md) |
| 개발에 참여하기 | [기여 가이드](CONTRIBUTING.md) | [API 명세](architecture/api_spec.json) |

## 빠른 시작

| 문서 | 내용 |
| --- | --- |
| [README](../README.md) | 프로젝트 소개, 핵심 기능, 빠른 시작, 주요 진입점 |
| [초보자 클라이언트 설정](beginner-client-setup.md) | 비개발자 기준 설치와 기본 설정 |
| [전체 설정과 운영 가이드](full-guide.md) | 실행 방식, 환경 변수, 배포, 문제 해결 |
| [FAQ](FAQ.md) | 자주 묻는 설정, 모델, 알림, 배포 문제 |
| [변경 로그](CHANGELOG.md) | 주요 변경 사항과 마이그레이션 메모 |

## 설정

| 문서 | 내용 |
| --- | --- |
| [LLM 설정 가이드](LLM_CONFIG_GUIDE.md) | LLM channel, LiteLLM, Agent 모델, Vision 모델 설정 |
| [LLM provider 운영 가이드](llm-providers.md) | provider별 endpoint, 모델 예시, 오류 분류 |
| [LiteLLM YAML 예시](examples/litellm_config.example.yaml) | 고급 LiteLLM YAML 구성 예시 |
| [알림 기능 기준](notifications.md) | Telegram, Discord, Slack, 이메일 등 알림 채널 |
| [Tushare 종목 목록 가이드](TUSHARE_STOCK_LIST_GUIDE.md) | Tushare 종목 목록 관련 설정 |

## 기능별 문서

| 문서 | 내용 |
| --- | --- |
| [Bot 명령과 연동](bot-command.md) | Bot 명령, webhook, platform 연동 |
| [Bot 플랫폼 설정](bot/) | 플랫폼별 Bot 설정 보조 문서 |
| [실시간 알림 센터](alerts.md) | EventMonitor, Web 규칙 관리, 알림 결과 |
| [이미지 추출 프롬프트](image-extract-prompt.md) | Vision LLM 주식 정보 추출 프롬프트 |
| [OpenClaw Skill 연동](openclaw-skill-integration.md) | OpenClaw 외부 Skill 연동 |

## 배포와 패키징

| 문서 | 내용 |
| --- | --- |
| [배포 가이드](DEPLOY.md) | 서버, Docker, systemd, Supervisor 배포 |
| [클라우드 Web UI 배포](deploy-webui-cloud.md) | 클라우드에서 Web UI를 공개하는 방법 |
| [Zeabur 배포](docker/zeabur-deployment.md) | Zeabur 기반 배포와 운영 |
| [데스크톱 앱 패키징 가이드](desktop-package.md) | Electron 데스크톱 앱 빌드와 릴리스 |

## 개발 참고

| 문서 | 내용 |
| --- | --- |
| [API 명세](architecture/api_spec.json) | FastAPI OpenAPI 산출물 |
| [기여 가이드](CONTRIBUTING.md) | Issue, PR, 테스트, 문서 동기화 규칙 |

## 다른 언어 문서

| 문서 | 내용 |
| --- | --- |
| [English documentation index](INDEX_EN.md) | English documentation index |
| [English README](README_EN.md) | English project overview and quick start |
