#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Index Generation Script

Generate stock index file for frontend autocomplete functionality
Output to apps/dsa-web/public/stocks.index.json

Two-phase strategy:
1. MVP: Use existing STOCK_NAME_MAP
2. Future: Combine with AkShare for complete list

Usage:
    python3 scripts/generate_stock_index.py
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Dict, Any

# Add the project root to sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pypinyin import lazy_pinyin
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False
    print("[Warning] pypinyin not available, pinyin fields will be empty")
    print("[Info] Install with: pip install pypinyin")


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


def generate_stock_index_from_map() -> List[Dict[str, Any]]:
    """
    Generate index from STOCK_NAME_MAP (MVP)

    Returns:
        List of stock index
    """
    from src.data.stock_mapping import STOCK_NAME_MAP

    index = []

    for code, name in STOCK_NAME_MAP.items():
        # Generate pinyin fields.
        pinyin_full = None
        pinyin_abbr = None
        if PYPINYIN_AVAILABLE:
            try:
                normalized_name = normalize_name_for_pinyin(name)
                py = lazy_pinyin(normalized_name)
                pinyin_full = ''.join(py)
                pinyin_abbr = ''.join([p[0] for p in py])
            except Exception:
                pass

        # Determine market and asset type.
        market, asset_type = determine_market_and_type(code)

        # Generate short aliases.
        aliases = generate_aliases(name)

        index.append({
            "canonicalCode": build_canonical_code(code, market),
            "displayCode": code,
            "nameZh": name,
            "pinyinFull": pinyin_full,
            "pinyinAbbr": pinyin_abbr,
            "aliases": aliases,
            "market": market,
            "assetType": asset_type,
            "active": True,
            "popularity": 100,  # Default popularity
        })

    return index


def determine_market_and_type(code: str) -> tuple:
    """
    Determine market and asset type based on stock code

    Args:
        code: Stock code

    Returns:
        Tuple of (market, asset_type)
    """
    if code.isdigit():
        if len(code) == 5:
            # Five digits: likely HK stock or legacy B-share.
            if code.startswith('0') or code.startswith('2'):
                return 'HK', 'stock'
            return 'CN', 'stock'
        elif len(code) == 6:
            # Six digits: A-share universe.
            if code.startswith('6'):
                return 'CN', 'stock'  # Shanghai
            elif code.startswith(('0', '2', '3')):
                return 'CN', 'stock'  # Shenzhen
            elif code.startswith('8'):
                return 'BSE', 'stock'  # Beijing Stock Exchange
            return 'CN', 'stock'
        elif len(code) == 4:
            # Four digits: likely a US symbol or special market code.
            return 'US', 'stock'

    # zimudaima，meiguhuoqita
    return 'US', 'stock'


def market_to_suffix(market: str) -> str:
    """
    Convert market code to suffix

    Args:
        market: Market code

    Returns:
        Market suffix
    """
    suffix_map = {
        'CN': 'SH',  # jianhuachuli，morenshanghai
        'HK': 'HK',
        'US': 'US',
        'INDEX': 'SH',
        'ETF': 'SH',
        'BSE': 'BJ',
    }
    return suffix_map.get(market, 'SH')


def build_canonical_code(code: str, market: str) -> str:
    """
    Generate canonical stock code based on code and market.

    A-shares need to distinguish between SH/SZ/BJ, cannot rely solely on the general CN -> SH mapping.
    """
    if market == 'CN' and code.isdigit() and len(code) == 6:
        # Shanghai Stock Exchange (SH)
        # 60xxxx: Main board, 688xxx: STAR market, 900xxx: B-shares
        if code.startswith(('6', '900')):
            return f"{code}.SH"

        # Shenzhen Stock Exchange (SZ)
        # 00xxxx: Main board, 30xxxx: ChiNext, 20xxxx: B-shares
        if code.startswith(('0', '2', '3')):
            return f"{code}.SZ"

        # Beijing Stock Exchange (BJ)
        # 920xxx: New codes and migrated stock codes after April 2024
        # 43xxxx, 83xxxx, 87xxxx, 88xxxx: Historical/Temporary codes
        # 81xxxx, 82xxxx: Convertible bonds/Preferred stocks
        if code.startswith(('920', '43', '83', '87', '88', '81', '82')):
            return f"{code}.BJ"

    if market == 'BSE' and code.isdigit() and len(code) == 6:
        return f"{code}.BJ"

    return f"{code}.{market_to_suffix(market)}"


def generate_aliases(name: str) -> List[str]:
    """
    Generate stock aliases (abbreviations)

    Args:
        name: Full stock name

    Returns:
        List of aliases
    """
    aliases = []

    # changjianjianchengyingshe
    alias_map = {
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

    if name in alias_map:
        aliases.extend(alias_map[name])

    return aliases


def compress_index(index: List[Dict[str, Any]]) -> List[List]:
    """
    Compress index to array format to reduce file size

    Args:
        index: Original index

    Returns:
        Compressed index
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
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Generate the stock autocomplete index file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/generate_stock_index.py              # Generate index file
  python3 scripts/generate_stock_index.py --test       # Validate only, do not write
  python3 scripts/generate_stock_index.py --test -v    # Validate and show a preview
        """
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Validate data without writing the index file'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show the first 10 generated records'
    )
    args = parser.parse_args()

    print("Generating stock index...")

    index = generate_stock_index_from_map()
    print(f"Generated {len(index)} index records")

    market_stats = {}
    for item in index:
        market = item['market']
        market_stats[market] = market_stats.get(market, 0) + 1
    print(f"Market distribution: {market_stats}")

    compressed = compress_index(index)

    if args.test:
        print("\n[Test mode] No file will be written")
        print(f"Estimated file size: {len(json.dumps(compressed, ensure_ascii=False, separators=(',', ':'))) / 1024:.2f} KB")

        if args.verbose:
            print("\nFirst 10 records:")
            for i, item in enumerate(index[:10]):
                print(f"  {i + 1}. {item['canonicalCode']} - {item['nameZh']} ({item['market']})")

        print("\nOK: data format is valid")
        return 0

    output_path = Path(__file__).parent.parent / "apps" / "dsa-web" / "public" / "stocks.index.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

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
    print(f"Index generated: {output_path}")
    print(f"File size: {file_size / 1024:.2f} KB")

    with open(output_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
        print(f"Validation passed: {len(test_data)} records")

    return 0


if __name__ == "__main__":
    sys.exit(main())
