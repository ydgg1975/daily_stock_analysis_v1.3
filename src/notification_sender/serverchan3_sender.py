# -*- coding: utf-8 -*-

"""

Serverjiang3 sendtixingfuwu



zhize竊?
1. tongguo Serverjiang3 API send Serverjiang3 xiaoxi

"""

import logging

from typing import Optional

import requests

from datetime import datetime

import re



from src.config import Config





logger = logging.getLogger(__name__)





class Serverchan3Sender:

    

    def __init__(self, config: Config):

        """

        chushihua Serverjiang3 config



        Args:

            config: configduixiang

        """

        self._serverchan3_sendkey = getattr(config, 'serverchan3_sendkey', None)

        

    def send_to_serverchan3(

        self,

        content: str,

        title: Optional[str] = None,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        """

        tuisongxiaoxidao Serverjiang3



        Serverjiang3 API geshi竊?
        POST https://sctapi.ftqq.com/{sendkey}.send

        huo

        POST https://{num}.push.ft07.com/send/{sendkey}.send

        {

            "title": "xiaoxibiaoti",

            "desp": "xiaoxineirong",

            "options": {}

        }



        Serverjiang3 tedian竊?
        - guoneituisongfuwu竊똺hichiduojiaguochanxitongtuisongtongdao竊똩ewuhoutaituisong

        - jiandanyiyongde API jiekou



        Args:

            content: xiaoxineirong竊뉾arkdown geshi竊?
            title: xiaoxibiaoti竊늟exuan竊?


        Returns:

            shifousendchenggong

        """

        if not self._serverchan3_sendkey:

            logger.warning("Serverjiang3 SendKey weiconfig竊똳iaoguotuisong")

            return False



        # chulixiaoxibiaoti

        if title is None:

            date_str = datetime.now().strftime('%Y-%m-%d')

            title = f"?뱢 stockanalysisbaogao - {date_str}"



        try:

            # genju sendkey geshigouzao URL

            sendkey = self._serverchan3_sendkey

            if sendkey.startswith('sctp'):

                match = re.match(r'sctp(\d+)t', sendkey)

                if match:

                    num = match.group(1)

                    url = f"https://{num}.push.ft07.com/send/{sendkey}.send"

                else:

                    logger.error("Invalid sendkey format for sctp")

                    return False

            else:

                url = f"https://sctapi.ftqq.com/{sendkey}.send"



            # goujianqingqiucanshu

            params = {

                'title': title,

                'desp': content,

                'options': {}

            }



            # sendqingqiu

            headers = {

                'Content-Type': 'application/json;charset=utf-8'

            }

            response = requests.post(url, json=params, headers=headers, timeout=timeout_seconds or 10)



            if response.status_code == 200:

                result = response.json()

                logger.info(f"Serverjiang3 xiaoxisendchenggong: {result}")

                return True

            else:

                logger.error(f"Serverjiang3 request_failed: HTTP {response.status_code}")

                logger.error(f"xiangyingneirong: {response.text}")

                return False



        except Exception as e:

            logger.error(f"send Serverjiang3 xiaoxishibai: {e}")

            import traceback

            logger.debug(traceback.format_exc())

            return False


