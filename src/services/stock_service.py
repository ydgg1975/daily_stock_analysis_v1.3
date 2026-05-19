# -*- coding: utf-8 -*-

"""

===================================

stockshujufuwuceng

===================================



zhize竊?
1. fengzhuangstockshujuhuoquluoji

2. tigongshishixingqinghelishishujujiekou

"""



import logging

from datetime import datetime, timedelta

from typing import Optional, Dict, Any, List



from src.repositories.stock_repo import StockRepository



logger = logging.getLogger(__name__)





class StockService:

    """

    stockshujufuwu

    

    fengzhuangstockshujuhuoqudeyewuluoji

    """

    

    def __init__(self):

        """chushihuastockshujufuwu"""

        self.repo = StockRepository()

    

    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:

        """

        huoqustockshishixingqing

        

        Args:

            stock_code: stockdaima

            

        Returns:

            shishixinginputjuzidian

        """

        try:

            # diaoyongshujuhuoquqihuoqushishixingqing

            from data_provider.base import DataFetcherManager

            

            manager = DataFetcherManager()

            quote = manager.get_realtime_quote(stock_code)

            

            if quote is None:

                logger.warning(f"huoqu {stock_code} shishixingqingshibai")

                return None

            

            # UnifiedRealtimeQuote shi dataclass竊똲hiyong getattr anquanfangwenziduan

            # ziduanyingshe: UnifiedRealtimeQuote -> API xiangying

            # - code -> stock_code

            # - name -> stock_name

            # - price -> current_price

            # - change_amount -> change

            # - change_pct -> change_percent

            # - open_price -> open

            # - high -> high

            # - low -> low

            # - pre_close -> prev_close

            # - volume -> volume

            # - amount -> amount

            return {

                "stock_code": getattr(quote, "code", stock_code),

                "stock_name": getattr(quote, "name", None),

                "current_price": getattr(quote, "price", 0.0) or 0.0,

                "change": getattr(quote, "change_amount", None),

                "change_percent": getattr(quote, "change_pct", None),

                "open": getattr(quote, "open_price", None),

                "high": getattr(quote, "high", None),

                "low": getattr(quote, "low", None),

                "prev_close": getattr(quote, "pre_close", None),

                "volume": getattr(quote, "volume", None),

                "amount": getattr(quote, "amount", None),

                "update_time": datetime.now().isoformat(),

            }

            

        except ImportError:

            logger.warning("DataFetcherManager weizhaodao竊똲hiyongzhanweishuju")

            return self._get_placeholder_quote(stock_code)

        except Exception as e:

            logger.error(f"huoqushishixingqingshibai: {e}", exc_info=True)

            return None

    

    def get_history_data(

        self,

        stock_code: str,

        period: str = "daily",

        days: int = 30

    ) -> Dict[str, Any]:

        """

        huoqustocklishiquote

        

        Args:

            stock_code: stockdaima

            period: K xianzhouqi (daily/weekly/monthly)

            days: huoqutianshu

            

        Returns:

            lishiquoteshujuzidian

            

        Raises:

            ValueError: dang period bushi daily shipaochu竊늳eekly/monthly zanweishixian竊?
        """

        # yanzheng period canshu竊똺hizhichi daily

        if period != "daily":

            raise ValueError(

                f"Unsupported period '{period}'. Only 'daily' is currently supported. "

                "Weekly/monthly aggregation can be added in a later version."

            )

        

        try:

            # diaoyongshujuhuoquqihuoqulishishuju

            from data_provider.base import DataFetcherManager

            

            manager = DataFetcherManager()

            df, source = manager.get_daily_data(stock_code, days=days)

            

            if df is None or df.empty:

                logger.warning(f"huoqu {stock_code} lishishujushibai")

                return {"stock_code": stock_code, "period": period, "data": []}

            

            # huoqustockmingcheng

            stock_name = manager.get_stock_name(stock_code)

            

            # zhuanhuanweixiangyinggeshi

            data = []

            for _, row in df.iterrows():

                date_val = row.get("date")

                if hasattr(date_val, "strftime"):

                    date_str = date_val.strftime("%Y-%m-%d")

                else:

                    date_str = str(date_val)

                

                data.append({

                    "date": date_str,

                    "open": float(row.get("open", 0)),

                    "high": float(row.get("high", 0)),

                    "low": float(row.get("low", 0)),

                    "close": float(row.get("close", 0)),

                    "volume": float(row.get("volume", 0)) if row.get("volume") else None,

                    "amount": float(row.get("amount", 0)) if row.get("amount") else None,

                    "change_percent": float(row.get("pct_chg", 0)) if row.get("pct_chg") else None,

                })

            

            return {

                "stock_code": stock_code,

                "stock_name": stock_name,

                "period": period,

                "data": data,

            }

            

        except ImportError:

            logger.warning("DataFetcherManager weizhaodao竊똣anhuikongshuju")

            return {"stock_code": stock_code, "period": period, "data": []}

        except Exception as e:

            logger.error(f"huoqulishishujushibai: {e}", exc_info=True)

            return {"stock_code": stock_code, "period": period, "data": []}

    

    def _get_placeholder_quote(self, stock_code: str) -> Dict[str, Any]:

        """

        huoquzhanweiquoteshuju竊늶ongyutest竊?
        

        Args:

            stock_code: stockdaima

            

        Returns:

            zhanweiquoteshuju

        """

        return {

            "stock_code": stock_code,

            "stock_name": f"stock{stock_code}",

            "current_price": 0.0,

            "change": None,

            "change_percent": None,

            "open": None,

            "high": None,

            "low": None,

            "prev_close": None,

            "volume": None,

            "amount": None,

            "update_time": datetime.now().isoformat(),

        }


