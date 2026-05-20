#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tushare Pro에서 A주, 홍콩 주식, 미국 주식 목록을 받아 CSV로 저장합니다."""

from __future__ import annotations

import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import tushare as ts
except ImportError:
    print("[오류] tushare 패키지가 설치되어 있지 않습니다.")
    print("실행해 주세요: pip install tushare")
    sys.exit(1)


load_dotenv()

TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN")
OUTPUT_DIR = Path(__file__).parent.parent / "data"
PAGE_SIZE = 5000
SLEEP_MIN = 5
SLEEP_MAX = 10


def get_tushare_api() -> Optional[ts.pro_api]:
    """Tushare API 클라이언트를 만들고 간단한 연결 확인을 수행합니다."""
    if not TUSHARE_TOKEN:
        print("[오류] TUSHARE_TOKEN을 찾지 못했습니다.")
        print(".env 파일에 TUSHARE_TOKEN=your_token 형식으로 설정해 주세요.")
        return None

    try:
        api = ts.pro_api(TUSHARE_TOKEN)
        api.trade_cal(exchange="SSE", start_date="20240101", end_date="20240101")
        print("Tushare API 연결 성공")
        return api
    except Exception as exc:
        print(f"[오류] Tushare API 연결 실패: {exc}")
        print("확인할 항목:")
        print("  1. TUSHARE_TOKEN 값이 올바른지 확인")
        print("  2. 계정 포인트가 충분한지 확인")
        return None


def random_sleep(min_seconds: int = SLEEP_MIN, max_seconds: int = SLEEP_MAX) -> None:
    """API 요청 간격을 두어 빈번한 호출을 피합니다."""
    sleep_time = random.uniform(min_seconds, max_seconds)
    print(f"  {sleep_time:.1f}초 대기...")
    time.sleep(sleep_time)


def fetch_a_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """A주 상장 종목 목록을 가져옵니다."""
    print("\n[1/3] A주 목록을 가져오는 중...")

    try:
        df = api.stock_basic(
            exchange="",
            list_status="L",
            fields=(
                "ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,"
                "exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type"
            ),
        )

        if df is not None and len(df) > 0:
            print(f"A주 목록 수집 성공: {len(df)}개 종목")
            if "exchange" in df.columns:
                print("  거래소 분포:")
                for exchange, count in df["exchange"].value_counts().items():
                    print(f"    {exchange}: {count}개")
            return df

        print("[오류] A주 데이터가 비어 있습니다.")
        return None
    except Exception as exc:
        print(f"[오류] A주 목록 수집 실패: {exc}")
        return None


def fetch_hk_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """홍콩 주식 상장 종목 목록을 가져옵니다."""
    print("\n[2/3] 홍콩 주식 목록을 가져오는 중...")

    try:
        df = api.hk_basic(list_status="L")
        if df is not None and len(df) > 0:
            print(f"홍콩 주식 목록 수집 성공: {len(df)}개 종목")
            return df

        print("[오류] 홍콩 주식 데이터가 비어 있습니다.")
        return None
    except Exception as exc:
        print(f"[오류] 홍콩 주식 목록 수집 실패: {exc}")
        return None


def fetch_us_stock_list(api: ts.pro_api) -> Optional[pd.DataFrame]:
    """미국 주식 목록을 페이지 단위로 가져옵니다."""
    print("\n[3/3] 미국 주식 목록을 가져오는 중...")

    all_data: list[pd.DataFrame] = []
    offset = 0
    page = 1

    try:
        while True:
            print(f"  {page}페이지 요청(offset={offset})...")
            df = api.us_basic(offset=offset, limit=PAGE_SIZE)

            if df is None or len(df) == 0:
                print(f"  {page}페이지에 데이터가 없어 수집을 종료합니다.")
                break

            all_data.append(df)
            print(f"  {page}페이지 수집: {len(df)}개 종목")

            if len(df) < PAGE_SIZE:
                break

            offset += PAGE_SIZE
            page += 1
            random_sleep()

        if all_data:
            result_df = pd.concat(all_data, ignore_index=True)
            print(f"미국 주식 목록 수집 성공: {len(result_df)}개 종목, {page}페이지")

            if "classify" in result_df.columns:
                print("  분류 분포:")
                for classify, count in result_df["classify"].value_counts().items():
                    print(f"    {classify}: {count}개")

            return result_df

        print("[오류] 미국 주식 데이터가 비어 있습니다.")
        return None
    except Exception as exc:
        print(f"[오류] 미국 주식 목록 수집 실패: {exc}")
        return None


