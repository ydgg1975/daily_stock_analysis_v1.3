#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSV 파일에서 Web 자동완성용 주식 색인을 생성합니다."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pypinyin import Style, lazy_pinyin

    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False
    print("[경고] pypinyin이 설치되어 있지 않아 pinyin 필드는 비어 있게 됩니다.")
    print("[안내] 설치 명령: pip install pypinyin")


def load_csv_data(csv_path: Path) -> List[Dict[str, Any]]:
    """AkShare 형식 CSV에서 주식 데이터를 읽습니다."""
    stocks: List[Dict[str, Any]] = []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts_code = row["ts_code"].strip()
            symbol = row["symbol"].strip()
            name = row["name"].strip()

            if not ts_code or not symbol or not name:
                continue

            stocks.append(
                {
                    "ts_code": ts_code,
                    "symbol": symbol,
                    "name": name,
                    "area": row.get("area", ""),
                    "industry": row.get("industry", ""),
                    "list_date": row.get("list_date", ""),
                }
            )

    return stocks


def load_tushare_data(data_dir: Path) -> List[Dict[str, Any]]:
    """Tushare CSV 파일 세 개를 읽어 통합 주식 목록을 만듭니다."""
    all_stocks: List[Dict[str, Any]] = []
    market_files = {
        "CN": data_dir / "stock_list_a.csv",
        "HK": data_dir / "stock_list_hk.csv",
        "US": data_dir / "stock_list_us.csv",
    }

    for market_name, csv_file in market_files.items():
        if not csv_file.exists():
            print(f"[경고] 파일을 찾지 못했습니다: {csv_file}")
            continue

        print(f"  {market_name} 시장 데이터를 읽는 중: {csv_file.name}")

        try:
            file_stocks: List[Dict[str, Any]] = []
            selected_us_stocks: Dict[str, tuple[Dict[str, Any], int]] = {}

            with open(csv_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    parsed = parse_stock_row(row, market_name)
                    if not parsed:
                        continue

                    if market_name == "US":
                        delist_priority = get_us_delist_priority(row)
                        existing = selected_us_stocks.get(parsed["ts_code"])
                        if existing is None or delist_priority > existing[1]:
                            selected_us_stocks[parsed["ts_code"]] = (parsed, delist_priority)
                        continue

                    all_stocks.append(parsed)
                    file_stocks.append(parsed)

            if market_name == "US":
                file_stocks = [item for item, _priority in selected_us_stocks.values()]
                all_stocks.extend(file_stocks)

            print(f"    {market_name} 시장 읽기 완료: {len(file_stocks)}개 종목")
        except Exception as exc:
            print(f"    [오류] {csv_file.name} 읽기 실패: {exc}")

    return all_stocks


def get_us_delist_priority(row: Dict[str, str]) -> int:
    """재사용된 미국 ticker 중 어떤 행을 보존할지 결정하는 우선순위를 반환합니다."""
    delist_date = (row.get("delist_date") or "").strip()
    if not delist_date:
        return 2
    if delist_date.upper() == "NAT":
        return 1
    return 0


def load_akshare_data(logs_dir: Path) -> List[Dict[str, Any]]:
    """AkShare CSV 파일에서 주식 목록을 읽습니다."""
    csv_files = list(logs_dir.glob("stock_basic_*.csv"))

    if not csv_files:
        print("[오류] CSV 파일을 찾지 못했습니다: logs/stock_basic_*.csv")
        return []

    csv_file = sorted(csv_files)[-1]
    print(f"  AkShare 데이터를 읽는 중: {csv_file.name}")

    stocks: List[Dict[str, Any]] = []
    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts_code = row["ts_code"].strip()
            symbol = row["symbol"].strip()
            name = row["name"].strip()

            if not ts_code or not symbol or not name:
                continue

            stocks.append(
                {
                    "ts_code": ts_code,
                    "symbol": symbol,
                    "name": name,
                    "area": row.get("area", ""),
                    "industry": row.get("industry", ""),
                    "list_date": row.get("list_date", ""),
                }
            )

    print(f"    총 {len(stocks)}개 종목을 읽었습니다.")
    return stocks


def generate_pinyin(name: str) -> tuple[Optional[str], Optional[str]]:
    """주식명에서 전체 pinyin과 초성 pinyin을 생성합니다."""
    if not PYPINYIN_AVAILABLE:
        return (None, None)

    try:
        normalized_name = normalize_name_for_pinyin(name)
        pinyin_full = "".join(lazy_pinyin(normalized_name, style=Style.NORMAL))
        pinyin_abbr = "".join(lazy_pinyin(normalized_name, style=Style.FIRST_LETTER))
        return (pinyin_full, pinyin_abbr)
    except Exception as exc:
        print(f"[경고] pinyin 생성 실패({name}): {exc}")
        return (None, None)


def normalize_name_for_pinyin(name: str) -> str:
    """pinyin 색인 생성을 위해 종목명을 정규화합니다."""
    normalized = unicodedata.normalize("NFKC", name).strip()
    normalized = re.sub(r"^(?:\*?ST|N)+", "", normalized, flags=re.IGNORECASE)
    return normalized.strip() or unicodedata.normalize("NFKC", name).strip()


def extract_symbol_from_ts_code(ts_code: str, market: str) -> Optional[str]:
    """Tushare `ts_code`에서 화면 표시용 코드를 추출합니다."""
    if not ts_code:
        return None

    if market == "US":
        return ts_code

    if "." in ts_code:
        return ts_code.split(".")[0]

    return ts_code


def get_stock_name(row: Dict[str, str], market: str) -> Optional[str]:
    """시장별로 색인에 사용할 종목명을 선택합니다."""
    if market == "US":
        name = row.get("enname", "").strip()
    else:
        name = row.get("name", "").strip()
    return name or None


def parse_stock_row(row: Dict[str, str], preferred_market: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """CSV 한 행을 자동완성 색인 원천 데이터로 변환합니다."""
    ts_code = row.get("ts_code", "").strip()
    if not ts_code:
        return None

    market = determine_market(ts_code)
    if "." not in ts_code and preferred_market:
        market = preferred_market

    if market == "US":
        enname = row.get("enname", "").strip()
        if not enname or "DUMMY" in enname.upper():
            return None

    name = get_stock_name(row, market)
    if not name:
        return None

    display_code = extract_symbol_from_ts_code(ts_code, market)
    if not display_code:
        return None

    return {
        "ts_code": ts_code,
        "symbol": display_code,
        "name": name,
        "market": market,
    }


def determine_market(ts_code: str) -> str:
    """거래 코드에서 시장 코드를 추정합니다."""
    if "." in ts_code:
        suffix = ts_code.split(".")[-1]
        if suffix in ["SH", "SZ"]:
            return "CN"
        if suffix == "HK":
            return "HK"
        if suffix == "BJ":
            return "BSE"

        prefix = ts_code.split(".")[0]
        if prefix.isalpha():
            return "US"
    elif ts_code.isalpha():
        return "US"

    return "CN"


def generate_aliases(name: str, market: str) -> List[str]:
    """검색 품질을 위한 종목 별칭을 생성합니다."""
    aliases: List[str] = []

    cn_alias_map = {
        "贵州茅台": ["茅台"],
        "中国平安": ["平安"],
        "平安银行": ["平银"],
        "招商银行": ["招行"],
        "五粮液": ["五粮"],
        "宁德时代": ["宁德"],
        "比亚迪": ["比亚"],
        "工商银行": ["工行"],
        "建设银行": ["建行"],
        "农业银行": ["农行"],
        "中国银行": ["中行"],
        "交通银行": ["交行"],
        "兴业银行": ["兴业"],
        "浦发银行": ["浦发"],
        "民生银行": ["民生"],
        "中信证券": ["中信"],
        "东方财富": ["东财"],
        "海康威视": ["海康"],
        "隆基绿能": ["隆基"],
        "中国神华": ["神华"],
        "长江电力": ["长电"],
        "中国石化": ["石化"],
        "中国石油": ["石油"],
    }

    hk_alias_map = {
        "腾讯控股": ["腾讯", "Tencent"],
        "阿里巴巴-SW": ["阿里", "阿里巴巴", "Alibaba"],
        "美团-W": ["美团", "Meituan"],
        "小米集团-W": ["小米", "Xiaomi"],
        "京东集团-SW": ["京东", "JD"],
        "网易-S": ["网易", "NetEase"],
        "百度集团-SW": ["百度", "Baidu"],
        "中芯国际": ["中芯", "SMIC"],
        "中国移动": ["中移动", "China Mobile"],
        "中国海洋石油": ["中海油", "CNOOC"],
    }

    us_alias_map = {
        "Apple Inc.": ["Apple", "AAPL"],
        "Microsoft Corporation": ["Microsoft", "MSFT"],
        "Amazon.com, Inc.": ["Amazon", "AMZN"],
        "Tesla Inc.": ["Tesla", "TSLA"],
        "Meta Platforms, Inc.": ["Meta", "Facebook", "META"],
        "Alphabet Inc.": ["Google", "Alphabet", "GOOGL"],
        "NVIDIA Corporation": ["NVIDIA", "NVDA"],
        "Netflix Inc.": ["Netflix", "NFLX"],
        "Intel Corporation": ["Intel", "INTC"],
        "Advanced Micro Devices": ["AMD"],
    }

    if market == "CN":
        alias_map = cn_alias_map
    elif market == "HK":
        alias_map = hk_alias_map
    elif market == "US":
        alias_map = us_alias_map
    else:
        alias_map = {}

    if name in alias_map:
        aliases.extend(alias_map[name])

    if not aliases and market == "CN" and name.startswith("中国") and len(name) >= 3:
        aliases.append(name[-3:])
    elif not aliases and market == "HK" and len(name) >= 3:
        aliases.append(name[:3])

    return aliases


def build_stock_index(stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """원천 주식 목록을 Web 자동완성 색인 구조로 변환합니다."""
    index: List[Dict[str, Any]] = []

    for stock in stocks:
        ts_code = stock["ts_code"]
        symbol = stock["symbol"]
        name = stock["name"]
        market = stock.get("market", "CN")

        if market == "CN" and "." not in ts_code:
            market = determine_market(ts_code)

        pinyin_full, pinyin_abbr = generate_pinyin(name)
        aliases = generate_aliases(name, market)

        index.append(
            {
                "canonicalCode": ts_code,
                "displayCode": symbol,
                "nameZh": name,
                "pinyinFull": pinyin_full,
                "pinyinAbbr": pinyin_abbr,
                "aliases": aliases,
                "market": market,
                "assetType": "stock",
                "active": True,
                "popularity": 100,
            }
        )

    return index


def compress_index(index: List[Dict[str, Any]]) -> List[List[Any]]:
    """JSON 파일 크기를 줄이기 위해 색인 항목을 배열 형식으로 압축합니다."""
    compressed: List[List[Any]] = []
    for item in index:
        compressed.append(
            [
                item["canonicalCode"],
                item["displayCode"],
                item["nameZh"],
                item.get("pinyinFull"),
                item.get("pinyinAbbr"),
                item.get("aliases", []),
                item["market"],
                item["assetType"],
                item["active"],
                item.get("popularity", 0),
            ]
        )
    return compressed


def main() -> int:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="CSV에서 주식 자동완성 색인을 생성합니다.")
    parser.add_argument(
        "--source",
        choices=["tushare", "akshare"],
        default="tushare",
        help="데이터 소스 선택. 기본값: tushare",
    )
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="검증만 수행하고 파일은 쓰지 않습니다.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("주식 색인 생성 도구(CSV 입력)")
    print("=" * 60)
    print(f"데이터 소스: {args.source}")

    print("\n[1/5] CSV 데이터 읽기...")
    if args.source == "tushare":
        data_dir = Path(__file__).parent.parent / "data"
        stocks = load_tushare_data(data_dir)
    elif args.source == "akshare":
        logs_dir = Path(__file__).parent.parent / "logs"
        stocks = load_akshare_data(logs_dir)
    else:
        print(f"[오류] 지원하지 않는 데이터 소스: {args.source}")
        return 1

    if not stocks:
        print("[오류] 읽어온 주식 데이터가 없습니다.")
        return 1

    print(f"      총 {len(stocks)}개 종목")

    if not PYPINYIN_AVAILABLE:
        print("\n[안내] pypinyin을 설치하면 중국어 종목명 pinyin 검색 품질이 좋아집니다.")
        print("       pip install pypinyin")

    print("\n[2/5] 색인 데이터 생성...")
    index = build_stock_index(stocks)

    output_path = Path(__file__).parent.parent / "apps" / "dsa-web" / "public" / "stocks.index.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n[3/5] 색인 데이터 압축...")
    compressed = compress_index(index)

    if args.test:
        print("\n[4/5] 테스트 모드: 파일 쓰기 건너뜀")
        print(f"      출력 경로: {output_path}")

        print("\n[5/5] 데이터 검증...")
        print(f"      압축 전: {len(index)}개 항목")
        print(f"      압축 후: {len(compressed)}개 항목")

        if compressed:
            print("\n      앞 5개 예시:")
            for i, item in enumerate(compressed[:5]):
                print(f"        {i + 1}. {item}")
    else:
        print(f"\n[4/5] 파일 쓰기: {output_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("[\n")
            for i, item in enumerate(compressed):
                json.dump(item, f, ensure_ascii=False, separators=(",", ":"))
                f.write(",\n" if i < len(compressed) - 1 else "\n")
            f.write("]\n")

        file_size = output_path.stat().st_size
        print(f"      파일 크기: {file_size / 1024:.2f} KB")

        print("\n[5/5] 파일 검증...")
        with open(output_path, "r", encoding="utf-8") as f:
            test_data = json.load(f)
        print(f"      검증 통과: {len(test_data)}개 항목")

    market_stats: Dict[str, int] = {}
    for item in index:
        market = item["market"]
        market_stats[market] = market_stats.get(market, 0) + 1

    print(f"\n{'=' * 60}")
    print("생성 완료. 시장 분포:")
    for market, count in sorted(market_stats.items()):
        print(f"  - {market}: {count}개")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
