# -*- coding: utf-8 -*-

"""

Email sendtixingfuwu



zhize竊?
1. tongguo SMTP send Email xiaoxi

"""

import logging

from typing import Optional, List

from datetime import datetime

from email.mime.text import MIMEText

from email.mime.multipart import MIMEMultipart

from email.mime.image import MIMEImage

from email.header import Header

from email.utils import formataddr

import smtplib



from data_provider.base import normalize_stock_code

from src.config import Config

from src.formatters import markdown_to_html_document





logger = logging.getLogger(__name__)





# SMTP fuwuqiconfig竊늷idongshibie竊?
SMTP_CONFIGS = {

    # QQyouxiang

    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},

    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},

    # wangyiyouxiang

    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},

    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},

    # Gmail

    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},

    # Outlook

    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},

    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},

    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},

    # xinlang

    "sina.com": {"server": "smtp.sina.com", "port": 465, "ssl": True},

    # souhu

    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "ssl": True},

    # aliyun

    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},

    # 139youxiang

    "139.com": {"server": "smtp.139.com", "port": 465, "ssl": True},

}





class EmailSender:

    

    def __init__(self, config: Config):

        """

        chushihua Email config



        Args:

            config: configduixiang

        """

        self._email_config = {

            'sender': config.email_sender,

            'sender_name': getattr(config, 'email_sender_name', 'daily_stock_analysisstockanalysiszhushou'),

            'password': config.email_password,

            'receivers': config.email_receivers or ([config.email_sender] if config.email_sender else []),

        }

        self._stock_email_groups = getattr(config, 'stock_email_groups', None) or []

        

    def _is_email_configured(self) -> bool:

        """알림 sender 설명입니다."""

        return bool(self._email_config['sender'] and self._email_config['password'])

    

    def get_receivers_for_stocks(self, stock_codes: List[str]) -> List[str]:

        """

        Look up email receivers for given stock codes based on stock_email_groups.

        Returns union of receivers for all matching groups; falls back to default if none match.

        Stock codes are canonicalized before comparison so that equivalent

        formats (e.g. SH600519 vs 600519) match correctly.

        """

        if not stock_codes or not self._stock_email_groups:

            return self._email_config['receivers']

        normalized_codes = [normalize_stock_code(c) for c in stock_codes]

        seen: set = set()

        result: List[str] = []

        for stocks, emails in self._stock_email_groups:

            for code in normalized_codes:

                if code in stocks:

                    for e in emails:

                        if e not in seen:

                            seen.add(e)

                            result.append(e)

                    break

        return result if result else self._email_config['receivers']



    def get_all_email_receivers(self) -> List[str]:

        """

        Return union of all configured email receivers (all groups + default).

        Used for market review which should go to everyone.

        """

        seen: set = set()

        result: List[str] = []

        for _, emails in self._stock_email_groups:

            for e in emails:

                if e not in seen:

                    seen.add(e)

                    result.append(e)

        for e in self._email_config['receivers']:

            if e not in seen:

                seen.add(e)

                result.append(e)

        return result



    def _format_sender_address(self, sender: str) -> str:

        """알림 sender 설명입니다."""

        sender_name = self._email_config.get('sender_name') or 'stockanalysiszhushou'

        return formataddr((str(Header(str(sender_name), 'utf-8')), sender))



    @staticmethod

    def _close_server(server: Optional[smtplib.SMTP]) -> None:

        """Best-effort SMTP cleanup to avoid leaving sockets open on header/build errors.



        Exceptions from quit()/close() are intentionally silenced ??connection may already

        be in a broken state, and there is nothing useful to do at this point.

        """

        if server is None:

            return

        try:

            server.quit()

        except Exception:

            try:

                server.close()

            except Exception:

                pass

    

    def send_to_email(

        self,

        content: str,

        subject: Optional[str] = None,

        receivers: Optional[List[str]] = None,

        *,

        timeout_seconds: Optional[float] = None,

    ) -> bool:

        """

        tongguo SMTP sendyoujian竊늷idongshibie SMTP fuwuqi竊?
        

        Args:

            content: youjianneirong竊늷hichi Markdown竊똦uizhuanhuanwei HTML竊?
            subject: youjianzhuti竊늟exuan竊똫orenzidongshengcheng竊?
            receivers: shoujianrenliebiao竊늟exuan竊똫orenshiyongconfigde receivers竊?
            

        Returns:

            shifousendchenggong

        """

        if not self._is_email_configured():

            logger.warning("youjianconfigbuwanzheng竊똳iaoguotuisong")

            return False

        

        sender = self._email_config['sender']

        password = self._email_config['password']

        receivers = receivers or self._email_config['receivers']

        server: Optional[smtplib.SMTP] = None

        

        try:

            # shengchengzhuti

            if subject is None:

                date_str = datetime.now().strftime('%Y-%m-%d')

                subject = f"?뱢 stockzhinenganalysisbaogao - {date_str}"

            

            # jiang Markdown zhuanhuanweijiandan HTML

            html_content = markdown_to_html_document(content)

            

            # goujianyoujian

            msg = MIMEMultipart('alternative')

            msg['Subject'] = Header(subject, 'utf-8')

            msg['From'] = self._format_sender_address(sender)

            msg['To'] = ', '.join(receivers)

            

            # addchunwenbenhe HTML lianggebanben

            text_part = MIMEText(content, 'plain', 'utf-8')

            html_part = MIMEText(html_content, 'html', 'utf-8')

            msg.attach(text_part)

            msg.attach(html_part)

            

            # zidongshibie SMTP config

            domain = sender.split('@')[-1].lower()

            smtp_config = SMTP_CONFIGS.get(domain)

            

            if smtp_config:

                smtp_server = smtp_config['server']

                smtp_port = smtp_config['port']

                use_ssl = smtp_config['ssl']

                logger.info(f"zidongshibieyouxiangleixing: {domain} -> {smtp_server}:{smtp_port}")

            else:

                # weizhiyouxiang竊똠hangshitongyongconfig

                smtp_server = f"smtp.{domain}"

                smtp_port = 465

                use_ssl = True

                logger.warning(f"weizhiyouxiangleixing {domain}竊똠hangshitongyongconfig: {smtp_server}:{smtp_port}")

            

            # genjuconfigxuanzelianjiefangshi

            if use_ssl:

                # SSL lianjie竊늕uankou 465竊?
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=timeout_seconds or 30)

            else:

                # TLS lianjie竊늕uankou 587竊?
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=timeout_seconds or 30)

                server.starttls()

            

            server.login(sender, password)

            server.send_message(msg)

            

            logger.info(f"youjiansendchenggong竊똲houjianren: {receivers}")

            return True

            

        except smtplib.SMTPAuthenticationError:

            logger.error("youjiansendshibai竊쉜enzhengcuowu竊똰ingjianchayouxiangheshouquanmashifouzhengque")

            return False

        except smtplib.SMTPConnectError as e:

            logger.error(f"youjiansendshibai竊쉢ufalianjie SMTP fuwuqi - {e}")

            return False

        except Exception as e:

            logger.error(f"sendyoujianshibai: {e}")

            return False

        finally:

            self._close_server(server)



    def _send_email_with_inline_image(

        self, image_bytes: bytes, receivers: Optional[List[str]] = None

    ) -> bool:

        """알림 sender 설명입니다."""

        if not self._is_email_configured():

            return False

        sender = self._email_config['sender']

        password = self._email_config['password']

        receivers = receivers or self._email_config['receivers']

        server: Optional[smtplib.SMTP] = None

        try:

            date_str = datetime.now().strftime('%Y-%m-%d')

            subject = f"?뱢 stockzhinenganalysisbaogao - {date_str}"

            msg = MIMEMultipart('related')

            msg['Subject'] = Header(subject, 'utf-8')

            msg['From'] = self._format_sender_address(sender)

            msg['To'] = ', '.join(receivers)



            alt = MIMEMultipart('alternative')

            alt.attach(MIMEText('보고서가 생성되었습니다. 아래 이미지를 확인하세요.', 'plain', 'utf-8'))

            html_body = (

                '<p>baogaoyishengcheng竊똸iangjianxiafangtupian竊늕ianjikeviewdatu竊됵폏</p>'

                '<p><img src="cid:report-image" alt="stockanalysisbaogao" style="max-width:100%%;" /></p>'

            )

            alt.attach(MIMEText(html_body, 'html', 'utf-8'))

            msg.attach(alt)



            img_part = MIMEImage(image_bytes, _subtype='png')

            img_part.add_header('Content-Disposition', 'inline', filename='report.png')

            img_part.add_header('Content-ID', '<report-image>')

            msg.attach(img_part)



            domain = sender.split('@')[-1].lower()

            smtp_config = SMTP_CONFIGS.get(domain)

            if smtp_config:

                smtp_server, smtp_port = smtp_config['server'], smtp_config['port']

                use_ssl = smtp_config['ssl']

            else:

                smtp_server, smtp_port = f"smtp.{domain}", 465

                use_ssl = True



            if use_ssl:

                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)

            else:

                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)

                server.starttls()

            server.login(sender, password)

            server.send_message(msg)

            logger.info("youjian竊늧eiliantupian竊뎕asongchenggong竊똲houjianren: %s", receivers)

            return True

        except Exception as e:

            logger.error("youjian竊늧eiliantupian竊뎕asongshibai: %s", e)

            return False

        finally:

            self._close_server(server)