def save_to_csv(df: pd.DataFrame, filename: str, market_name: str) -> bool:
    """DataFrame을 CSV 파일로 저장합니다."""
    if df is None or len(df) == 0:
        print(f"[건너뜀] {market_name} 데이터가 비어 있어 파일을 저장하지 않습니다.")
        return False

    try:
        output_path = OUTPUT_DIR / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")

        file_size = output_path.stat().st_size / 1024
        print(f"{market_name} 데이터 저장 완료: {output_path} ({file_size:.2f} KB)")
        return True
    except Exception as exc:
        print(f"[오류] {market_name} 데이터 저장 실패: {exc}")
        return False


def generate_data_documentation(
    a_df: Optional[pd.DataFrame],
    hk_df: Optional[pd.DataFrame],
    us_df: Optional[pd.DataFrame],
) -> None:
    """수집한 CSV 파일 설명 문서를 생성합니다."""
    doc_path = OUTPUT_DIR / "README_stock_list.md"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = f"""# Tushare 주식 목록 데이터 설명

> 데이터 출처: [Tushare Pro](https://tushare.pro)
> 생성 시간: {generated_at}

## 파일 설명

| 파일 | 설명 | 기록 수 |
| --- | --- | --- |
| `stock_list_a.csv` | A주 상장 종목 목록 | {len(a_df) if a_df is not None else 0} |
| `stock_list_hk.csv` | 홍콩 주식 상장 종목 목록 | {len(hk_df) if hk_df is not None else 0} |
| `stock_list_us.csv` | 미국 주식 종목 목록 | {len(us_df) if us_df is not None else 0} |

## 데이터 인터페이스

### A주: `stock_basic`

- 최소 포인트: 보통 2000포인트 이상 필요
- 주요 필드: `ts_code`, `symbol`, `name`, `area`, `industry`, `fullname`, `enname`, `market`, `exchange`, `list_date`

### 홍콩 주식: `hk_basic`

- 최소 포인트: 보통 2000포인트 이상 필요
- 주요 필드: `ts_code`, `name`, `fullname`, `enname`, `market`, `list_status`, `list_date`, `trade_unit`, `curr_type`

### 미국 주식: `us_basic`

- 기본 조회는 120포인트부터 가능하며, 전체 권한은 계정 등급에 따라 다를 수 있습니다.
- 주요 필드: `ts_code`, `name`, `enname`, `classify`, `list_date`, `delist_date`

## 사용 예시

```python
import pandas as pd

a_stocks = pd.read_csv("data/stock_list_a.csv")
hk_stocks = pd.read_csv("data/stock_list_hk.csv")
us_stocks = pd.read_csv("data/stock_list_us.csv")
```

## 코드 형식

- A주: `000001.SZ`, `600000.SH`, `8xxxxx.BJ`
- 홍콩 주식: `00700.HK` 같은 5자리 코드 + `.HK`
- 미국 주식: `AAPL`, `TSLA` 같은 ticker

## 주의 사항

1. 데이터는 정기적으로 갱신하는 것을 권장합니다.
2. 계정 포인트와 호출 제한은 Tushare 계정 정책을 따릅니다.
3. 이 데이터는 기본 종목 정보 중심이며, 추가 필드는 Tushare 공식 문서를 확인하세요.

## 관련 링크

- [Tushare 공식 사이트](https://tushare.pro)
- [Tushare API 문서](https://tushare.pro/document/2)
- [포인트 안내](https://tushare.pro/document/1)
"""

    try:
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"데이터 설명 문서 생성 완료: {doc_path}")
    except Exception as exc:
        print(f"[오류] 데이터 설명 문서 생성 실패: {exc}")


def main() -> int:
    """스크립트 진입점."""
    print("=" * 60)
    print("Tushare 주식 목록 수집 도구")
    print("=" * 60)

    api = get_tushare_api()
    if not api:
        return 1

    a_df = fetch_a_stock_list(api)
    if a_df is not None:
        save_to_csv(a_df, "stock_list_a.csv", "A주")

    random_sleep()
    hk_df = fetch_hk_stock_list(api)
    if hk_df is not None:
        save_to_csv(hk_df, "stock_list_hk.csv", "홍콩 주식")

    random_sleep()
    us_df = fetch_us_stock_list(api)
    if us_df is not None:
        save_to_csv(us_df, "stock_list_us.csv", "미국 주식")

    print("\n데이터 설명 문서를 생성하는 중...")
    generate_data_documentation(a_df, hk_df, us_df)

    print("\n" + "=" * 60)
    print("작업 완료")
    print("=" * 60)

    total_count = 0
    if a_df is not None:
        total_count += len(a_df)
        print(f"  A주: {len(a_df)}개")
    if hk_df is not None:
        total_count += len(hk_df)
        print(f"  홍콩 주식: {len(hk_df)}개")
    if us_df is not None:
        total_count += len(us_df)
        print(f"  미국 주식: {len(us_df)}개")

    print(f"\n총 {total_count}개 종목")
    print(f"출력 디렉터리: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자가 작업을 취소했습니다.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[오류] 예상하지 못한 예외: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
