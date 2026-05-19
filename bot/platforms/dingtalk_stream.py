# -*- coding: utf-8 -*-

"""

===================================

dingding Stream moshishipeiqi

===================================



shiyongdingdingguanfang Stream SDK jierujiqiren竊똷uxugongwang IP he Webhook config??


youshi竊?
- buxuyaogongwang IP huoyuming

- buxuyaoconfig Webhook URL

- tongguo WebSocket zhanglianjiejieshouxiaoxi

- gengjiandandejierufangshi



yilai竊?
pip install dingtalk-stream



dingding Stream SDK竊?
https://github.com/open-dingtalk/dingtalk-stream-sdk-python

"""



import logging

import inspect

import threading

from datetime import datetime

from typing import Optional, Callable, Any



logger = logging.getLogger(__name__)



# changshidaorudingding Stream SDK

try:

    import dingtalk_stream

    from dingtalk_stream import AckMessage



    DINGTALK_STREAM_AVAILABLE = True

except ImportError:

    DINGTALK_STREAM_AVAILABLE = False

    logger.warning("[DingTalk Stream] dingtalk-stream SDK weianzhuang竊똕tream moshibukeyong")

    logger.warning("[DingTalk Stream] qingyunxing: pip install dingtalk-stream")



from bot.models import BotMessage, BotResponse, ChatType





class DingtalkStreamHandler:

    """

    dingding Stream moshixiaoxichuliqi



    jiang Stream SDK dehuidiaozhuanhuanweitongyide BotMessage geshi竊?
    bingdiaoyongminglingfenfaqichuli??
    """



    def __init__(self, on_message: Callable[[BotMessage], Any]):

        """

        Args:

            on_message: xiaoxichulihuidiaohanshu竊똨ieshou BotMessage fanhui BotResponse

        """

        self._on_message = on_message

        self._logger = logger



    @staticmethod

    def _truncate_log_content(text: str, max_len: int = 200) -> str:

        cleaned = text.replace("\n", " ").strip()

        if len(cleaned) > max_len:

            return f"{cleaned[:max_len]}..."

        return cleaned



    def _log_incoming_message(self, message: BotMessage) -> None:

        content = message.raw_content or message.content or ""

        summary = self._truncate_log_content(content)

        self._logger.info(

            "[DingTalk Stream] Incoming message: msg_id=%s user_id=%s chat_id=%s chat_type=%s content=%s",

            message.message_id,

            message.user_id,

            message.chat_id,

            getattr(message.chat_type, "value", message.chat_type),

            summary,

        )



    if DINGTALK_STREAM_AVAILABLE:

        class _ChatbotHandler(dingtalk_stream.ChatbotHandler):

            """설명 문자열입니다."""



            def __init__(self, parent: 'DingtalkStreamHandler'):

                super().__init__()

                self._parent = parent

                self.logger = logger



            async def process(self, callback: dingtalk_stream.CallbackMessage):

                """설명 문자열입니다."""

                try:

                    # jiexixiaoxi

                    incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)



                    # zhuanhuanweitongyigeshi

                    bot_message = self._parent._parse_stream_message(incoming, callback.data)



                    if bot_message:

                        self._parent._log_incoming_message(bot_message)

                        # diaoyongxiaoxichulihuidiao

                        response = self._parent._on_message(bot_message)

                        if inspect.isawaitable(response):

                            response = await response



                        # sendhuifu

                        if response and response.text:

                            # goujian @yonghu qianzhui竊늫unliaochangjingxiaxuyaozaiwenbenzhongbaohan @yonghuming竊?
                            if response.at_user and incoming.sender_nick:

                                if response.markdown:

                                    self.reply_markdown(

                                        title="stockanalysiszhushou",

                                        text=f"@{incoming.sender_nick} " + response.text,

                                        incoming_message=incoming

                                    )

                                else:

                                    self.reply_text(response.text, incoming)



                    return AckMessage.STATUS_OK, 'OK'



                except Exception as e:

                    self.logger.error(f"[DingTalk Stream] chulixiaoxishibai: {e}")

                    self.logger.exception(e)

                    return AckMessage.STATUS_SYSTEM_EXCEPTION, str(e)



        def create_handler(self) -> '_ChatbotHandler':

            """설명 문자열입니다."""

            return self._ChatbotHandler(self)



    def _parse_stream_message(self, incoming: Any, raw_data: dict) -> Optional[BotMessage]:

        """

        jiexi Stream xiaoxiweitongyigeshi



        Args:

            incoming: ChatbotMessage duixiang

            raw_data: yuanshihuidiaoshuju

        """

        try:

            raw_data = dict(raw_data or {})



            # huoquxiaoxineirong

            raw_content = incoming.text.content if incoming.text else ''



            # tiqumingling竊늫uchu @jiqiren竊?
            content = self._extract_command(raw_content)



            # huihualeixing

            conversation_type = getattr(incoming, 'conversation_type', None)

            if conversation_type == '1':

                chat_type = ChatType.PRIVATE

            elif conversation_type == '2':

                chat_type = ChatType.GROUP

            else:

                chat_type = ChatType.UNKNOWN



            # shifou @lejiqiren竊늆tream moshixiashoudaodexiaoxiyibandoushi @jiqirende竊?
            mentioned = True



            # tiqu sessionWebhook竊똟ianyuyibutuisong

            session_webhook = (

                    getattr(incoming, 'session_webhook', None)

                    or raw_data.get('sessionWebhook')

                    or raw_data.get('session_webhook')

            )

            if session_webhook:

                raw_data['_session_webhook'] = session_webhook



            return BotMessage(

                platform='dingtalk',

                message_id=getattr(incoming, 'msg_id', '') or '',

                user_id=getattr(incoming, 'sender_id', '') or '',

                user_name=getattr(incoming, 'sender_nick', '') or '',

                chat_id=getattr(incoming, 'conversation_id', '') or '',

                chat_type=chat_type,

                content=content,

                raw_content=raw_content,

                mentioned=mentioned,

                mentions=[],

                timestamp=datetime.now(),

                raw_data=raw_data,

            )



        except Exception as e:

            logger.error(f"[DingTalk Stream] jiexixiaoxishibai: {e}")

            return None



    def _extract_command(self, text: str) -> str:

        """설명 문자열입니다."""

        import re

        text = re.sub(r'^@[\S]+\s*', '', text.strip())

        return text.strip()





