# 이미지 추출 프롬프트

이 문서는 `src/services/image_stock_extractor.py`의 `EXTRACT_PROMPT` 내용을 기록합니다. Vision LLM으로 이미지에서 종목 코드와 이름을 추출하는 동작을 검토할 때 사용합니다.

`EXTRACT_PROMPT`를 변경하면 이 문서도 함께 갱신하고, PR 설명에 변경 전후 프롬프트를 함께 적습니다. 특히 `code`, `name`, `confidence` 추출 규칙이 바뀌었는지 명확히 설명해야 합니다.

## 현재 프롬프트

```text
주식 시장 스크린샷 또는 이미지를 분석해, 이미지 안에 보이는 모든 종목 코드와 종목명을 추출하세요.

중요:
- 이미지에 종목명과 코드가 함께 보이면 둘 다 추출하세요.
- 관심 종목 목록, ETF 목록, 차트 캡션, 검색 결과처럼 여러 종목이 보이는 경우 각 종목을 개별 객체로 반환하세요.
- 출력은 유효한 JSON 배열만 반환하세요.
- markdown, 설명 문장, 코드 블록 표시는 반환하지 마세요.

각 배열 요소는 다음 형식을 사용합니다.
{"code":"종목 코드","name":"종목명","confidence":"high|medium|low"}

필드 규칙:
- code: 필수입니다. A주 6자리, 홍콩 주식 5자리, 미국 ticker, ETF 코드 등을 인식합니다.
- name: 이미지에 이름이 보이면 필수입니다. 이름이 실제로 보이지 않을 때만 생략할 수 있습니다.
- confidence: 필수입니다. high는 확실함, medium은 비교적 확실함, low는 불확실함을 의미합니다.

예시:
- A주: 600519 Kweichow Moutai, 300750 CATL
- 홍콩 주식: 00700 Tencent, 09988 Alibaba
- 미국 주식: AAPL Apple, TSLA Tesla
- ETF: 159887 Bank ETF, 512880 Securities ETF, 512000 Brokerage ETF, 512480 Semiconductor ETF

출력 예시:
[{"code":"600519","name":"Kweichow Moutai","confidence":"high"},{"code":"159887","name":"Bank ETF","confidence":"high"}]

금지:
- ["159887","512880"]처럼 코드 배열만 반환하지 마세요.
- JSON 배열 외의 텍스트를 함께 반환하지 마세요.
- 종목 코드를 찾지 못하면 []를 반환하세요.
```
