# -*- coding: utf-8 -*-
"""
===================================
YfinanceFetcher - doudishujuyuan (Priority 4)
===================================

shujulaiyuan：Yahoo Finance（tongguo yfinance ku）
tedian：guojishujuyuan、kenengyouyanchihuoqueshi
dingwei：dangsuoyouguoneishujuyuandoushibaishidezuihoubaozhang

guanjiancelve：
1. zidongjiang A gudaimazhuanhuanwei yfinance geshi（.SS / .SZ）
2. chuli Yahoo Finance deshujugeshichayi
3. shibaihouzhishutuibizhongshi
"""

import csv
import logging
from datetime import datetime
from io import StringIO
from typing import Optional, List, Dict, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS, is_bse_code
from .realtime_types import UnifiedRealtimeQuote, RealtimeSource
from .us_index_mapping import get_us_index_yf_symbol, is_us_stock_code

# kexuandaorubendigupiaoyingshebuding，ruoqueshizeshiyongkongzidiandoudi
try:
    from src.data.stock_mapping import STOCK_NAME_MAP, is_meaningful_stock_name
except (ImportError, ModuleNotFoundError):
    STOCK_NAME_MAP = {}

    def is_meaningful_stock_name(name: str | None, stock_code: str) -> bool:
        """jiandandemingchengyouxiaoxingjiaoyandoudi"""
        if not name:
            return False
        n = str(name).strip()
        return bool(n and n.upper() != str(stock_code).strip().upper())

import os

logger = logging.getLogger(__name__)


