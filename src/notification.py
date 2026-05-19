# -*- coding: utf-8 -*-

"""

===================================

Aguwatchlistguzhinenganalysisxitong - notificationceng

===================================



zhize竊?
1. huizonganalysisjieguoshengchengribao

2. zhichi Markdown geshishuchu

3. duoqudaotuisong竊늷idongshibie竊됵폏

   - qiyeweixin Webhook

   - feishu Webhook

   - Telegram Bot

   - youjian SMTP

   - Pushover竊늮houji/zhuomiantuisong竊?
"""

from __future__ import annotations



import logging

import time

from dataclasses import dataclass, field

from datetime import datetime

from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

from enum import Enum



from src.config import Config, get_config

from src.enums import ReportType

from src.notification_routing import (

    get_notification_route_config,

    split_notification_route_channels,

)

from src.notification_noise import (

    NotificationNoiseDecision,

    evaluate_notification_noise,

    record_notification_noise,

    release_notification_noise,

)

from src.report_language import (

    get_localized_stock_name,

    get_report_labels,

    get_signal_level,

    localize_chip_health,

    localize_operation_advice,

    localize_trend_prediction,

    normalize_report_language,

)

from bot.models import BotMessage

from src.utils.sanitize import sanitize_diagnostic_text

from src.utils.data_processing import normalize_model_used

from src.notification_sender import (

    AstrbotSender,

    CustomWebhookSender,

    DiscordSender,

    EmailSender,

    FeishuSender,

    GotifySender,

    NtfySender,

    PushoverSender,

    PushplusSender,

    Serverchan3Sender,

    SlackSender,

    TelegramSender,

    WechatSender,

    WECHAT_IMAGE_MAX_BYTES,

    resolve_gotify_message_endpoint,

    resolve_ntfy_endpoint,

)



logger = logging.getLogger(__name__)



if TYPE_CHECKING:

    from src.analyzer import AnalysisResult





class NotificationChannel(Enum):

    """notificationqudaoleixing"""

    WECHAT = "wechat"      # qiyeweixin

    FEISHU = "feishu"      # feishu

    TELEGRAM = "telegram"  # Telegram

    EMAIL = "email"        # youjian

    PUSHOVER = "pushover"  # Pushover竊늮houji/zhuomiantuisong竊?
    NTFY = "ntfy"          # ntfy

    GOTIFY = "gotify"      # Gotify

    PUSHPLUS = "pushplus"  # PushPlus竊늛uoneituisongfuwu竊?
    SERVERCHAN3 = "serverchan3"  # Serverjiang3竊늮houjiAPPtuisongfuwu竊?
    CUSTOM = "custom"      # zidingyi Webhook

    DISCORD = "discord"    # Discord jiqiren (Bot)

    SLACK = "slack"        # Slack

    ASTRBOT = "astrbot"

    UNKNOWN = "unknown"    # weizhi





@dataclass

class ChannelAttemptResult:

    """One static notification channel send attempt."""



    channel: str

    success: bool

    error_code: Optional[str] = None

    retryable: bool = False

    latency_ms: Optional[int] = None

    diagnostics: Optional[str] = None





@dataclass

class NotificationDispatchResult:

    """Structured result for notification dispatch diagnostics."""



    dispatched: bool

    success: bool

    status: str

    channel_results: List[ChannelAttemptResult] = field(default_factory=list)

    message: Optional[str] = None





class ChannelDetector:

    """

    qudaojianceqi - jianhuaban

    

    genjuconfigzhijiepanduanqudaoleixing竊늒uzaixuyao URL jiexi竊?
    """

    

    @staticmethod

    def get_channel_name(channel: NotificationChannel) -> str:

        """huoququdaozhongwenmingcheng"""

        names = {

            NotificationChannel.WECHAT: "qiyeweixin",

            NotificationChannel.FEISHU: "feishu",

            NotificationChannel.TELEGRAM: "Telegram",

            NotificationChannel.EMAIL: "youjian",

            NotificationChannel.PUSHOVER: "Pushover",

            NotificationChannel.NTFY: "ntfy",

            NotificationChannel.GOTIFY: "Gotify",

            NotificationChannel.PUSHPLUS: "PushPlus",

            NotificationChannel.SERVERCHAN3: "Serverjiang3",

            NotificationChannel.CUSTOM: "zidingyiWebhook",

            NotificationChannel.DISCORD: "Discordjiqiren",

            NotificationChannel.SLACK: "Slack",

            NotificationChannel.ASTRBOT: "ASTRBOTjiqiren",

            NotificationChannel.UNKNOWN: "weizhiqudao",

        }

        return names.get(channel, "weizhiqudao")





