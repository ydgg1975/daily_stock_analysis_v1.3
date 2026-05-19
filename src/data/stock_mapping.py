# -*- coding: utf-8 -*-
from __future__ import annotations

"""
===================================
stockdaimayumingchengyingshe
===================================

Shared stock code -> name mapping, used by analyzer, data_provider, and name_to_code_resolver.
"""

# Stock code -> name mapping (common stocks)
STOCK_NAME_MAP = {
    # === A-shares ===
    "600519": "guizhoumaotai",
    "000001": "pinganyinhang",
    "300750": "ningdeshidai",
    "002594": "biyadi",
    "600036": "zhaoshangyinhang",
    "601318": "chinapingan",
    "000858": "wuliangye",
    "600276": "hengruiyiyao",
    "601012": "longjilvneng",
    "002475": "lixunjingmi",
    "300059": "dongfangcaifu",
    "002415": "haikangweishi",
    "600900": "changjiangdianli",
    "601166": "xingyeyinhang",
    "600028": "chinashihua",
    "600030": "citiczhengquan",
    "600031": "sanyizhonggong",
    "600050": "chinaliantong",
    "600104": "shangqijituan",
    "600111": "beifangxitu",
    "600150": "chinachuanbo",
    "600309": "wanhuahuaxue",
    "600406": "guodiannanrui",
    "600690": "haierzhijia",
    "600760": "zhonghangshenfei",
    "600809": "shanxifenjiu",
    "600887": "yiligufen",
    "600930": "huadianxinneng",
    "601088": "chinashenhua",
    "601127": "sailisi",
    "601211": "guotaihaitong",
    "601225": "shanximeiye",
    "601288": "nongyeyinhang",
    "601328": "jiaotongyinhang",
    "601398": "gongshangyinhang",
    "601601": "chinataibao",
    "601628": "chinarenshou",
    "601658": "youchuyinhang",
    "601668": "chinajianzhu",
    "601728": "chinadianxin",
    "601816": "jinghugaotie",
    "601857": "chinashiyou",
    "601888": "chinazhongmian",
    "601899": "zijinkuangye",
    "601919": "zhongyuanhaikong",
    "601985": "chinahedian",
    "601988": "chinayinhang",
    "603019": "zhongkeshuguang",
    "603259": "yaomingkangde",
    "603501": "haoweijituan",
    "603993": "luoyangmuye",
    "688008": "lanqikeji",
    "688012": "zhongweigongsi",
    "688041": "haiguangxinxi",
    "688111": "jinshanbangong",
    "688256": "hanwuji",
    "688981": "neutraluoji",
    # === US stocks ===
    "AAPL": "pingguo",
    "TSLA": "tesila",
    "MSFT": "weiruan",
    "GOOGL": "gugeA",
    "GOOG": "gugeC",
    "AMZN": "yamaxun",
    "NVDA": "yingweida",
    "META": "Meta",
    "AMD": "AMD",
    "INTC": "yingteer",
    "BABA": "alibaba",
    "PDD": "pinduoduo",
    "JD": "jingdong",
    "BIDU": "baidu",
    "NIO": "weilai",
    "XPEV": "xiaopengqiche",
    "LI": "lixiangqiche",
    "COIN": "Coinbase",
    "MSTR": "MicroStrategy",
    # === HK stocks (5-digit) ===
    "00700": "tengxunkonggu",
    "03690": "meituan",
    "01810": "xiaomijituan",
    "09988": "alibaba",
    "09618": "jingdongjituan",
    "09888": "baidujituan",
    "01024": "kuaishou",
    "00981": "neutraluoji",
    "02015": "lixiangqiche",
    "09868": "xiaopengqiche",
    "00005": "huifengkonggu",
    "01299": "youbangbaoxian",
    "00941": "chinayidong",
    "00883": "chinahaiyangshiyou",
}


def is_meaningful_stock_name(name: str | None, stock_code: str) -> bool:
    """Return whether a stock name is useful for display or caching."""
    if not name:
        return False

    normalized_name = str(name).strip()
    if not normalized_name:
        return False

    normalized_code = (stock_code or "").strip().upper()
    if normalized_name.upper() == normalized_code:
        return False

    if normalized_name.startswith("stock"):
        return False

    placeholder_values = {
        "N/A",
        "NA",
        "NONE",
        "NULL",
        "--",
        "-",
        "UNKNOWN",
        "TICKER",
    }
    if normalized_name.upper() in placeholder_values:
        return False

    return True

