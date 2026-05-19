# LLM 설정 가이드

이 문서는 AI 모델 연결 방식을 한국어 기준으로 정리합니다.

## 1. 기본 구조

프로젝트는 OpenAI 호환 API 형식을 우선 지원합니다.

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

공급자가 OpenAI 호환 엔드포인트를 제공하면 같은 방식으로 설정할 수 있습니다.

## 2. 필수 설정

| 변수 | 설명 |
| --- | --- |
| `OPENAI_API_KEY` | API 키 |
| `OPENAI_BASE_URL` | API 기본 주소 |
| `OPENAI_MODEL` | 사용할 모델명 |

## 3. 공급자 선택 기준

모델 공급자를 고를 때는 다음을 확인하세요.

- 한국어 응답 품질
- 금융 문서와 뉴스 요약 능력
- tool/function calling 지원 여부
- 비용과 rate limit
- 장애 시 대체 모델로 전환 가능한지

## 4. 로컬 모델

Ollama 같은 로컬 모델 서버를 사용할 수 있습니다.

```env
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=llama3.1
```

로컬 모델은 비용이 낮지만 금융 분석 품질과 속도는 모델 성능에 크게 좌우됩니다.

## 5. 프롬프트 언어

사용자에게 보이는 리포트 언어는 한국어를 기본으로 유지합니다.

확인 항목:

- 리포트 제목과 섹션명
- 매수/보유/매도 같은 판단 문구
- 오류 메시지
- 알림 메시지
- Web UI 표시 문구

## 6. 장애 대응

모델 호출이 실패하면 다음을 확인합니다.

- API 키가 유효한지
- `OPENAI_BASE_URL` 뒤에 `/v1`이 필요한지
- 모델명이 공급자에서 실제로 지원되는지
- rate limit에 걸리지 않았는지
- 네트워크 timeout이 너무 짧지 않은지

## 7. 검증

설정 후 단일 종목으로 먼저 확인합니다.

```bash
python main.py --stocks KR005930 --debug
```

Web UI를 사용하는 경우 분석 요청, 진행 상태, 최종 리포트가 모두 한국어로 표시되는지 확인하세요.
