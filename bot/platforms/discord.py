# -*- coding: utf-8 -*-

"""

===================================

Discord pingtaishipeiqi

===================================



fuze竊?
1. yanzheng Discord Webhook qingqiu

2. jiexi Discord xiaoxiweitongyigeshi

3. jiangxiangyingzhuanhuanwei Discord geshi

"""



import logging

import time

from datetime import datetime

from typing import Dict, Any, Optional, Tuple, List



import requests

from nacl.exceptions import BadSignatureError

from nacl.signing import VerifyKey



from bot.platforms.base import BotPlatform

from bot.models import BotMessage, WebhookResponse, ChatType





logger = logging.getLogger(__name__)





class DiscordPlatform(BotPlatform):

    """설명 문자열입니다."""



    def __init__(self):

        from src.config import get_config



        config = get_config()

        self._interactions_public_key = (

            getattr(config, "discord_interactions_public_key", None) or ""

        ).strip()

    

    @property

    def platform_name(self) -> str:

        """설명 문자열입니다."""

        return "discord"

    

    def verify_request(self, headers: Dict[str, str], body: bytes) -> bool:

        """yanzheng Discord Webhook qingqiuqianming

        

        Discord Webhook qianmingyanzheng竊?
        1. congqingqiutouhuoqu X-Signature-Ed25519 he X-Signature-Timestamp

        2. shiyonggongyaoyanzhengqianming

        

        Args:

            headers: HTTP qingqiutou

            body: qingqiutiyuanshizijie

            

        Returns:

            qianmingshifouyouxiao

        """

        if not self._interactions_public_key:

            logger.warning("[Discord] weiconfig interactions public key竊똨ujueqingqiu")

            return False



        normalized_headers = {str(k).lower(): v for k, v in headers.items()}

        signature = normalized_headers.get("x-signature-ed25519", "")

        timestamp = normalized_headers.get("x-signature-timestamp", "")



        if not signature or not timestamp:

            logger.warning("[Discord] queshaoqianmingtou竊똨ujueqingqiu")

            return False



        # jiaoyan timestamp geshiyushixiaoxing竊똣angzhizhongfanggongji

        try:

            ts_int = int(timestamp)

        except (TypeError, ValueError):

            logger.warning("[Discord] feifade timestamp竊쉇ixuwei Unix miaozhengshu竊똨ujueqingqiu")

            return False



        try:

            now_ts = int(time.time())

        except Exception as exc:

            logger.warning("[Discord] huoqudangqianshijianshibai: %s竊똨ujueqingqiu", exc)

            return False



        # yunxudeshijianchuangkou竊슿? fenzhong

        if abs(now_ts - ts_int) > 300:

            logger.warning(

                "[Discord] qingqiu timestamp chaochuyunxuchuangkou竊똩enengweizhongfanggongji竊쉞imestamp=%s, now=%s",

                ts_int,

                now_ts,

            )

            return False



        try:

            verify_key = VerifyKey(bytes.fromhex(self._interactions_public_key))

            signature_bytes = bytes.fromhex(signature)

        except ValueError:

            logger.warning("[Discord] gongyaohuoqianmingbushihefashiliujinzhi竊똨ujueqingqiu")

            return False

        except Exception as exc:

            logger.warning("[Discord] wufajiazaiqianminggongyao: %s", exc)

            return False



        try:

            verify_key.verify(timestamp.encode("utf-8") + body, signature_bytes)

        except BadSignatureError:

            logger.warning("[Discord] qianmingyanzhengshibai")

            return False

        except Exception as exc:

            logger.warning("[Discord] qianmingjiaoyanyichang: %s", exc)

            return False



        return True



    def handle_webhook(

        self,

        headers: Dict[str, str],

        body: bytes,

        data: Dict[str, Any],

    ) -> Tuple[Optional[BotMessage], Optional[WebhookResponse]]:

        """설명 문자열입니다."""

        if not self.verify_request(headers, body):

            return None, WebhookResponse.error("Invalid Discord signature", 401)



        challenge_response = self.handle_challenge(data)

        if challenge_response:

            return None, challenge_response



        message = self.parse_message(data)

        if message is not None and data.get("type") == 2:

            # Discord requires an initial response within 3 s.  Return a

            # deferred acknowledgement (type 5 = DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE)

            # so the handler can dispatch the command in the background and

            # deliver the result via follow-up webhook.

            return message, WebhookResponse.success({"type": 5})



        return message, None

    

    def parse_message(self, data: Dict[str, Any]) -> Optional[BotMessage]:

        """jiexi Discord xiaoxiweitongyigeshi

        

        Args:

            data: jiexihoude JSON shuju

            

        Returns:

            BotMessage duixiang竊똦uo None竊늒uxuyaochuli竊?
        """

        interaction_type = data.get("type")

        if interaction_type != 2:

            return None



        interaction_data = data.get("data", {})

        content = self._build_command_content(interaction_data)

        if not content:

            return None



        author = (

            data.get("user")

            or (data.get("member") or {}).get("user")

            or data.get("author", {})

        )

        user_id = str(author.get("id") or "")

        user_name = author.get("username", "unknown")

        channel_id = str(data.get("channel_id") or "")

        guild_id = str(data.get("guild_id") or "")



        if guild_id:

            chat_type = ChatType.GROUP

        elif channel_id:

            chat_type = ChatType.PRIVATE

        else:

            chat_type = ChatType.UNKNOWN



        return BotMessage(

            platform=self.platform_name,

            message_id=str(data.get("id") or ""),

            user_id=user_id,

            user_name=user_name,

            chat_id=channel_id or guild_id or user_id,

            chat_type=chat_type,

            content=content,

            raw_content=content,

            mentioned=False,

            mentions=[],

            timestamp=self._parse_timestamp(data.get("timestamp")),

            raw_data={

                **data,

                "_interaction_name": interaction_data.get("name", ""),

            },

        )

    

    def format_response(self, response: Any, message: BotMessage) -> WebhookResponse:

        """jiangtongyixiangyingzhuanhuanwei Discord geshi

        

        duiyu Interaction竊늯ype=2竊뎢ingqiu竊똣anhui Discord Interaction Response

        callback geshi竊늯ype=4 CHANNEL_MESSAGE_WITH_SOURCE + nested data竊됥?
        

        Args:

            response: tongyixiangyingduixiang

            message: yuanshixiaoxiduixiang

            

        Returns:

            WebhookResponse duixiang

        """

        content = response.text if hasattr(response, "text") else str(response)



        message_data = {

            "content": content,

            "tts": False,

            "embeds": [],

            "allowed_mentions": {

                "parse": ["users", "roles", "everyone"]

            },

        }



        # Interaction竊늮lash-command竊뎪uyao Interaction Response huidiaogeshi

        if message.raw_data.get("type") == 2:

            discord_response = {

                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE

                "data": message_data,

            }

        else:

            discord_response = message_data



        return WebhookResponse.success(discord_response)

    

    # Discord message content hard limit

    DISCORD_MAX_CONTENT_LENGTH = 2000



    def send_followup(self, response: Any, message: BotMessage) -> bool:

        """Edit the deferred interaction placeholder with the real result.



        Uses ``PATCH /webhooks/{application_id}/{token}/messages/@original``

        to update the original deferred message, then sends additional

        follow-up messages via ``POST`` if the content exceeds Discord's

        2 000-character limit.

        """

        raw = message.raw_data

        application_id = raw.get("application_id", "")

        interaction_token = raw.get("token", "")

        if not application_id or not interaction_token:

            logger.warning(

                "[Discord] queshao application_id huo interaction token竊똷ufasend follow-up"

            )

            return False



        content = response.text if hasattr(response, "text") else str(response)



        from src.formatters import chunk_content_by_max_words



        try:

            chunks = chunk_content_by_max_words(

                content, self.DISCORD_MAX_CONTENT_LENGTH

            )

        except (ValueError, Exception) as exc:

            logger.warning("[Discord] xiaoxifenkuaishibai: %s竊똠hangshizhengduansend", exc)

            chunks = [content]



        base_url = (

            f"https://discord.com/api/v10/webhooks/"

            f"{application_id}/{interaction_token}"

        )



        success = True

        for idx, chunk in enumerate(chunks):

            try:

                if idx == 0:

                    # PATCH the original deferred message

                    resp = requests.patch(

                        f"{base_url}/messages/@original",

                        json={"content": chunk},

                        timeout=10,

                    )

                else:

                    # POST additional follow-up messages

                    resp = requests.post(

                        base_url,

                        json={"content": chunk},

                        timeout=10,

                    )

                if resp.status_code >= 300:

                    logger.error(

                        "[Discord] follow-up chunk %d/%d sendshibai: %s %s",

                        idx + 1,

                        len(chunks),

                        resp.status_code,

                        resp.text[:200],

                    )

                    success = False

            except Exception as exc:

                logger.error(

                    "[Discord] follow-up chunk %d/%d qingqiuyichang: %s",

                    idx + 1,

                    len(chunks),

                    exc,

                )

                success = False



        if success:

            logger.info("[Discord] follow-up xiaoxisendchenggong (%d kuai)", len(chunks))

        return success



    def handle_challenge(self, data: Dict[str, Any]) -> Optional[WebhookResponse]:

        """chuli Discord yanzhengqingqiu

        

        Discord zaiconfig Webhook shihuisendyanzhengqingqiu

        

        Args:

            data: qingqiushuju

            

        Returns:

            yanzhengxiangying竊똦uo None竊늒ushiyanzhengqingqiu竊?
        """

        # Discord Webhook yanzhengqingqiuleixingshi 1

        if data.get("type") == 1:

            return WebhookResponse.success({

                "type": 1

            })

        

        # Discord minglingjiaohuyanzheng

        if "challenge" in data:

            return WebhookResponse.success({

                "challenge": data["challenge"]

            })

        

        return None



    def _build_command_content(self, interaction_data: Dict[str, Any]) -> str:

        command_name = str(interaction_data.get("name", "")).strip()

        if not command_name:

            return ""



        parts = [f"/{command_name}"]

        self._append_option_parts(parts, interaction_data.get("options", []))

        return " ".join(parts).strip()



    def _append_option_parts(self, parts: List[str], options: Any) -> None:

        if not isinstance(options, list):

            return



        for option in options:

            if not isinstance(option, dict):

                continue



            nested_options = option.get("options")

            if nested_options:

                nested_name = str(option.get("name", "")).strip()

                if nested_name:

                    parts.append(nested_name)

                self._append_option_parts(parts, nested_options)

                continue



            value = option.get("value")

            if value is None:

                continue

            if isinstance(value, bool):

                # Emit the option name for truthy flags so downstream

                # commands receive a semantic token (e.g. "full") instead

                # of a literal "true"/"false" string.  False flags are

                # simply omitted.

                if value:

                    opt_name = str(option.get("name", "")).strip()

                    if opt_name:

                        parts.append(opt_name)

            else:

                parts.append(str(value))



    def _parse_timestamp(self, value: Any) -> datetime:

        if not value:

            return datetime.now()



        if isinstance(value, datetime):

            return value



        try:

            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        except ValueError:

            return datetime.now()