class NotificationService(

    AstrbotSender,

    CustomWebhookSender,

    DiscordSender,

    EmailSender,

    FeishuSender,

    GotifySender,

    NtfySender,

    PushoverSender,

    PushplusSender,

    Serverchan3Sender,

    SlackSender,

    TelegramSender,

    WechatSender

):

    """

    notificationfuwu

    

    zhize竊?
    1. shengcheng Markdown geshideanalysisribao

    2. xiangsuoyouyiconfigdequdaotuisongxiaoxi竊늕uoqudaobingfa竊?
    3. zhichibendisaveribao

    

    zhichidequdao竊?
    - qiyeweixin Webhook

    - feishu Webhook

    - Telegram Bot

    - youjian SMTP

    - Pushover竊늮houji/zhuomiantuisong竊?
    

    zhuyi竊쉝uoyouyiconfigdequdaoduhuishoudaotuisong

    """

    

    def __init__(self, source_message: Optional[BotMessage] = None):

        """

        chushihuanotificationfuwu

        

        jiancesuoyouyiconfigdequdao竊똳uisongshihuixiangsuoyouqudaosend

        """

        config = get_config()

        self._config = config

        self._source_message = source_message

        self._context_channels: List[str] = []



        # Markdown zhuantupian竊뉹ssue #289竊?
        self._markdown_to_image_channels = set(

            getattr(config, 'markdown_to_image_channels', []) or []

        )

        self._markdown_to_image_max_chars = getattr(

            config, 'markdown_to_image_max_chars', 15000

        )



        # jinanalysisjieguozhaiyao竊뉹ssue #262竊됵폏true shizhituisonghuizong竊똟uhangeguxiangqing

        self._report_summary_only = getattr(config, 'report_summary_only', False)

        self._report_show_llm_model = getattr(config, 'report_show_llm_model', True)

        self._history_compare_cache: Dict[Tuple[int, Tuple[Tuple[str, str], ...]], Dict[str, List[Dict[str, Any]]]] = {}



        # chushihuagequdao

        AstrbotSender.__init__(self, config)

        CustomWebhookSender.__init__(self, config)

        DiscordSender.__init__(self, config)

        EmailSender.__init__(self, config)

        FeishuSender.__init__(self, config)

        GotifySender.__init__(self, config)

        NtfySender.__init__(self, config)

        PushoverSender.__init__(self, config)

        PushplusSender.__init__(self, config)

        Serverchan3Sender.__init__(self, config)

        SlackSender.__init__(self, config)

        TelegramSender.__init__(self, config)

        WechatSender.__init__(self, config)



        # jiancesuoyouyiconfigdequdao

        self._available_channels = self._detect_all_channels()

        if self._has_context_channel():

            self._context_channels.append("dingdinghuihua")



        if not self._available_channels and not self._context_channels:

            logger.warning("유효한 알림 채널이 설정되지 않아 알림을 보내지 않습니다.")
        else:

            channel_names = [ChannelDetector.get_channel_name(ch) for ch in self._available_channels]

            channel_names.extend(self._context_channels)

            logger.info(f"알림 채널 {len(channel_names)}개가 설정되었습니다: {', '.join(channel_names)}")


    def _normalize_report_type(self, report_type: Any) -> ReportType:

        """Normalize string/enum input into ReportType."""

        if isinstance(report_type, ReportType):

            return report_type

        return ReportType.from_str(report_type)



    def _get_report_language(self, payload: Optional[Any] = None) -> str:

        """Resolve report language from result payload or global config."""

        if isinstance(payload, list):

            for item in payload:

                language = getattr(item, "report_language", None)

                if language:

                    return normalize_report_language(language)

        elif payload is not None:

            language = getattr(payload, "report_language", None)

            if language:

                return normalize_report_language(language)



        return normalize_report_language(getattr(get_config(), "report_language", "zh"))



    def _get_labels(self, payload: Optional[Any] = None) -> Dict[str, str]:

        return get_report_labels(self._get_report_language(payload))



    def _get_display_name(self, result: AnalysisResult, language: Optional[str] = None) -> str:

        report_language = normalize_report_language(language or self._get_report_language(result))

        return self._escape_md(

            get_localized_stock_name(result.name, result.code, report_language)

        )



    def _get_history_compare_context(self, results: List[AnalysisResult]) -> Dict[str, Any]:

        """Fetch and cache history comparison data for markdown rendering."""

        config = get_config()

        history_compare_n = getattr(config, 'report_history_compare_n', 0)

        if history_compare_n <= 0 or not results:

            return {"history_by_code": {}}



        cache_key = (

            history_compare_n,

            tuple(sorted((r.code, getattr(r, 'query_id', '') or '') for r in results)),

        )

        if cache_key in self._history_compare_cache:

            return {"history_by_code": self._history_compare_cache[cache_key]}



        try:

            from src.services.history_comparison_service import get_signal_changes_batch



            exclude_ids = {

                r.code: r.query_id

                for r in results

                if getattr(r, 'query_id', None)

            }

            codes = list(dict.fromkeys(r.code for r in results))

            history_by_code = get_signal_changes_batch(

                codes,

                limit=history_compare_n,

                exclude_query_ids=exclude_ids,

            )

        except Exception as e:

            logger.debug("History comparison skipped: %s", e)

            history_by_code = {}



        self._history_compare_cache[cache_key] = history_by_code

        return {"history_by_code": history_by_code}



    def generate_aggregate_report(

        self,

        results: List[AnalysisResult],

        report_type: Any,

        report_date: Optional[str] = None,

    ) -> str:

        """Generate the aggregate report content used by merge/save/push paths."""

        normalized_type = self._normalize_report_type(report_type)

        if normalized_type == ReportType.BRIEF:

            return self.generate_brief_report(results, report_date=report_date)

        return self.generate_dashboard_report(results, report_date=report_date)



    def _collect_models_used(self, results: List[AnalysisResult]) -> List[str]:

        if not self._should_show_llm_model():

            return []

        models: List[str] = []

        for result in results:

            model = normalize_model_used(getattr(result, "model_used", None))

            if model:

                models.append(model)

        return list(dict.fromkeys(models))



    def _should_show_llm_model(self) -> bool:

        return bool(getattr(self._config, "report_show_llm_model", self._report_show_llm_model))

    

    @staticmethod

    def detect_configured_channels(config: Config) -> List[NotificationChannel]:

        """

        Detect statically configured notification channels from Config.



        This intentionally mirrors sender availability without instantiating

        sender objects, so diagnostics and runtime use the same channel truth.

        Runtime-only context channels are handled by instance methods.

        """

        channels = []



        if getattr(config, "wechat_webhook_url", None):

            channels.append(NotificationChannel.WECHAT)



        if getattr(config, "feishu_webhook_url", None):

            channels.append(NotificationChannel.FEISHU)



        if (

            getattr(config, "telegram_bot_token", None)

            and getattr(config, "telegram_chat_id", None)

        ):

            channels.append(NotificationChannel.TELEGRAM)



        if getattr(config, "email_sender", None) and getattr(config, "email_password", None):

            channels.append(NotificationChannel.EMAIL)



        if (

            getattr(config, "pushover_user_key", None)

            and getattr(config, "pushover_api_token", None)

        ):

            channels.append(NotificationChannel.PUSHOVER)



        ntfy_server_url, ntfy_topic = resolve_ntfy_endpoint(getattr(config, "ntfy_url", None))

        if ntfy_server_url and ntfy_topic:

            channels.append(NotificationChannel.NTFY)



        gotify_endpoint = resolve_gotify_message_endpoint(getattr(config, "gotify_url", None))

        if gotify_endpoint and (getattr(config, "gotify_token", None) or "").strip():

            channels.append(NotificationChannel.GOTIFY)



        if getattr(config, "pushplus_token", None):

            channels.append(NotificationChannel.PUSHPLUS)



        if getattr(config, "serverchan3_sendkey", None):

            channels.append(NotificationChannel.SERVERCHAN3)



        if getattr(config, "custom_webhook_urls", None):

            channels.append(NotificationChannel.CUSTOM)



        if (

            getattr(config, "discord_webhook_url", None)

            or (

                getattr(config, "discord_bot_token", None)

                and getattr(config, "discord_main_channel_id", None)

            )

        ):

            channels.append(NotificationChannel.DISCORD)



        if (

            getattr(config, "slack_webhook_url", None)

            or (

                getattr(config, "slack_bot_token", None)

                and getattr(config, "slack_channel_id", None)

            )

        ):

            channels.append(NotificationChannel.SLACK)



        if getattr(config, "astrbot_url", None):

            channels.append(NotificationChannel.ASTRBOT)



        return channels



    def _detect_all_channels(self) -> List[NotificationChannel]:

        """

        jiancesuoyouyiconfigdequdao



        Returns:

            yiconfigdequdaoliebiao

        """

        return self.detect_configured_channels(self._config)



    def is_available(self) -> bool:

        """jianchanotificationfuwushifoukeyong竊늷hishaoyouyigequdaohuoshangxiawenqudao竊?"""

        return len(self._available_channels) > 0 or self._has_context_channel()

    

    def get_available_channels(self) -> List[NotificationChannel]:

        """huoqusuoyouyiconfigdequdao"""

        return self._available_channels



    def get_channels_for_route(

        self,

        route_type: Optional[str],

        channels: Optional[List[NotificationChannel]] = None,

    ) -> List[NotificationChannel]:

        """Return channels allowed for a route type.



        ``route_type=None`` keeps the legacy behavior and returns all supplied

        static channels. Empty route config also keeps all supplied channels.

        Non-empty route config that matches no enabled channel returns an empty

        list.

        """

        target_channels = list(channels if channels is not None else self._available_channels)

        if route_type is None:

            return target_channels



        route_config = get_notification_route_config(route_type)

        if route_config is None:

            logger.warning("weizhinotificationluyouleixing %s竊똹anyongquanbuyiconfigqudao", route_type)

            return target_channels



        configured_route_channels = getattr(self._config, route_config["config_attr"], []) or []

        if not configured_route_channels:

            return target_channels



        valid_channels, invalid_channels = split_notification_route_channels(configured_route_channels)

        if invalid_channels:

            logger.warning(

                "%s baohanweizhinotificationqudao竊똨ianghulve: %s",

                route_config["env_key"],

                ", ".join(invalid_channels),

            )



        allowed = set(valid_channels)

        return [channel for channel in target_channels if channel.value in allowed]

    

    def get_channel_names(self) -> str:

        """huoqusuoyouyiconfigqudaodemingcheng"""

        names = [ChannelDetector.get_channel_name(ch) for ch in self._available_channels]

        if self._has_context_channel():

            names.append("dingdinghuihua")

        return ', '.join(names)



    def evaluate_noise_control(

        self,

        content: str,

        *,

        route_type: Optional[str] = None,

        severity: Optional[str] = None,

        dedup_key: Optional[str] = None,

        cooldown_key: Optional[str] = None,

    ) -> NotificationNoiseDecision:

        """Evaluate static-channel notification noise controls."""

        return evaluate_notification_noise(

            self._config,

            content=content,

            route_type=route_type,

            severity=severity,

            dedup_key=dedup_key,

            cooldown_key=cooldown_key,

        )



    @staticmethod

    def record_noise_control(decision: NotificationNoiseDecision) -> None:

        """Record static-channel notification noise state after a successful send."""

        record_notification_noise(decision)



    @staticmethod

    def release_noise_control(decision: NotificationNoiseDecision) -> None:

        """Release static-channel in-flight noise reservation after send failure."""

        release_notification_noise(decision)



    # ===== Context channel =====

    def _has_context_channel(self) -> bool:

        """panduanshifoucunzaijiyuxiaoxishangxiawendelinshiqudao竊늭udingdinghuihua?갽eishuhuihua竊?"""

        return (

            self._extract_dingtalk_session_webhook() is not None

            or self._extract_feishu_reply_info() is not None

        )



    def _extract_dingtalk_session_webhook(self) -> Optional[str]:

        """conglaiyuanxiaoxizhongtiqudingdinghuihua Webhook竊늶ongyu Stream moshihuifu竊?"""

        if not isinstance(self._source_message, BotMessage):

            return None

        raw_data = getattr(self._source_message, "raw_data", {}) or {}

        if not isinstance(raw_data, dict):

            return None

        session_webhook = (

            raw_data.get("_session_webhook")

            or raw_data.get("sessionWebhook")

            or raw_data.get("session_webhook")

            or raw_data.get("session_webhook_url")

        )

        if not session_webhook and isinstance(raw_data.get("headers"), dict):

            session_webhook = raw_data["headers"].get("sessionWebhook")

        return session_webhook



    def _extract_feishu_reply_info(self) -> Optional[Dict[str, str]]:

        """

        conglaiyuanxiaoxizhongtiqufeishuhuifuxinxi竊늶ongyu Stream moshihuifu竊?
        

        Returns:

            baohan chat_id dezidian竊똦uo None

        """

        if not isinstance(self._source_message, BotMessage):

            return None

        if getattr(self._source_message, "platform", "") != "feishu":

            return None

        chat_id = getattr(self._source_message, "chat_id", "")

        if not chat_id:

            return None

        return {"chat_id": chat_id}



    def send_to_context(self, content: str) -> bool:

        """

        xiangjiyuxiaoxishangxiawendequdaosendxiaoxi竊늢irudingding Stream huihua竊?
        

        Args:

            content: Markdown geshineirong

        """

        return self._send_via_source_context(content)

    

    def _send_via_source_context(self, content: str) -> bool:

        """

        shiyongxiaoxishangxiawen竊늭udingding/feishuhuihua竊뎕asongyifenbaogao

        

        zhuyaoyongyucongjiqiren Stream moshichufaderenwu竊똰uebaojieguonenghuidaochufadehuihua??
        """

        success = False

        

        # changshidingdinghuihua

        session_webhook = self._extract_dingtalk_session_webhook()

        if session_webhook:

            try:

                if self._send_dingtalk_chunked(session_webhook, content, max_bytes=20000):

                    logger.info("yitongguodingdinghuihua竊늆tream竊뎥uisongbaogao")

                    success = True

                else:

                    logger.error("dingdinghuihua竊늆tream竊뎥uisongshibai")

            except Exception as e:

                logger.error(f"dingdinghuihua竊늆tream竊뎥uisongyichang: {e}")



        # changshifeishuhuihua

        feishu_info = self._extract_feishu_reply_info()

        if feishu_info:

            try:

                if self._send_feishu_stream_reply(feishu_info["chat_id"], content):

                    logger.info("yitongguofeishuhuihua竊늆tream竊뎥uisongbaogao")

                    success = True

                else:

                    logger.error("feishuhuihua竊늆tream竊뎥uisongshibai")

            except Exception as e:

                logger.error(f"feishuhuihua竊늆tream竊뎥uisongyichang: {e}")



        return success



    def _send_feishu_stream_reply(self, chat_id: str, content: str) -> bool:

        """

        tongguofeishu Stream moshisendxiaoxidaozhidinghuihua

        

        Args:

            chat_id: feishuhuihua ID

            content: xiaoxineirong

            

        Returns:

            shifousendchenggong

        """

        try:

            from bot.platforms.feishu_stream import FeishuReplyClient, FEISHU_SDK_AVAILABLE

            if not FEISHU_SDK_AVAILABLE:

                logger.warning("feishu SDK bukeyong竊똷ufasend Stream huifu")

                return False

            

            from src.config import get_config

            config = get_config()

            

            app_id = getattr(config, 'feishu_app_id', None)

            app_secret = getattr(config, 'feishu_app_secret', None)

            

            if not app_id or not app_secret:

                logger.warning("feishu APP_ID huo APP_SECRET weiconfig")

                return False

            

            # chuangjianhuifukehuduan

            reply_client = FeishuReplyClient(app_id, app_secret)

            

            # feishuwenbenxiaoxiyouchangduxianzhi竊똸uyaofenpisend

            max_bytes = getattr(config, 'feishu_max_bytes', 20000)

            content_bytes = len(content.encode('utf-8'))

            

            if content_bytes > max_bytes:

                return self._send_feishu_stream_chunked(reply_client, chat_id, content, max_bytes)

            

            return reply_client.send_to_chat(chat_id, content)

            

        except ImportError as e:

            logger.error(f"daorufeishu Stream mokuaishibai: {e}")

            return False

        except Exception as e:

            logger.error(f"feishu Stream huifuyichang: {e}")

            return False



    def _send_feishu_stream_chunked(

        self, 

        reply_client, 

        chat_id: str, 

        content: str, 

        max_bytes: int

    ) -> bool:

        """

        fenpisendzhangxiaoxidaofeishu竊늆tream moshi竊?
        

        Args:

            reply_client: FeishuReplyClient shili

            chat_id: feishuhuihua ID

            content: wanzhengxiaoxineirong

            max_bytes: dantiaoxiaoxizuidazijieshu

            

        Returns:

            shifouquanbusendchenggong

        """

        import time

        

        def get_bytes(s: str) -> int:

            return len(s.encode('utf-8'))

        

        # anduanluohuofengexianfenge

        if "\n---\n" in content:

            sections = content.split("\n---\n")

            separator = "\n---\n"

        elif "\n### " in content:

            parts = content.split("\n### ")

            sections = [parts[0]] + [f"### {p}" for p in parts[1:]]

            separator = "\n"

        else:

            # anxingfenge

            sections = content.split("\n")

            separator = "\n"

        

        chunks = []

        current_chunk = []

        current_bytes = 0

        separator_bytes = get_bytes(separator)

        

        for section in sections:

            section_bytes = get_bytes(section) + separator_bytes

            

            if current_bytes + section_bytes > max_bytes:

                if current_chunk:

                    chunks.append(separator.join(current_chunk))

                current_chunk = [section]

                current_bytes = section_bytes

            else:

                current_chunk.append(section)

                current_bytes += section_bytes

        

        if current_chunk:

            chunks.append(separator.join(current_chunk))

        

        # sendmeigefenkuai

        success = True

        for i, chunk in enumerate(chunks):

            if i > 0:

                time.sleep(0.5)  # bimianqingqiuguokuai

            

            if not reply_client.send_to_chat(chat_id, chunk):

                success = False

                logger.error(f"feishu Stream fenkuai {i+1}/{len(chunks)} sendshibai")

        

        return success

        

    def generate_daily_report(

        self,

        results: List[AnalysisResult],

        report_date: Optional[str] = None

    ) -> str:

        """

        shengcheng Markdown geshideribao竊늵iangxiban竊?


        Args:

            results: analysisjieguoliebiao

            report_date: baogaoriqi竊늤orenjintian竊?


        Returns:

            Markdown geshideribaoneirong

        """

        if report_date is None:

            report_date = datetime.now().strftime('%Y-%m-%d')

        report_language = self._get_report_language(results)

        labels = get_report_labels(report_language)



        # biaoti

        report_lines = [

            f"# ?뱟 {report_date} {labels['report_title']}",

            "",

            f"> {labels['analyzed_prefix']} **{len(results)}** {labels['stock_unit']} | "

            f"{labels['generated_at_label']}: {datetime.now().strftime('%H:%M:%S')}",

            "",

            "---",

            "",

        ]

        

        # anpingfenpaixu竊늛aofenzaiqian竊?
        sorted_results = sorted(

            results, 

            key=lambda x: x.sentiment_score, 

            reverse=True

        )

        

        # tongjixinxi - shiyong decision_type ziduanzhunquetongji

        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')

        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')

        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))

        avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0

        

        report_lines.extend([

            f"## ?뱤 {labels['summary_heading']}",

            "",

            "| zhibiao | shuzhi |",

            "|------|------|",

            f"| ?윟 {labels['buy_label']} | **{buy_count}** {labels['stock_unit_compact']} |",

            f"| ?윞 {labels['watch_label']} | **{hold_count}** {labels['stock_unit_compact']} |",

            f"| ?뵶 {labels['sell_label']} | **{sell_count}** {labels['stock_unit_compact']} |",

            f"| ?뱢 {labels['avg_score_label']} | **{avg_score:.1f}** |",

            "",

            "---",

            "",

        ])

        

        # Issue #262: summary_only shijinshuchuzhaiyao竊똳iaoguogeguxiangqing

        if self._report_summary_only:

            report_lines.extend([f"## ?뱤 {labels['summary_heading']}", ""])

            for r in sorted_results:

                _, emoji, _ = self._get_signal_level(r)

                report_lines.append(

                    f"{emoji} **{self._get_display_name(r, report_language)}({r.code})**: "

                    f"{localize_operation_advice(r.operation_advice, report_language)} | "

                    f"{labels['score_label']} {r.sentiment_score} | "

                    f"{localize_trend_prediction(r.trend_prediction, report_language)}"

                )

        else:

            report_lines.extend([f"## ?뱢 {labels['report_title']}", ""])

            # zhugestockdexiangxianalysis

            for result in sorted_results:

                _, emoji, _ = self._get_signal_level(result)

                confidence_stars = result.get_confidence_stars() if hasattr(result, 'get_confidence_stars') else '★★'

                

                report_lines.extend([

                    f"### {emoji} {self._get_display_name(result, report_language)} ({result.code})",

                    "",

                    f"**{labels['action_advice_label']}: {localize_operation_advice(result.operation_advice, report_language)}** | "

                    f"**{labels['score_label']}: {result.sentiment_score}** | "

                    f"**{labels['trend_label']}: {localize_trend_prediction(result.trend_prediction, report_language)}** | "

                    f"**Confidence: {confidence_stars}**",

                    "",

                ])



                self._append_market_snapshot(report_lines, result)

                

                # hexinkandian

                if hasattr(result, 'key_points') and result.key_points:

                    report_lines.extend([

                        f"**핵심 포인트**: {result.key_points}",

                        "",

                    ])

                

                # mairu/maichuliyou

                if hasattr(result, 'buy_reason') and result.buy_reason:

                    report_lines.extend([

                        f"**판단 근거**: {result.buy_reason}",

                        "",

                    ])

                

                # zoushianalysis

                if hasattr(result, 'trend_analysis') and result.trend_analysis:

                    report_lines.extend([

                        "#### 추세 분석",

                        f"{result.trend_analysis}",

                        "",

                    ])

                

                # duanqi/zhongqizhanwang

                outlook_lines = []

                if hasattr(result, 'short_term_outlook') and result.short_term_outlook:

                    outlook_lines.append(f"- **단기(1-3일)**: {result.short_term_outlook}")

                if hasattr(result, 'medium_term_outlook') and result.medium_term_outlook:

                    outlook_lines.append(f"- **중기(1-2주)**: {result.medium_term_outlook}")

                if outlook_lines:

                    report_lines.extend([

                        "#### 시장 전망",

                        *outlook_lines,

                        "",

                    ])

                

                # jishumiananalysis

                tech_lines = []

                if result.technical_analysis:

                    tech_lines.append(f"**종합**: {result.technical_analysis}")

                if hasattr(result, 'ma_analysis') and result.ma_analysis:

                    tech_lines.append(f"**이동평균**: {result.ma_analysis}")

                if hasattr(result, 'volume_analysis') and result.volume_analysis:

                    tech_lines.append(f"**거래량**: {result.volume_analysis}")

                if hasattr(result, 'pattern_analysis') and result.pattern_analysis:

                    tech_lines.append(f"**패턴**: {result.pattern_analysis}")

                if tech_lines:

                    report_lines.extend([

                        "#### 기술적 분석",

                        *tech_lines,

                        "",

                    ])

                

                # jibenmiananalysis

                fund_lines = []

                if hasattr(result, 'fundamental_analysis') and result.fundamental_analysis:

                    fund_lines.append(result.fundamental_analysis)

                if hasattr(result, 'sector_position') and result.sector_position:

                    fund_lines.append(f"**섹터 위치**: {result.sector_position}")

                if hasattr(result, 'company_highlights') and result.company_highlights:

                    fund_lines.append(f"**회사 핵심 포인트**: {result.company_highlights}")

                if fund_lines:

                    report_lines.extend([

                        "#### 기본적 분석",

                        *fund_lines,

                        "",

                    ])

                

                # xiaoximian/qingxumian

                news_lines = []

                if result.news_summary:

                    news_lines.append(f"**뉴스 요약**: {result.news_summary}")

                if hasattr(result, 'market_sentiment') and result.market_sentiment:

                    news_lines.append(f"**시장 심리**: {result.market_sentiment}")

                if hasattr(result, 'hot_topics') and result.hot_topics:

                    news_lines.append(f"**관련 이슈**: {result.hot_topics}")

                if news_lines:

                    report_lines.extend([

                        "#### 뉴스와 심리",

                        *news_lines,

                        "",

                    ])

                

                # zongheanalysis

                if result.analysis_summary:

                    report_lines.extend([

                        "#### 종합 분석",

                        result.analysis_summary,

                        "",

                    ])

                

                # fengxiantishi

                if hasattr(result, 'risk_warning') and result.risk_warning:

                    report_lines.extend([

                        f"**리스크 안내**: {result.risk_warning}",

                        "",

                    ])

                

                # shujulaiyuanshuoming

                if hasattr(result, 'search_performed') and result.search_performed:

                    report_lines.append("*온라인 검색을 수행했습니다.*")

                if hasattr(result, 'data_sources') and result.data_sources:

                    report_lines.append(f"*데이터 출처: {result.data_sources}*")

                

                # cuowuxinxi竊늭uguoyou竊?
                if not result.success and result.error_message:

                    report_lines.extend([

                        "",

                        f"**분석 오류**: {result.error_message[:100]}",

                    ])

                

                report_lines.extend([

                    "",

                    "---",

                    "",

                ])

        

        # dibuxinxi竊늫uchumianzeshengming竊?
        report_lines.extend([

            "",

            f"*{labels['generated_at_label']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",

        ])

        

        return "\n".join(report_lines)

    

    @staticmethod

    def _escape_md(name: str) -> str:

        """Escape markdown special characters in stock names (e.g. *ST ??\\*ST)."""

        return name.replace('*', r'\*') if name else name



    @staticmethod

    def _clean_sniper_value(value: Any) -> str:

        """Normalize sniper point values and remove redundant label prefixes."""

        if value is None:

            return 'N/A'

        if isinstance(value, (int, float)):

            return str(value)

        if not isinstance(value, str):

            return str(value)

        if not value or value == 'N/A':

            return value

        prefixes = [
            '이상 매수 지점:', '보조 매수 지점:', '손절선:', '목표가:',
            'lixiangmairudian:', 'ciyoumairudian:', 'zhisunwei:', 'mubiaowei:',
            'Ideal Entry:', 'Secondary Entry:', 'Stop Loss:', 'Target:',
        ]

        for prefix in prefixes:

            if value.startswith(prefix):

                return value[len(prefix):]

        return value



    def _get_signal_level(self, result: AnalysisResult) -> tuple:

        """Get localized signal level and color based on operation advice."""

        return get_signal_level(

            result.operation_advice,

            result.sentiment_score,

            self._get_report_language(result),

        )

    

    def generate_dashboard_report(

        self,

        results: List[AnalysisResult],

        report_date: Optional[str] = None

    ) -> str:

        """

        shengchengjueceyibiaopangeshideribao竊늵iangxiban竊?


        geshi竊쉝hichanggailan + zhongyaoxinxi + hexinjielun + shujutoushi + zuozhanjihua



        Args:

            results: analysisjieguoliebiao

            report_date: baogaoriqi竊늤orenjintian竊?


        Returns:

            Markdown geshidejueceyibiaopanribao

        """

        config = get_config()

        report_language = self._get_report_language(results)

        labels = get_report_labels(report_language)

        reason_label = "Rationale" if report_language == "en" else "caozuoliyou"

        risk_warning_label = "Risk Warning" if report_language == "en" else "fengxiantishi"

        technical_heading = "Technicals" if report_language == "en" else "jishumian"

        ma_label = "Moving Averages" if report_language == "en" else "junxian"

        volume_analysis_label = "Volume" if report_language == "en" else "liangneng"

        news_heading = "News Flow" if report_language == "en" else "xiaoximian"

        if getattr(config, 'report_renderer_enabled', False) and results:

            from src.services.report_renderer import render

            out = render(

                platform='markdown',

                results=results,

                report_date=report_date,

                summary_only=self._report_summary_only,

                extra_context={

                    **self._get_history_compare_context(results),

                    "report_language": report_language,

                },

            )

            if out:

                return out



        if report_date is None:

            report_date = datetime.now().strftime('%Y-%m-%d')



        # anpingfenpaixu竊늛aofenzaiqian竊?
        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)



        # tongjixinxi - shiyong decision_type ziduanzhunquetongji

        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')

        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')

        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))



        report_lines = [

            f"# ?렞 {report_date} {labels['dashboard_title']}",

            "",

            f"> {labels['analyzed_prefix']} **{len(results)}** {labels['stock_unit']} | "

            f"?윟{labels['buy_label']}:{buy_count} ?윞{labels['watch_label']}:{hold_count} ?뵶{labels['sell_label']}:{sell_count}",

            "",

        ]



        # === xinzeng竊쉌enxijieguozhaiyao (Issue #112) ===

        if results:

            report_lines.extend([

                f"## ?뱤 {labels['summary_heading']}",

                "",

            ])

            for r in sorted_results:

                _, signal_emoji, _ = self._get_signal_level(r)

                display_name = self._get_display_name(r, report_language)

                report_lines.append(

                    f"{signal_emoji} **{display_name}({r.code})**: "

                    f"{localize_operation_advice(r.operation_advice, report_language)} | "

                    f"{labels['score_label']} {r.sentiment_score} | "

                    f"{localize_trend_prediction(r.trend_prediction, report_language)}"

                )

            report_lines.extend([

                "",

                "---",

                "",

            ])



        # zhugestockdejueceyibiaopan竊뉹ssue #262: summary_only shitiaoguoxiangqing竊?
        if not self._report_summary_only:

            for result in sorted_results:

                signal_text, signal_emoji, signal_tag = self._get_signal_level(result)

                dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}

                

                # stockmingcheng竊늶ouxianshiyong dashboard huo result zhongdemingcheng竊똺huanyi *ST dengteshuzifu竊?
                stock_name = self._get_display_name(result, report_language)

                

                report_lines.extend([

                    f"## {signal_emoji} {stock_name} ({result.code})",

                    "",

                ])

                

                # ========== yuqingyujibenmiangailan竊늗angzaizuiqianmian竊?=========

                intel = dashboard.get('intelligence', {}) if dashboard else {}

                if intel:

                    report_lines.extend([

                        f"### ?벐 {labels['info_heading']}",

                        "",

                    ])

                    # yuqingqingxuzongjie

                    if intel.get('sentiment_summary'):

                        report_lines.append(f"**?뮡 {labels['sentiment_summary_label']}**: {intel['sentiment_summary']}")

                    # yejiyuqi

                    if intel.get('earnings_outlook'):

                        report_lines.append(f"**?뱤 {labels['earnings_outlook_label']}**: {intel['earnings_outlook']}")

                    # fengxianjingbao竊늵ingmuxianshi竊?
                    risk_alerts = intel.get('risk_alerts', [])

                    if risk_alerts:

                        report_lines.append("")

                        report_lines.append(f"**?슚 {labels['risk_alerts_label']}**:")

                        for alert in risk_alerts:

                            report_lines.append(f"- {alert}")

                    # lihaocuihua

                    catalysts = intel.get('positive_catalysts', [])

                    if catalysts:

                        report_lines.append("")

                        report_lines.append(f"**??{labels['positive_catalysts_label']}**:")

                        for cat in catalysts:

                            report_lines.append(f"- {cat}")

                    # zuixinxiaoxi

                    if intel.get('latest_news'):

                        report_lines.append("")

                        report_lines.append(f"**?뱼 {labels['latest_news_label']}**: {intel['latest_news']}")

                    report_lines.append("")

                

                # ========== hexinjielun ==========

                core = dashboard.get('core_conclusion', {}) if dashboard else {}

                one_sentence = core.get('one_sentence', result.analysis_summary)

                time_sense = core.get('time_sensitivity', labels['default_time_sensitivity'])

                pos_advice = core.get('position_advice', {})

                

                report_lines.extend([

                    f"### ?뱦 {labels['core_conclusion_heading']}",

                    "",

                    f"**{signal_emoji} {signal_text}** | {localize_trend_prediction(result.trend_prediction, report_language)}",

                    "",

                    f"> **{labels['one_sentence_label']}**: {one_sentence}",

                    "",

                    f"??**{labels['time_sensitivity_label']}**: {time_sense}",

                    "",

                ])

                # chicangfenleijianyi

                if pos_advice:

                    report_lines.extend([

                        f"| {labels['position_status_label']} | {labels['action_advice_label']} |",

                        "|---------|---------|",

                        f"| ?넅 **{labels['no_position_label']}** | {pos_advice.get('no_position', localize_operation_advice(result.operation_advice, report_language))} |",

                        f"| ?뮳 **{labels['has_position_label']}** | {pos_advice.get('has_position', labels['continue_holding'])} |",

                        "",

                    ])



                self._append_market_snapshot(report_lines, result)

                

                # ========== shujutoushi ==========

                data_persp = dashboard.get('data_perspective', {}) if dashboard else {}

                if data_persp:

                    trend_data = data_persp.get('trend_status', {})

                    price_data = data_persp.get('price_position', {})

                    vol_data = data_persp.get('volume_analysis', {})

                    chip_data = data_persp.get('chip_structure', {})

                    

                    report_lines.extend([

                        f"### ?뱤 {labels['data_perspective_heading']}",

                        "",

                    ])

                    # qushizhuangtai

                    if trend_data:

                        is_bullish = (

                            f"??{labels['yes_label']}"

                            if trend_data.get('is_bullish', False)

                            else f"??{labels['no_label']}"

                        )

                        report_lines.extend([

                            f"**{labels['ma_alignment_label']}**: {trend_data.get('ma_alignment', 'N/A')} | "

                            f"{labels['bullish_alignment_label']}: {is_bullish} | "

                            f"{labels['trend_strength_label']}: {trend_data.get('trend_score', 'N/A')}/100",

                            "",

                        ])

                    # jiageweizhi

                    if price_data:

                        bias_status = price_data.get('bias_status', 'N/A')

                        report_lines.extend([

                            f"| {labels['price_metrics_label']} | {labels['current_price_label']} |",

                            "|---------|------|",

                            f"| {labels['current_price_label']} | {price_data.get('current_price', 'N/A')} |",

                            f"| {labels['ma5_label']} | {price_data.get('ma5', 'N/A')} |",

                            f"| {labels['ma10_label']} | {price_data.get('ma10', 'N/A')} |",

                            f"| {labels['ma20_label']} | {price_data.get('ma20', 'N/A')} |",

                            f"| {labels['bias_ma5_label']} | {price_data.get('bias_ma5', 'N/A')}% {bias_status} |",

                            f"| {labels['support_level_label']} | {price_data.get('support_level', 'N/A')} |",

                            f"| {labels['resistance_level_label']} | {price_data.get('resistance_level', 'N/A')} |",

                            "",

                        ])

                    # liangnenganalysis

                    if vol_data:

                        report_lines.extend([

                            f"**{labels['volume_label']}**: {labels['volume_ratio_label']} {vol_data.get('volume_ratio', 'N/A')} ({vol_data.get('volume_status', '')}) | "

                            f"{labels['turnover_rate_label']} {vol_data.get('turnover_rate', 'N/A')}%",

                            f"?뮕 *{vol_data.get('volume_meaning', '')}*",

                            "",

                        ])

                    # choumajiegou

                    if chip_data:

                        chip_health = localize_chip_health(chip_data.get('chip_health', 'N/A'), report_language)

                        report_lines.extend([

                            f"**{labels['chip_label']}**: {chip_data.get('profit_ratio', 'N/A')} | {chip_data.get('avg_cost', 'N/A')} | "

                            f"{chip_data.get('concentration', 'N/A')} {chip_health}",

                            "",

                        ])

                

                # ========== zuozhanjihua ==========

                battle = dashboard.get('battle_plan', {}) if dashboard else {}

                if battle:

                    report_lines.extend([

                        f"### ?렞 {labels['battle_plan_heading']}",

                        "",

                    ])

                    # jujidianwei

                    sniper = battle.get('sniper_points', {})

                    if sniper:

                        report_lines.extend([

                            f"**?뱧 {labels['action_points_heading']}**",

                            "",

                            f"| {labels['action_points_heading']} | {labels['current_price_label']} |",

                            "|---------|------|",

                            f"| ?렞 {labels['ideal_buy_label']} | {self._clean_sniper_value(sniper.get('ideal_buy', 'N/A'))} |",

                            f"| ?뵷 {labels['secondary_buy_label']} | {self._clean_sniper_value(sniper.get('secondary_buy', 'N/A'))} |",

                            f"| ?썞 {labels['stop_loss_label']} | {self._clean_sniper_value(sniper.get('stop_loss', 'N/A'))} |",

                            f"| ?럧 {labels['take_profit_label']} | {self._clean_sniper_value(sniper.get('take_profit', 'N/A'))} |",

                            "",

                        ])

                    # cangweicelve

                    position = battle.get('position_strategy', {})

                    if position:

                        report_lines.extend([

                            f"**?뮥 {labels['suggested_position_label']}**: {position.get('suggested_position', 'N/A')}",

                            f"- {labels['entry_plan_label']}: {position.get('entry_plan', 'N/A')}",

                            f"- {labels['risk_control_label']}: {position.get('risk_control', 'N/A')}",

                            "",

                        ])

                    # jianchaqingdan

                    checklist = battle.get('action_checklist', []) if battle else []

                    if checklist:

                        report_lines.extend([

                            f"**??{labels['checklist_heading']}**",

                            "",

                        ])

                        for item in checklist:

                            report_lines.append(f"- {item}")

                        report_lines.append("")

                

                # ruguomeiyou dashboard竊똸ianshichuantonggeshi

                if not dashboard:

                    # caozuoliyou

                    if result.buy_reason:

                        report_lines.extend([

                            f"**?뮕 {reason_label}**: {result.buy_reason}",

                            "",

                        ])

                    # fengxiantishi

                    if result.risk_warning:

                        report_lines.extend([

                            f"**?좑툘 {risk_warning_label}**: {result.risk_warning}",

                            "",

                        ])

                    # jishumiananalysis

                    if result.ma_analysis or result.volume_analysis:

                        report_lines.extend([

                            f"### ?뱤 {technical_heading}",

                            "",

                        ])

                        if result.ma_analysis:

                            report_lines.append(f"**{ma_label}**: {result.ma_analysis}")

                        if result.volume_analysis:

                            report_lines.append(f"**{volume_analysis_label}**: {result.volume_analysis}")

                        report_lines.append("")

                    # xiaoximian

                    if result.news_summary:

                        report_lines.extend([

                            f"### ?벐 {news_heading}",

                            f"{result.news_summary}",

                            "",

                        ])

                

                report_lines.extend([

                    "---",

                    "",

                ])

        

        # dibu竊늫uchumianzeshengming竊?
        report_lines.extend([

            "",

            f"*{labels['generated_at_label']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",

        ])

        models = self._collect_models_used(results)

        if models:

            report_lines.append(f"*{labels['analysis_model_label']}: {', '.join(models)}*")

        

        return "\n".join(report_lines)

    

    def generate_wechat_dashboard(self, results: List[AnalysisResult]) -> str:

        """

        shengchengqiyeweixinjueceyibiaopanjingjianban竊늟ongzhizai4000zifunei竊?
        

        zhibaoliuhexinjielunhejujidianwei

        

        Args:

            results: analysisjieguoliebiao

            

        Returns:

            jingjianbanjueceyibiaopan

        """

        config = get_config()

        report_language = self._get_report_language(results)

        labels = get_report_labels(report_language)

        if getattr(config, 'report_renderer_enabled', False) and results:

            from src.services.report_renderer import render

            out = render(

                platform='wechat',

                results=results,

                report_date=datetime.now().strftime('%Y-%m-%d'),

                summary_only=self._report_summary_only,

                extra_context={"report_language": report_language},

            )

            if out:

                return out



        report_date = datetime.now().strftime('%Y-%m-%d')

        

        # anpingfenpaixu

        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)

        

        # tongji - shiyong decision_type ziduanzhunquetongji

        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')

        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')

        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))

        

        lines = [

            f"## ?렞 {report_date} {labels['dashboard_title']}",

            "",

            f"> {len(results)} {labels['stock_unit']} | "

            f"?윟{labels['buy_label']}:{buy_count} ?윞{labels['watch_label']}:{hold_count} ?뵶{labels['sell_label']}:{sell_count}",

            "",

        ]

        

        # Issue #262: summary_only shijinshuchuzhaiyaoliebiao

        if self._report_summary_only:

            lines.append(f"**?뱤 {labels['summary_heading']}**")

            lines.append("")

            for r in sorted_results:

                _, signal_emoji, _ = self._get_signal_level(r)

                stock_name = self._get_display_name(r, report_language)

                lines.append(

                    f"{signal_emoji} **{stock_name}({r.code})**: "

                    f"{localize_operation_advice(r.operation_advice, report_language)} | "

                    f"{labels['score_label']} {r.sentiment_score} | "

                    f"{localize_trend_prediction(r.trend_prediction, report_language)}"

                )

        else:

            for result in sorted_results:

                signal_text, signal_emoji, _ = self._get_signal_level(result)

                dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}

                core = dashboard.get('core_conclusion', {}) if dashboard else {}

                battle = dashboard.get('battle_plan', {}) if dashboard else {}

                intel = dashboard.get('intelligence', {}) if dashboard else {}

                

                # stockmingcheng

                stock_name = self._get_display_name(result, report_language)

                

                # biaotixing竊쉣inhaodengji + stockmingcheng

                lines.append(f"### {signal_emoji} **{signal_text}** | {stock_name}({result.code})")

                lines.append("")

                

                # hexinjuece竊늶ijuhua竊?
                one_sentence = core.get('one_sentence', result.analysis_summary) if core else result.analysis_summary

                if one_sentence:

                    lines.append(f"?뱦 **{one_sentence[:80]}**")

                    lines.append("")

                

                # zhongyaoxinxiqu竊늶uqing+jibenmian竊?
                info_lines = []

                

                # yejiyuqi

                if intel.get('earnings_outlook'):

                    outlook = str(intel['earnings_outlook'])[:60]

                    info_lines.append(f"?뱤 {labels['earnings_outlook_label']}: {outlook}")

                if intel.get('sentiment_summary'):

                    sentiment = str(intel['sentiment_summary'])[:50]

                    info_lines.append(f"?뮡 {labels['sentiment_summary_label']}: {sentiment}")

                if info_lines:

                    lines.extend(info_lines)

                    lines.append("")

                

                # fengxianjingbao竊늷uizhongyao竊똸ingmuxianshi竊?
                risks = intel.get('risk_alerts', []) if intel else []

                if risks:

                    lines.append(f"?슚 **{labels['risk_alerts_label']}**:")

                    for risk in risks[:2]:  # zuiduoxianshi2tiao

                        risk_str = str(risk)

                        risk_text = risk_str[:50] + "..." if len(risk_str) > 50 else risk_str

                        lines.append(f"   ??{risk_text}")

                    lines.append("")

                

                # lihaocuihua

                catalysts = intel.get('positive_catalysts', []) if intel else []

                if catalysts:

                    lines.append(f"??**{labels['positive_catalysts_label']}**:")

                    for cat in catalysts[:2]:  # zuiduoxianshi2tiao

                        cat_str = str(cat)

                        cat_text = cat_str[:50] + "..." if len(cat_str) > 50 else cat_str

                        lines.append(f"   ??{cat_text}")

                    lines.append("")

                

                # jujidianwei

                sniper = battle.get('sniper_points', {}) if battle else {}

                if sniper:

                    ideal_buy = str(sniper.get('ideal_buy', ''))

                    stop_loss = str(sniper.get('stop_loss', ''))

                    take_profit = str(sniper.get('take_profit', ''))

                    points = []

                    if ideal_buy:

                        points.append(f"?렞{labels['ideal_buy_label']}:{ideal_buy[:15]}")

                    if stop_loss:

                        points.append(f"?썞{labels['stop_loss_label']}:{stop_loss[:15]}")

                    if take_profit:

                        points.append(f"?럧{labels['take_profit_label']}:{take_profit[:15]}")

                    if points:

                        lines.append(" | ".join(points))

                        lines.append("")

                

                # chicangjianyi

                pos_advice = core.get('position_advice', {}) if core else {}

                if pos_advice:

                    no_pos = str(pos_advice.get('no_position', ''))

                    has_pos = str(pos_advice.get('has_position', ''))

                    if no_pos:

                        lines.append(f"?넅 {labels['no_position_label']}: {no_pos[:50]}")

                    if has_pos:

                        lines.append(f"?뮳 {labels['has_position_label']}: {has_pos[:50]}")

                    lines.append("")

                

                # jianchaqingdanjianhuaban

                checklist = battle.get('action_checklist', []) if battle else []

                if checklist:

                    # zhixianshibutongguodexiangmu

                    failed_checks = [
                        str(c) for c in checklist
                        if str(c).startswith('실패') or str(c).startswith('주의') or str(c).startswith('위험')
                    ]

                    if failed_checks:

                        lines.append(f"**{labels['failed_checks_heading']}**:")

                        for check in failed_checks[:3]:

                            lines.append(f"   {check[:40]}")

                        lines.append("")

                

                lines.append("---")

                lines.append("")

        

        # dibu

        lines.append(f"*{labels['report_time_label']}: {datetime.now().strftime('%H:%M')}*")

        models = self._collect_models_used(results)

        if models:

            lines.append(f"*{labels['analysis_model_label']}: {', '.join(models)}*")



        content = "\n".join(lines)



        return content



    def generate_wechat_summary(self, results: List[AnalysisResult]) -> str:

        """

        shengchengqiyeweixinjingjianbanribao竊늟ongzhizai4000zifunei竊?


        Args:

            results: analysisjieguoliebiao



        Returns:

            jingjianban Markdown neirong

        """

        report_date = datetime.now().strftime('%Y-%m-%d')

        report_language = self._get_report_language(results)

        labels = get_report_labels(report_language)



        # anpingfenpaixu

        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)



        # tongji - shiyong decision_type ziduanzhunquetongji

        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')

        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')

        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))

        avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0



        lines = [

            f"## ?뱟 {report_date} {labels['report_title']}",

            "",

            f"> {labels['analyzed_prefix']} **{len(results)}** {labels['stock_unit_compact']} | "

            f"?윟{labels['buy_label']}:{buy_count} ?윞{labels['watch_label']}:{hold_count} ?뵶{labels['sell_label']}:{sell_count} | "

            f"{labels['avg_score_label']}:{avg_score:.0f}",

            "",

        ]

        

        # meizhistockjingjianxinxi竊늟ongzhichangdu竊?
        for result in sorted_results:

            _, emoji, _ = self._get_signal_level(result)

            

            # hexinxinxixing

            lines.append(f"### {emoji} {self._get_display_name(result, report_language)}({result.code})")

            lines.append(

                f"**{localize_operation_advice(result.operation_advice, report_language)}** | "

                f"{labels['score_label']}:{result.sentiment_score} | "

                f"{localize_trend_prediction(result.trend_prediction, report_language)}"

            )

            

            # caozuoliyou竊늞ieduan竊?
            if hasattr(result, 'buy_reason') and result.buy_reason:

                reason = result.buy_reason[:80] + "..." if len(result.buy_reason) > 80 else result.buy_reason

                lines.append(f"?뮕 {reason}")

            

            # hexinkandian

            if hasattr(result, 'key_points') and result.key_points:

                points = result.key_points[:60] + "..." if len(result.key_points) > 60 else result.key_points

                lines.append(f"?렞 {points}")

            

            # fengxiantishi竊늞ieduan竊?
            if hasattr(result, 'risk_warning') and result.risk_warning:

                risk = result.risk_warning[:50] + "..." if len(result.risk_warning) > 50 else result.risk_warning

                lines.append(f"?좑툘 {risk}")

            

            lines.append("")

        

        # dibu竊늤oxingxingzai --- zhiqian竊똈ssue #528竊?
        models = self._collect_models_used(results)

        if models:

            lines.append(f"*{labels['analysis_model_label']}: {', '.join(models)}*")

        lines.extend([

            "---",

            f"*{labels['not_investment_advice']}*",

            f"*{labels['details_report_hint']} reports/report_{report_date.replace('-', '')}.md*"

        ])



        content = "\n".join(lines)



        return content



    def generate_brief_report(

        self,

        results: List[AnalysisResult],

        report_date: Optional[str] = None,

    ) -> str:

        """

        Generate brief report (3-5 sentences per stock) for mobile/push.



        Args:

            results: Analysis results list (use [result] for single stock).

            report_date: Report date (default: today).



        Returns:

            Brief markdown content.

        """

        if report_date is None:

            report_date = datetime.now().strftime('%Y-%m-%d')

        report_language = self._get_report_language(results)

        labels = get_report_labels(report_language)

        config = get_config()

        if getattr(config, 'report_renderer_enabled', False) and results:

            from src.services.report_renderer import render

            out = render(

                platform='brief',

                results=results,

                report_date=report_date,

                summary_only=False,

                extra_context={"report_language": report_language},

            )

            if out:

                return out

        # Fallback: brief summary from dashboard report

        if not results:

            return f"# {report_date} {labels['brief_title']}\n\n{labels['no_results']}"

        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)

        buy_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'buy')

        sell_count = sum(1 for r in results if getattr(r, 'decision_type', '') == 'sell')

        hold_count = sum(1 for r in results if getattr(r, 'decision_type', '') in ('hold', ''))

        lines = [

            f"# {report_date} {labels['brief_title']}",

            "",

            f"> {len(results)} {labels['stock_unit_compact']} | ?윟{buy_count} ?윞{hold_count} ?뵶{sell_count}",

            "",

        ]

        for r in sorted_results:

            _, emoji, _ = self._get_signal_level(r)

            name = self._get_display_name(r, report_language)

            dash = r.dashboard or {}

            core = dash.get('core_conclusion', {}) or {}

            one = (core.get('one_sentence') or r.analysis_summary or '')[:60]

            lines.append(

                f"**{name}({r.code})** {emoji} "

                f"{localize_operation_advice(r.operation_advice, report_language)} | "

                f"{labels['score_label']} {r.sentiment_score} | {one}"

            )

        lines.append("")

        lines.append(f"*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        models = self._collect_models_used(results)

        if models:

            lines.append(f"*{labels['analysis_model_label']}: {', '.join(models)}*")

        return "\n".join(lines)



    def generate_single_stock_report(self, result: AnalysisResult) -> str:

        """

        shengchengdanzhistockdeanalysisbaogao竊늶ongyudangutuisongmoshi #55竊?
        

        geshijingjiandanxinxiwanzheng竊똲hihemeianalysiswanyizhistocklijituisong

        

        Args:

            result: danzhistockdeanalysisjieguo

            

        Returns:

            Markdown geshidedangubaogao

        """

        report_date = datetime.now().strftime('%Y-%m-%d %H:%M')

        report_language = self._get_report_language(result)

        labels = get_report_labels(report_language)

        signal_text, signal_emoji, _ = self._get_signal_level(result)

        dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}

        core = dashboard.get('core_conclusion', {}) if dashboard else {}

        battle = dashboard.get('battle_plan', {}) if dashboard else {}

        intel = dashboard.get('intelligence', {}) if dashboard else {}

        

        # stockmingcheng竊늷huanyi *ST dengteshuzifu竊?
        stock_name = self._get_display_name(result, report_language)

        

        lines = [

            f"## {signal_emoji} {stock_name} ({result.code})",

            "",

            f"> {report_date} | {labels['score_label']}: **{result.sentiment_score}** | {localize_trend_prediction(result.trend_prediction, report_language)}",

            "",

        ]



        self._append_market_snapshot(lines, result)

        

        # hexinjuece竊늶ijuhua竊?
        one_sentence = core.get('one_sentence', result.analysis_summary) if core else result.analysis_summary

        if one_sentence:

            lines.extend([

                f"### ?뱦 {labels['core_conclusion_heading']}",

                "",

                f"**{signal_text}**: {one_sentence}",

                "",

            ])

        

        # zhongyaoxinxi竊늶uqing+jibenmian竊?
        info_added = False

        if intel:

            if intel.get('earnings_outlook'):

                if not info_added:

                    lines.append(f"### ?벐 {labels['info_heading']}")

                    lines.append("")

                    info_added = True

                lines.append(f"?뱤 **{labels['earnings_outlook_label']}**: {str(intel['earnings_outlook'])[:100]}")

            

            if intel.get('sentiment_summary'):

                if not info_added:

                    lines.append(f"### ?벐 {labels['info_heading']}")

                    lines.append("")

                    info_added = True

                lines.append(f"?뮡 **{labels['sentiment_summary_label']}**: {str(intel['sentiment_summary'])[:80]}")

            

            # fengxianjingbao

            risks = intel.get('risk_alerts', [])

            if risks:

                if not info_added:

                    lines.append(f"### ?벐 {labels['info_heading']}")

                    lines.append("")

                    info_added = True

                lines.append("")

                lines.append(f"?슚 **{labels['risk_alerts_label']}**:")

                for risk in risks[:3]:

                    lines.append(f"- {str(risk)[:60]}")

            

            # lihaocuihua

            catalysts = intel.get('positive_catalysts', [])

            if catalysts:

                lines.append("")

                lines.append(f"??**{labels['positive_catalysts_label']}**:")

                for cat in catalysts[:3]:

                    lines.append(f"- {str(cat)[:60]}")

        

        if info_added:

            lines.append("")

        

        # jujidianwei

        sniper = battle.get('sniper_points', {}) if battle else {}

        if sniper:

            lines.extend([

                f"### ?렞 {labels['action_points_heading']}",

                "",

                f"| {labels['ideal_buy_label']} | {labels['stop_loss_label']} | {labels['take_profit_label']} |",

                "|------|------|------|",

            ])

            ideal_buy = sniper.get('ideal_buy', '-')

            stop_loss = sniper.get('stop_loss', '-')

            take_profit = sniper.get('take_profit', '-')

            lines.append(f"| {ideal_buy} | {stop_loss} | {take_profit} |")

            lines.append("")

        

        # chicangjianyi

        pos_advice = core.get('position_advice', {}) if core else {}

        if pos_advice:

            lines.extend([

                f"### ?뮳 {labels['position_advice_heading']}",

                "",

                f"- ?넅 **{labels['no_position_label']}**: {pos_advice.get('no_position', localize_operation_advice(result.operation_advice, report_language))}",

                f"- ?뮳 **{labels['has_position_label']}**: {pos_advice.get('has_position', labels['continue_holding'])}",

                "",

            ])

        

        lines.append("---")

        if self._should_show_llm_model():

            model_used = normalize_model_used(getattr(result, "model_used", None))

            if model_used:

                lines.append(f"*{labels['analysis_model_label']}: {model_used}*")

        lines.append(f"*{labels['not_investment_advice']}*")



        return "\n".join(lines)



    # Display name mapping for realtime data sources

    _SOURCE_DISPLAY_NAMES = {

        "tencent": {"zh": "tengxuncaijing", "en": "Tencent Finance"},

        "akshare_em": {"zh": "dongfangcaifu", "en": "Eastmoney"},

        "akshare_sina": {"zh": "xinlangcaijing", "en": "Sina Finance"},

        "akshare_qq": {"zh": "tengxuncaijing", "en": "Tencent Finance"},

        "efinance": {"zh": "dongfangcaifu(efinance)", "en": "Eastmoney (efinance)"},

        "tushare": {"zh": "Tushare Pro", "en": "Tushare Pro"},

        "sina": {"zh": "xinlangcaijing", "en": "Sina Finance"},

        "stooq": {"zh": "Stooq", "en": "Stooq"},

        "longbridge": {"zh": "zhangqiao", "en": "Longbridge"},

        "fallback": {"zh": "jiangjidoudi", "en": "Fallback"},

    }



    def _get_source_display_name(self, source: Any, language: Optional[str]) -> str:

        raw_source = str(source or "N/A")

        mapping = self._SOURCE_DISPLAY_NAMES.get(raw_source)

        if not mapping:

            return raw_source

        return mapping[normalize_report_language(language)]



    def _append_market_snapshot(self, lines: List[str], result: AnalysisResult) -> None:

        snapshot = getattr(result, 'market_snapshot', None)

        if not snapshot:

            return



        report_language = self._get_report_language(result)

        labels = get_report_labels(report_language)



        lines.extend([

            f"### ?뱢 {labels['market_snapshot_heading']}",

            "",

            f"| {labels['close_label']} | {labels['prev_close_label']} | {labels['open_label']} | {labels['high_label']} | {labels['low_label']} | {labels['change_pct_label']} | {labels['change_amount_label']} | {labels['amplitude_label']} | {labels['volume_label']} | {labels['amount_label']} |",

            "|------|------|------|------|------|-------|-------|------|--------|--------|",

            f"| {snapshot.get('close', 'N/A')} | {snapshot.get('prev_close', 'N/A')} | "

            f"{snapshot.get('open', 'N/A')} | {snapshot.get('high', 'N/A')} | "

            f"{snapshot.get('low', 'N/A')} | {snapshot.get('pct_chg', 'N/A')} | "

            f"{snapshot.get('change_amount', 'N/A')} | {snapshot.get('amplitude', 'N/A')} | "

            f"{snapshot.get('volume', 'N/A')} | {snapshot.get('amount', 'N/A')} |",

        ])



        if "price" in snapshot:

            display_source = self._get_source_display_name(snapshot.get('source', 'N/A'), report_language)

            lines.extend([

                "",

                f"| {labels['current_price_label']} | {labels['volume_ratio_label']} | {labels['turnover_rate_label']} | {labels['source_label']} |",

                "|-------|------|--------|----------|",

                f"| {snapshot.get('price', 'N/A')} | {snapshot.get('volume_ratio', 'N/A')} | "

                f"{snapshot.get('turnover_rate', 'N/A')} | {display_source} |",

            ])



        lines.append("")



    def _should_use_image_for_channel(

        self, channel: NotificationChannel, image_bytes: Optional[bytes]

    ) -> bool:

        """

        Decide whether to send as image for the given channel (Issue #289).



        Fallback rules (send as Markdown text instead of image):

        - image_bytes is None: conversion failed / imgkit not installed / content over max_chars

        - WeChat: image exceeds ~2MB limit

        """

        if channel.value not in self._markdown_to_image_channels or image_bytes is None:

            return False

        if channel == NotificationChannel.WECHAT and len(image_bytes) > WECHAT_IMAGE_MAX_BYTES:

            logger.warning(

                "qiyeweixintupianchaoxian (%d bytes)竊똦uituiwei Markdown wenbensend",

                len(image_bytes),

            )

            return False

        return True



    @staticmethod

    def _sanitize_notification_diagnostics(text: Any) -> str:

        return sanitize_diagnostic_text(text)



    def _send_to_static_channel(

        self,

        channel: NotificationChannel,

        content: str,

        *,

        image_bytes: Optional[bytes],

        email_stock_codes: Optional[List[str]],

        email_send_to_all: bool,

    ) -> bool:

        use_image = self._should_use_image_for_channel(channel, image_bytes)

        if channel == NotificationChannel.WECHAT:

            if use_image:

                return self._send_wechat_image(image_bytes)

            return self.send_to_wechat(content)

        if channel == NotificationChannel.FEISHU:

            return self.send_to_feishu(content)

        if channel == NotificationChannel.TELEGRAM:

            if use_image:

                return self._send_telegram_photo(image_bytes)

            return self.send_to_telegram(content)

        if channel == NotificationChannel.EMAIL:

            receivers = None

            if email_send_to_all and self._stock_email_groups:

                receivers = self.get_all_email_receivers()

            elif email_stock_codes and self._stock_email_groups:

                receivers = self.get_receivers_for_stocks(email_stock_codes)

            if use_image:

                return self._send_email_with_inline_image(image_bytes, receivers=receivers)

            return self.send_to_email(content, receivers=receivers)

        if channel == NotificationChannel.PUSHOVER:

            return self.send_to_pushover(content)

        if channel == NotificationChannel.NTFY:

            return self.send_to_ntfy(content)

        if channel == NotificationChannel.GOTIFY:

            return self.send_to_gotify(content)

        if channel == NotificationChannel.PUSHPLUS:

            return self.send_to_pushplus(content)

        if channel == NotificationChannel.SERVERCHAN3:

            return self.send_to_serverchan3(content)

        if channel == NotificationChannel.CUSTOM:

            if use_image:

                return self._send_custom_webhook_image(image_bytes, fallback_content=content)

            return self.send_to_custom(content)

        if channel == NotificationChannel.DISCORD:

            return self.send_to_discord(content)

        if channel == NotificationChannel.SLACK:

            if use_image:

                return self._send_slack_image(image_bytes, fallback_content=content)

            return self.send_to_slack(content)

        if channel == NotificationChannel.ASTRBOT:

            return self.send_to_astrbot(content)

        logger.warning(f"buzhichidenotificationqudao: {channel}")

        return False



    def send_with_results(

        self,

        content: str,

        email_stock_codes: Optional[List[str]] = None,

        email_send_to_all: bool = False,

        route_type: Optional[str] = None,

        severity: Optional[str] = None,

        dedup_key: Optional[str] = None,

        cooldown_key: Optional[str] = None,

    ) -> NotificationDispatchResult:

        """

        Send a notification and return per-channel diagnostics.



        ``send()`` keeps the historical bool API and delegates here.



        Fallback rules (Markdown-to-image, Issue #289):

        - When image_bytes is None (conversion failed / imgkit not installed /

          content over max_chars): all channels configured for image will send

          as Markdown text instead.

        - When WeChat image exceeds ~2MB: that channel falls back to Markdown text.



        Args:

            content: xiaoxineirong竊뉾arkdown geshi竊?
            email_stock_codes: stockdaimaliebiao竊늟exuan竊똹ongyuyoujianqudaoluyoudaoduiyingfenzuyouxiang竊똈ssue #268竊?
            email_send_to_all: youjianshifoufawangsuoyouconfigyouxiang竊늶ongyudapanfupandengwustockguishudeneirong竊?
            route_type: notificationluyouleixing竊쌢one baochijiuxingwei竊똱eport/alert/system_error anconfigguolvjingtaiqudao

            severity: notificationyanzhongjibie竊썊eishezhishianluyouleixingtuiduan

            dedup_key: kexuanwendingquzhong key竊썊eishezhishishiyongneirong hash

            cooldown_key: kexuanlengque key竊썊eishezhishishiyongluyou/jibiemoren key



        Returns:

            Structured dispatch diagnostics.

        """

        context_success = self.send_to_context(content)



        if not self._available_channels:

            if context_success:

                logger.info("메시지 컨텍스트 채널로 알림을 완료했습니다. 추가 알림 채널은 없습니다.")

                return NotificationDispatchResult(

                    dispatched=True,

                    success=True,

                    status="sent",

                    channel_results=[ChannelAttemptResult(channel="__context__", success=True)],

                )

            logger.warning("알림 서비스를 사용할 수 없어 알림을 건너뜁니다.")

            return NotificationDispatchResult(

                dispatched=False,

                success=False,

                status="no_channel",

                message="notification service unavailable",

            )



        target_channels = self.get_channels_for_route(route_type)

        if not target_channels:

            if context_success:

                logger.info("메시지 컨텍스트 채널로 알림을 완료했습니다. 라우팅 가능한 추가 채널은 없습니다.")

                return NotificationDispatchResult(

                    dispatched=True,

                    success=True,

                    status="sent",

                    channel_results=[ChannelAttemptResult(channel="__context__", success=True)],

                )

            logger.warning("notificationluyou %s weimingzhongrenheyiconfigqudao竊똳iaoguojingtainotificationqudao", route_type)

            return NotificationDispatchResult(

                dispatched=False,

                success=False,

                status="no_channel",

                message=f"notification route {route_type} has no configured channel",

            )



        noise_decision = self.evaluate_noise_control(

            content,

            route_type=route_type,

            severity=severity,

            dedup_key=dedup_key,

            cooldown_key=cooldown_key,

        )

        if not noise_decision.should_send:

            logger.info(noise_decision.message)

            status = "sent" if context_success else "noise_suppressed"

            results = [ChannelAttemptResult(channel="__context__", success=True)] if context_success else []

            return NotificationDispatchResult(

                dispatched=bool(context_success),

                success=bool(context_success),

                status=status,

                channel_results=results,

                message=noise_decision.message,

            )



        # Markdown to image (Issue #289): convert once if any channel needs it.

        # Per-channel decision via _should_use_image_for_channel (see send() docstring for fallback rules).

        image_bytes = None

        channels_needing_image = {

            ch for ch in target_channels

            if ch.value in self._markdown_to_image_channels

            and ch not in {NotificationChannel.NTFY, NotificationChannel.GOTIFY}

        }

        if channels_needing_image:

            from src.md2img import markdown_to_image

            image_bytes = markdown_to_image(

                content, max_chars=self._markdown_to_image_max_chars

            )

            if image_bytes:

                logger.info("Markdown yizhuanhuanweitupian竊똨iangxiang %s sendtupian",

                            [ch.value for ch in channels_needing_image])

            elif channels_needing_image:

                try:

                    from src.config import get_config

                    engine = getattr(get_config(), "md2img_engine", "wkhtmltoimage")

                except Exception:

                    engine = "wkhtmltoimage"

                hint = (

                    "npm i -g markdown-to-file" if engine == "markdown-to-file"

                    else "wkhtmltopdf (apt install wkhtmltopdf / brew install wkhtmltopdf)"

                )

                logger.warning(

                    "Markdown 이미지 변환에 실패해 텍스트 전송으로 대체합니다. MARKDOWN_TO_IMAGE_CHANNELS 설정과 의존성을 확인하세요: %s",

                    hint,

                )



        channel_names = ', '.join(ChannelDetector.get_channel_name(ch) for ch in target_channels)

        logger.info(f"{len(target_channels)}개 채널로 알림을 전송합니다: {channel_names}")



        success_count = 0

        fail_count = 0

        channel_results: List[ChannelAttemptResult] = []



        for channel in target_channels:

            channel_name = ChannelDetector.get_channel_name(channel)

            started_at = time.monotonic()

            try:

                result = self._send_to_static_channel(

                    channel,

                    content,

                    image_bytes=image_bytes,

                    email_stock_codes=email_stock_codes,

                    email_send_to_all=email_send_to_all,

                )

                latency_ms = int((time.monotonic() - started_at) * 1000)



                if result:

                    success_count += 1

                else:

                    fail_count += 1

                channel_results.append(

                    ChannelAttemptResult(

                        channel=channel.value,

                        success=bool(result),

                        error_code=None if result else "send_failed",

                        retryable=not bool(result),

                        latency_ms=latency_ms,

                    )

                )



            except Exception as e:

                logger.error(f"{channel_name} sendshibai: {e}")

                fail_count += 1

                channel_results.append(

                    ChannelAttemptResult(

                        channel=channel.value,

                        success=False,

                        error_code="exception",

                        retryable=True,

                        latency_ms=int((time.monotonic() - started_at) * 1000),

                        diagnostics=self._sanitize_notification_diagnostics(str(e)),

                    )

                )



        logger.info(f"notificationsendwancheng竊쉉henggong {success_count} ge竊똲hibai {fail_count} ge")

        if success_count > 0:

            self.record_noise_control(noise_decision)

        else:

            self.release_noise_control(noise_decision)

        success = success_count > 0 or context_success

        if success_count > 0 and fail_count > 0:

            status = "partial_failed"

        elif success_count > 0 or context_success:

            status = "sent"

        else:

            status = "all_failed"

        if context_success:

            channel_results.insert(0, ChannelAttemptResult(channel="__context__", success=True))

        return NotificationDispatchResult(

            dispatched=True,

            success=success,

            status=status,

            channel_results=channel_results,

        )



    def send(

        self,

        content: str,

        email_stock_codes: Optional[List[str]] = None,

        email_send_to_all: bool = False,

        route_type: Optional[str] = None,

        severity: Optional[str] = None,

        dedup_key: Optional[str] = None,

        cooldown_key: Optional[str] = None,

    ) -> bool:

        """

        tongyisendjiekou - xiangsuoyouyiconfigdequdaosend??


        Returns:

            shifouzhishaoyouyigequdaosendchenggong

        """

        result = self.send_with_results(

            content,

            email_stock_codes=email_stock_codes,

            email_send_to_all=email_send_to_all,

            route_type=route_type,

            severity=severity,

            dedup_key=dedup_key,

            cooldown_key=cooldown_key,

        )

        return bool(result.success)

   

    def save_report_to_file(

        self, 

        content: str, 

        filename: Optional[str] = None

    ) -> str:

        """

        saveribaodaobendiwenjian

        

        Args:

            content: ribaoneirong

            filename: wenjianming竊늟exuan竊똫orenanriqishengcheng竊?
            

        Returns:

            savedewenjianlujing

        """

        from pathlib import Path

        

        if filename is None:

            date_str = datetime.now().strftime('%Y%m%d')

            filename = f"report_{date_str}.md"

        

        # quebao reports mulucunzai竊늮hiyongxiangmugenmuluxiade reports竊?
        reports_dir = Path(__file__).parent.parent / 'reports'

        reports_dir.mkdir(parents=True, exist_ok=True)

        

        filepath = reports_dir / filename

        

        with open(filepath, 'w', encoding='utf-8') as f:

            f.write(content)

        

        logger.info(f"ribaoyisavedao: {filepath}")

        return str(filepath)





