# OpenClaw Skill 연동

이 문서는 OpenClaw skill에서 Daily Stock Analysis REST API를 호출하는 방법을 설명합니다.

## 사용 시나리오

OpenClaw 대화 중 사용자가 종목 분석을 요청하면 DSA API에 분석 요청을 보내고 결과를 반환합니다.

예시 요청:

- `KR005930 분석해줘`
- `analyze AAPL`
- `hk00700 리포트 보여줘`

## API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
| --- | --- | --- |
| `/api/v1/analysis/analyze` | POST | 종목 분석 실행 |
| `/api/v1/history` | GET | 분석 이력 조회 |
| `/api/health` | GET | 상태 확인 |

## 분석 요청 예시

```json
{
  "stock_code": "KR005930",
  "report_type": "detailed",
  "force_refresh": false,
  "async_mode": false
}
```

`force_refresh`와 `async_mode`는 boolean 값으로 전달합니다.

## 종목 코드 형식

| 시장 | 예시 |
| --- | --- |
| 한국 | `KR005930` |
| 중국 | `CN600519` |
| 홍콩 | `hk00700` |
| 미국 | `AAPL` |

## Skill 설정 예시

```yaml
name: daily-stock-analysis
description: Call the Daily Stock Analysis API for stock analysis.
```

Skill은 사용자 메시지에서 종목 코드를 추출하고, 종목명이 필요한 경우 코드 입력을 요청합니다.

## cURL 예시

```bash
curl -X POST "{DSA_BASE_URL}/api/v1/analysis/analyze" \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"KR005930","report_type":"detailed","force_refresh":false,"async_mode":false}'
```

## 오류 처리

| 상태 | 의미 | 대응 |
| --- | --- | --- |
| 409 | 같은 종목이 이미 분석 중 | 잠시 후 다시 시도 |
| 500 | 분석 실패 | DSA 로그 확인 |
| 연결 실패 | API 서버 미실행 또는 주소 오류 | `DSA_BASE_URL`과 서버 상태 확인 |

동기 분석은 시간이 걸릴 수 있으므로 HTTP timeout을 충분히 길게 설정하세요.
