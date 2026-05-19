# Tushare 종목 목록 도구

Tushare Pro에서 주식 목록을 내려받아 로컬 CSV로 저장하는 도구 안내입니다.

## 1. Token 설정

`.env`에 Tushare Token을 설정합니다.

```env
TUSHARE_TOKEN=your_token
```

## 2. 실행

```bash
python scripts/fetch_tushare_stock_list.py
```

## 3. 출력

결과 파일은 `data/` 디렉터리에 저장됩니다.

예상 산출물:

- A주 목록 CSV
- 홍콩 주식 목록 CSV
- 미국 주식 목록 CSV
- 데이터 설명 문서

## 4. 갱신 주기

종목 목록은 정기적으로 바뀔 수 있으므로 월 1회 이상 갱신을 권장합니다.

## 5. 문제 해결

- Token이 올바른지 확인합니다.
- Tushare 계정 권한과 포인트 상태를 확인합니다.
- 네트워크 오류나 rate limit 여부를 확인합니다.

참고:

- [Tushare](https://tushare.pro)
- [Tushare 문서](https://tushare.pro/document/2)
