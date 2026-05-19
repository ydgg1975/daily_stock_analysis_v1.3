# -*- coding: utf-8 -*-

"""

AstrBot sendtixingfuwu



zhize竊?
1. tongguo Astrbot API send AstrBot xiaoxi

"""

import logging

import json

import hmac

import hashlib

from typing import Optional



import requests



from src.config import Config

from src.formatters import markdown_to_html_document





logger = logging.getLogger(__name__)





class AstrbotSender:

    

    def __init__(self, config: Config):

        """

        chushihua AstrBot config



        Args:

            config: configduixiang

        """

        self._astrbot_config = {

            'astrbot_url': getattr(config, 'astrbot_url', None),

            'astrbot_token': getattr(config, 'astrbot_token', None),

        }

        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

        

    def _is_astrbot_configured(self) -> bool:

        """알림 sender 설명입니다."""

        # zhiyaoconfigle URL竊똨ishiweikeyong

        url_ok = bool(self._astrbot_config['astrbot_url'])

        return url_ok



    def send_to_astrbot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        tuisongxiaoxidao AstrBot竊늯ongguoshipeiqizhichi竊?


        Args:

            content: Markdown geshidexiaoxineirong



        Returns:

            shifousendchenggong

        """

        if self._astrbot_config['astrbot_url']:

            return self._send_astrbot(content, timeout_seconds=timeout_seconds)



        logger.warning("AstrBot configbuwanzheng竊똳iaoguotuisong")

        return False





    def _send_astrbot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        import time

        """

        shiyong Bot API sendxiaoxidao AstrBot



        Args:

            content: Markdown geshidexiaoxineirong



        Returns:

            shifousendchenggong

        """



        html_content = markdown_to_html_document(content)



        try:

            payload = {

                'content': html_content

            }

            signature =  ""

            timestamp = str(int(time.time()))

            if self._astrbot_config['astrbot_token']:

                """알림 sender 설명입니다."""

                payload_json = json.dumps(payload, sort_keys=True)

                sign_data = f"{timestamp}.{payload_json}".encode('utf-8')

                key = self._astrbot_config['astrbot_token']

                signature = hmac.new(

                    key.encode('utf-8'),

                    sign_data,

                    hashlib.sha256

                ).hexdigest()

            url = self._astrbot_config['astrbot_url']

            response = requests.post(

                url, json=payload, timeout=timeout_seconds or 10,

                headers={

                    "Content-Type": "application/json",

                    "X-Signature": signature,

                    "X-Timestamp": timestamp

                },

                verify=self._webhook_verify_ssl

            )



            if response.status_code == 200:

                logger.info("AstrBot xiaoxisendchenggong")

                return True

            else:

                logger.error(f"AstrBot sendshibai: {response.status_code} {response.text}")

                return False

        except Exception as e:

            logger.error(f"AstrBot sendyichang: {e}")

            return False


