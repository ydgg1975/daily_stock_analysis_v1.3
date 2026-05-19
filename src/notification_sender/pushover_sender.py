# -*- coding: utf-8 -*-

"""

Pushover sendtixingfuwu



zhize竊?
1. tongguo Pushover API send Pushover xiaoxi

"""

import logging

from typing import Optional

from datetime import datetime

import requests



from src.config import Config

from src.formatters import markdown_to_plain_text





logger = logging.getLogger(__name__)





class PushoverSender:

    

    def __init__(self, config: Config):

        """

        chushihua Pushover config



        Args:

            config: configduixiang

        """

        self._pushover_config = {

            'user_key': getattr(config, 'pushover_user_key', None),

            'api_token': getattr(config, 'pushover_api_token', None),

        }

        

    def _is_pushover_configured(self) -> bool:

        """알림 sender 설명입니다."""

        return bool(self._pushover_config['user_key'] and self._pushover_config['api_token'])



    def send_to_pushover(

        self,

        content: str,

        title: Optional[str] = None,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        """

        tuisongxiaoxidao Pushover

        

        Pushover API geshi竊?
        POST https://api.pushover.net/1/messages.json

        {

            "token": "yingyong API Token",

            "user": "yonghu Key",

            "message": "xiaoxineirong",

            "title": "biaoti竊늟exuan竊?

        }

        

        Pushover tedian竊?
        - zhichi iOS/Android/zhuomianduopingtaituisong

        - xiaoxixianzhi 1024 zifu

        - zhichiyouxianjishezhi

        - zhichi HTML geshi

        

        Args:

            content: xiaoxineirong竊뉾arkdown geshi竊똦uizhuanweichunwenben竊?
            title: xiaoxibiaoti竊늟exuan竊똫orenwei"stockanalysisbaogao"竊?


        Returns:

            shifousendchenggong

        """

        if not self._is_pushover_configured():

            logger.warning("Pushover configbuwanzheng竊똳iaoguotuisong")

            return False

        

        user_key = self._pushover_config['user_key']

        api_token = self._pushover_config['api_token']

        

        # Pushover API duandian

        api_url = "https://api.pushover.net/1/messages.json"

        

        # chulixiaoxibiaoti

        if title is None:

            date_str = datetime.now().strftime('%Y-%m-%d')

            title = f"?뱢 stockanalysisbaogao - {date_str}"

        

        # Pushover xiaoxixianzhi 1024 zifu

        max_length = 1024

        

        # zhuanhuan Markdown weichunwenben竊늁ushover zhichi HTML竊똡anchunwenbengengtongyong竊?
        plain_content = markdown_to_plain_text(content)

        

        if len(plain_content) <= max_length:

            # dantiaoxiaoxisend

            return self._send_pushover_message(api_url, user_key, api_token, plain_content, title, timeout_seconds=timeout_seconds)

        else:

            # fenduansendzhangxiaoxi

            return self._send_pushover_chunked(

                api_url,

                user_key,

                api_token,

                plain_content,

                title,

                max_length,

                timeout_seconds=timeout_seconds,

            )

      

    def _send_pushover_message(

        self, 

        api_url: str, 

        user_key: str, 

        api_token: str, 

        message: str, 

        title: str,

        priority: int = 0,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        """

        senddantiao Pushover xiaoxi

        

        Args:

            api_url: Pushover API duandian

            user_key: yonghu Key

            api_token: yingyong API Token

            message: xiaoxineirong

            title: xiaoxibiaoti

            priority: youxianji (-2 ~ 2竊똫oren 0)

        """

        try:

            payload = {

                "token": api_token,

                "user": user_key,

                "message": message,

                "title": title,

                "priority": priority,

            }

            

            response = requests.post(api_url, data=payload, timeout=timeout_seconds or 30)

            

            if response.status_code == 200:

                result = response.json()

                if result.get('status') == 1:

                    logger.info("Pushover xiaoxisendchenggong")

                    return True

                else:

                    errors = result.get('errors', ['weizhicuowu'])

                    logger.error(f"Pushover fanhuicuowu: {errors}")

                    return False

            else:

                logger.error(f"Pushover request_failed: HTTP {response.status_code}")

                logger.debug(f"xiangyingneirong: {response.text}")

                return False

                

        except Exception as e:

            logger.error(f"send Pushover xiaoxishibai: {e}")

            return False

    

    def _send_pushover_chunked(

        self, 

        api_url: str, 

        user_key: str, 

        api_token: str, 

        content: str, 

        title: str,

        max_length: int,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        """

        fenduansendzhang Pushover xiaoxi

        

        anduanluofenge竊똰uebaomeiduanbuchaoguozuidachangdu

        """

        import time

        

        # anduanluo竊늗engexianhuoshuanghuanhang竊뎕enge

        if "????????" in content:

            sections = content.split("????????")

            separator = "????????"

        else:

            sections = content.split("\n\n")

            separator = "\n\n"

        

        chunks = []

        current_chunk = []

        current_length = 0

        

        for section in sections:

            # jisuanaddzhege section houdeshijichangdu

            # join() zhizaiyuansuzhijianfangzhifengefu竊똟ushimeigeyuansuhoumian

            # suoyi竊쉊iyigeyuansubuxuyaofengefu竊똦ouxuyuansuxuyaoyigefengefulianjie

            if current_chunk:

                # yiyouyuansu竊똳ianjiaxinyuansuxuyao竊쉊angqianchangdu + fengefu + xin section

                new_length = current_length + len(separator) + len(section)

            else:

                # diyigeyuansu竊똟uxuyaofengefu

                new_length = len(section)

            

            if new_length > max_length:

                if current_chunk:

                    chunks.append(separator.join(current_chunk))

                current_chunk = [section]

                current_length = len(section)

            else:

                current_chunk.append(section)

                current_length = new_length

        

        if current_chunk:

            chunks.append(separator.join(current_chunk))

        

        total_chunks = len(chunks)

        success_count = 0

        

        logger.info(f"Pushover fenpisend竊쉍ong {total_chunks} pi")

        

        for i, chunk in enumerate(chunks):

            # addfenyebiaojidaobiaoti

            chunk_title = f"{title} ({i+1}/{total_chunks})" if total_chunks > 1 else title

            

            if self._send_pushover_message(

                api_url,

                user_key,

                api_token,

                chunk,

                chunk_title,

                timeout_seconds=timeout_seconds,

            ):

                success_count += 1

                logger.info(f"Pushover di {i+1}/{total_chunks} pisendchenggong")

            else:

                logger.error(f"Pushover di {i+1}/{total_chunks} pisendshibai")

            

            # picijiange竊똟imianchufapinlvxianzhi

            if i < total_chunks - 1:

                time.sleep(1)



        return success_count == total_chunks


