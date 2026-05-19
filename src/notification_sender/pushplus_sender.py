# -*- coding: utf-8 -*-

"""

PushPlus sendtixingfuwu



zhize竊?
1. tongguo PushPlus API send PushPlus xiaoxi

"""

import logging

import time

from typing import Optional

from datetime import datetime

import requests



from src.config import Config

from src.formatters import chunk_content_by_max_bytes





logger = logging.getLogger(__name__)





class PushplusSender:

    

    def __init__(self, config: Config):

        """

        chushihua PushPlus config



        Args:

            config: configduixiang

        """

        self._pushplus_token = getattr(config, 'pushplus_token', None)

        self._pushplus_topic = getattr(config, 'pushplus_topic', None)

        self._pushplus_max_bytes = getattr(config, 'pushplus_max_bytes', 20000)

        

    def send_to_pushplus(

        self,

        content: str,

        title: Optional[str] = None,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        """

        tuisongxiaoxidao PushPlus



        PushPlus API geshi竊?
        POST http://www.pushplus.plus/send

        {

            "token": "yonghulingpai",

            "title": "xiaoxibiaoti",

            "content": "xiaoxineirong",

            "template": "html/txt/json/markdown"

        }



        PushPlus tedian竊?
        - guoneituisongfuwu竊똫ianfeieduchongzu

        - zhichiweixingongzhonghaotuisong

        - zhichiduozhongxiaoxigeshi



        Args:

            content: xiaoxineirong竊뉾arkdown geshi竊?
            title: xiaoxibiaoti竊늟exuan竊?


        Returns:

            shifousendchenggong

        """

        if not self._pushplus_token:

            logger.warning("PushPlus Token weiconfig竊똳iaoguotuisong")

            return False



        api_url = "http://www.pushplus.plus/send"



        if title is None:

            date_str = datetime.now().strftime('%Y-%m-%d')

            title = f"?뱢 stockanalysisbaogao - {date_str}"



        try:

            content_bytes = len(content.encode('utf-8'))

            if content_bytes > self._pushplus_max_bytes:

                logger.info(

                    "PushPlus xiaoxineirongchaochang(%szijie/%szifu)竊똨iangfenpisend",

                    content_bytes,

                    len(content),

                )

                return self._send_pushplus_chunked(

                    api_url,

                    content,

                    title,

                    self._pushplus_max_bytes,

                )



            return self._send_pushplus_message(api_url, content, title, timeout_seconds=timeout_seconds)

        except Exception as e:

            logger.error(f"send PushPlus xiaoxishibai: {e}")

            return False



    def _send_pushplus_message(

        self,

        api_url: str,

        content: str,

        title: str,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        payload = {

            "token": self._pushplus_token,

            "title": title,

            "content": content,

            "template": "markdown",

        }



        if self._pushplus_topic:

            payload["topic"] = self._pushplus_topic



        response = requests.post(api_url, json=payload, timeout=timeout_seconds or 10)



        if response.status_code == 200:

            result = response.json()

            if result.get('code') == 200:

                logger.info("PushPlus xiaoxisendchenggong")

                return True



            error_msg = result.get('msg', 'weizhicuowu')

            logger.error(f"PushPlus fanhuicuowu: {error_msg}")

            return False



        logger.error(f"PushPlus request_failed: HTTP {response.status_code}")

        return False



    def _send_pushplus_chunked(self, api_url: str, content: str, title: str, max_bytes: int) -> bool:

        """알림 sender 설명입니다."""

        budget = max(1000, max_bytes - 1500)

        chunks = chunk_content_by_max_bytes(content, budget, add_page_marker=True)

        total_chunks = len(chunks)

        success_count = 0



        logger.info(f"PushPlus fenpisend竊쉍ong {total_chunks} pi")



        for i, chunk in enumerate(chunks):

            chunk_title = f"{title} ({i+1}/{total_chunks})" if total_chunks > 1 else title

            if self._send_pushplus_message(api_url, chunk, chunk_title):

                success_count += 1

                logger.info(f"PushPlus di {i+1}/{total_chunks} pisendchenggong")

            else:

                logger.error(f"PushPlus di {i+1}/{total_chunks} pisendshibai")



            if i < total_chunks - 1:

                time.sleep(1)



        return success_count == total_chunks


