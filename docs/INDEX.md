# 문서 인덱스

Daily Stock Analysis의 주요 문서 진입점입니다. 처음 사용하는 경우 `README.md`, `beginner-client-setup.md`, `full-guide.md` 순서로 읽는 것을 권장합니다.

## 시작하기

| 문서 | 내용 |
| --- | --- |
| [README](../README.md) | 프로젝트 개요, 빠른 시작, 주요 기능 |
| [초보자용 클라이언트 설정](beginner-client-setup.md) | 데스크톱/클라이언트 설치와 기본 설정 |
| [전체 가이드](full-guide.md) | 실행, 설정, 배포, 운영 전반 |
| [FAQ](FAQ.md) | 자주 발생하는 문제와 해결 방법 |

## 설정

| 문서 | 내용 |
| --- | --- |
| [LLM 설정 가이드](LLM_CONFIG_GUIDE.md) | AI 모델과 채널 설정 |
| [LLM 공급자 설정](llm-providers.md) | 공급자별 설정과 진단 |
| [설정 도움말](settings-help.md) | Web 설정 화면의 필드 설명 |
| [알림 설정](notifications.md) | 알림 채널, 라우팅, 진단 |

## 기능

| 문서 | 내용 |
| --- | --- |
| [Bot 명령](bot-command.md) | 메신저 봇 명령과 사용법 |
| [알림 센터](alerts.md) | 규칙 생성, 테스트, 트리거 기록 |
| [이미지 종목 추출 Prompt](image-extract-prompt.md) | 이미지에서 종목 코드를 추출하는 Prompt |
| [OpenClaw Skill 연동](openclaw-skill-integration.md) | 외부 Skill 연동 방식 |

## 배포와 패키징

| 문서 | 내용 |
| --- | --- |
| [배포 가이드](DEPLOY.md) | 서버, Docker, 운영 배포 |
| [Web UI 클라우드 배포](deploy-webui-cloud.md) | 클라우드에서 Web UI 열기 |
| [데스크톱 패키징](desktop-package.md) | Electron 데스크톱 빌드와 배포 |
| [Zeabur 배포](docker/zeabur-deployment.md) | Zeabur 배포 참고 |

## 개발

| 문서 | 내용 |
| --- | --- |
| [기여 가이드](CONTRIBUTING.md) | 개발 참여와 PR 규칙 |
| [API 스펙](architecture/api_spec.json) | OpenAPI 산출물 |
| [변경 이력](CHANGELOG.md) | 릴리스와 주요 변경 |

## 운영 메모

- 한국어 사용자 경험을 우선합니다.
- 사용자 노출 문구에는 깨진 문자, 중국어 한자, 로마자화된 임시 문구를 남기지 않습니다.
- 언어 아티팩트 검사는 `python scripts/check_language_artifacts.py`로 실행합니다.
