# LLM 공급자

이 프로젝트는 OpenAI 호환 API를 기준으로 여러 LLM 공급자를 연결할 수 있습니다.

## 공통 설정

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://provider.example.com/v1
OPENAI_MODEL=model-name
```

## 선택 기준

| 기준 | 확인 내용 |
| --- | --- |
| 한국어 품질 | 금융 뉴스와 리포트 요약이 자연스러운지 |
| 안정성 | timeout, rate limit, 장애 빈도 |
| 비용 | 분석 횟수 대비 비용 |
| 기능 | tool calling, JSON 응답, 긴 컨텍스트 지원 |
| 호환성 | OpenAI 호환 API 지원 여부 |

## 권장 운영 방식

- 기본 모델과 예비 모델을 분리합니다.
- 긴 리포트 생성에는 컨텍스트가 충분한 모델을 사용합니다.
- 비용이 중요한 작업은 작은 모델로 먼저 테스트합니다.
- 모델 변경 후에는 같은 종목으로 결과 품질을 비교합니다.

## 장애 점검

모델 호출 실패 시 확인할 항목:

- API 키 유효성
- 결제 또는 quota 상태
- 모델명 오타
- endpoint의 `/v1` 포함 여부
- 요청 timeout
- 응답 형식이 프로젝트 파서와 맞는지
