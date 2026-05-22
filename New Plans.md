# New Plans

daily_stock_analysis 주식분석 에이전트 고도화 작업의 남은 계획입니다.
구현이 완료된 항목은 아래 목록에서 지웁니다.

## 1. 리포트 통합

- 종목 리포트에 차트 분석 요약을 포함한다.
- 리포트에 이벤트 모니터링 우선순위와 thesis 훼손 위험을 표시한다.
- 포트폴리오 분석 결과를 리포트 또는 Agent 응답에 요약한다.
- confidence, evidence graph, risk, chart, event, portfolio 정보를 한 화면에서 볼 수 있게 정리한다.

## 2. Vision/VLM 차트 해석 연결

- 생성된 SVG 또는 PNG 차트를 Vision 모델 입력으로 전달할 수 있게 한다.
- VLM 해석 결과와 수치 지표 결과를 비교한다.
- VLM 해석의 근거와 불확실성을 표시한다.
- Vision provider가 없을 때는 기존 수치 기반 분석으로 안전하게 fallback한다.

## 3. 운영 안정화와 평가

- 각 도구별 성공률, 실패율, 평균 실행 시간을 기록한다.
- 차트 분석, paper trading, portfolio analysis용 eval fixture를 만든다.
- 대표 종목 A-share, HK, US에 대한 smoke test를 추가한다.
- 사용자 노출 문구와 깨진 문자열을 점검한다.
- 2차 작업 완료 후 전체 CI gate를 실행한다.
