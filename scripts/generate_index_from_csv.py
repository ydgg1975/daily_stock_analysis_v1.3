#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Stock Index from CSV File

Input:
  - Tushare format: data/stock_list_{a,hk,us}.csv
  - AkShare format: logs/stock_basic_*.csv

Output: apps/dsa-web/public/stocks.index.json

Usage:
    python3 scripts/generate_index_from_csv.py              # morenshiyong Tushare
    python3 scripts/generate_index_from_csv.py --source akshare
    python3 scripts/generate_index_from_csv.py --test       # ceshimoshi
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add the project root to sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pypinyin import lazy_pinyin, Style
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False
    print("[Warning] pypinyin not available, pinyin fields will be empty")
    print("[Info] Install with: pip install pypinyin")


def load_csv_data(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Load stock data from AkShare format CSV file

    Args:
        csv_path: CSV file path

    Returns:
        List of stock data
    """
    stocks = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts_code = row['ts_code'].strip()
            symbol = row['symbol'].strip()
            name = row['name'].strip()

            # Skip invalid rows.
            if not ts_code or not symbol or not name:
                continue

            stocks.append({
                'ts_code': ts_code,
                'symbol': symbol,
                'name': name,
                'area': row.get('area', ''),
                'industry': row.get('industry', ''),
                'list_date': row.get('list_date', ''),
            })

    return stocks


def load_tushare_data(data_dir: Path) -> List[Dict[str, Any]]:
    """
    cong Tushare CSV wenjianjiazaisangeshichangdegupiaoshuju

    Args:
        data_dir: shujumululujing

    Returns:
        hebinghoudegupiaoliebiao
    """
    all_stocks = []
    market_files = {
        'CN': data_dir / 'stock_list_a.csv',
        'HK': data_dir / 'stock_list_hk.csv',
        'US': data_dir / 'stock_list_us.csv',
    }

    for market_name, csv_file in market_files.items():
        if not csv_file.exists():
            print(f"[Warning] weizhaodaowenjian：{csv_file}")
            continue

        print(f"  zhengzaiduqu {market_name} shichangshuju：{csv_file.name}")

        try:
            file_stocks = []
            selected_us_stocks: Dict[str, tuple[Dict[str, Any], int]] = {}
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # chuanrushichangcanshuyiyouhuapanduan（duiyuteshugeshiru DUMMY）
                    parsed = parse_stock_row(row, market_name)
                    if not parsed:
                        continue

                    if market_name == 'US':
                        # Tushare us_basic may include historical rows for a reused ticker.
                        # Keep one deterministic row per ts_code before generating the index.
                        delist_priority = get_us_delist_priority(row)
                        existing = selected_us_stocks.get(parsed['ts_code'])
                        if existing is None or delist_priority > existing[1]:
                            selected_us_stocks[parsed['ts_code']] = (parsed, delist_priority)
                        continue

                    if parsed:
                        all_stocks.append(parsed)
                        file_stocks.append(parsed)

            if market_name == 'US':
                file_stocks = [item for item, _priority in selected_us_stocks.values()]
                all_stocks.extend(file_stocks)

            print(f"    ✓ {market_name} shichangduquwancheng：{len(file_stocks)} zhigupiao")

        except Exception as e:
            print(f"    [Error] duqu {csv_file.name} shibai：{e}")

    return all_stocks


def get_us_delist_priority(row: Dict[str, str]) -> int:
    """
    weifuyong ticker demeigujilushengchengquzhongyouxianji。

    Tushare us_basic daochude delist_date duidangqianjilubingbuzongshiwending：
    - kongzifuchuantongchangbiaoshidangqianrengzaishiyongde ticker
    - ``NaT`` duojianyulishijiluhuoriqizhanweizhi
    - shijiriqibiaoshimingquetuishi

    yinciqianzhiquzhongshiyouxianxuanze：
    1. delist_date weikong
    2. delist_date wei NaT
    3. delist_date weishijiriqi

    tongyouxianjishibaoliu CSV zhongzuixianchuxiandejilu，bimianzaixinxibuzushisuiyiqiehuanmingcheng。
    """
    delist_date = (row.get('delist_date') or '').strip()
    if not delist_date:
        return 2
    if delist_date.upper() == 'NAT':
        return 1
    return 0


def load_akshare_data(logs_dir: Path) -> List[Dict[str, Any]]:
    """
    cong AkShare CSV wenjianjiazaigupiaoshuju

    Args:
        logs_dir: rizhimululujing

    Returns:
        gupiaoliebiao
    """
    csv_files = list(logs_dir.glob("stock_basic_*.csv"))

    if not csv_files:
        print("[Error] weizhaodao CSV wenjian：logs/stock_basic_*.csv")
        return []

    # shiyongzuixinde CSV wenjian
    csv_file = sorted(csv_files)[-1]
    print(f"  zhengzaiduqu AkShare shuju：{csv_file.name}")

    stocks = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts_code = row['ts_code'].strip()
            symbol = row['symbol'].strip()
            name = row['name'].strip()

            # Skip invalid rows.
            if not ts_code or not symbol or not name:
                continue

            stocks.append({
                'ts_code': ts_code,
                'symbol': symbol,
                'name': name,
                'area': row.get('area', ''),
                'industry': row.get('industry', ''),
                'list_date': row.get('list_date', ''),
            })

    print(f"    ✓ gongduqu {len(stocks)} zhigupiao")
    return stocks


def generate_pinyin(name: str) -> tuple:
    """
    Generate pinyin for stock name

    Args:
        name: Stock name

    Returns:
        Tuple of (pinyin_full, pinyin_abbr)
    """
    if not PYPINYIN_AVAILABLE:
        return (None, None)

    try:
        normalized_name = normalize_name_for_pinyin(name)

        # Full pinyin spelling.
        py_full = lazy_pinyin(normalized_name, style=Style.NORMAL)
        pinyin_full = ''.join(py_full)

        # Pinyin abbreviation.
        py_abbr = lazy_pinyin(normalized_name, style=Style.FIRST_LETTER)
        pinyin_abbr = ''.join(py_abbr)

        return (pinyin_full, pinyin_abbr)
    except Exception as e:
        print(f"[Warning] Failed to generate pinyin for {name}: {e}")
        return (None, None)


def normalize_name_for_pinyin(name: str) -> str:
    """
    Normalize stock name to avoid special prefixes and full-width characters polluting pinyin index

    Args:
        name: Original stock name

    Returns:
        Normalized name for pinyin generation
    """
    normalized = unicodedata.normalize('NFKC', name).strip()

    # Strip common A-share prefixes while preserving the core name.
    normalized = re.sub(r'^(?:\*?ST|N)+', '', normalized, flags=re.IGNORECASE)

    return normalized.strip() or unicodedata.normalize('NFKC', name).strip()


def extract_symbol_from_ts_code(ts_code: str, market: str) -> Optional[str]:
    """
    cong ts_code tiqu displayCode

    - Agu：000001.SZ → 000001
    - ganggu：00700.HK → 00700
    - meigu：AAPL → AAPL

    Args:
        ts_code: TSdaima
        market: shichangdaima

    Returns:
        displayCode huo None
    """
    if not ts_code:
        return None

    if market == 'US':
        # meiguwuhouzhui，zhijiefanhui
        return ts_code

    if '.' in ts_code:
        # Aguheganggu：quchuhouzhui
        return ts_code.split('.')[0]

    return ts_code


def get_stock_name(row: Dict[str, str], market: str) -> Optional[str]:
    """
    huoqugupiaomingcheng

    - Agu/ganggu：shiyong name ziduan
    - meigu：shiyong enname ziduan（yingwenmingcheng）

    Args:
        row: CSV xingshuju
        market: shichangdaima

    Returns:
        gupiaomingchenghuo None
    """
    if market == 'US':
        # meigushiyongyingwenmingcheng
        name = row.get('enname', '').strip()
        return name if name else None
    else:
        # Aguheganggushiyongzhongwenmingcheng
        name = row.get('name', '').strip()
        return name if name else None


def parse_stock_row(row: Dict[str, str], preferred_market: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    jiexidanxinggupiaoshuju

    - meigu DUMMY guolv（yangeguolv）
    - kongzhijiaoyan
    - zidongpanduanshichangleixing（dangwufapanduanshishiyong preferred_market）
    - fanhuitongyigeshidezidian

    Args:
        row: CSV xingshuju
        preferred_market: dang ts_code wufapanduanshichangshishiyong（rumeigu DUMMY jilu）

    Returns:
        jiexihoudegupiaozidian，wuxiaoshujufanhui None
    """
    ts_code = row.get('ts_code', '').strip()

    if not ts_code:
        return None

    # zidongpanduanshichangleixing
    market = determine_market(ts_code)

    # ruguo ts_code meiyouhouzhui（wufazhunquepanduan），qietigongle preferred_market，zeshiyongta
    # zhezhuyaoyongyuchulimeigudeteshugeshi（ru DUMMY jilu）
    if '.' not in ts_code and preferred_market:
        market = preferred_market

    # meiguteshuchuli：yangeguolv DUMMY jilu
    if market == 'US':
        enname = row.get('enname', '').strip()
        if not enname or 'DUMMY' in enname.upper():
            return None

    # huoqugupiaomingcheng
    name = get_stock_name(row, market)
    if not name:
        return None

    # tiqu displayCode
    display_code = extract_symbol_from_ts_code(ts_code, market)
    if not display_code:
        return None

    return {
        'ts_code': ts_code,
        'symbol': display_code,
        'name': name,
        'market': market,
    }


def determine_market(ts_code: str) -> str:
    """
    Determine market based on code

    Args:
        ts_code: Trading code (e.g., 000001.SZ, AAPL, BRK.B, GOOG.A)

    Returns:
        Market code (CN, HK, US, BSE)
    """
    if '.' in ts_code:
        # youhouzhuideqingkuang
        suffix = ts_code.split('.')[1]
        # jianchashifouweizhongguoshichanghouzhui
        if suffix in ['SH', 'SZ']:
            return 'CN'
        elif suffix == 'HK':
            return 'HK'
        elif suffix == 'BJ':
            return 'BSE'
        # youhouzhuidanbushizhongguoshichanghouzhui，jianchashifouweimeigu
        # meigukenengyoudianhaohouzhui（ru BRK.B, GOOG.A, AAPL.U）
        prefix = ts_code.split('.')[0]
        if prefix.isalpha():
            return 'US'
    else:
        # wuhouzhuideqingkuang
        # chunzimudaimaweimeigu
        if ts_code.isalpha():
            return 'US'

    # morenwei Agu
    return 'CN'


def generate_aliases(name: str, market: str) -> List[str]:
    """
    Generate stock aliases

    Args:
        name: Stock name
        market: Market code

    Returns:
        List of aliases
    """
    aliases = []

    # Aguchangjianbieming
    cn_alias_map = {
        'guizhoumaotai': ['maotai'],
        'zhongguopingan': ['pingan'],
        'pinganyinhang': ['pingyin'],
        'zhaoshangyinhang': ['zhaohang'],
        'wuliangye': ['wuliang'],
        'ningdeshidai': ['ningde'],
        'biyadi': ['biya'],
        'gongshangyinhang': ['gonghang'],
        'jiansheyinhang': ['jianhang'],
        'nongyeyinhang': ['nonghang'],
        'zhongguoyinhang': ['zhonghang'],
        'jiaotongyinhang': ['jiaohang'],
        'xingyeyinhang': ['xingye'],
        'pufayinhang': ['pufa'],
        'minshengyinhang': ['minsheng'],
        'zhongxinzhengquan': ['zhongxin'],
        'dongfangcaifu': ['dongcai'],
        'haikangweishi': ['haikang'],
        'longjilvneng': ['longji'],
        'zhongguoshenhua': ['shenhua'],
        'changjiangdianli': ['zhangdian'],
        'zhongguoshihua': ['shihua'],
        'zhongguoshiyou': ['shiyou'],
    }

    # gangguchangjianbieming
    hk_alias_map = {
        'tengxunkonggu': ['tengxun', 'Tencent'],
        'alibaba-SW': ['ali', 'alibaba', 'Alibaba'],
        'meituan-W': ['meituan', 'Meituan'],
        'xiaomijituan-W': ['xiaomi', 'Xiaomi'],
        'jingdongjituan-SW': ['jingdong', 'JD'],
        'wangyi-S': ['wangyi', 'NetEase'],
        'baidujituan-SW': ['baidu', 'Baidu'],
        'zhongxinguoji': ['zhongxin', 'SMIC'],
        'zhongguoyidong': ['zhongyidong', 'China Mobile'],
        'zhongguohaiyangshiyou': ['zhonghaiyou', 'CNOOC'],
    }

    # meiguchangjianbieming
    us_alias_map = {
        'Apple Inc.': ['Apple', 'AAPL'],
        'Microsoft Corporation': ['Microsoft', 'MSFT'],
        'Amazon.com, Inc.': ['Amazon', 'AMZN'],
        'Tesla Inc.': ['Tesla', 'TSLA'],
        'Meta Platforms, Inc.': ['Meta', 'Facebook', 'META'],
        'Alphabet Inc.': ['Google', 'Alphabet', 'GOOGL'],
        'NVIDIA Corporation': ['NVIDIA', 'NVDA'],
        'Netflix Inc.': ['Netflix', 'NFLX'],
        'Intel Corporation': ['Intel', 'INTC'],
        'Advanced Micro Devices': ['AMD', 'AMD'],
    }

    # genjushichangxuanzeyingshebiao
    if market == 'CN':
        alias_map = cn_alias_map
    elif market == 'HK':
        alias_map = hk_alias_map
    elif market == 'US':
        alias_map = us_alias_map
    else:
        alias_map = {}

    if name in alias_map:
        aliases.extend(alias_map[name])

    return aliases


def build_stock_index(stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build the stock index.

    Args:
        stocks: Raw stock rows（yibaohan market ziduan）

    Returns:
        Stock index entries
    """
    index = []

    for stock in stocks:
        ts_code = stock['ts_code']
        symbol = stock['symbol']
        name = stock['name']
        market = stock.get('market', 'CN')  # youxianshiyongyijiexideshichang，fouzecong ts_code panduan

        # ruguomeiyou market ziduan，cong ts_code panduan
        if market == 'CN' and '.' not in ts_code:
            market = determine_market(ts_code)

        # Generate pinyin fields.
        pinyin_full, pinyin_abbr = generate_pinyin(name)

        # Generate aliases.
        aliases = generate_aliases(name, market)

        index.append({
            "canonicalCode": ts_code,    # Example: 000001.SZ, AAPL
            "displayCode": symbol,       # Example: 000001, AAPL
            "nameZh": name,
            "pinyinFull": pinyin_full,
            "pinyinAbbr": pinyin_abbr,
            "aliases": aliases,
            "market": market,
            "assetType": "stock",
            "active": True,
            "popularity": 100,
        })

    return index


def compress_index(index: List[Dict[str, Any]]) -> List[List]:
    """
    yasuosuoyinweishuzugeshiyijianshaowenjiandaxiao

    Args:
        index: yuanshisuoyin

    Returns:
        yasuohoudesuoyin
    """
    compressed = []
    for item in index:
        compressed.append([
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
        ])
    return compressed


def main():
    """zhuhanshu"""
    parser = argparse.ArgumentParser(description='cong CSV shengchenggupiaozidongbuquansuoyin')
    parser.add_argument(
        '--source',
        choices=['tushare', 'akshare'],
        default='tushare',
        help='shujuyuanxuanze（moren: tushare）'
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='ceshimoshi：zhiyanzhengbuxieruwenjian'
    )
    args = parser.parse_args()

    print("=" * 60)
    print("gupiaosuoyinshengchenggongju（cong CSV）")
    print("=" * 60)
    print(f"shujuyuan：{args.source}")

    # jiazaishuju
    print("\n[1/5] duqu CSV shuju...")
    if args.source == 'tushare':
        data_dir = Path(__file__).parent.parent / 'data'
        stocks = load_tushare_data(data_dir)
    elif args.source == 'akshare':
        logs_dir = Path(__file__).parent.parent / 'logs'
        stocks = load_akshare_data(logs_dir)
    else:
        print(f"[Error] buzhichideshujuyuan：{args.source}")
        return 1

    if not stocks:
        print("[Error] weijiazaidaorenhegupiaoshuju")
        return 1

    print(f"      gongduqu {len(stocks)} zhigupiao")

    # shengchengpinyintishi
    if not PYPINYIN_AVAILABLE:
        print("\n[tishi] anzhuang pypinyin kehuodepinyinsousuogongneng：")
        print("       pip install pypinyin")

    print("\n[2/5] shengchengsuoyinshuju...")
    index = build_stock_index(stocks)

    # shuchulujing
    output_path = (
        Path(__file__).parent.parent / "apps" / "dsa-web" / "public" / "stocks.index.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n[3/5] yasuosuoyinshuju...")
    compressed = compress_index(index)

    if args.test:
        print("\n[4/5] ceshimoshi：tiaoguoxieruwenjian")
        print(f"      shuchulujing：{output_path}")

        # yanzhengshuju
        print("\n[5/5] yanzhengshuju...")
        print(f"      yasuoqian：{len(index)} tiaojilu")
        print(f"      yasuohou：{len(compressed)} tiaojilu")

        # xianshiqian5tiaoshili
        if compressed:
            print("\n      qian5tiaoshili：")
            for i, item in enumerate(compressed[:5]):
                print(f"        {i + 1}. {item}")
    else:
        print("\n[4/5] xieruwenjian：{output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('[\n')
            for i, item in enumerate(compressed):
                json.dump(item, f, ensure_ascii=False, separators=(',', ':'))
                if i < len(compressed) - 1:
                    f.write(',\n')
                else:
                    f.write('\n')
            f.write(']\n')

        file_size = output_path.stat().st_size
        print(f"      wenjiandaxiao：{file_size / 1024:.2f} KB")

        # yanzhengwenjian
        print("\n[5/5] yanzhengwenjian...")
        with open(output_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
            print(f"      yanzhengtongguo：{len(test_data)} tiaojilu")

    # tongjixinxi
    market_stats = {}
    for item in index:
        market = item['market']
        market_stats[market] = market_stats.get(market, 0) + 1

    print(f"\n{'=' * 60}")
    print("shengchengwancheng！shichangfenbu：")
    for market, count in sorted(market_stats.items()):
        print(f"  - {market}: {count} zhi")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
