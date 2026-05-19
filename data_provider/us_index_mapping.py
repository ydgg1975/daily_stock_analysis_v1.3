# -*- coding: utf-8 -*-
"""
===================================
meiguzhishuyugupiaodaimagongju
===================================

tigong：
1. meiguzhishudaimayingshe（ru SPX -> ^GSPC）
2. meigugupiaodaimashibie（AAPL、TSLA deng）

meiguzhishuzai Yahoo Finance zhongxushiyong ^ qianzhui，yugupiaodaimabutong。
"""

import re

# meigudaimazhengze：1-5 gedaxiezimu，kexuan .X houzhui（ru BRK.B）
_US_STOCK_PATTERN = re.compile(r'^[A-Z]{1,5}(\.[A-Z])?$')


# yonghushuru -> (Yahoo Finance fuhao, zhongwenmingcheng)
US_INDEX_MAPPING = {
    # biaopu 500
    'SPX': ('^GSPC', 'biaopu500zhishu'),
    '^GSPC': ('^GSPC', 'biaopu500zhishu'),
    'GSPC': ('^GSPC', 'biaopu500zhishu'),
    # daoqiongsigongyepingjunzhishu
    'DJI': ('^DJI', 'daoqiongsigongyezhishu'),
    '^DJI': ('^DJI', 'daoqiongsigongyezhishu'),
    'DJIA': ('^DJI', 'daoqiongsigongyezhishu'),
    # nasidakezonghezhishu
    'IXIC': ('^IXIC', 'nasidakezonghezhishu'),
    '^IXIC': ('^IXIC', 'nasidakezonghezhishu'),
    'NASDAQ': ('^IXIC', 'nasidakezonghezhishu'),
    # nasidake 100
    'NDX': ('^NDX', 'nasidake100zhishu'),
    '^NDX': ('^NDX', 'nasidake100zhishu'),
    # VIX bodonglvzhishu
    'VIX': ('^VIX', 'VIXkonghuangzhishu'),
    '^VIX': ('^VIX', 'VIXkonghuangzhishu'),
    # luosu 2000
    'RUT': ('^RUT', 'luosu2000zhishu'),
    '^RUT': ('^RUT', 'luosu2000zhishu'),
}


def is_us_index_code(code: str) -> bool:
    """
    panduandaimashifouweimeiguzhishufuhao。

    Args:
        code: gupiao/zhishudaima，ru 'SPX', 'DJI'

    Returns:
        True biaoshishiyizhimeiguzhishufuhao，fouze False

    Examples:
        >>> is_us_index_code('SPX')
        True
        >>> is_us_index_code('AAPL')
        False
    """
    return (code or '').strip().upper() in US_INDEX_MAPPING


def is_us_stock_code(code: str) -> bool:
    """
    panduandaimashifouweimeigugupiaofuhao（paichumeiguzhishu）。

    meigugupiaodaimawei 1-5 gedaxiezimu，kexuan .X houzhuiru BRK.B。
    meiguzhishu（SPX、DJI deng）mingquepaichu。

    Args:
        code: gupiaodaima，ru 'AAPL', 'TSLA', 'BRK.B'

    Returns:
        True biaoshishimeigugupiaofuhao，fouze False

    Examples:
        >>> is_us_stock_code('AAPL')
        True
        >>> is_us_stock_code('TSLA')
        True
        >>> is_us_stock_code('BRK.B')
        True
        >>> is_us_stock_code('SPX')
        False
        >>> is_us_stock_code('600519')
        False
    """
    normalized = (code or '').strip().upper()
    # meiguzhishubushigupiao
    if normalized in US_INDEX_MAPPING:
        return False
    return bool(_US_STOCK_PATTERN.match(normalized))


def get_us_index_yf_symbol(code: str) -> tuple:
    """
    huoqumeiguzhishude Yahoo Finance fuhaoyuzhongwenmingcheng。

    Args:
        code: yonghushuru，ru 'SPX', '^GSPC', 'DJI'

    Returns:
        (yf_symbol, chinese_name) yuanzu，weizhaodaoshifanhui (None, None)。

    Examples:
        >>> get_us_index_yf_symbol('SPX')
        ('^GSPC', 'biaopu500zhishu')
        >>> get_us_index_yf_symbol('AAPL')
        (None, None)
    """
    normalized = (code or '').strip().upper()
    return US_INDEX_MAPPING.get(normalized, (None, None))
