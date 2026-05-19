#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test generate_index_from_csv.py
"""

import csv
import json
import pytest
from pathlib import Path
from typing import Dict, List

# Add scripts directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from generate_index_from_csv import (
    extract_symbol_from_ts_code,
    get_stock_name,
    get_us_delist_priority,
    parse_stock_row,
    determine_market,
    generate_aliases,
    normalize_name_for_pinyin,
    generate_pinyin,
    compress_index,
    build_stock_index,
    load_tushare_data,
    load_akshare_data,
)


class TestExtractSymbol:
    """ceshi Symbol tiquhanshu"""

    def test_a_stock_sz(self):
        """ceshi Agushenzhen"""
        result = extract_symbol_from_ts_code("000001.SZ", "CN")
        assert result == "000001"

    def test_a_stock_sh(self):
        """ceshi Agushanghai"""
        result = extract_symbol_from_ts_code("600519.SH", "CN")
        assert result == "600519"

    def test_hk_stock(self):
        """ceshiganggu"""
        result = extract_symbol_from_ts_code("00700.HK", "HK")
        assert result == "00700"

    def test_us_stock(self):
        """ceshimeigu"""
        result = extract_symbol_from_ts_code("AAPL", "US")
        assert result == "AAPL"

    def test_empty_ts_code(self):
        """ceshikong ts_code"""
        result = extract_symbol_from_ts_code("", "CN")
        assert result is None

    def test_none_ts_code(self):
        """ceshi None ts_code"""
        result = extract_symbol_from_ts_code(None, "CN")
        assert result is None


class TestDetermineMarket:
    """ceshishichangpanduanhanshu"""

    def test_a_stock_sz(self):
        """ceshi Agushenzhen"""
        result = determine_market("000001.SZ")
        assert result == "CN"

    def test_a_stock_sh(self):
        """ceshi Agushanghai"""
        result = determine_market("600519.SH")
        assert result == "CN"

    def test_hk_stock(self):
        """ceshiganggu"""
        result = determine_market("00700.HK")
        assert result == "HK"

    def test_bse_stock(self):
        """ceshibeijiaosuo"""
        result = determine_market("832566.BJ")
        assert result == "BSE"

    def test_us_stock(self):
        """ceshimeigu"""
        result = determine_market("AAPL")
        assert result == "US"

    def test_us_stock_tesla(self):
        """ceshimeigutesila"""
        result = determine_market("TSLA")
        assert result == "US"

    def test_us_stock_with_dot_suffix(self):
        """ceshimeigudaidianhaohouzhui（BRK.B）"""
        result = determine_market("BRK.B")
        assert result == "US"

    def test_us_stock_class_a(self):
        """ceshimeigu A leigu（GOOG.A）"""
        result = determine_market("GOOG.A")
        assert result == "US"

    def test_us_stock_units(self):
        """ceshimeigu Unit（AAPL.U）"""
        result = determine_market("AAPL.U")
        assert result == "US"


class TestGetStockName:
    """ceshigupiaomingchenghuoquhanshu"""

    def test_cn_stock_name(self):
        """ceshi Agushiyong name ziduan"""
        row = {'name': 'pinganyinhang', 'enname': 'Ping An Bank'}
        result = get_stock_name(row, 'CN')
        assert result == 'pinganyinhang'

    def test_hk_stock_name(self):
        """ceshiganggushiyong name ziduan"""
        row = {'name': 'tengxunkonggu', 'enname': 'Tencent'}
        result = get_stock_name(row, 'HK')
        assert result == 'tengxunkonggu'

    def test_us_stock_name(self):
        """ceshimeigushiyong enname ziduan"""
        row = {'name': 'pingguo', 'enname': 'Apple Inc.'}
        result = get_stock_name(row, 'US')
        assert result == 'Apple Inc.'

    def test_empty_name(self):
        """ceshikongmingcheng"""
        row = {'name': '', 'enname': ''}
        result = get_stock_name(row, 'CN')
        assert result is None


class TestDataCleaning:
    """ceshishujuqingxiluoji"""

    def test_valid_cn_stock(self):
        """ceshiyouxiaode Agujilu"""
        row = {
            'ts_code': '000001.SZ',
            'symbol': '000001',
            'name': 'pinganyinhang'
        }
        result = parse_stock_row(row, 'CN')
        assert result is not None
        assert result['ts_code'] == '000001.SZ'
        assert result['symbol'] == '000001'
        assert result['name'] == 'pinganyinhang'
        assert result['market'] == 'CN'

    def test_valid_hk_stock(self):
        """ceshiyouxiaodeganggujilu"""
        row = {
            'ts_code': '00700.HK',
            'name': 'tengxunkonggu',
            'enname': 'Tencent'
        }
        result = parse_stock_row(row, 'HK')
        assert result is not None
        assert result['ts_code'] == '00700.HK'
        assert result['symbol'] == '00700'
        assert result['name'] == 'tengxunkonggu'
        assert result['market'] == 'HK'

    def test_valid_us_stock(self):
        """ceshiyouxiaodemeigujilu"""
        row = {
            'ts_code': 'AAPL',
            'name': 'pingguo',
            'enname': 'Apple Inc.'
        }
        result = parse_stock_row(row, 'US')
        assert result is not None
        assert result['ts_code'] == 'AAPL'
        assert result['symbol'] == 'AAPL'
        assert result['name'] == 'Apple Inc.'
        assert result['market'] == 'US'

    def test_valid_us_stock_with_dot_suffix(self):
        """ceshiyouxiaodemeigujilu（daidianhaohouzhui，ru BRK.B）"""
        row = {
            'ts_code': 'BRK.B',
            'name': '',
            'enname': "BERKSHIRE HATHAWAY 'B'"
        }
        result = parse_stock_row(row, None)
        assert result is not None
        assert result['ts_code'] == 'BRK.B'
        assert result['symbol'] == 'BRK.B'
        assert result['name'] == "BERKSHIRE HATHAWAY 'B'"
        assert result['market'] == 'US'

    def test_us_dummy_filtered(self):
        """ceshimeigu DUMMY jilubeiguolv"""
        row = {
            'ts_code': 'DUMMY001',
            'name': 'ceshi',
            'enname': 'DUMMY Test Stock'
        }
        result = parse_stock_row(row, 'US')
        assert result is None

    def test_us_dummy_case_insensitive(self):
        """ceshi DUMMY guolvbuqufendaxiaoxie"""
        row = {
            'ts_code': 'DUMMY002',
            'name': 'ceshi',
            'enname': 'dummy test stock'
        }
        result = parse_stock_row(row, 'US')
        assert result is None

    def test_empty_ts_code(self):
        """ceshikong ts_code beiguolv"""
        row = {
            'ts_code': '',
            'symbol': '000001',
            'name': 'pinganyinhang'
        }
        result = parse_stock_row(row, 'CN')
        assert result is None

    def test_empty_name(self):
        """ceshikongmingchengbeiguolv"""
        row = {
            'ts_code': '000001.SZ',
            'symbol': '000001',
            'name': ''
        }
        result = parse_stock_row(row, 'CN')
        assert result is None

    def test_us_empty_enname(self):
        """ceshimeigukong enname beiguolv"""
        row = {
            'ts_code': 'AAPL',
            'name': 'pingguo',
            'enname': ''
        }
        result = parse_stock_row(row, 'US')
        assert result is None

    def test_us_delist_priority_prefers_blank_over_nat(self):
        """ceshimeiguquzhongyouxianji：kong delist_date youxianyu NaT"""
        assert get_us_delist_priority({'delist_date': ''}) == 2
        assert get_us_delist_priority({'delist_date': 'NaT'}) == 1
        assert get_us_delist_priority({'delist_date': '20250131'}) == 0


class TestAliases:
    """ceshibiemingshengchenghanshu"""

    def test_cn_aliases(self):
        """ceshi Agubieming"""
        result = generate_aliases('guizhoumaotai', 'CN')
        assert 'maotai' in result

    def test_hk_aliases(self):
        """ceshiganggubieming"""
        result = generate_aliases('tengxunkonggu', 'HK')
        assert 'tengxun' in result or 'Tencent' in result

    def test_us_aliases(self):
        """ceshimeigubieming"""
        result = generate_aliases('Apple Inc.', 'US')
        assert 'Apple' in result or 'AAPL' in result

    def test_no_aliases(self):
        """ceshiwubiemingdeqingkuang"""
        result = generate_aliases('weizhigupiao', 'CN')
        assert result == []


class TestOutputFormat:
    """ceshishuchugeshi"""

    def test_compress_index_field_order(self):
        """ceshiyasuogeshideziduanshunxu"""
        index = [{
            "canonicalCode": "000001.SZ",
            "displayCode": "000001",
            "nameZh": "pinganyinhang",
            "pinyinFull": "pinganyinhang",
            "pinyinAbbr": "pyyh",
            "aliases": ["pingyin"],
            "market": "CN",
            "assetType": "stock",
            "active": True,
            "popularity": 100,
        }]

        compressed = compress_index(index)

        assert len(compressed) == 1
        item = compressed[0]

        # yanzhengziduanshunxu
        assert item[0] == "000001.SZ"      # canonicalCode
        assert item[1] == "000001"         # displayCode
        assert item[2] == "pinganyinhang"       # nameZh
        assert item[3] == "pinganyinhang"  # pinyinFull
        assert item[4] == "pyyh"           # pinyinAbbr
        assert item[5] == ["pingyin"]         # aliases
        assert item[6] == "CN"             # market
        assert item[7] == "stock"          # assetType
        assert item[8] == True             # active
        assert item[9] == 100              # popularity

    def test_compress_index_field_count(self):
        """ceshiyasuogeshideziduanshuliang"""
        index = [{
            "canonicalCode": "AAPL",
            "displayCode": "AAPL",
            "nameZh": "Apple Inc.",
            "pinyinFull": None,
            "pinyinAbbr": None,
            "aliases": [],
            "market": "US",
            "assetType": "stock",
            "active": True,
            "popularity": 100,
        }]

        compressed = compress_index(index)
        assert len(compressed[0]) == 10  # 10geziduan

    def test_json_serialization(self):
        """ceshi JSON xuliehua"""
        index = [{
            "canonicalCode": "00700.HK",
            "displayCode": "00700",
            "nameZh": "tengxunkonggu",
            "pinyinFull": "xunxiongkonggu",
            "pinyinAbbr": "xxkg",
            "aliases": ["tengxun"],
            "market": "HK",
            "assetType": "stock",
            "active": True,
            "popularity": 100,
        }]

        compressed = compress_index(index)

        # yinggainengchenggongxuliehuawei JSON
        json_str = json.dumps(compressed, ensure_ascii=False)
        assert json_str is not None

        # yinggainengchenggongfanxuliehua
        loaded = json.loads(json_str)
        assert len(loaded) == 1


class TestIntegration:
    """jichengceshi"""

    def test_full_workflow_tushare(self, tmp_path):
        """ceshiwanzhengde Tushare gongzuoliu"""
        # chuangjianceshi CSV wenjian
        a_csv = tmp_path / 'stock_list_a.csv'
        with open(a_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'symbol', 'name'])
            writer.writeheader()
            writer.writerow({
                'ts_code': '000001.SZ',
                'symbol': '000001',
                'name': 'pinganyinhang'
            })

        hk_csv = tmp_path / 'stock_list_hk.csv'
        with open(hk_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'name', 'enname'])
            writer.writeheader()
            writer.writerow({
                'ts_code': '00700.HK',
                'name': 'tengxunkonggu',
                'enname': 'Tencent'
            })

        us_csv = tmp_path / 'stock_list_us.csv'
        with open(us_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'name', 'enname'])
            writer.writeheader()
            writer.writerow({
                'ts_code': 'AAPL',
                'name': 'pingguo',
                'enname': 'Apple Inc.'
            })

        # jiazaishuju
        stocks = load_tushare_data(tmp_path)

        # yanzhengshuju
        assert len(stocks) == 3

        # goujiansuoyin
        index = build_stock_index(stocks)

        # yanzhengsuoyin
        assert len(index) == 3

        # yasuosuoyin
        compressed = compress_index(index)

        # yanzhengyasuo
        assert len(compressed) == 3

        # yanzhengziduanshuliang
        for item in compressed:
            assert len(item) == 10

    def test_market_distribution(self, tmp_path):
        """ceshishichangfenbutongji"""
        # chuangjianceshishuju
        csv_file = tmp_path / 'stock_list_a.csv'
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ts_code', 'symbol', 'name'])
            writer.writeheader()
            writer.writerow({'ts_code': '000001.SZ', 'symbol': '000001', 'name': 'pinganyinhang'})
            writer.writerow({'ts_code': '600519.SH', 'symbol': '600519', 'name': 'guizhoumaotai'})
            writer.writerow({'ts_code': '832566.BJ', 'symbol': '832566', 'name': 'zizhuangkeji'})

        stocks = load_tushare_data(tmp_path)
        index = build_stock_index(stocks)

        # tongjishichangfenbu
        market_stats = {}
        for item in index:
            market = item['market']
            market_stats[market] = market_stats.get(market, 0) + 1

        # yanzhengtongji
        assert market_stats.get('CN', 0) == 2  # SZ, SH
        assert market_stats.get('BSE', 0) == 1  # BJ

    def test_us_reused_symbols_are_deduplicated(self, tmp_path):
        """ceshimeigufuyong ticker zaijiazaishihuixianquzhong"""
        us_csv = tmp_path / 'stock_list_us.csv'
        with open(us_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['ts_code', 'name', 'enname', 'list_date', 'delist_date']
            )
            writer.writeheader()
            writer.writerow({
                'ts_code': 'B',
                'name': '',
                'enname': 'BARNES GROUP',
                'list_date': '19631014',
                'delist_date': 'NaT',
            })
            writer.writerow({
                'ts_code': 'B',
                'name': '',
                'enname': 'BARRICK MINING (NYS)',
                'list_date': '19850213',
                'delist_date': '',
            })
            writer.writerow({
                'ts_code': 'DOC',
                'name': '',
                'enname': 'HEALTHPEAK PROPERTIES',
                'list_date': '19850523',
                'delist_date': '',
            })
            writer.writerow({
                'ts_code': 'DOC',
                'name': '',
                'enname': 'PHYSICIANS REALTY TST.',
                'list_date': '20130719',
                'delist_date': '',
            })
            writer.writerow({
                'ts_code': 'SPWR',
                'name': '',
                'enname': 'COMPLETE SOLARIA',
                'list_date': '20210419',
                'delist_date': '',
            })
            writer.writerow({
                'ts_code': 'SPWR',
                'name': '',
                'enname': 'SUNPOWER',
                'list_date': '20051109',
                'delist_date': 'NaT',
            })

        stocks = load_tushare_data(tmp_path)

        assert len(stocks) == 3
        assert {stock['ts_code'] for stock in stocks} == {'B', 'DOC', 'SPWR'}
        assert next(stock for stock in stocks if stock['ts_code'] == 'B')['name'] == 'BARRICK MINING (NYS)'
        assert next(stock for stock in stocks if stock['ts_code'] == 'DOC')['name'] == 'HEALTHPEAK PROPERTIES'
        assert next(stock for stock in stocks if stock['ts_code'] == 'SPWR')['name'] == 'COMPLETE SOLARIA'


class TestPinyin:
    """ceshipinyinshengcheng"""

    def test_normalize_name(self):
        """ceshimingchengbiaozhunhua"""
        # ceshi ST qianzhuiquchu
        result = normalize_name_for_pinyin('*STpingan')
        assert 'ST' not in result

        # ceshi N qianzhuiquchu
        result = normalize_name_for_pinyin('Npinganyinhang')
        assert 'N' not in result

    def test_generate_pinyin(self):
        """ceshipinyinshengcheng"""
        # zhuyi：zhegeceshixuyao pypinyin keyong
        pinyin_full, pinyin_abbr = generate_pinyin('pinganyinhang')
        if pinyin_full:
            assert isinstance(pinyin_full, str)
        if pinyin_abbr:
            assert isinstance(pinyin_abbr, str)
