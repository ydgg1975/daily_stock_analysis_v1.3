# -*- coding: utf-8 -*-

"""

feishu sendtixingfuwu



zhize竊?
1. tongguo webhook sendfeishuxiaoxi

"""

import base64

import hashlib

import hmac

import logging

import time

from typing import Any, Dict, Optional



import requests



from src.config import Config

from src.formatters import (

    MIN_MAX_BYTES,

    PAGE_MARKER_SAFE_BYTES,

    chunk_content_by_max_bytes,

    format_feishu_markdown,

)





logger = logging.getLogger(__name__)





class FeishuSender:

    

    def __init__(self, config: Config):

        """

        chushihuafeishuconfig



        Args:

            config: configduixiang

        """

        self._feishu_url = getattr(config, 'feishu_webhook_url', None)

        self._feishu_secret = (getattr(config, 'feishu_webhook_secret', None) or '').strip()

        self._feishu_keyword = (getattr(config, 'feishu_webhook_keyword', None) or '').strip()

        self._feishu_max_bytes = getattr(config, 'feishu_max_bytes', 20000)

        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)



    def _get_keyword_prefix(self) -> str:

        """알림 sender 설명입니다."""

        if not self._feishu_keyword:

            return ""

        return f"{self._feishu_keyword}\n"



    def _apply_keyword_prefix(self, content: str) -> str:

        """알림 sender 설명입니다."""

        prefix = self._get_keyword_prefix()

        if not prefix:

            return content

        return f"{prefix}{content}" if content else self._feishu_keyword



    def _build_security_fields(self) -> Dict[str, str]:

        """알림 sender 설명입니다."""

        if not self._feishu_secret:

            return {}



        timestamp = str(int(time.time()))

        string_to_sign = f"{timestamp}\n{self._feishu_secret}"

        sign = base64.b64encode(

            hmac.new(

                string_to_sign.encode('utf-8'),

                digestmod=hashlib.sha256,

            ).digest()

        ).decode('utf-8')

        return {

            "timestamp": timestamp,

            "sign": sign,

        }

    

          

    def send_to_feishu(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        tuisongxiaoxidaofeishujiqiren

        

        feishuzidingyijiqiren Webhook xiaoxigeshi竊?
        {

            "msg_type": "interactive",

            "card": {

                "config": { "wide_screen_mode": true },

                "elements": [

                    {

                        "tag": "div",

                        "text": {

                            "tag": "lark_md",

                            "content": "..."

                        }

                    }

                ],

                "header": {

                    "title": {

                        "tag": "plain_text",

                        "content": "Aguzhinenganalysisbaogao"

                    }

                }

            }

        }

        

        shuoming竊쉌eishuwenbenxiaoxibuhuixuanran Markdown竊똸ushiyongjiaohukapian竊늢ark_md竊뎖eshi

        

        zhuyi竊쉌eishuwenbenxiaoxixianzhiyue 20KB竊똠haochangneironghuizidongfenpisend

        ketongguohuanjingbianliang FEISHU_MAX_BYTES tiaozhengxianzhizhi

        

        Args:

            content: xiaoxineirong竊뉾arkdown huizhuanweichunwenben竊?
            

        Returns:

            shifousendchenggong

        """

        if not self._feishu_url:

            logger.warning("feishu Webhook weiconfig竊똳iaoguotuisong")

            return False

        

        # feishu lark_md zhichiyouxian竊똸ianzuogeshizhuanhuan

        formatted_content = format_feishu_markdown(content)



        max_bytes = self._feishu_max_bytes  # congconfigduqu竊똫oren 20000 zijie

        keyword_overhead = len(self._get_keyword_prefix().encode('utf-8'))

        effective_max_bytes = max_bytes - keyword_overhead



        if effective_max_bytes <= 0:

            logger.error("feishuguanjianciguochang竊똠haoguodantiaoxiaoxiyunxudezuidazijieshu竊똷ufasend")

            return False

        

        # jianchazijiechangdu竊똠haochangzefenpisend

        content_bytes = len(formatted_content.encode('utf-8')) + keyword_overhead

        if content_bytes > max_bytes:

            min_chunk_bytes = MIN_MAX_BYTES + PAGE_MARKER_SAFE_BYTES

            if effective_max_bytes < min_chunk_bytes:

                logger.error(

                    "feishuguanjianciguochang竊똲hengyufenpianyusuan(%szijie)buzuyianquanfenyesend竊똺hishaoxuyao %s zijie",

                    effective_max_bytes,

                    min_chunk_bytes,

                )

                return False

            logger.info(f"feishuxiaoxineirongchaochang({content_bytes}zijie/{len(content)}zifu)竊똨iangfenpisend")

            return self._send_feishu_chunked(formatted_content, effective_max_bytes)

        

        try:

            return self._send_feishu_message(formatted_content, timeout_seconds=timeout_seconds)

        except Exception as e:

            logger.error(f"sendfeishuxiaoxishibai: {e}")

            return False

   

    def _send_feishu_chunked(self, content: str, max_bytes: int) -> bool:

        """

        fenpisendzhangxiaoxidaofeishu

        

        anstockanalysiskuai竊늶i --- huo ### fenge竊뎭hinengfenge竊똰uebaomeipibuchaoguoxianzhi

        

        Args:

            content: wanzhengxiaoxineirong

            max_bytes: dantiaoxiaoxizuidazijieshu

            

        Returns:

            shifouquanbusendchenggong

        """

        try:

            chunks = chunk_content_by_max_bytes(content, max_bytes, add_page_marker=True)

        except ValueError as e:

            logger.error("feishuxiaoxifenpianshibai竊똡anpianyusuanbuzuyianquanfenye竊늛uanjianciguochanghuo max_bytes guoxiao竊? %s", e)

            return False

        

        # fenpisend

        total_chunks = len(chunks)

        success_count = 0

        

        logger.info(f"feishufenpisend竊쉍ong {total_chunks} pi")

        

        for i, chunk in enumerate(chunks):

            try:

                if self._send_feishu_message(chunk):

                    success_count += 1

                    logger.info(f"feishudi {i+1}/{total_chunks} pisendchenggong")

                else:

                    logger.error(f"feishudi {i+1}/{total_chunks} pisendshibai")

            except Exception as e:

                logger.error(f"feishudi {i+1}/{total_chunks} pisendyichang: {e}")

            

            # picijiange竊똟imianchufapinlvxianzhi

            if i < total_chunks - 1:

                time.sleep(1)

        

        return success_count == total_chunks

    

    def _send_feishu_message(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """알림 sender 설명입니다."""

        prepared_content = self._apply_keyword_prefix(content)

        security_fields = self._build_security_fields()



        def _post_payload(payload: Dict[str, Any]) -> bool:

            request_payload = dict(payload)

            request_payload.update(security_fields)

            logger.debug(f"feishuqingqiu URL: {self._feishu_url}")

            logger.debug(f"feishuqingqiu payload changdu: {len(prepared_content)} zifu")



            response = requests.post(

                self._feishu_url,

                json=request_payload,

                timeout=timeout_seconds or 30,

                verify=self._webhook_verify_ssl

            )



            logger.debug(f"feishuxiangyingzhuangtaima: {response.status_code}")

            logger.debug(f"feishuxiangyingneirong: {response.text}")



            if response.status_code == 200:

                result = response.json()

                code = result.get('code') if 'code' in result else result.get('StatusCode')

                if code == 0:

                    logger.info("feishuxiaoxisendchenggong")

                    return True

                else:

                    error_msg = result.get('msg') or result.get('StatusMessage', 'weizhicuowu')

                    error_code = result.get('code') or result.get('StatusCode', 'N/A')

                    logger.error(f"feishufanhuicuowu [code={error_code}]: {error_msg}")

                    logger.error(f"wanzhengxiangying: {result}")

                    return False

            else:

                logger.error(f"feishurequest_failed: HTTP {response.status_code}")

                logger.error(f"xiangyingneirong: {response.text}")

                return False



        # 1) youxianshiyongjiaohukapian竊늷hichi Markdown xuanran竊?
        card_payload = {

            "msg_type": "interactive",

            "card": {

                "config": {"wide_screen_mode": True},

                "header": {

                    "title": {

                        "tag": "plain_text",

                        "content": "stockzhinenganalysisbaogao"

                    }

                },

                "elements": [

                    {

                        "tag": "div",

                        "text": {

                            "tag": "lark_md",

                            "content": prepared_content

                        }

                    }

                ]

            }

        }



        if _post_payload(card_payload):

            return True



        # 2) huituiweiputongwenbenxiaoxi

        text_payload = {

            "msg_type": "text",

            "content": {

                "text": prepared_content

            }

        }



        return _post_payload(text_payload)


