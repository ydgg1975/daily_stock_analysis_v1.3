# Tushare 종목 목록 가져오기 가이드

이 문서는 Tushare Pro에서 A주, 홍콩 주식, 미국 주식 목록을 가져와 로컬 CSV 파일로 저장하는 방법을 설명합니다.

## 기능 개요

`scripts/fetch_tushare_stock_list.py`는 Tushare API를 호출해 시장별 종목 목록을 수집하고 `data/` 디렉터리에 CSV 파일을 생성합니다. 이후 `scripts/generate_index_from_csv.py`를 사용하면 WebUI 자동완성이나 종목 검색에 활용할 색인 파일을 만들 수 있습니다.

## 준비

### 1. Tushare Token 설정

프로젝트 루트의 `.env` 파일에 Tushare Token을 추가합니다.

```env
TUSHARE_TOKEN=your_tushare_token
```

Token은 [Tushare Pro](https://tushare.pro/weborder/#/login)에 가입한 뒤 발급받을 수 있습니다.

### 2. 종목 목록 수집

```bash
python scripts/fetch_tushare_stock_list.py
```

### 3. 결과 확인

수집 결과는 `data/` 디렉터리에 저장됩니다.

```text
data/
├── stock_list_a.csv       # A주 목록
├── stock_list_hk.csv      # 홍콩 주식 목록
├── stock_list_us.csv      # 미국 주식 목록
└── README_stock_list.md   # 생성 데이터 설명
```

## 주요 특징

- 자동 페이지 처리: 대량 데이터는 여러 페이지로 나누어 가져옵니다.
- 요청 간 대기: API 제한을 피하기 위해 요청 사이에 대기 시간을 둡니다.
- 시장별 실패 격리: 한 시장 수집이 실패해도 다른 시장 처리를 계속할 수 있습니다.
- 진행 상황 표시: 실행 중 처리 상황을 콘솔에 표시합니다.
- 설명 문서 생성: 생성된 CSV 구조를 설명하는 문서를 함께 만들 수 있습니다.

## 시장별 API

| 시장 | Tushare API | 포인트 요구 사항 | 예상 규모 |
| --- | --- | --- | --- |
| A주 | `stock_basic` | Tushare 정책에 따름 | 약 5,000개 |
| 홍콩 주식 | `hk_basic` | Tushare 정책에 따름 | 약 2,000개 |
| 미국 주식 | `us_basic` | Tushare 정책에 따름 | 약 10,000개 |

포인트 정책은 Tushare에서 변경될 수 있으므로 실제 요구 조건은 Tushare 공식 문서를 기준으로 확인하세요.

## CSV 형식 예시

### A주: `stock_list_a.csv`

```csv
ts_code,symbol,name,area,industry,market,exchange,list_date,...
000001.SZ,000001,평안은행,선전,은행,메인보드,SZSE,19910403,...
600519.SH,600519,귀주모태,귀주,백주,메인보드,SSE,20010827,...
```

### 홍콩 주식: `stock_list_hk.csv`

```csv
ts_code,name,fullname,market,list_date,trade_unit,curr_type,...
00700.HK,Tencent,Tencent Holdings Ltd,메인보드,20040616,100,HKD,...
00005.HK,HSBC,HSBC Holdings plc,메인보드,19750401,100,HKD,...
```

### 미국 주식: `stock_list_us.csv`

```csv
ts_code,name,enname,classify,list_date,...
AAPL,Apple,Apple Inc.,EQT,19801212,...
TSLA,Tesla,Tesla Inc.,EQT,20100629,...
BABA,Alibaba,Alibaba Group,ADR,20140919,...
```

실제 원천 데이터에는 중국어 종목명이나 지역명이 포함될 수 있습니다. 이 값은 데이터 자체의 일부이므로 문서의 설명 언어와 별개로 유지될 수 있습니다.

## Python에서 읽기

```python
import pandas as pd

a_stocks = pd.read_csv("data/stock_list_a.csv")
print(f"A주 종목 수: {len(a_stocks)}")

main_board = a_stocks[a_stocks["market"] == "메인보드"]
print(f"메인보드 종목 수: {len(main_board)}")

stock = a_stocks[a_stocks["ts_code"] == "600519.SH"]
print(stock[["name", "industry", "list_date"]])
```

## 색인 생성

CSV를 가져온 뒤 종목 검색 색인을 만들 수 있습니다.

```bash
python scripts/generate_index_from_csv.py --test
python scripts/generate_index_from_csv.py
```

`--test`는 실제 파일 갱신 전 점검 용도로 사용합니다.

## 주의 사항

1. Tushare 포인트와 권한 정책은 계정 상태에 따라 다릅니다.
2. API 호출 제한이 있으므로 짧은 시간에 반복 실행하지 않는 것이 좋습니다.
3. CSV 파일은 원천 데이터 스냅샷입니다. 최신 상장/상폐 상태가 필요하면 다시 수집하세요.
4. 네트워크 오류나 권한 오류가 나면 Token, 계정 권한, 포인트, Tushare 서비스 상태를 확인합니다.

## 자주 묻는 질문

### `TUSHARE_TOKEN`이 없다는 오류가 납니다.

`.env` 파일에 다음 형식으로 Token을 추가했는지 확인합니다.

```env
TUSHARE_TOKEN=your_tushare_token
```

### 포인트가 부족하다는 오류가 납니다.

Tushare 계정의 포인트와 API 사용 권한을 확인하세요. 시장별 API는 필요한 권한이 다를 수 있습니다.

### 수집이 중간에 실패합니다.

네트워크 상태, Token 유효성, Tushare API 제한을 확인합니다. 일부 시장만 실패했다면 성공한 CSV는 그대로 활용할 수 있고, 나중에 다시 실행해 보강할 수 있습니다.

## 참고 링크

- [Tushare](https://tushare.pro)
- [Tushare 문서](https://tushare.pro/document/2)
- [Tushare 포인트 안내](https://tushare.pro/document/1)
