# OpenClaw Skill 연동 가이드

이 문서는 [OpenClaw](https://github.com/openclaw/openclaw) Skill에서 daily_stock_analysis REST API를 호출해 주식 분석을 실행하는 방법을 설명합니다.

## 개요

- 연동 방식: OpenClaw Skill이 HTTP로 daily_stock_analysis API를 호출합니다.
- 사용 상황: DSA API가 실행 중이고, OpenClaw 대화에서 종목 분석을 트리거하고 싶을 때 사용합니다.
- 예시 요청: `analyze AAPL`, `600519 분석해줘`, `hk00700 리포트 보여줘`

## 전제 조건

1. daily_stock_analysis API가 실행 중이어야 합니다.
2. OpenClaw 쪽에서 HTTP 요청을 보낼 수 있어야 합니다.
3. GitHub Actions 예약 작업만으로는 API가 상시 노출되지 않으므로, 로컬 실행이나 서버 배포가 필요합니다.

API 실행 예시는 다음과 같습니다.

```bash
python main.py --serve-only
```

## 핵심 API

| Endpoint | Method | 용도 |
| --- | --- | --- |
| `/api/v1/analysis/analyze` | POST | 종목 분석 실행 |
| `/api/v1/analysis/status/{task_id}` | GET | 비동기 분석 상태 조회 |
| `/api/v1/agent/chat` | POST | Agent 전략 상담 |
| `/api/health` | GET | 상태 확인 |

## 분석 요청 예시

```json
{
  "stock_code": "600519",
  "report_type": "detailed",
  "force_refresh": true,
  "async_mode": false
}
```

필드 설명은 다음과 같습니다.

| 필드 | 설명 |
| --- | --- |
| `stock_code` | 분석할 종목 코드입니다. |
| `report_type` | `simple`, `detailed`, `brief` 중 하나입니다. |
| `force_refresh` | 캐시를 무시하고 새로 분석할지 결정합니다. |
| `async_mode` | `true`면 `task_id`를 받은 뒤 상태 조회 endpoint를 polling합니다. |

`force_refresh`와 `async_mode`는 문자열이 아니라 boolean 값으로 전달합니다.

## 응답 예시

```json
{
  "query_id": "abc123def456",
  "stock_code": "600519",
  "stock_name": "Kweichow Moutai",
  "report": {
    "summary": {
      "analysis_summary": "...",
      "operation_advice": "hold",
      "trend_prediction": "bullish",
      "sentiment_score": 75
    },
    "strategy": {
      "ideal_buy": "1850",
      "stop_loss": "1780",
      "take_profit": "1950"
    }
  },
  "created_at": "2026-03-13T10:00:00"
}
```

## 종목 코드 형식

| 시장 | 형식 | 예시 |
| --- | --- | --- |
| A주 | 6자리 숫자 | `600519`, `000001`, `300750` |
| 베이징거래소 | 8, 4, 92로 시작하는 6자리 코드 또는 `BJ` prefix | `920748`, `BJ920493`, `920493.BJ` |
| 홍콩 | `hk` + 5자리 숫자 | `hk00700`, `hk09988` |
| 미국 | 1-5자리 ticker, 필요 시 점 포함 | `AAPL`, `TSLA`, `BRK.B` |
| 미국 지수 | 지수 ticker | `SPX`, `DJI`, `NASDAQ`, `VIX` |

API는 기본적으로 종목명을 직접 받지 않고 종목 코드를 받습니다. Skill 쪽에서 종목명 입력을 허용하려면 별도 매핑을 두거나 사용자에게 코드를 다시 요청합니다.

## OpenClaw 설정 예시

`~/.openclaw/openclaw.json`에 API 주소를 등록합니다.

```json
{
  "skills": {
    "entries": {
      "daily-stock-analysis": {
        "enabled": true,
        "env": {
          "DSA_BASE_URL": "http://localhost:8000"
        }
      }
    }
  }
}
```

`DSA_BASE_URL`은 마지막에 `/`를 붙이지 않는 것을 권장합니다.

## SKILL.md 예시

다음 내용을 `~/.openclaw/skills/daily-stock-analysis/SKILL.md`에 둘 수 있습니다.

````markdown
---
name: daily-stock-analysis
description: Call the daily_stock_analysis API to analyze stocks. Use when the user asks to analyze a stock such as AAPL, 600519, or hk00700. Prefer stock codes over company names.
metadata:
  {"openclaw": {"requires": {"env": ["DSA_BASE_URL"]}, "primaryEnv": "DSA_BASE_URL"}}
---

## Trigger

Use this skill when the user asks for stock analysis.

## Workflow

1. Extract a stock code from the user message.
2. POST to `{DSA_BASE_URL}/api/v1/analysis/analyze`.
3. Use this request body:

```json
{"stock_code": "<code>", "report_type": "detailed", "force_refresh": true, "async_mode": false}
```

4. If the request times out, retry with `async_mode: true` and poll `/api/v1/analysis/status/{task_id}`.
5. Summarize `report.summary` and `report.strategy` for the user.
````

## Agent 상담

`AGENT_MODE=true`가 설정되어 있으면 Agent 상담 endpoint를 사용할 수 있습니다.

```bash
curl -X POST {DSA_BASE_URL}/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Analyze 600519 with the configured strategy", "session_id": "optional-session-id"}'
```

응답에는 대화 내용인 `content`와 이어지는 대화에 사용할 수 있는 `session_id`가 포함됩니다.

## 오류 처리

| 상태 | 원인 | 대응 |
| --- | --- | --- |
| 연결 실패 | API 미실행, 포트 오류, 방화벽 | `python main.py --serve-only` 실행 상태와 `DSA_BASE_URL`을 확인합니다. |
| 400 | 종목 코드 형식 오류 | 코드 형식과 요청 본문을 확인합니다. |
| 409 | 같은 종목 분석이 이미 진행 중 | 잠시 뒤 재시도하거나 상태 조회 endpoint를 사용합니다. |
| 500 | 분석 중 오류 | DSA 로그, LLM 키, 데이터 소스 설정을 확인합니다. |
| timeout | 동기 분석 시간이 길어짐 | HTTP timeout을 늘리거나 비동기 모드를 사용합니다. |

## 인증

기본 API는 인증 없이 사용할 수 있습니다. `.env`에서 `ADMIN_AUTH_ENABLED=true`를 켠 경우에는 로그인 후 발급되는 Cookie를 Skill 요청에 포함해야 합니다. 현재 API는 Bearer token 방식보다 Cookie 기반 인증을 우선합니다.
