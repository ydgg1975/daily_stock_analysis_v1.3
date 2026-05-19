# -*- coding: utf-8 -*-

"""

Discord sendtixingfuwu



zhize竊?
1. tongguo webhook huo Discord bot API send Discord xiaoxi

"""

import logging

from typing import Optional



import requests



from src.config import Config

from src.formatters import chunk_content_by_max_words





logger = logging.getLogger(__name__)





class DiscordSender:

    

    def __init__(self, config: Config):

        """

        chushihua Discord config



        Args:

            config: configduixiang

        """

        self._discord_config = {

            'bot_token': getattr(config, 'discord_bot_token', None),

            'channel_id': getattr(config, 'discord_main_channel_id', None),

            'webhook_url': getattr(config, 'discord_webhook_url', None),

        }

        self._discord_max_words = getattr(config, 'discord_max_words', 2000)

        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

    

    def _is_discord_configured(self) -> bool:

        """알림 sender 설명입니다."""

        # zhiyaoconfigle Webhook huowanzhengde Bot Token+Channel竊똨ishiweikeyong

        bot_ok = bool(self._discord_config['bot_token'] and self._discord_config['channel_id'])

        webhook_ok = bool(self._discord_config['webhook_url'])

        return bot_ok or webhook_ok

    

    def send_to_discord(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        tuisongxiaoxidao Discord竊늷hichi Webhook he Bot API竊?
        

        Args:

            content: Markdown geshidexiaoxineirong

            

        Returns:

            shifousendchenggong

        """

        # fengeneirong竊똟imiandantiaoxiaoxichaoguo Discord xianzhi

        try:

            chunks = chunk_content_by_max_words(content, self._discord_max_words)

        except ValueError as e:

            logger.error(f"Discord 메시지 분할 실패: {e}. 전체 메시지 전송을 시도합니다.")

            chunks = [content]



        # youxianshiyong Webhook竊늩eizhijiandan竊똰uanxiandi竊?
        if self._discord_config['webhook_url']:

            return all(self._send_discord_webhook(chunk, timeout_seconds=timeout_seconds) for chunk in chunks)



        # qicishiyong Bot API竊늫uanxiangao竊똸uyao channel_id竊?
        if self._discord_config['bot_token'] and self._discord_config['channel_id']:

            return all(self._send_discord_bot(chunk, timeout_seconds=timeout_seconds) for chunk in chunks)



        logger.warning("Discord configbuwanzheng竊똳iaoguotuisong")

        return False



  

    def _send_discord_webhook(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        shiyong Webhook sendxiaoxidao Discord

        

        Discord Webhook zhichi Markdown geshi

        

        Args:

            content: Markdown geshidexiaoxineirong

            

        Returns:

            shifousendchenggong

        """

        try:

            payload = {

                'content': content,

                'username': 'Aguanalysisjiqiren',

                'avatar_url': 'https://picsum.photos/200'

            }

            

            response = requests.post(

                self._discord_config['webhook_url'],

                json=payload,

                timeout=timeout_seconds or 10,

                verify=self._webhook_verify_ssl

            )

            

            if response.status_code in [200, 204]:

                logger.info("Discord Webhook xiaoxisendchenggong")

                return True

            else:

                logger.error(f"Discord Webhook sendshibai: {response.status_code} {response.text}")

                return False

        except Exception as e:

            logger.error(f"Discord Webhook sendyichang: {e}")

            return False

    

    def _send_discord_bot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:

        """

        shiyong Bot API sendxiaoxidao Discord

        

        Args:

            content: Markdown geshidexiaoxineirong

            

        Returns:

            shifousendchenggong

        """

        try:

            headers = {

                'Authorization': f'Bot {self._discord_config["bot_token"]}',

                'Content-Type': 'application/json'

            }

            

            payload = {

                'content': content

            }

            

            url = f'https://discord.com/api/v10/channels/{self._discord_config["channel_id"]}/messages'

            response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds or 10)

            

            if response.status_code == 200:

                logger.info("Discord Bot xiaoxisendchenggong")

                return True

            else:

                logger.error(f"Discord Bot sendshibai: {response.status_code} {response.text}")

                return False

        except Exception as e:

            logger.error(f"Discord Bot sendyichang: {e}")

            return False


