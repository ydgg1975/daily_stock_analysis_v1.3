# 초보자용 데스크톱 클라이언트 설치와 설정 가이드

이 문서는 코드를 잘 모르는 사용자가 데스크톱 앱을 내려받아 첫 분석 보고서를 만드는 흐름을 설명합니다. 목표는 간단합니다. 클라이언트를 설치하고, LLM API Key를 넣고, 종목 코드를 입력한 뒤 분석을 실행합니다.

> 이 프로젝트가 생성하는 내용은 보조 분석 보고서이며 투자 조언이 아닙니다. 실제 거래 판단과 위험 관리는 사용자 본인이 책임져야 합니다.

## 준비물

1. Windows 또는 macOS 컴퓨터
2. LLM API Key
   - [Anspire Open](https://open.anspire.cn/?share_code=QFBC0FYC): 여러 모델과 뉴스 검색을 한 Key로 쓰고 싶을 때 편합니다.
   - [AIHubMix](https://aihubmix.com/?aff=CfMq): 여러 모델을 한 플랫폼에서 바꿔 쓰고 싶을 때 적합합니다.
   - OpenAI, Anthropic, Gemini 등 다른 provider도 설정 페이지에서 직접 구성할 수 있습니다.
3. 분석할 종목 코드
   - 예: `600519,hk00700,AAPL`

## 1. 클라이언트 다운로드

릴리스 페이지를 엽니다.

<https://github.com/robot0971-art/daily_stock_analysis/releases/latest>

페이지 하단의 `Assets`에서 운영체제에 맞는 파일을 받습니다.

| 환경 | 다운로드 파일 |
| --- | --- |
| Windows 설치형 | `daily-stock-analysis-windows-installer-<version>.exe` |
| Windows 무설치 | `daily-stock-analysis-windows-noinstall-<version>.zip` |
| macOS Apple Silicon | `daily-stock-analysis-macos-arm64-<version>.dmg` |
| macOS Intel | `daily-stock-analysis-macos-x64-<version>.dmg` |

`latest.yml`이나 `*.blockmap` 파일은 자동 업데이트용 메타데이터이므로 사용자가 직접 실행하는 설치 파일이 아닙니다.

Mac 칩 종류를 모르면 왼쪽 위 Apple 메뉴에서 `이 Mac에 관하여`를 확인합니다. M1/M2/M3/M4는 `arm64`, Intel은 `x64`를 선택합니다.

## 2. 설치와 실행

- Windows 설치형: `.exe` 파일을 실행하고 기본 안내에 따라 설치합니다.
- Windows 무설치: `.zip` 파일을 압축 해제한 뒤 `Daily Stock Analysis.exe`를 실행합니다.
- macOS: `.dmg` 파일을 열고 앱을 `Applications`로 드래그합니다. 미확인 개발자 경고가 나오면 시스템 설정의 개인정보 보호 및 보안에서 실행을 허용합니다.

macOS에서 기존 버전을 업그레이드하기 전에는 설정 화면에서 구성 백업을 한 번 내보내는 것을 권장합니다.

## 3. AI 모델 설정

앱을 열고 다음 위치로 이동합니다.

```text
설정 -> AI 모델
```

처음에는 provider 하나만 설정해도 됩니다. 설정을 바꾼 뒤에는 반드시 저장 버튼을 누르고, 저장 성공 메시지를 확인한 뒤 연결 테스트를 실행합니다.

### Anspire Open

1. [Anspire Open](https://open.anspire.cn/?share_code=QFBC0FYC)에 가입하거나 로그인합니다.
2. API Key를 생성합니다.
3. 앱의 빠른 추가 또는 LLM 채널 설정에서 `Anspire Open`을 선택합니다.
4. API Key를 붙여넣고 사용할 모델명을 선택합니다.
5. 저장 후 연결 테스트를 실행합니다.

### AIHubMix

1. [AIHubMix](https://aihubmix.com/?aff=CfMq)에 가입하거나 로그인합니다.
2. API Key를 생성합니다.
3. 앱의 빠른 추가 또는 LLM 채널 설정에서 `AIHubMix`를 선택합니다.
4. API Key를 붙여넣고 사용할 모델명을 선택합니다.
5. 저장 후 연결 테스트를 실행합니다.

연결 테스트가 성공하면 다음 단계로 넘어갑니다.

## 4. 자주 보는 종목 입력

다음 위치로 이동합니다.

```text
설정 -> 기본 설정
```

`자주 보는 종목` 또는 `STOCK_LIST` 항목에 종목 코드를 입력합니다.

```text
600519,hk00700,AAPL
```

여러 종목은 영문 쉼표로 구분합니다.

| 시장 | 예시 |
| --- | --- |
| A주 | `600519`, `300750`, `000001` |
| 홍콩 주식 | `hk00700`, `hk09988` |
| 미국 주식 | `AAPL`, `TSLA`, `NVDA` |

입력 후 저장하고 저장 성공 메시지를 확인합니다.

## 5. 뉴스 소스 설정

뉴스 소스는 필수는 아니지만 권장합니다. 최근 뉴스, 공시, 이벤트, 섹터 이슈, 리스크 경고 품질에 영향을 줍니다.

다음 위치로 이동합니다.

```text
설정 -> 데이터 소스
```

- Anspire Open을 사용한다면 `Anspire API Keys`에 같은 Key를 넣을 수 있습니다.
- AIHubMix만 사용하는 경우 [SerpAPI](https://serpapi.com/baidu-search-api?utm_source=github_daily_stock_analysis) 또는 [Tavily](https://tavily.com/) Key를 추가로 설정하는 것을 권장합니다.

뉴스 소스를 건너뛰어도 기본 분석은 실행할 수 있습니다.

## 6. 첫 분석 실행

홈 화면으로 돌아갑니다.

1. 종목 코드를 입력합니다. 예: `600519`
2. `분석` 버튼을 누릅니다.
3. 작업 상태가 대기, 분석 중, 완료 순서로 바뀌는지 확인합니다.
4. 분석 기록에서 보고서를 확인합니다.

## 자주 묻는 질문

### 다운로드 파일이 많은데 무엇을 받아야 하나요?

Windows 일반 사용자는 `.exe` 설치 파일을 받으면 됩니다. `latest.yml`과 `*.blockmap`은 직접 내려받아 실행하는 파일이 아닙니다.

### API Key를 넣었는데 연결 테스트가 실패합니다.

다음을 확인합니다.

1. Key 앞뒤에 공백이 없는지 확인합니다.
2. provider 계정에 잔액 또는 사용 한도가 남아 있는지 확인합니다.
3. 선택한 모델이 계정에서 사용 가능한지 확인합니다.
4. 연결 테스트 오류에 인증 실패, 모델 없음, 권한 부족, 잔액 부족이 표시되는지 확인합니다.

### 설정이 꼬인 것 같습니다.

설정 화면에서 구성 백업을 내보낼 수 있습니다. 문제가 계속되면 기존 백업을 가져오거나, AI 모델, 자주 보는 종목, 뉴스 소스만 남기고 다시 설정합니다.
