# Changelog

이 문서는 Daily Stock Analysis 프로젝트의 주요 변경 사항을 기록합니다.

형식은 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)를 따르며, 버전 관리는 [Semantic Versioning](https://semver.org/)을 기준으로 합니다.

사용자 친화적인 릴리스 요약은 [GitHub Releases](https://github.com/ZhuLinsen/daily_stock_analysis/releases)를 참고하세요.

## [Unreleased]

- [수정] 데스크톱 업데이트 확인과 설치 흐름의 깨진 문구 및 JavaScript 문법 오류를 복구했습니다.
- [ci] 데스크톱 앱 변경 시 `apps/dsa-desktop` 테스트를 실행하는 CI 게이트를 추가했습니다.
- [문서] README, 문서 인덱스, FAQ, Bot 명령 가이드를 한국어 기준 문서로 정리했습니다.
- [문서] 전체 운영 가이드, 배포 가이드, LLM 설정, 알림, 경고, 설정 도움말 문서를 한국어 기준 문서로 정리했습니다.
- [개선] 리포트 언어 매핑의 사용자 표시값을 한국어로 정리했습니다.
- [chore] 언어 아티팩트 검사 스크립트를 추가하고 CI에서 사용자 노출 영역을 검사하도록 연결했습니다.
- [수정] Windows에서 symlink가 일반 파일로 체크아웃되는 환경에서도 AI 작업 자산 검사가 Git 인덱스의 symlink 상태를 확인하도록 보강했습니다.
- [수정] API 오류 메시지와 Bot 명령 응답에 남아 있던 깨진 문구를 한국어로 정리했습니다.

## 이전 릴리스

이전 릴리스의 상세 변경 이력은 GitHub Releases에서 확인할 수 있습니다.

주요 릴리스 흐름:

- 3.17.x: Web UI, 데이터 공급자, 분석 안정성 개선
- 3.16.x: 포트폴리오 리포트 표시 개선
- 3.15.x: 분석 워크플로와 배포 편의성 개선
- 3.14.x 이하: 기본 분석 기능, 알림, 자동화 문서 개선

과거 변경 로그 원문에는 중국어와 깨진 표기가 포함되어 있어, 한국어 전용 프로젝트 맥락에 맞춰 이 문서에서는 요약 형태로 유지합니다.
