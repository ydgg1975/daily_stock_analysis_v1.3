# -*- coding: utf-8 -*-

"""

Wechat sendtixingfuwu



zhize竊?
1. tongguoqiyeweixin Webhook sendwenbenxiaoxi

2. tongguoqiyeweixin Webhook sendtupianxiaoxi

"""

import logging

import base64

import hashlib

import requests

import time

from typing import Optional



from src.config import Config

from src.formatters import chunk_content_by_max_bytes





logger = logging.getLogger(__name__)





# WeChat Work image msgtype limit ~2MB (base64 payload)

WECHAT_IMAGE_MAX_BYTES = 2 * 1024 * 1024



class WechatSender:

    

    def __init__(self, config: Config):

        """

        chushihuaqiyeweixinconfig



        Args:

            config: configduixiang

        """

        self._wechat_url = config.wechat_webhook_url

        self._wechat_max_bytes = getattr(config, 'wechat_max_bytes', 4000)

        self._wechat_msg_type = getattr(config, 'wechat_msg_type', 'markdown')

        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

        

    def send_to_wechat(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        tuisongxiaoxidaoqiyeweixinjiqiren

        

        qiyeweixin Webhook xiaoxigeshi竊?
        zhichi markdown leixingyiji text leixing, markdown leixingzaiweixinzhongwufazhanshi竊똩eyishiyong text leixing,

        markdown leixinghuijiexi markdown geshi,text leixinghuizhijiesendchunwenben??


        markdown leixingshili竊?
        {

            "msgtype": "markdown",

            "markdown": {

                "content": "## biaoti\n\nneirong"

            }

        }

        

        text leixingshili竊?
        {

            "msgtype": "text",

            "text": {

                "content": "neirong"

            }

        }



        zhuyi竊쉛iyeweixin Markdown xianzhi 4096 zijie竊늗eizifu竊? Text leixingxianzhi 2048 zijie竊똠haochangneironghuizidongfenpisend

        ketongguohuanjingbianliang WECHAT_MAX_BYTES tiaozhengxianzhizhi

        

        Args:

            content: Markdown geshidexiaoxineirong

            

        Returns:

            shifousendchenggong

        """

        if not self._wechat_url:

            logger.warning("qiyeweixin Webhook weiconfig竊똳iaoguotuisong")

            return False

        

        # genjuxiaoxileixingdongtaixianzhishangxian竊똟imian text leixingchaoguoqiyeweixin 2048 zijiexianzhi

        if self._wechat_msg_type == 'text':

            max_bytes = min(self._wechat_max_bytes, 2000)  # yuliuyidingzijiegeixitong/fenyebiaoji

        else:

            max_bytes = self._wechat_max_bytes  # markdown moren 4000 zijie

        

        # jianchazijiechangdu竊똠haochangzefenpisend

        content_bytes = len(content.encode('utf-8'))

        if content_bytes > max_bytes:

            logger.info(f"xiaoxineirongchaochang({content_bytes}zijie/{len(content)}zifu)竊똨iangfenpisend")

            return self._send_wechat_chunked(content, max_bytes)

        

        try:

            return self._send_wechat_message(content, timeout_seconds=timeout_seconds)

        except Exception as e:

            logger.error(f"sendqiyeweixinxiaoxishibai: {e}")

            return False



    def _send_wechat_image(self, image_bytes: bytes) -> bool:

        """알림 sender 설명입니다."""

        if not self._wechat_url:

            return False

        if len(image_bytes) > WECHAT_IMAGE_MAX_BYTES:

            logger.warning(

                "qiyeweixintupianchaoxian (%d > %d bytes)竊똨ujuesend竊똡iaoyongfangying fallback weiwenben",

                len(image_bytes), WECHAT_IMAGE_MAX_BYTES,

            )

            return False

        try:

            b64 = base64.b64encode(image_bytes).decode("ascii")

            md5_hash = hashlib.md5(image_bytes).hexdigest()

            payload = {

                "msgtype": "image",

                "image": {"base64": b64, "md5": md5_hash},

            }

            response = requests.post(

                self._wechat_url, json=payload, timeout=30, verify=self._webhook_verify_ssl

            )

            if response.status_code == 200:

                result = response.json()

                if result.get("errcode") == 0:

                    logger.info("qiyeweixintupiansendchenggong")

                    return True

                logger.error("qiyeweixintupiansendshibai: %s", result.get("errmsg", ""))

            else:

                logger.error("qiyeweixinrequest_failed: HTTP %s", response.status_code)

            return False

        except Exception as e:

            logger.error("qiyeweixintupiansendyichang: %s", e)

            return False

    

    def _send_wechat_message(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """알림 sender 설명입니다."""

        payload = self._gen_wechat_payload(content)

        

        response = requests.post(

            self._wechat_url,

            json=payload,

            timeout=timeout_seconds or 10,

            verify=self._webhook_verify_ssl

        )

        

        if response.status_code == 200:

            result = response.json()

            if result.get('errcode') == 0:

                logger.info("qiyeweixinxiaoxisendchenggong")

                return True

            else:

                logger.error(f"qiyeweixinfanhuicuowu: {result}")

                return False

        else:

            logger.error(f"qiyeweixinrequest_failed: {response.status_code}")

            return False

        

    def _send_wechat_chunked(self, content: str, max_bytes: int) -> bool:

        """

        fenpisendzhangxiaoxidaoqiyeweixin

        

        anstockanalysiskuai竊늶i --- huo ### fenge竊뎭hinengfenge竊똰uebaomeipibuchaoguoxianzhi

        

        Args:

            content: wanzhengxiaoxineirong

            max_bytes: dantiaoxiaoxizuidazijieshu

            

        Returns:

            shifouquanbusendchenggong

        """

        chunks = chunk_content_by_max_bytes(content, max_bytes, add_page_marker=True)

        total_chunks = len(chunks)

        success_count = 0

        for i, chunk in enumerate(chunks):

            if self._send_wechat_message(chunk):

                success_count += 1

            else:

                logger.error(f"qiyeweixindi {i+1}/{total_chunks} pisendshibai")

            if i < total_chunks - 1:

                time.sleep(1)

        return success_count == len(chunks)



    def _gen_wechat_payload(self, content: str) -> dict:

        """알림 sender 설명입니다."""

        if self._wechat_msg_type == 'text':

            return {

                "msgtype": "text",

                "text": {

                    "content": content

                }

            }

        else:

            return {

                "msgtype": "markdown",

                "markdown": {

                    "content": content

                }

            }


