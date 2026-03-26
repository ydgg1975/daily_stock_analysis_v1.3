# -*- coding: utf-8 -*-
"""
Discord 发送提醒服务

职责：
1. 通过 webhook 或 Discord bot API 发送 Discord 消息
"""
import logging
import re
import time
import requests

from src.config import Config
from src.formatters import chunk_content_by_max_words


logger = logging.getLogger(__name__)
_NUMERIC_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")


class DiscordSender:
    
    def __init__(self, config: Config):
        """
        初始化 Discord 配置

        Args:
            config: 配置对象
        """
        self._discord_config = {
            'bot_token': getattr(config, 'discord_bot_token', None),
            'channel_id': getattr(config, 'discord_main_channel_id', None),
            'webhook_url': getattr(config, 'discord_webhook_url', None),
        }
        self._discord_max_words = getattr(config, 'discord_max_words', 2000)
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)
    
    def _is_discord_configured(self) -> bool:
        """检查 Discord 配置是否完整（支持 Bot 或 Webhook）"""
        # 只要配置了 Webhook 或完整的 Bot Token+Channel，即视为可用
        bot_ok = bool(self._discord_config['bot_token'] and self._discord_config['channel_id'])
        webhook_ok = bool(self._discord_config['webhook_url'])
        return bot_ok or webhook_ok
    
    def send_to_discord(self, content: str) -> bool:
        """
        推送消息到 Discord（支持 Webhook 和 Bot API）
        
        Args:
            content: Markdown 格式的消息内容
            
        Returns:
            是否发送成功
        """
        compact_content = self._compact_discord_markdown(content)
        chunks = self._chunk_discord_content(compact_content)

        # 优先使用 Webhook（配置简单，权限低）
        if self._discord_config['webhook_url']:
            return self._send_chunks_in_order(chunks, self._send_discord_webhook)

        # 其次使用 Bot API（权限高，需要 channel_id）
        if self._discord_config['bot_token'] and self._discord_config['channel_id']:
            return self._send_chunks_in_order(chunks, self._send_discord_bot)

        logger.warning("Discord 配置不完整，跳过推送")
        return False

    @staticmethod
    def _compact_discord_markdown(content: str) -> str:
        """Trim low-value verbose sections for mobile-friendly Discord cards."""
        if not content:
            return content
        lines = content.replace("\r\n", "\n").split("\n")

        hidden_section_titles = (
            "### 🕒 时间语义",
            "### 🧩 数据质量说明",
            "### 🧾 基本面摘要",
            "### 📈 财报趋势",
            "### 🧠 结构化情绪",
            "### 🧠 情绪摘要",
        )
        hidden_inline_prefix = (
            "> 报告时间(report_generated_at):",
            "> 市场时间(market_timestamp):",
            "> 交易日(market_session_date):",
            "> 会话类型(session_type):",
            "> news_published_at:",
            "report_generated_at:",
            "market_timestamp:",
            "market_session_date:",
            "session_type:",
            "news_published_at:",
            "*报告生成时间",
            "*Generated at",
            "**Alpha Vantage 补充指标**:",
            "**筹码**: 美股暂不支持该指标",
        )
        key_row_tokens = (
            "当前价", "涨跌幅", "最高", "最低", "成交量",
            "ma5", "ma10", "ma20", "支撑", "压力",
            "理想买入", "止损", "目标", "仓位",
            "空仓", "持仓",
        )
        metric_tokens = ("revenueGrowth", "forwardPE", "freeCashflow", "debtToEquity", "totalRevenue")

        def _safe_float(value):
            if value in (None, "", "N/A", "数据缺失"):
                return None
            try:
                text = str(value).strip().replace(",", "")
                if text.endswith("%"):
                    text = text[:-1]
                return float(text)
            except (TypeError, ValueError):
                return None

        def _format_price(value):
            num = _safe_float(value)
            if num is None:
                return str(value).strip()
            return f"{num:.2f}"

        def _format_percent(value, *, ratio: bool = False, digits: int = 1):
            if value in (None, "", "N/A", "数据缺失"):
                return ""
            text = str(value).strip()
            num = _safe_float(text)
            if num is None:
                return text
            if text.endswith("%"):
                return f"{num:.{digits}f}%"
            if ratio:
                num *= 100
            return f"{num:.{digits}f}%"

        def _format_money(value):
            num = _safe_float(value)
            if num is None:
                return str(value).strip()
            abs_num = abs(num)
            if abs_num >= 1_0000_0000:
                return f"{num / 1_0000_0000:.1f} 亿"
            if abs_num >= 1_0000:
                return f"{num / 1_0000:.1f} 万"
            return f"{num:.2f}"

        def _format_count(value):
            num = _safe_float(value)
            if num is None:
                return str(value).strip()
            abs_num = abs(num)
            if abs_num >= 1_0000_0000:
                return f"{num / 1_0000_0000:.2f}亿"
            if abs_num >= 1_0000:
                return f"{num / 1_0000:.2f}万"
            return f"{num:.0f}"

        def _format_numeric_phrase(value):
            text = str(value).strip()
            if not text:
                return text
            return _NUMERIC_TOKEN_RE.sub(lambda m: f"{float(m.group(0)):.2f}", text)

        def _join_short_clauses(parts: list[str]) -> str:
            cleaned = [p.strip(" ，。；;") for p in parts if p and p.strip(" ，。；;")]
            if not cleaned:
                return ""
            if len(cleaned) == 1:
                return f"{cleaned[0]}。"
            if len(cleaned) == 2:
                return f"{cleaned[0]}，{cleaned[1]}。"
            return f"{'、'.join(cleaned[:-1])}，{cleaned[-1]}。"

        def _strip_md_label(line: str) -> str:
            text = line.strip()
            if text.startswith("- "):
                text = text[2:].strip()
            return text.replace("**", "").strip()

        def _extract_labeled_value(body: list[str], labels: tuple[str, ...]) -> str:
            for raw in body:
                text = _strip_md_label(raw)
                for label in labels:
                    for sep in ("：", ":"):
                        prefix = f"{label}{sep}"
                        if text.startswith(prefix):
                            return text[len(prefix):].strip()
            return ""

        def _humanize_fundamental_conclusion(text: str) -> str:
            mapping = {
                "valuation_high": "估值偏高",
                "valuation_low": "估值偏低",
                "valuation_neutral": "估值合理",
                "high_growth": "增长强劲",
                "stable_growth": "增长稳健",
                "negative_growth": "增长承压",
                "profitable": "盈利能力优秀",
                "near_breakeven_or_loss": "盈利能力承压",
                "gross_margin_positive": "毛利水平尚可",
                "cashflow_healthy": "现金流健康",
                "cashflow_pressure": "现金流承压",
                "high_leverage": "杠杆偏高",
                "leverage_controllable": "杠杆可控",
            }
            tokens = [mapping.get(token.strip()) for token in text.replace("；", ",").split(",")]
            humanized = _join_short_clauses([item for item in tokens if item])
            if humanized:
                return humanized
            cleaned = text.strip(" ：:;；")
            if cleaned and not cleaned.endswith("。"):
                cleaned = f"{cleaned}。"
            return cleaned

        def _humanize_metric(name: str, value: str) -> str:
            key = name.strip()
            normalized_key = key.lower()
            if normalized_key == "revenuegrowth":
                return f"营收增速 {_format_percent(value, ratio=True, digits=1)}"
            if normalized_key == "forwardpe":
                return f"前瞻PE {_format_price(value)} 倍"
            if normalized_key == "trailingpe":
                return f"TTM PE {_format_price(value)} 倍"
            if normalized_key == "freecashflow":
                return f"自由现金流 {_format_money(value)}"
            if normalized_key == "operatingcashflow":
                return f"经营现金流 {_format_money(value)}"
            if normalized_key == "debtequity" or normalized_key == "debttoequity":
                return f"负债权益比 {_format_percent(value, digits=1)}"
            if normalized_key == "totalrevenue":
                return f"营收规模 {_format_money(value)}"
            return f"{key}={value}"

        def _humanize_table_value(key: str, value: str) -> str:
            raw_key = key.strip()
            if any(token in raw_key for token in ("当前价", "最高", "最低", "支撑", "压力", "MA", "ma")):
                return _format_price(value)
            if any(token in raw_key for token in ("理想买入", "次优买入", "止损", "目标")):
                return _format_numeric_phrase(value)
            if any(token in raw_key for token in ("涨跌幅", "乖离", "换手率", "仓位")):
                return _format_percent(value, digits=2)
            if "成交量" in raw_key:
                return _format_count(value)
            return value

        def _collect_section_body(start_idx: int) -> tuple[list[str], int]:
            body: list[str] = []
            j = start_idx + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if nxt.startswith("### ") or nxt.startswith("## "):
                    break
                body.append(lines[j])
                j += 1
            return body, j

        def _summarize_fundamentals(body: list[str]) -> str:
            conclusion = _extract_labeled_value(body, ("基本面", "基本面摘要", "基本面结论"))
            metrics_text = _extract_labeled_value(body, ("关键指标",))
            metrics: list[str] = []
            if conclusion:
                conclusion = _humanize_fundamental_conclusion(conclusion)
            if metrics_text:
                metrics_text = metrics_text.strip().rstrip("。")
            for line in body:
                s = line.strip()
                if "基本面结论" in s and not conclusion:
                    conclusion = _humanize_fundamental_conclusion(s.split(":", 1)[-1].strip())
                if s.startswith("|"):
                    row = [x.strip() for x in s.split("|")[1:-1]]
                    if len(row) >= 2 and any(t in row[0] for t in metric_tokens):
                        if row[1] and row[1] not in {"数据缺失", "N/A"}:
                            metrics.append(_humanize_metric(row[0], row[1]))
            metrics = metrics[:4]
            if not metrics_text and metrics:
                metrics_text = "、".join(metrics)
            if conclusion and metrics_text:
                return f"基本面：{conclusion.rstrip('。')}；关键指标：{metrics_text}"
            if conclusion:
                return f"基本面：{conclusion}"
            if metrics_text:
                return f"关键指标：{metrics_text}"
            return ""

        def _summarize_earnings(body: list[str]) -> str:
            for label in ("财报趋势", "结论"):
                text = _extract_labeled_value(body, (label,))
                if text:
                    cleaned = text.removeprefix("财报趋势：").removeprefix("财报趋势:").strip()
                    if cleaned and not cleaned.endswith("。"):
                        cleaned = f"{cleaned}。"
                    return f"财报趋势：{cleaned}"
            for line in body:
                s = line.strip()
                if s.startswith("- 结论:"):
                    cleaned = s.replace("- 结论:", "").strip()
                    if cleaned.startswith("财报趋势"):
                        cleaned = cleaned.split("：", 1)[-1].split(":", 1)[-1].strip()
                    if cleaned and not cleaned.endswith("。"):
                        cleaned = f"{cleaned}。"
                    return f"财报趋势：{cleaned}"
            return ""

        def _summarize_sentiment(body: list[str]) -> str:
            text = _extract_labeled_value(body, ("情绪", "情绪摘要"))
            if text:
                if not text.endswith("。"):
                    text = f"{text}。"
                return f"情绪：{text}"
            company = industry = regulatory = ""
            for line in body:
                s = line.strip()
                if s.startswith("- company_sentiment:"):
                    company = s.split(":", 1)[-1].strip()
                if s.startswith("- industry_sentiment:"):
                    industry = s.split(":", 1)[-1].strip()
                if s.startswith("- regulatory_sentiment:"):
                    regulatory = s.split(":", 1)[-1].strip()
            if regulatory == "negative":
                return "情绪：消息面存在监管扰动，市场整体偏谨慎。"
            if company == "positive":
                return "情绪：公司相关消息偏积极，市场整体偏谨慎乐观。"
            if company == "negative":
                return "情绪：公司相关消息偏谨慎，短线情绪仍以防守为主。"
            if company == "neutral" or industry == "neutral":
                return "情绪：消息面暂无明确方向性催化，市场情绪偏观望。"
            if company == "no_reliable_news":
                return "情绪：缺少高相关度公司新闻，市场情绪以观望为主。"
            return ""

        out: list[str] = []
        in_hidden_section = False
        in_info_section = False
        info_kept = 0
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()
            if stripped.startswith("|") and idx + 1 < len(lines) and lines[idx + 1].strip().startswith("|-"):
                table_rows: list[str] = []
                j = idx + 2
                while j < len(lines) and lines[j].strip().startswith("|"):
                    row = [x.strip() for x in lines[j].split("|")[1:-1]]
                    if len(row) >= 2:
                        k, v = row[0], row[1]
                        lk = k.lower()
                        if any(token in lk for token in key_row_tokens):
                            if v and v not in {"数据缺失", "N/A", "美股暂不支持该指标"}:
                                table_rows.append(f"- {k}: {_humanize_table_value(k, v)}")
                    j += 1
                out.extend(table_rows)
                idx = j
                continue

            if stripped.startswith("## "):
                in_hidden_section = False
                in_info_section = stripped.startswith("### 📰 重要信息速览") or stripped.startswith("## 📰 重要信息速览")
            if stripped.startswith("### "):
                in_hidden_section = any(stripped.startswith(x) for x in hidden_section_titles)
                in_info_section = stripped.startswith("### 📰 重要信息速览")
                if stripped.startswith("### 🧾 基本面摘要"):
                    body, idx = _collect_section_body(idx)
                    summary = _summarize_fundamentals(body)
                    if summary:
                        out.append(f"- {summary}")
                    continue
                if stripped.startswith("### 📈 财报趋势"):
                    body, idx = _collect_section_body(idx)
                    summary = _summarize_earnings(body)
                    if summary:
                        out.append(f"- {summary}")
                    continue
                if stripped.startswith("### 🧠 结构化情绪") or stripped.startswith("### 🧠 情绪摘要"):
                    body, idx = _collect_section_body(idx)
                    summary = _summarize_sentiment(body)
                    if summary:
                        out.append(f"- {summary}")
                    continue
            if in_hidden_section:
                idx += 1
                continue
            if any(stripped.startswith(x) for x in hidden_inline_prefix):
                idx += 1
                continue

            if any(x in stripped for x in ("数据缺失", "N/A", "美股暂不支持该指标")):
                idx += 1
                continue
            if in_info_section and stripped and not stripped.startswith("### "):
                if stripped.startswith("- ") or stripped.startswith("**"):
                    info_kept += 1
                    if info_kept > 4:
                        idx += 1
                        continue
            if (stripped.startswith("## ") or stripped.startswith("### ")) and "检查清单" in stripped:
                out.append("执行确认：重点确认买点、量价配合和止损纪律。")
                idx += 1
                continue
            if stripped.startswith("- ") and out and "检查清单" in out[-1]:
                idx += 1
                continue

            out.append(line)
            idx += 1

        # collapse excessive blank lines
        compact: list[str] = []
        blank_count = 0
        for line in out:
            if line.strip() == "":
                blank_count += 1
                if blank_count > 1:
                    continue
            else:
                blank_count = 0
            compact.append(line)
        return "\n".join(compact).strip()

    def _chunk_discord_content(self, content: str) -> list[str]:
        """Chunk content by markdown sections first, then fallback to generic word chunking."""
        if not content:
            return [""]
        try:
            return self._chunk_by_markdown_sections(content)
        except Exception as e:
            logger.warning("Discord 章节分块失败，回退普通分块: %s", e)
            try:
                return chunk_content_by_max_words(content, self._discord_max_words, add_page_marker=True)
            except ValueError:
                return [content]

    def _chunk_by_markdown_sections(self, content: str) -> list[str]:
        normalized = content.replace("\r\n", "\n")
        lines = normalized.split("\n")
        sections: list[str] = []
        cur: list[str] = []
        for line in lines:
            if line.startswith("## ") and cur:
                sections.append("\n".join(cur))
                cur = [line]
            else:
                cur.append(line)
        if cur:
            sections.append("\n".join(cur))

        chunks: list[str] = []
        current = ""
        for section in sections:
            candidate = f"{current}\n\n{section}".strip() if current else section
            try:
                parts = chunk_content_by_max_words(candidate, self._discord_max_words)
            except ValueError:
                parts = [candidate]
            if len(parts) == 1:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""
            try:
                section_parts = chunk_content_by_max_words(section, self._discord_max_words)
            except ValueError:
                section_parts = [section]
            chunks.extend(section_parts)

        if current:
            chunks.append(current)
        if not chunks:
            chunks = [normalized]

        total = len(chunks)
        if total > 1:
            return [f"{chunk}\n\n(Part {idx+1}/{total})" for idx, chunk in enumerate(chunks)]
        return chunks

    @staticmethod
    def _send_chunks_in_order(chunks: list[str], send_func) -> bool:
        failed_indexes: list[int] = []
        for idx, chunk in enumerate(chunks, start=1):
            ok = send_func(chunk)
            if not ok:
                failed_indexes.append(idx)
            if idx < len(chunks):
                time.sleep(0.3)
        if failed_indexes:
            logger.error("Discord 分块发送存在失败块: %s", failed_indexes)
            return False
        return True

  
    def _send_discord_webhook(self, content: str) -> bool:
        """
        使用 Webhook 发送消息到 Discord
        
        Discord Webhook 支持 Markdown 格式
        
        Args:
            content: Markdown 格式的消息内容
            
        Returns:
            是否发送成功
        """
        try:
            payload = {
                'content': content,
                'username': 'A股分析机器人',
                'avatar_url': 'https://picsum.photos/200'
            }
            
            response = requests.post(
                self._discord_config['webhook_url'],
                json=payload,
                timeout=10,
                verify=self._webhook_verify_ssl
            )
            
            if response.status_code in [200, 204]:
                logger.info("Discord Webhook 消息发送成功")
                return True
            else:
                logger.error(f"Discord Webhook 发送失败: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Discord Webhook 发送异常: {e}")
            return False
    
    def _send_discord_bot(self, content: str) -> bool:
        """
        使用 Bot API 发送消息到 Discord
        
        Args:
            content: Markdown 格式的消息内容
            
        Returns:
            是否发送成功
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
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info("Discord Bot 消息发送成功")
                return True
            else:
                logger.error(f"Discord Bot 发送失败: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Discord Bot 发送异常: {e}")
            return False
