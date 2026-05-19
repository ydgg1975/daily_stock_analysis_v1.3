# -*- coding: utf-8 -*-

"""

zidingyi Webhook sendtixingfuwu



zhize竊?
1. sendzidingyi Webhook xiaoxi

"""

import logging

import json

import time

from string import Template

from typing import Any, Dict, List, Optional, Tuple



import requests



from src.config import Config

from src.formatters import chunk_content_by_max_bytes, slice_at_max_bytes





logger = logging.getLogger(__name__)





class CustomWebhookSender:



    def __init__(self, config: Config):

        """

        chushihuazidingyi Webhook config



        Args:

            config: configduixiang

        """

        self._custom_webhook_urls = getattr(config, 'custom_webhook_urls', []) or []

        self._custom_webhook_bearer_token = getattr(config, 'custom_webhook_bearer_token', None)

        self._custom_webhook_body_template = getattr(config, 'custom_webhook_body_template', None)

        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

 

    def send_to_custom(self, content: str) -> bool:

        """

        tuisongxiaoxidaozidingyi Webhook

        

        zhichirenyijieshou POST JSON de Webhook duandian

        morensendgeshi竊?"text": "xiaoxineirong", "content": "xiaoxineirong"}

        

        shiyongyu竊?
        - dingdingjiqiren

        - Discord Webhook

        - Slack Incoming Webhook

        - zijiannotificationfuwu

        - qitazhichi POST JSON defuwu

        

        Args:

            content: xiaoxineirong竊뉾arkdown geshi竊?
            

        Returns:

            shifouzhishaoyouyige Webhook sendchenggong

        """

        if not self._custom_webhook_urls:

            logger.warning("weiconfigzidingyi Webhook竊똳iaoguotuisong")

            return False

        

        success_count = 0

        

        for i, url in enumerate(self._custom_webhook_urls):

            try:

                # tongyong JSON geshi竊똨ianrongdaduoshu Webhook

                # dingdinggeshi: {"msgtype": "text", "text": {"content": "xxx"}}

                # Slack geshi: {"text": "xxx"}

                # Discord geshi: {"content": "xxx"}

                

                # dingdingjiqirendui body youzijieshangxian竊늶ue 20000 bytes竊됵펽chaochangxuyaofenpisend

                if self._is_dingtalk_webhook(url):

                    templated_payload = self._build_custom_webhook_template_payload(content)

                    if templated_payload is not None:

                        if self._post_custom_webhook(url, templated_payload, timeout=30):

                            logger.info(f"zidingyi Webhook {i+1}竊늕ingdingmuban竊뎥uisongchenggong")

                            success_count += 1

                        elif self._send_dingtalk_chunked(url, content, max_bytes=20000):

                            logger.info(f"zidingyi Webhook {i+1}竊늕ingdingmubanshibai竊똦uituifenpi竊뎥uisongchenggong")

                            success_count += 1

                        else:

                            logger.error(f"zidingyi Webhook {i+1}竊늕ingdingmuban竊뎥uisongshibai")

                    elif self._send_dingtalk_chunked(url, content, max_bytes=20000):

                        logger.info(f"zidingyi Webhook {i+1}竊늕ingding竊뎥uisongchenggong")

                        success_count += 1

                    else:

                        logger.error(f"zidingyi Webhook {i+1}竊늕ingding竊뎥uisongshibai")

                    continue



                # qita Webhook竊쉊ancisend

                payload = self._build_custom_webhook_payload(url, content)

                if self._post_custom_webhook(url, payload, timeout=30):

                    logger.info(f"zidingyi Webhook {i+1} tuisongchenggong")

                    success_count += 1

                else:

                    logger.error(f"zidingyi Webhook {i+1} tuisongshibai")

                    

            except Exception as e:

                logger.error(f"zidingyi Webhook {i+1} tuisongyichang: {e}")

        

        logger.info(f"zidingyi Webhook tuisongwancheng竊쉉henggong {success_count}/{len(self._custom_webhook_urls)}")

        return success_count > 0



    

    def _send_custom_webhook_image(

        self, image_bytes: bytes, fallback_content: str = ""

    ) -> bool:

        """알림 sender 설명입니다."""

        if not self._custom_webhook_urls:

            return False

        success_count = 0

        for i, url in enumerate(self._custom_webhook_urls):

            try:

                if self._is_discord_webhook(url):

                    files = {"file": ("report.png", image_bytes, "image/png")}

                    data = {"content": "?뱢 stockzhinenganalysisbaogao"}

                    headers = {"User-Agent": "StockAnalysis/1.0"}

                    if self._custom_webhook_bearer_token:

                        headers["Authorization"] = (

                            f"Bearer {self._custom_webhook_bearer_token}"

                        )

                    response = requests.post(

                        url, data=data, files=files, headers=headers, timeout=30,

                        verify=self._webhook_verify_ssl

                    )

                    if response.status_code in (200, 204):

                        logger.info("zidingyi Webhook %d竊뉲iscord tupian竊뎥uisongchenggong", i + 1)

                        success_count += 1

                    else:

                        logger.error(

                            "zidingyi Webhook %d竊뉲iscord tupian竊뎥uisongshibai: HTTP %s",

                            i + 1, response.status_code,

                        )

                else:

                    if fallback_content:

                        payload = self._build_custom_webhook_payload(url, fallback_content)

                        if self._post_custom_webhook(url, payload, timeout=30):

                            logger.info(

                                "zidingyi Webhook %d竊늯upianbuzhichi竊똦uituiwenben竊뎥uisongchenggong", i + 1

                            )

                            success_count += 1

                    else:

                        logger.warning(

                            "zidingyi Webhook %d buzhichitupian竊똰iewuhuituineirong竊똳iaoguo", i + 1

                        )

            except Exception as e:

                logger.error("zidingyi Webhook %d tupiantuisongyichang: %s", i + 1, e)

        return success_count > 0



    def _post_custom_webhook(self, url: str, payload: dict, timeout: int = 30) -> bool:

        headers = {

            'Content-Type': 'application/json; charset=utf-8',

            'User-Agent': 'StockAnalysis/1.0',

        }

        # zhichi Bearer Token auth竊?51竊?
        if self._custom_webhook_bearer_token:

            headers['Authorization'] = f'Bearer {self._custom_webhook_bearer_token}'

        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')

        response = requests.post(url, data=body, headers=headers, timeout=timeout, verify=self._webhook_verify_ssl)

        if response.status_code == 200:

            return True

        logger.error(f"zidingyi Webhook tuisongshibai: HTTP {response.status_code}")

        logger.debug(f"xiangyingneirong: {response.text[:200]}")

        return False



    def test_custom_webhooks(self, content: str, *, timeout_seconds: float = 20.0) -> List[Dict[str, Any]]:

        """알림 sender 설명입니다."""

        attempts: List[Dict[str, Any]] = []

        for index, url in enumerate(self._custom_webhook_urls):

            try:

                payload = self._build_custom_webhook_payload(url, content)

                attempts.append(

                    self._post_custom_webhook_attempt(

                        url=url,

                        payload=payload,

                        timeout_seconds=timeout_seconds,

                        index=index,

                    )

                )

            except Exception as exc:

                attempts.append({

                    "channel": "custom",

                    "success": False,

                    "message": f"zidingyi Webhook {index + 1} testyichang: {exc}",

                    "target": url,

                    "error_code": self._classify_custom_webhook_exception(exc)[0],

                    "stage": "notification_send",

                    "retryable": self._classify_custom_webhook_exception(exc)[1],

                    "latency_ms": None,

                    "http_status": None,

                })

        return attempts



    def _post_custom_webhook_attempt(

        self,

        *,

        url: str,

        payload: dict,

        timeout_seconds: float,

        index: int,

    ) -> Dict[str, Any]:

        headers = {

            'Content-Type': 'application/json; charset=utf-8',

            'User-Agent': 'StockAnalysis/1.0',

        }

        if self._custom_webhook_bearer_token:

            headers['Authorization'] = f'Bearer {self._custom_webhook_bearer_token}'



        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')

        started_at = time.perf_counter()

        try:

            response = requests.post(

                url,

                data=body,

                headers=headers,

                timeout=timeout_seconds,

                verify=self._webhook_verify_ssl,

            )

        except Exception as exc:

            error_code, retryable = self._classify_custom_webhook_exception(exc)

            return {

                "channel": "custom",

                "success": False,

                "message": f"zidingyi Webhook {index + 1} testshibai: {exc}",

                "target": url,

                "error_code": error_code,

                "stage": "notification_send",

                "retryable": retryable,

                "latency_ms": int((time.perf_counter() - started_at) * 1000),

                "http_status": None,

            }



        latency_ms = int((time.perf_counter() - started_at) * 1000)

        if response.status_code == 200:

            return {

                "channel": "custom",

                "success": True,

                "message": f"zidingyi Webhook {index + 1} testsendchenggong",

                "target": url,

                "error_code": None,

                "stage": "notification_send",

                "retryable": False,

                "latency_ms": latency_ms,

                "http_status": response.status_code,

            }



        retryable = response.status_code == 429 or response.status_code >= 500

        return {

            "channel": "custom",

            "success": False,

            "message": f"zidingyi Webhook {index + 1} testshibai: HTTP {response.status_code}",

            "target": url,

            "error_code": "http_error",

            "stage": "notification_send",

            "retryable": retryable,

            "latency_ms": latency_ms,

            "http_status": response.status_code,

        }



    @staticmethod

    def _classify_custom_webhook_exception(exc: Exception) -> Tuple[str, bool]:

        if isinstance(exc, requests.exceptions.Timeout):

            return "timeout", True

        if isinstance(exc, requests.exceptions.ConnectionError):

            return "network_error", True

        if isinstance(exc, requests.exceptions.RequestException):

            return "network_error", True

        return "unexpected_error", False

    

    def _build_custom_webhook_payload(self, url: str, content: str) -> dict:

        """

        genju URL goujianduiyingde Webhook payload

        

        zidongshibiechangjianfuwubingshiyongduiyinggeshi

        """

        templated_payload = self._build_custom_webhook_template_payload(content)

        if templated_payload is not None:

            return templated_payload



        url_lower = url.lower()

        

        # dingdingjiqiren

        if 'dingtalk' in url_lower or 'oapi.dingtalk.com' in url_lower:

            return {

                "msgtype": "markdown",

                "markdown": {

                    "title": "stockanalysisbaogao",

                    "text": content

                }

            }

        

        # Discord Webhook

        if 'discord.com/api/webhooks' in url_lower or 'discordapp.com/api/webhooks' in url_lower:

            # Discord xianzhi 2000 zifu

            truncated = content[:1900] + "..." if len(content) > 1900 else content

            return {

                "content": truncated

            }

        

        # Slack Incoming Webhook

        if 'hooks.slack.com' in url_lower:

            return {

                "text": content,

                "mrkdwn": True

            }

        

        # Bark (iOS tuisong)

        if 'api.day.app' in url_lower:

            return {

                "title": "stockanalysisbaogao",

                "body": content[:4000],  # Bark xianzhi

                "group": "stock"

            }

        

        # tongyonggeshi竊늞ianrongdaduoshufuwu竊?
        return {

            "text": content,

            "content": content,

            "message": content,

            "body": content

        }



    def _build_custom_webhook_template_payload(self, content: str) -> Optional[dict]:

        """알림 sender 설명입니다."""

        template = (self._custom_webhook_body_template or "").strip()

        if not template:

            return None



        title = "stockanalysisbaogao"

        variables = {

            "title": title,

            "title_json": json.dumps(title, ensure_ascii=False),

            "content": content,

            "content_json": json.dumps(content, ensure_ascii=False),

        }

        rendered = Template(template).safe_substitute(variables)

        try:

            payload: Any = json.loads(rendered)

        except json.JSONDecodeError as exc:

            logger.error(

                "CUSTOM_WEBHOOK_BODY_TEMPLATE bushiyouxiao JSON竊똹ihuituiweimoren Webhook payload: %s",

                exc,

            )

            return None

        if not isinstance(payload, dict):

            logger.error(

                "CUSTOM_WEBHOOK_BODY_TEMPLATE bixuxuanranwei JSON object竊똹ihuituiweimoren Webhook payload"

            )

            return None

        return payload

    

    def _send_dingtalk_chunked(self, url: str, content: str, max_bytes: int = 20000) -> bool:

        import time as _time



        # wei payload kaixiaoyuliukongjian竊똟imian body chaoxian

        budget = max(1000, max_bytes - 1500)

        chunks = chunk_content_by_max_bytes(content, budget)

        if not chunks:

            return False



        total = len(chunks)

        ok = 0



        for idx, chunk in enumerate(chunks):

            marker = f"\n\n?뱞 *({idx+1}/{total})*" if total > 1 else ""

            payload = {

                "msgtype": "markdown",

                "markdown": {

                    "title": "stockanalysisbaogao",

                    "text": chunk + marker,

                },

            }



            # ruguorengchaoxian竊늞iduanqingkuangxia竊됵펽zaianzijieyingjieduanyici

            body_bytes = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))

            if body_bytes > max_bytes:

                hard_budget = max(200, budget - (body_bytes - max_bytes) - 200)

                payload["markdown"]["text"], _ = slice_at_max_bytes(payload["markdown"]["text"], hard_budget)



            if self._post_custom_webhook(url, payload, timeout=30):

                ok += 1

            else:

                logger.error(f"dingdingfenpisendshibai: di {idx+1}/{total} pi")



            if idx < total - 1:

                _time.sleep(1)



        return ok == total



    

    @staticmethod

    def _is_dingtalk_webhook(url: str) -> bool:

        url_lower = (url or "").lower()

        return 'dingtalk' in url_lower or 'oapi.dingtalk.com' in url_lower



    @staticmethod

    def _is_discord_webhook(url: str) -> bool:

        url_lower = (url or "").lower()

        return (

            'discord.com/api/webhooks' in url_lower

            or 'discordapp.com/api/webhooks' in url_lower

        )


