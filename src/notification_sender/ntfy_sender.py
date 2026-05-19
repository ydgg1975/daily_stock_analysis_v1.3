# -*- coding: utf-8 -*-

"""알림 sender 설명입니다."""



from __future__ import annotations



import logging

from datetime import datetime

from typing import Optional, Tuple

from urllib.parse import unquote, urlparse, urlunparse



import requests



from src.config import Config





logger = logging.getLogger(__name__)





def resolve_ntfy_endpoint(ntfy_url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:

    """알림 sender 설명입니다."""

    raw_url = (ntfy_url or "").strip().rstrip("/")

    if not raw_url:

        return None, None



    parsed = urlparse(raw_url)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:

        return None, None



    path_segments = [segment for segment in parsed.path.split("/") if segment]

    if not path_segments:

        return None, None



    topic = unquote(path_segments[-1]).strip()

    if not topic:

        return None, None



    root_path = "/".join(path_segments[:-1])

    server_url = urlunparse(

        parsed._replace(

            path=f"/{root_path}" if root_path else "",

            params="",

            query="",

            fragment="",

        )

    ).rstrip("/")



    return server_url, topic





class NtfySender:

    """알림 sender 설명입니다."""



    def __init__(self, config: Config):

        self._ntfy_url = getattr(config, "ntfy_url", None)

        self._ntfy_token = getattr(config, "ntfy_token", None)

        self._webhook_verify_ssl = getattr(config, "webhook_verify_ssl", True)



    def _is_ntfy_configured(self) -> bool:

        return bool(self._ntfy_url)



    def _resolve_ntfy_endpoint(self) -> Tuple[Optional[str], Optional[str]]:

        return resolve_ntfy_endpoint(self._ntfy_url)



    def send_to_ntfy(

        self,

        content: str,

        title: Optional[str] = None,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        """알림 sender 설명입니다."""

        if not self._is_ntfy_configured():

            logger.warning("ntfy URL weiconfig竊똳iaoguotuisong")

            return False



        server_url, topic = self._resolve_ntfy_endpoint()

        if not server_url or not topic:

            logger.error("NTFY_URL bixushibaohan topic path dewanzheng endpoint竊똪iru https://ntfy.sh/my-topic")

            return False



        if title is None:

            date_str = datetime.now().strftime("%Y-%m-%d")

            title = f"?뱢 stockanalysisbaogao - {date_str}"



        headers = {

            "Content-Type": "application/json; charset=utf-8",

            "User-Agent": "daily_stock_analysis",

        }

        token = (self._ntfy_token or "").strip()

        if token:

            headers["Authorization"] = f"Bearer {token}"



        payload = {

            "topic": topic,

            "title": title,

            "message": content,

            "markdown": True,

        }



        try:

            response = requests.post(

                server_url,

                json=payload,

                headers=headers,

                timeout=timeout_seconds or 10,

                verify=self._webhook_verify_ssl,

            )

            if 200 <= response.status_code < 300:

                logger.info("ntfy xiaoxisendchenggong")

                return True



            logger.error("ntfy request_failed: HTTP %s", response.status_code)

            logger.debug("ntfy xiangyingneirong: %s", response.text)

            return False

        except requests.exceptions.Timeout:

            logger.error("send ntfy xiaoxishibai: qingqiuchaoshi")

            return False

        except requests.exceptions.RequestException as exc:

            logger.error("send ntfy xiaoxishibai: wangluoqingqiuyichang")

            logger.debug("ntfy qingqiuyichangleixing: %s", type(exc).__name__)

            return False

        except Exception as exc:

            logger.error("send ntfy xiaoxishibai: weizhiyichang")

            logger.debug("ntfy weizhiyichangleixing: %s", type(exc).__name__)

            return False