class NotificationBuilder:

    """

    notificationxiaoxigoujianqi

    

    tigongbianjiedexiaoxigoujianfangfa

    """

    

    @staticmethod

    def build_simple_alert(

        title: str,

        content: str,

        alert_type: str = "info"

    ) -> str:

        """

        goujianjiandandetixingxiaoxi

        

        Args:

            title: biaoti

            content: neirong

            alert_type: leixing竊늝nfo, warning, error, success竊?
        """

        emoji_map = {

            "info": "[정보]",

            "warning": "[주의]",

            "error": "[오류]",

            "success": "[완료]",

        }

        emoji = emoji_map.get(alert_type, "[알림]")

        

        return f"{emoji} **{title}**\n\n{content}"

    

    @staticmethod

    def build_stock_summary(results: List[AnalysisResult]) -> str:

        """

        goujianstockzhaiyao竊늞ianduanban竊?
        

        shiyongyukuaisunotification

        """

        report_language = normalize_report_language(

            next((getattr(result, "report_language", None) for result in results if getattr(result, "report_language", None)), None)

        )

        labels = get_report_labels(report_language)

        lines = [f"?뱤 **{labels['summary_heading']}**", ""]

        

        for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):

            _, emoji, _ = get_signal_level(r.operation_advice, r.sentiment_score, report_language)

            name = get_localized_stock_name(r.name, r.code, report_language)

            lines.append(

                f"{emoji} {name}({r.code}): {localize_operation_advice(r.operation_advice, report_language)} | "

                f"{labels['score_label']} {r.sentiment_score}"

            )

        

        return "\n".join(lines)





