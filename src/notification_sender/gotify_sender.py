# -*- coding: utf-8 -*-

"""알림 sender 설명입니다."""



from __future__ import annotations



import logging

from datetime import datetime

from typing import Optional

from urllib.parse import urlparse, urlunparse



import requests



from src.config import Config





logger = logging.getLogger(__name__)





def resolve_gotify_message_endpoint(gotify_url: Optional[str]) -> Optional[str]:

    """알림 sender 설명입니다."""

    raw_url = (gotify_url or "").strip().rstrip("/")

    if not raw_url:

        return None



    parsed = urlparse(raw_url)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:

        return None

    if parsed.query or parsed.fragment:

        return None



    path_segments = [segment for segment in parsed.path.split("/") if segment]

    if path_segments and path_segments[-1].lower() == "message":

        return None



    base_url = urlunparse(

        parsed._replace(

            path="/" + "/".join(path_segments) if path_segments else "",

            params="",

            query="",

            fragment="",

        )

    ).rstrip("/")

    return f"{base_url}/message"





class GotifySender:

    """알림 sender 설명입니다."""



    def __init__(self, config: Config):

        self._gotify_url = getattr(config, "gotify_url", None)

        self._gotify_token = getattr(config, "gotify_token", None)

        self._webhook_verify_ssl = getattr(config, "webhook_verify_ssl", True)



    def _is_gotify_configured(self) -> bool:

        return bool((self._gotify_url or "").strip() and (self._gotify_token or "").strip())



    def _resolve_gotify_endpoint(self) -> Optional[str]:

        return resolve_gotify_message_endpoint(self._gotify_url)



    def send_to_gotify(

        self,

        content: str,

        title: Optional[str] = None,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        """알림 sender 설명입니다."""

        if not self._is_gotify_configured():

            logger.warning("Gotify configbuwanzheng竊똳iaoguotuisong")

            return False



        endpoint = self._resolve_gotify_endpoint()

        if not endpoint:

            logger.error("GOTIFY_URL bixushi Gotify server base URL竊똟ubaohan /message")

            return False



        if title is None:

            date_str = datetime.now().strftime("%Y-%m-%d")

            title = f"?뱢 stockanalysisbaogao - {date_str}"



        headers = {

            "Content-Type": "application/json; charset=utf-8",

            "User-Agent": "daily_stock_analysis",

            "X-Gotify-Key": str(self._gotify_token).strip(),

        }

        payload = {

            "title": title,

            "message": content,

            "extras": {

                "client::display": {

                    "contentType": "text/markdown",

                },

            },

        }



        try:

            response = requests.post(

                endpoint,

                json=payload,

                headers=headers,

                timeout=timeout_seconds or 10,

                verify=self._webhook_verify_ssl,

            )

            if 200 <= response.status_code < 300:

                logger.info("Gotify xiaoxisendchenggong")

                return True



            logger.error("Gotify request_failed: HTTP %s", response.status_code)

            logger.debug("Gotify xiangyingneirong: %s", response.text)

            return False

        except requests.exceptions.Timeout:

            logger.error("send Gotify xiaoxishibai: qingqiuchaoshi")

            return False

        except requests.exceptions.RequestException as exc:

            logger.error("send Gotify xiaoxishibai: wangluoqingqiuyichang")

            logger.debug("Gotify qingqiuyichangleixing: %s", type(exc).__name__)

            return False

        except Exception as exc:

            logger.error("send Gotify xiaoxishibai: weizhiyichang")

            logger.debug("Gotify weizhiyichangleixing: %s", type(exc).__name__)

            return False