class DingtalkStreamClient:

    """

    dingding Stream moshikehuduan



    fengzhuang dingtalk-stream SDK竊똳igongjiandandeqidongjiekou??


    shiyongfangshi竊?
        client = DingtalkStreamClient()

        client.start()  # zuseyunxing



        # huozhezaihoutaiyunxing

        client.start_background()

    """



    def __init__(

            self,

            client_id: Optional[str] = None,

            client_secret: Optional[str] = None

    ):

        """

        Args:

            client_id: yingyong AppKey竊늒uchuanzecongconfigduqu竊?
            client_secret: yingyong AppSecret竊늒uchuanzecongconfigduqu竊?
        """

        if not DINGTALK_STREAM_AVAILABLE:

            raise ImportError(

                "dingtalk-stream SDK weianzhuang??n"

                "qingyunxing: pip install dingtalk-stream"

            )



        from src.config import get_config

        config = get_config()



        self._client_id = client_id or getattr(config, 'dingtalk_app_key', None)

        self._client_secret = client_secret or getattr(config, 'dingtalk_app_secret', None)



        if not self._client_id or not self._client_secret:

            raise ValueError(

                "dingding Stream moshixuyaoconfig DINGTALK_APP_KEY he DINGTALK_APP_SECRET"

            )



        self._client: Optional[dingtalk_stream.DingTalkStreamClient] = None

        self._background_thread: Optional[threading.Thread] = None

        self._running = False



    def _create_message_handler(self) -> Callable[[BotMessage], Any]:

        """설명 문자열입니다."""



        async def handle_message(message: BotMessage) -> BotResponse:

            from bot.dispatcher import get_dispatcher

            dispatcher = get_dispatcher()

            return await dispatcher.dispatch_async(message)



        return handle_message



    def start(self) -> None:

        """

        qidong Stream kehuduan竊늷use竊?


        cifangfahuizusedangqianxiancheng竊똺hidaokehuduantingzhi??
        """

        logger.info("[DingTalk Stream] in_progressqidong...")



        # chuangjianpingzheng

        credential = dingtalk_stream.Credential(

            self._client_id,

            self._client_secret

        )



        # chuangjiankehuduan

        self._client = dingtalk_stream.DingTalkStreamClient(credential)



        # zhucexiaoxichuliqi

        handler = DingtalkStreamHandler(self._create_message_handler())

        self._client.register_callback_handler(

            dingtalk_stream.chatbot.ChatbotMessage.TOPIC,

            handler.create_handler()

        )



        self._running = True

        logger.info("[DingTalk Stream] kehuduanyiqidong竊똡engdaixiaoxi...")



        # qidong竊늷use竊?
        self._client.start_forever()



    def start_background(self) -> None:

        """

        zaihoutaixianchengqidong Stream kehuduan竊늗eizuse竊?


        shiyongyuyuqitafuwu竊늭u WebUI竊뎥ongshiyunxingdechangjing??
        """

        if self._background_thread and self._background_thread.is_alive():

            logger.warning("[DingTalk Stream] kehuduanyizaiyunxing")

            return



        self._running = True

        self._background_thread = threading.Thread(

            target=self._run_in_background,

            daemon=True,

            name="DingtalkStreamClient"

        )

        self._background_thread.start()

        logger.info("[DingTalk Stream] houtaikehuduanyiqidong")



    def _run_in_background(self) -> None:

        """설명 문자열입니다."""

        import time



        while self._running:

            try:

                self.start()

            except Exception as e:

                logger.error(f"[DingTalk Stream] yunxingyichang: {e}")

                if self._running:

                    logger.info("[DingTalk Stream] 5 miaohouzhonglian...")

                    time.sleep(5)



    def stop(self) -> None:

        """설명 문자열입니다."""

        self._running = False

        logger.info("[DingTalk Stream] kehuduanyitingzhi")



    @property

    def is_running(self) -> bool:

        """설명 문자열입니다."""

        return self._running





# quanjukehuduanshili

_stream_client: Optional[DingtalkStreamClient] = None





def get_dingtalk_stream_client() -> Optional[DingtalkStreamClient]:

    """설명 문자열입니다."""

    global _stream_client



    if _stream_client is None and DINGTALK_STREAM_AVAILABLE:

        try:

            _stream_client = DingtalkStreamClient()

        except (ImportError, ValueError) as e:

            logger.warning(f"[DingTalk Stream] wufachuangjiankehuduan: {e}")

            return None



    return _stream_client





def start_dingtalk_stream_background() -> bool:

    """

    zaihoutaiqidongdingding Stream kehuduan



    Returns:

        shifouchenggongqidong

    """

    client = get_dingtalk_stream_client()

    if client:

        client.start_background()

        return True

    return False


