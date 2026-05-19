# -*- coding: utf-8 -*-

"""

Slack sendtixingfuwu



zhize竊?
1. tongguo Slack Bot API huo Incoming Webhook send Slack xiaoxi

   竊늯ongshiconfigshiyouxianshiyong Bot API竊똰uebaowenbenyutupiansenddaotongyipindao竊?
"""

import logging

import json

from typing import Optional



import requests



from src.config import Config

from src.formatters import chunk_content_by_max_bytes



logger = logging.getLogger(__name__)



# Slack Block Kit zhongdange section block de text ziduanshangxianwei 3000 zifu

_BLOCK_TEXT_LIMIT = 3000

# Slack chat.postMessage / Webhook de text ziduanshangxianyue 40000 zifu竊똟aoshouqu 39000

_TEXT_LIMIT = 39000





class SlackSender:



    def __init__(self, config: Config):

        """

        chushihua Slack config



        Args:

            config: configduixiang

        """

        self._slack_webhook_url = getattr(config, 'slack_webhook_url', None)

        self._slack_bot_token = getattr(config, 'slack_bot_token', None)

        self._slack_channel_id = getattr(config, 'slack_channel_id', None)

        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)



    @property

    def _use_bot(self) -> bool:

        """알림 sender 설명입니다."""

        return bool(self._slack_bot_token and self._slack_channel_id)



    def _is_slack_configured(self) -> bool:

        """알림 sender 설명입니다."""

        return self._use_bot or bool(self._slack_webhook_url)



    def send_to_slack(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        tuisongxiaoxidao Slack竊늷hichi Webhook he Bot API竊?


        chuanshuyouxianjiyu _send_slack_image() baochiyizhi竊숥ot > Webhook竊?
        bimianwenbenzou Webhook?걎upianzou Bot daozhixiaoxiluorubutongpindao??


        Args:

            content: Markdown geshidexiaoxineirong



        Returns:

            shifousendchenggong

        """

        # anzijiefenkuai竊똟imiandantiaoxiaoxichaoxian

        try:

            chunks = chunk_content_by_max_bytes(content, _TEXT_LIMIT, add_page_marker=True)

        except Exception as e:

            logger.error(f"Slack 메시지 분할 실패: {e}. 전체 메시지 전송을 시도합니다.")

            chunks = [content]



        # youxianshiyong Bot API竊늶u _send_slack_image baochiyizhi竊?
        if self._use_bot:

            return all(self._send_slack_bot(chunk, timeout_seconds=timeout_seconds) for chunk in chunks)



        # qicishiyong Webhook

        if self._slack_webhook_url:

            return all(self._send_slack_webhook(chunk, timeout_seconds=timeout_seconds) for chunk in chunks)



        logger.warning("Slack configbuwanzheng竊똳iaoguotuisong")

        return False



    def _build_blocks(self, content: str) -> list:

        """

        jiangneironggoujianwei Slack Block Kit geshi



        ruguoneirongchaoguodange section block xianzhi竊똦uizidongchaifenweiduoge block??
        """

        blocks = []

        # an block text shangxianchaifen

        pos = 0

        while pos < len(content):

            segment = content[pos:pos + _BLOCK_TEXT_LIMIT]

            blocks.append({

                "type": "section",

                "text": {

                    "type": "mrkdwn",

                    "text": segment

                }

            })

            pos += _BLOCK_TEXT_LIMIT

        return blocks



    def _send_slack_webhook(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        shiyong Incoming Webhook sendxiaoxidao Slack



        Args:

            content: xiaoxineirong



        Returns:

            shifousendchenggong

        """

        try:

            payload = {

                "text": content,

                "blocks": self._build_blocks(content),

            }

            response = requests.post(

                self._slack_webhook_url,

                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),

                headers={'Content-Type': 'application/json; charset=utf-8'},

                timeout=timeout_seconds or 15,

                verify=self._webhook_verify_ssl,

            )

            if response.status_code == 200 and response.text == "ok":

                logger.info("Slack Webhook xiaoxisendchenggong")

                return True

            logger.error(f"Slack Webhook sendshibai: HTTP {response.status_code} {response.text[:200]}")

            return False

        except Exception as e:

            logger.error(f"Slack Webhook sendyichang: {e}")

            return False



    def _send_slack_bot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        shiyong Bot API (chat.postMessage) sendxiaoxidao Slack



        Args:

            content: xiaoxineirong



        Returns:

            shifousendchenggong

        """

        try:

            headers = {

                'Authorization': f'Bearer {self._slack_bot_token}',

                'Content-Type': 'application/json; charset=utf-8',

            }

            payload = {

                "channel": self._slack_channel_id,

                "text": content,

                "blocks": self._build_blocks(content),

            }

            response = requests.post(

                'https://slack.com/api/chat.postMessage',

                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),

                headers=headers,

                timeout=timeout_seconds or 15,

            )

            result = response.json()

            if result.get("ok"):

                logger.info("Slack Bot xiaoxisendchenggong")

                return True

            logger.error(f"Slack Bot sendshibai: {result.get('error', 'unknown')}")

            return False

        except Exception as e:

            logger.error(f"Slack Bot sendyichang: {e}")

            return False



    def _send_slack_image(self, image_bytes: bytes, fallback_content: str = "") -> bool:

        """

        sendtupiandao Slack



        Bot moshixiashiyong files.getUploadURLExternal + files.completeUploadExternal

        (Slack xinbanwenjianshangchuan API)竊쌯ebhook moshixiahuituiweiwenben??


        Args:

            image_bytes: PNG tupianzijie

            fallback_content: tupiansendshibaishidehuituiwenben



        Returns:

            shifousendchenggong

        """

        # Bot moshi竊쉝hiyongxinbanwenjianshangchuan API

        if self._use_bot:

            headers = {'Authorization': f'Bearer {self._slack_bot_token}'}

            try:

                # Step 1: huoqushangchuan URL

                resp1 = requests.post(

                    'https://slack.com/api/files.getUploadURLExternal',

                    headers=headers,

                    data={

                        'filename': 'report.png',

                        'length': len(image_bytes),

                    },

                    timeout=30,

                )

                result1 = resp1.json()

                if not result1.get("ok"):

                    logger.error("Slack huoqushangchuan URL shibai: %s", result1.get('error', 'unknown'))

                    raise RuntimeError(result1.get('error', 'unknown'))



                upload_url = result1['upload_url']

                file_id = result1['file_id']



                # Step 2: shangchuanwenjianneirong竊늭aw body竊똟unengyong multipart竊?
                resp2 = requests.post(

                    upload_url,

                    data=image_bytes,

                    headers={'Content-Type': 'application/octet-stream'},

                    timeout=30,

                )

                if resp2.status_code != 200:

                    logger.error("Slack wenjianshangchuanshibai: HTTP %s", resp2.status_code)

                    raise RuntimeError(f"HTTP {resp2.status_code}")



                # Step 3: wanchengshangchuanbinganalysisangdaopindao

                resp3 = requests.post(

                    'https://slack.com/api/files.completeUploadExternal',

                    headers={**headers, 'Content-Type': 'application/json'},

                    json={

                        'files': [{'id': file_id, 'title': 'stockanalysisbaogao'}],

                        'channel_id': self._slack_channel_id,

                    },

                    timeout=30,

                )

                result3 = resp3.json()

                if result3.get("ok"):

                    logger.info("Slack Bot tupiansendchenggong")

                    return True

                logger.error("Slack wanchengshangchuanshibai: %s", result3.get('error', 'unknown'))

            except Exception as e:

                logger.error("Slack Bot tupiansendyichang: %s", e)



        # Webhook moshihuo Bot shangchuanshibai竊쉎uituiweiwenben

        if fallback_content:

            logger.info("Slack tupianbuzhichihuoshibai竊똦uituiweiwenbensend")

            return self.send_to_slack(fallback_content)



        logger.warning("Slack tupiansendshibai竊똰iewuhuituineirong")

        return False