# bianjiehanshu

def get_notification_service() -> NotificationService:

    """huoqunotificationfuwushili"""

    return NotificationService()





def send_daily_report(results: List[AnalysisResult]) -> bool:

    """

    sendmeiribaogaodekuaijiefangshi

    

    zidongshibiequdaobingtuisong

    """

    service = get_notification_service()

    

    # shengchengbaogao

    report = service.generate_daily_report(results)

    

    # savedaobendi

    service.save_report_to_file(report)

    

    # tuisongdaoconfigdequdao竊늷idongshibie竊?
    return service.send(report)





if __name__ == "__main__":

    # testdaima

    logging.basicConfig(level=logging.DEBUG)

    from src.analyzer import AnalysisResult

    

    # monianalysisjieguo

    test_results = [

        AnalysisResult(

            code='600519',

            name='Samsung Electronics',

            sentiment_score=75,

            trend_prediction='kanduo',

            analysis_summary='jishumianqiangshi竊똸iaoximianlihao',

            operation_advice='mairu',

            technical_analysis='fangliangtupo MA20竊똌ACD jincha',

            news_summary='gongsifabufenhonggonggao竊똹ejichaoyuqi',

        ),

        AnalysisResult(

            code='000001',

            name='pinganyinhang',

            sentiment_score=45,

            trend_prediction='zhendang',

            analysis_summary='hengpanzhengli竊똡engdaifangxiang',

            operation_advice='chiyou',

            technical_analysis='junxianzhanhe竊똠hengjiaoliangweisuo',

            news_summary='jinqiwuzhongdaxiaoxi',

        ),

        AnalysisResult(

            code='300750',

            name='ningdeshidai',

            sentiment_score=35,

            trend_prediction='kankong',

            analysis_summary='jishumianzouruo竊똺huyifengxian',

            operation_advice='maichu',

            technical_analysis='diepo MA10 zhicheng竊똪iangnengbuzu',

            news_summary='hangyejingzhengjiaju竊똫aolilvchengya',

        ),

    ]

    

    service = NotificationService()

    

    # xianshijiancedaodequdao

    print("=== notificationqudaojiance ===")

    print(f"dangqianqudao: {service.get_channel_names()}")

    print(f"qudaoliebiao: {service.get_available_channels()}")

    print(f"fuwukeyong: {service.is_available()}")

    

    # shengchengribao

    print("\n=== shengchengribaotest ===")

    report = service.generate_daily_report(test_results)

    print(report)

    

    # savedaowenjian

    print("\n=== saveribao ===")

    filepath = service.save_report_to_file(report)

    print(f"savechenggong: {filepath}")

    

    # tuisongtest

    if service.is_available():

        print(f"\n=== 알림 테스트: {service.get_channel_names()} ===")

        success = service.send(report)

        print(f"tuisongjieguo: {'chenggong' if success else 'shibai'}")

    else:

        print("\nnotificationqudaoweiconfig竊똳iaoguotuisongtest")