class YfinanceFetcher(BaseFetcher):
    """
    Yahoo Finance shujuyuanshixian

    youxianji：4（zuidi，zuoweidoudi）
    shujulaiyuan：Yahoo Finance

    guanjiancelve：
    - zidongzhuanhuangupiaodaimageshi
    - chulishiquheshujugeshichayi
    - shibaihouzhishutuibizhongshi

    zhuyishixiang：
    - A gushujukenengyouyanchi
    - mouxiegupiaokenengwushuju
    - shujujingdukenengyuguoneiyuanlveyouchayi
    """

    name = "YfinanceFetcher"
    priority = int(os.getenv("YFINANCE_PRIORITY", "4"))

    def __init__(self):
        """chushihua YfinanceFetcher"""
        pass

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        zhuanhuangupiaodaimawei Yahoo Finance geshi

        Yahoo Finance daimageshi：
        - Aguhushi：600519.SS (Shanghai Stock Exchange)
        - Agushenshi：000001.SZ (Shenzhen Stock Exchange)
        - ganggu：0700.HK (Hong Kong Stock Exchange)
        - meigu：AAPL, TSLA, GOOGL (wuxuhouzhui)

        Args:
            stock_code: yuanshidaima，ru '600519', 'hk00700', 'AAPL'

        Returns:
            Yahoo Finance geshidaima

        Examples:
            >>> fetcher._convert_stock_code('600519')
            '600519.SS'
            >>> fetcher._convert_stock_code('hk00700')
            '0700.HK'
            >>> fetcher._convert_stock_code('AAPL')
            'AAPL'
        """
        code = stock_code.strip().upper()

        # meiguzhishu：yingshedao Yahoo Finance fuhao（ru SPX -> ^GSPC）
        yf_symbol, _ = get_us_index_yf_symbol(code)
        if yf_symbol:
            logger.debug(f"shibieweimeiguzhishu: {code} -> {yf_symbol}")
            return yf_symbol

        # meigu：1-5 gedaxiezimu（kexuan .X houzhui），yuanyangfanhui
        if is_us_stock_code(code):
            logger.debug(f"shibieweimeigudaima: {code}")
            return code

        # ganggu：hkqianzhui -> .HKhouzhui
        if code.startswith('HK'):
            hk_code = code[2:].lstrip('0') or '0'  # quchuqiandao0，danbaoliuzhishaoyige0
            hk_code = hk_code.zfill(4)  # buqidao4wei
            logger.debug(f"zhuanhuanganggudaima: {stock_code} -> {hk_code}.HK")
            return f"{hk_code}.HK"

        # yijingbaohanhouzhuideqingkuang
        if '.SS' in code or '.SZ' in code or '.HK' in code or '.BJ' in code:
            return code

        # quchukenengde .SH houzhui
        code = code.replace('.SH', '')

        # ETF: Shanghai ETF (51xx, 52xx, 56xx, 58xx) -> .SS; Shenzhen ETF (15xx, 16xx, 18xx) -> .SZ
        if len(code) == 6:
            if code.startswith(('51', '52', '56', '58')):
                return f"{code}.SS"
            if code.startswith(('15', '16', '18')):
                return f"{code}.SZ"

        # BSE (Beijing Stock Exchange): 8xxxxx, 4xxxxx, 920xxx
        if is_bse_code(code):
            base = code.split('.')[0] if '.' in code else code
            return f"{base}.BJ"

        # Agu：genjudaimaqianzhuipanduanshichang
        if code.startswith(('600', '601', '603', '688')):
            return f"{code}.SS"
        elif code.startswith(('000', '002', '300')):
            return f"{code}.SZ"
        else:
            logger.warning(f"wufaquedinggupiao {code} deshichang，morenshiyongshenshi")
            return f"{code}.SZ"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        cong Yahoo Finance huoquyuanshishuju

        shiyong yfinance.download() huoqulishishuju

        liucheng：
        1. zhuanhuangupiaodaimageshi
        2. diaoyong yfinance API
        3. chulifanhuishuju
        """
        import yfinance as yf

        # zhuanhuandaimageshi
        yf_code = self._convert_stock_code(stock_code)

        logger.debug(f"diaoyong yfinance.download({yf_code}, {start_date}, {end_date})")

        try:
            # shiyong yfinance xiazaishuju
            df = yf.download(
                tickers=yf_code,
                start=start_date,
                end=end_date,
                progress=False,  # jinzhijindutiao
                auto_adjust=True,  # zidongtiaozhengjiage（fuquan）
                multi_level_index=True
            )

            # shaixuanchu yf_code delie, bimianduozhigupiaoshujuhunxiao
            if isinstance(df.columns, pd.MultiIndex) and len(df.columns) > 1:
                ticker_level = df.columns.get_level_values(1)
                mask = ticker_level == yf_code
                if mask.any():
                    df = df.loc[:, mask].copy()

            if df.empty:
                raise DataFetchError(f"Yahoo Finance weichaxundao {stock_code} deshuju")

            return df

        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Yahoo Finance huoqushujushibai: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        biaozhunhua Yahoo Finance shuju

        yfinance fanhuidelieming：
        Open, High, Low, Close, Volume（suoyinshiriqi）

        zhuyi：xinban yfinance fanhui MultiIndex lieming，ru ('Close', 'AMD')
        xuyaoxianbianpinghualiemingzaijinxingchuli

        xuyaoyingshedaobiaozhunlieming：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # chuli MultiIndex lieming（xinban yfinance fanhuigeshi）
        # liru: ('Close', 'AMD') -> 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            logger.debug("jiancedao MultiIndex lieming，jinxingbianpinghuachuli")
            # qudiyijilieming（Price level: Close, High, Low, etc.）
            df.columns = df.columns.get_level_values(0)

        # zhongzhisuoyin，jiangriqicongsuoyinbianweilie
        df = df.reset_index()

        # liemingyingshe（yfinance shiyongshouzimudaxie）
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        }

        df = df.rename(columns=column_mapping)

        # jisuanzhangdiefu（yinwei yfinance buzhijietigong）
        if 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pct_chg'] = df['pct_chg'].fillna(0).round(2)

        # jisuanchengjiaoe（yfinance butigong，shiyonggusuanzhi）
        # chengjiaoe ≈ chengjiaoliang * pingjunjiage
        if 'volume' in df.columns and 'close' in df.columns:
            df['amount'] = df['volume'] * df['close']
        else:
            df['amount'] = 0

        # tianjiagupiaodaimalie
        df['code'] = stock_code

        # zhibaoliuxuyaodelie
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def _fetch_yf_ticker_data(self, yf, yf_code: str, name: str, return_code: str) -> Optional[Dict[str, Any]]:
        """
        tongguo yfinance laqudangezhishu/gupiaodehangqingshuju。

        Args:
            yf: yfinance mokuaiyinyong
            yf_code: yfinance shiyongdedaima（ru '000001.SS'、'^GSPC'）
            name: zhishuxianshimingcheng
            return_code: xierujieguo dict de code ziduan（ru 'sh000001'、'SPX'）

        Returns:
            hangqingzidian，shibaishifanhui None
        """
        ticker = yf.Ticker(yf_code)
        # qujinliangrishujuyijisuanzhangdiefu
        hist = ticker.history(period='2d')
        if hist.empty:
            return None
        today_row = hist.iloc[-1]
        prev_row = hist.iloc[-2] if len(hist) > 1 else today_row
        price = float(today_row['Close'])
        prev_close = float(prev_row['Close'])
        change = price - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0
        high = float(today_row['High'])
        low = float(today_row['Low'])
        # zhenfu = (zuigao - zuidi) / zuoshou * 100
        amplitude = ((high - low) / prev_close * 100) if prev_close else 0
        return {
            'code': return_code,
            'name': name,
            'current': price,
            'change': change,
            'change_pct': change_pct,
            'open': float(today_row['Open']),
            'high': high,
            'low': low,
            'prev_close': prev_close,
            'volume': float(today_row['Volume']),
            'amount': 0.0,  # Yahoo Finance butigongzhunquechengjiaoe
            'amplitude': amplitude,
        }

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        huoquzhuyaozhishuhangqing (Yahoo Finance)，zhichi A gu、meiguyuganggu。
        region=us shiweituogei _get_us_main_indices。
        region=hk shiweituogei _get_hk_main_indices。
        """
        import yfinance as yf

        if region == "us":
            return self._get_us_main_indices(yf)
        if region == "hk":
            return self._get_hk_main_indices(yf)

        # A guzhishu：akshare daima -> (yfinance daima, xianshimingcheng)
        yf_mapping = {
            'sh000001': ('000001.SS', 'shangzhengzhishu'),
            'sz399001': ('399001.SZ', 'shenzhengchengzhi'),
            'sz399006': ('399006.SZ', 'chuangyebanzhi'),
            'sh000688': ('000688.SS', 'kechuang50'),
            'sh000016': ('000016.SS', 'shangzheng50'),
            'sh000300': ('000300.SS', 'hushen300'),
        }

        results = []
        try:
            for ak_code, (yf_code, name) in yf_mapping.items():
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_code, name, ak_code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] huoquzhishu {name} chenggong")
                except Exception as e:
                    logger.warning(f"[Yfinance] huoquzhishu {name} shibai: {e}")

            if results:
                logger.info(f"[Yfinance] chenggonghuoqu {len(results)} ge A guzhishuhangqing")
                return results

        except Exception as e:
            logger.error(f"[Yfinance] huoqu A guzhishuhangqingshibai: {e}")

        return None

    def _get_us_main_indices(self, yf) -> Optional[List[Dict[str, Any]]]:
        """huoqumeiguzhuyaozhishuhangqing（SPX、IXIC、DJI、VIX），fuyong _fetch_yf_ticker_data"""
        # dapanfupansuoxuhexinmeiguzhishu
        us_indices = ['SPX', 'IXIC', 'DJI', 'VIX']
        results = []
        try:
            for code in us_indices:
                yf_symbol, name = get_us_index_yf_symbol(code)
                if not yf_symbol:
                    continue
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_symbol, name, code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] huoqumeiguzhishu {name} chenggong")
                except Exception as e:
                    logger.warning(f"[Yfinance] huoqumeiguzhishu {name} shibai: {e}")

            if results:
                logger.info(f"[Yfinance] chenggonghuoqu {len(results)} gemeiguzhishuhangqing")
                return results

        except Exception as e:
            logger.error(f"[Yfinance] huoqumeiguzhishuhangqingshibai: {e}")

        return None

    def _get_hk_main_indices(self, yf) -> Optional[List[Dict[str, Any]]]:
        """huoqugangguzhuyaozhishuhangqing（HSI、HSTECH、HSCEI），fuyong _fetch_yf_ticker_data"""
        # Yahoo Finance gangguzhishufuhaoyingshe：
        # - HSI -> ^HSI
        # - HSTECH -> HSTECH.HK（bushi ^HSTECH）
        # - HSCEI -> ^HSCE（bushi ^HSCEI）
        # gaiyingsheyoulixiandance tests/test_yfinance_hk_indices.py guhua，bimianzaixianyilaidaozhifeiquedingxingshibai。
        hk_indices = {
            'HSI': ('^HSI', 'hengshengzhishu'),
            'HSTECH': ('HSTECH.HK', 'hengshengkejizhishu'),
            'HSCEI': ('^HSCE', 'guoqizhishu'),
        }
        results = []
        try:
            for code, (yf_symbol, name) in hk_indices.items():
                try:
                    item = self._fetch_yf_ticker_data(yf, yf_symbol, name, code)
                    if item:
                        results.append(item)
                        logger.debug(f"[Yfinance] huoqugangguzhishu {name} chenggong")
                except Exception as e:
                    logger.warning(f"[Yfinance] huoqugangguzhishu {name} shibai: {e}")

            if results:
                logger.info(f"[Yfinance] chenggonghuoqu {len(results)} gegangguzhishuhangqing")
                return results

        except Exception as e:
            logger.error(f"[Yfinance] huoqugangguzhishuhangqingshibai: {e}")

        return None

    def _is_us_stock(self, stock_code: str) -> bool:
        """
        panduandaimashifouweimeigugupiao（paichumeiguzhishu）。

        weituogei us_index_mapping mokuaide is_us_stock_code()。
        """
        return is_us_stock_code(stock_code)

    def _get_us_stock_quote_from_stooq(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        shiyong Stooq weimeigushishixingqingtigongmianmiyaodoudi。

        Stooq tigongdeshizuixinjiaoyirihangqing，jingduburufenshishishijiekou，danzai Yahoo / yfinance
        beixianliushi，zhishaonengwei Web UI tigongkeyongjiage；ruokehuoqudaozuoshoujia，zetongshitigongzhangdiefudengyanshengzhibiao。
        """
        symbol = stock_code.strip().upper()
        stooq_symbol = f"{symbol.lower()}.us"
        url = f"https://stooq.com/q/l/?s={stooq_symbol}"
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DSA/1.0; +https://github.com/ZhuLinsen/daily_stock_analysis)",
                "Accept": "text/plain,text/csv,*/*",
            },
        )

        try:
            with urlopen(request, timeout=15) as response:
                payload = response.read().decode("utf-8", "ignore").strip()
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.warning(f"[Stooq] huoqumeigu {symbol} shishixingqingshibai: {exc}")
            return None

        if not payload or payload.upper().startswith("NO DATA"):
            logger.warning(f"[Stooq] wufahuoqu {symbol} dehangqingshuju")
            return None

        def _fetch_prev_close() -> Optional[float]:
            history_url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
            history_request = Request(
                history_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; DSA/1.0; +https://github.com/ZhuLinsen/daily_stock_analysis)",
                    "Accept": "text/plain,text/csv,*/*",
                },
            )
            try:
                with urlopen(history_request, timeout=15) as response:
                    history_payload = response.read().decode("utf-8", "ignore").strip()
            except (HTTPError, URLError, TimeoutError) as exc:
                logger.debug(f"[Stooq] huoqumeigu {symbol} rixianlishishibai: {exc}")
                return None

            if not history_payload or history_payload.upper().startswith("NO DATA"):
                return None

            try:
                reader = csv.reader(StringIO(history_payload))
                header = next(reader, None)
                if not header:
                    return None

                header_tokens = [cell.strip().lower() for cell in header]
                has_header = "close" in header_tokens and "date" in header_tokens
                if not has_header:
                    return None

                date_index = header_tokens.index("date")
                close_index = header_tokens.index("close")

                daily_rows: list[tuple[datetime, float]] = []
                for row in reader:
                    if not row:
                        continue
                    date_text = row[date_index].strip() if len(row) > date_index else ""
                    close_text = row[close_index].strip() if len(row) > close_index else ""
                    if not date_text or not close_text:
                        continue
                    try:
                        dt = datetime.strptime(date_text, "%Y-%m-%d")
                        close_val = float(close_text)
                    except Exception:
                        continue
                    daily_rows.append((dt, close_val))

                if len(daily_rows) < 2:
                    return None

                daily_rows.sort(key=lambda item: item[0])
                return daily_rows[-2][1]
            except Exception:
                return None

        try:
            reader = csv.reader(StringIO(payload))
            first_row = next(reader, None)
            if first_row is None:
                raise ValueError(f"unexpected Stooq payload: {payload}")

            normalized_first_row = [cell.strip() for cell in first_row]
            header_tokens = {cell.lower() for cell in normalized_first_row if cell}
            has_header = 'open' in header_tokens and 'close' in header_tokens
            row = next(reader, None) if has_header else first_row
            if row is None:
                raise ValueError(f"unexpected Stooq payload: {payload}")

            normalized_row = [cell.strip() for cell in row]
            while normalized_row and normalized_row[-1] == '':
                normalized_row.pop()

            if len(normalized_row) >= 8:
                open_index, high_index, low_index, price_index, volume_index = 3, 4, 5, 6, 7
            elif len(normalized_row) >= 7:
                open_index, high_index, low_index, price_index, volume_index = 2, 3, 4, 5, 6
            else:
                raise ValueError(f"unexpected Stooq payload: {payload}")

            open_price = float(normalized_row[open_index])
            high = float(normalized_row[high_index])
            low = float(normalized_row[low_index])
            price = float(normalized_row[price_index])
            volume = int(float(normalized_row[volume_index]))

            prev_close = _fetch_prev_close()
            change_amount = None
            change_pct = None
            amplitude = None
            if prev_close is not None and prev_close > 0:
                change_amount = price - prev_close
                change_pct = (change_amount / prev_close) * 100
                amplitude = ((high - low) / prev_close) * 100

            quote = UnifiedRealtimeQuote(
                code=symbol,
                name=STOCK_NAME_MAP.get(symbol, ''),
                source=RealtimeSource.STOOQ,
                price=price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                change_amount=round(change_amount, 4) if change_amount is not None else None,
                volume=volume,
                amount=None,
                volume_ratio=None,
                turnover_rate=None,
                amplitude=round(amplitude, 2) if amplitude is not None else None,
                open_price=open_price,
                high=high,
                low=low,
                pre_close=prev_close,
                pe_ratio=None,
                pb_ratio=None,
                total_mv=None,
                circ_mv=None,
            )
            logger.info(f"[Stooq] huoqumeigu {symbol} doudihangqingchenggong: jiage={price}")
            return quote
        except Exception as exc:
            logger.warning(f"[Stooq] jieximeigu {symbol} hangqingshibai: {exc}")
            return None

    def _get_us_index_realtime_quote(
        self,
        user_code: str,
        yf_symbol: str,
        index_name: str,
    ) -> Optional[UnifiedRealtimeQuote]:
        """
        Get realtime quote for US index (e.g. SPX -> ^GSPC).

        Args:
            user_code: User input code (e.g. SPX)
            yf_symbol: Yahoo Finance symbol (e.g. ^GSPC)
            index_name: Chinese name for the index

        Returns:
            UnifiedRealtimeQuote or None
        """
        import yfinance as yf

        try:
            logger.debug(f"[Yfinance] huoqumeiguzhishu {user_code} ({yf_symbol}) shishixingqing")
            ticker = yf.Ticker(yf_symbol)

            try:
                info = ticker.fast_info
                if info is None:
                    raise ValueError("fast_info is None")
                price = getattr(info, 'lastPrice', None) or getattr(info, 'last_price', None)
                prev_close = getattr(info, 'previousClose', None) or getattr(info, 'previous_close', None)
                open_price = getattr(info, 'open', None)
                high = getattr(info, 'dayHigh', None) or getattr(info, 'day_high', None)
                low = getattr(info, 'dayLow', None) or getattr(info, 'day_low', None)
                volume = getattr(info, 'lastVolume', None) or getattr(info, 'last_volume', None)
            except Exception:
                logger.debug("[Yfinance] fast_info shibai，changshi history fangfa")
                hist = ticker.history(period='2d')
                if hist.empty:
                    logger.warning(f"[Yfinance] wufahuoqu {yf_symbol} deshuju")
                    return None
                today = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else today
                price = float(today['Close'])
                prev_close = float(prev['Close'])
                open_price = float(today['Open'])
                high = float(today['High'])
                low = float(today['Low'])
                volume = int(today['Volume'])

            change_amount = None
            change_pct = None
            if price is not None and prev_close is not None and prev_close > 0:
                change_amount = price - prev_close
                change_pct = (change_amount / prev_close) * 100

            amplitude = None
            if high is not None and low is not None and prev_close is not None and prev_close > 0:
                amplitude = ((high - low) / prev_close) * 100

            quote = UnifiedRealtimeQuote(
                code=user_code,
                name=index_name or user_code,
                source=RealtimeSource.FALLBACK,
                price=price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                change_amount=round(change_amount, 4) if change_amount is not None else None,
                volume=volume,
                amount=None,
                volume_ratio=None,
                turnover_rate=None,
                amplitude=round(amplitude, 2) if amplitude is not None else None,
                open_price=open_price,
                high=high,
                low=low,
                pre_close=prev_close,
                pe_ratio=None,
                pb_ratio=None,
                total_mv=None,
                circ_mv=None,
            )
            logger.info(f"[Yfinance] huoqumeiguzhishu {user_code} shishixingqingchenggong: jiage={price}")
            return quote
        except Exception as e:
            logger.warning(f"[Yfinance] huoqumeiguzhishu {user_code} shishixingqingshibai: {e}")
            return None

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoqumeigu/meiguzhishushishixingqingshuju

        zhichimeigugupiao（AAPL、TSLA）hemeiguzhishu（SPX、DJI deng）。
        shujulaiyuan：yfinance Ticker.info

        Args:
            stock_code: meigudaimahuozhishudaima，ru 'AMD', 'AAPL', 'SPX', 'DJI'

        Returns:
            UnifiedRealtimeQuote duixiang，huoqushibaifanhui None
        """
        import yfinance as yf

        # meiguzhishu：shiyongyingshe（SPX -> ^GSPC）
        yf_symbol, index_name = get_us_index_yf_symbol(stock_code)
        if yf_symbol:
            return self._get_us_index_realtime_quote(
                user_code=stock_code.strip().upper(),
                yf_symbol=yf_symbol,
                index_name=index_name,
            )

        # jinchulimeigugupiao
        if not self._is_us_stock(stock_code):
            logger.debug(f"[Yfinance] {stock_code} bushimeigu，tiaoguo")
            return None

        try:
            symbol = stock_code.strip().upper()
            logger.debug(f"[Yfinance] huoqumeigu {symbol} shishixingqing")

            ticker = yf.Ticker(symbol)

            # changshihuoqu fast_info（gengkuai，danziduanjiaoshao）
            try:
                info = ticker.fast_info
                if info is None:
                    raise ValueError("fast_info is None")

                price = getattr(info, 'lastPrice', None) or getattr(info, 'last_price', None)
                prev_close = getattr(info, 'previousClose', None) or getattr(info, 'previous_close', None)
                open_price = getattr(info, 'open', None)
                high = getattr(info, 'dayHigh', None) or getattr(info, 'day_high', None)
                low = getattr(info, 'dayLow', None) or getattr(info, 'day_low', None)
                volume = getattr(info, 'lastVolume', None) or getattr(info, 'last_volume', None)
                market_cap = getattr(info, 'marketCap', None) or getattr(info, 'market_cap', None)

            except Exception:
                # huituidao history fangfahuoquzuixinshuju
                logger.debug("[Yfinance] fast_info shibai，changshi history fangfa")
                hist = ticker.history(period='2d')
                if hist.empty:
                    logger.warning(f"[Yfinance] wufahuoqu {symbol} deshuju，changshi Stooq doudi")
                    return self._get_us_stock_quote_from_stooq(symbol)

                today = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else today

                price = float(today['Close'])
                prev_close = float(prev['Close'])
                open_price = float(today['Open'])
                high = float(today['High'])
                low = float(today['Low'])
                volume = int(today['Volume'])
                market_cap = None

            # jisuanzhangdiefu
            change_amount = None
            change_pct = None
            if price is not None and prev_close is not None and prev_close > 0:
                change_amount = price - prev_close
                change_pct = (change_amount / prev_close) * 100

            # jisuanzhenfu
            amplitude = None
            if high is not None and low is not None and prev_close is not None and prev_close > 0:
                amplitude = ((high - low) / prev_close) * 100

            # huoqugupiaomingcheng
            try:
                info_name = ticker.info.get('shortName', '') or ticker.info.get('longName', '') or ''
                name = info_name if is_meaningful_stock_name(info_name, symbol) else STOCK_NAME_MAP.get(symbol, '')
            except Exception:
                name = STOCK_NAME_MAP.get(symbol, '')

            quote = UnifiedRealtimeQuote(
                code=symbol,
                name=name,
                source=RealtimeSource.FALLBACK,
                price=price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                change_amount=round(change_amount, 4) if change_amount is not None else None,
                volume=volume,
                amount=None,  # yfinance buzhijietigongchengjiaoe
                volume_ratio=None,
                turnover_rate=None,
                amplitude=round(amplitude, 2) if amplitude is not None else None,
                open_price=open_price,
                high=high,
                low=low,
                pre_close=prev_close,
                pe_ratio=None,
                pb_ratio=None,
                total_mv=market_cap,
                circ_mv=None,
            )

            logger.info(f"[Yfinance] huoqumeigu {symbol} shishixingqingchenggong: jiage={price}")
            return quote

        except Exception as e:
            logger.warning(f"[Yfinance] huoqumeigu {stock_code} shishixingqingshibai: {e}，changshi Stooq doudi")
            return self._get_us_stock_quote_from_stooq(stock_code)


if __name__ == "__main__":
    # ceshidaima
    logging.basicConfig(level=logging.DEBUG)

    fetcher = YfinanceFetcher()

    try:
        df = fetcher.get_daily_data('600519')  # maotai
        print(f"huoquchenggong，gong {len(df)} tiaoshuju")
        print(df.tail())
    except Exception as e:
        print(f"huoqushibai: {e}")
