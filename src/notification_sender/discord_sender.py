import re
# -*- coding: utf-8 -*-
"""
Discord 发送提醒服务

职责：
1. 通过 webhook 或 Discord bot API 发送 Discord 消息
"""
import logging
import time
import requests

from src.config import Config
from src.formatters import chunk_content_by_max_words


logger = logging.getLogger(__name__)
_NUMERIC_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")
_DISCORD_FIELD_RE = re.compile(r"^- \*\*(.+?)\*\*: (.+)$")
_DISCORD_HARD_CHAR_LIMIT = 2000
_DISCORD_PART_MARKER_RESERVE = 32


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
        configured_limit = getattr(config, 'discord_max_words', _DISCORD_HARD_CHAR_LIMIT)
        self._discord_max_words = max(1, int(configured_limit))
        self._discord_chunk_limit = min(
            self._discord_max_words,
            _DISCORD_HARD_CHAR_LIMIT - _DISCORD_PART_MARKER_RESERVE,
        )
        self._discord_hard_char_limit = _DISCORD_HARD_CHAR_LIMIT
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
        if not self._is_discord_configured():
            logger.warning("Discord 配置不完整，跳过推送")
            return False

        discord_ready = self._optimize_markdown_for_discord(content)
        chunks = self._chunk_discord_content(discord_ready)
        transport = "webhook" if self._discord_config['webhook_url'] else "bot"
        logger.info(
            "Discord 推送已触发: transport=%s, chunks=%d, original_chars=%d, optimized_chars=%d",
            transport,
            len(chunks),
            len(content or ""),
            len(discord_ready or ""),
        )

        # 优先使用 Webhook（配置简单，权限低）
        if self._discord_config['webhook_url']:
            return self._send_chunks_in_order(chunks, self._send_discord_webhook)

        # 其次使用 Bot API（权限高，需要 channel_id）
        if self._discord_config['bot_token'] and self._discord_config['channel_id']:
            return self._send_chunks_in_order(chunks, self._send_discord_bot)
        return False

    @classmethod
    def _optimize_markdown_for_discord(cls, content: str) -> str:
        """Convert the full markdown report into a Discord-friendly compact digest."""
        if not content:
            return content
        compact = cls._build_compact_stock_digest(content)
        source = compact or content
        return cls._flatten_markdown_tables(source)

    @staticmethod
    def _flatten_markdown_tables(content: str) -> str:
        """Convert markdown tables into compact bullet lists for Discord readability."""
        lines = content.replace("\r\n", "\n").split("\n")
        out: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("|") and i + 2 < len(lines) and lines[i + 1].strip().startswith("|"):
                headers = [x.strip() for x in stripped.split("|")[1:-1]]
                divider = lines[i + 1].strip()
                if divider.startswith("|") and all(set(seg.strip()) <= set('-:') for seg in divider.split('|')[1:-1]):
                    i += 2
                    while i < len(lines) and lines[i].strip().startswith("|"):
                        cells = [x.strip() for x in lines[i].strip().split("|")[1:-1]]
                        if len(headers) == 2 and len(cells) >= 2:
                            out.append(f"- **{cells[0]}**: {cells[1]}")
                        elif len(headers) == len(cells):
                            pairs = [f"{h}={v}" for h, v in zip(headers, cells)]
                            out.append(f"- {' | '.join(pairs)}")
                        else:
                            out.append(lines[i])
                        i += 1
                    continue
            out.append(line)
            i += 1
        return "\n".join(out)

    @staticmethod
    def _compact_list_value(value: str, limit: int = 2) -> str:
        text = str(value or "").strip()
        if not text:
            return "NA（接口未返回）"
        if text.startswith("NA（"):
            return text
        items = [item.strip() for item in re.split(r"[；;]\s*", text) if item.strip()]
        if not items:
            return text
        return "；".join(items[:limit])

    @staticmethod
    def _truncate_text(value: str, limit: int = 96) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit - 1]}…"

    @classmethod
    def _build_compact_stock_digest(cls, content: str) -> str:
        normalized = content.replace("\r\n", "\n")
        if (
            "### 1. 标题区 / Title" not in normalized
            and "### 1. Title" not in normalized
            and "### Part A. Executive Summary" not in normalized
        ):
            return ""
        lines = normalized.split("\n")
        header_lines: list[str] = []
        stocks: list[dict[str, object]] = []
        current_stock: dict[str, object] | None = None
        current_section = ""

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## ") and not stripped.startswith("## 📊"):
                if current_stock:
                    stocks.append(current_stock)
                current_stock = {
                    "header": stripped[3:].strip(),
                    "fields": {},
                    "checklist": [],
                }
                current_section = ""
                continue

            if current_stock is None:
                if stripped and (stripped.startswith("# ") or stripped.startswith("> ")):
                    header_lines.append(stripped)
                continue

            if stripped.startswith("### ") or stripped.startswith("#### "):
                current_section = stripped
                continue

            if not stripped or stripped == "---":
                continue

            if stripped.startswith("- "):
                field_match = _DISCORD_FIELD_RE.match(stripped)
                if field_match:
                    fields = current_stock["fields"]
                    if isinstance(fields, dict):
                        fields[field_match.group(1).strip()] = field_match.group(2).strip()
                    continue

                if (
                    "检查清单" in current_section
                    or "Checklist" in current_section
                    or "Action Plan" in current_section
                ):
                    checklist = current_stock["checklist"]
                    if isinstance(checklist, list):
                        checklist.append(stripped[2:].strip())

        if current_stock:
            stocks.append(current_stock)

        if not stocks:
            return ""

        output: list[str] = []
        if header_lines:
            output.extend(header_lines[:3])

        for stock in stocks:
            fields = stock.get("fields")
            checklist = stock.get("checklist")
            if not isinstance(fields, dict):
                continue

            def pick(label: str, default: str = "NA（接口未返回）") -> str:
                value = str(fields.get(label) or "").strip()
                return value or default

            header = str(stock.get("header") or "").strip()
            if not header:
                continue

            output.append("")
            output.append(f"## {header}")
            score_line = pick(
                "评分 / 建议 / 趋势",
                f"{pick('评分')} / {pick('买入 / 观望 / 卖出')} / {pick('看多 / 看空 / 震荡')}",
            )
            one_line = pick("一句话结论", pick("一句话决策"))
            current_line = pick(
                "当前价 / 涨跌",
                f"当前价 {pick('当前价')} | 涨跌 {pick('涨跌额')} / {pick('涨跌幅')}",
            )
            execution_line = pick(
                "理想买入点 / 次优买入点 / 止损位 / 目标位 / 仓位",
                f"{pick('理想买入点')} / {pick('次优买入点')} / {pick('止损位')} / {pick('目标位')} / {pick('仓位建议')}",
            )
            top_risk = pick("核心风险", cls._compact_list_value(pick("风险警报")))
            top_catalyst = pick("核心利好", cls._compact_list_value(pick("利好催化")))
            latest_update = pick("最新关键更新", cls._compact_list_value(pick("最新动态 / 重要公告", pick("新闻价值分级"))))
            no_position = pick("空仓者建议")
            holder = pick("持仓者建议")

            output.append(f"- **评分 / 建议 / 趋势**: {score_line}")
            output.append(f"- **一句话结论**: {cls._truncate_text(one_line)}")
            output.append(f"- **当前价 / 涨跌**: {current_line}")
            output.append(f"- **执行计划**: {execution_line}")
            output.append(f"- **核心风险**: {cls._truncate_text(top_risk, 120)}")
            output.append(f"- **核心利好**: {cls._truncate_text(top_catalyst, 120)}")
            output.append(f"- **最新关键更新**: {cls._truncate_text(latest_update, 120)}")
            if no_position != "NA（接口未返回）" or holder != "NA（接口未返回）":
                output.append(
                    f"- **空仓 / 持仓建议**: 空仓 {cls._truncate_text(no_position, 64)} | 持仓 {cls._truncate_text(holder, 64)}"
                )

            compact_checklist = []
            if isinstance(checklist, list):
                compact_checklist = [str(item).strip() for item in checklist if str(item).strip()][:4]
            checklist_summary = pick("Checklist 摘要")
            if checklist_summary != "NA（接口未返回）":
                output.append(f"- **Checklist 摘要**: {cls._truncate_text(checklist_summary, 120)}")
            elif compact_checklist:
                output.append(f"- **Checklist 摘要**: {'；'.join(compact_checklist)}")

        return "\n".join(output).strip()

    def _chunk_discord_content(self, content: str) -> list[str]:
        """Chunk content by markdown sections first, then fallback to generic word chunking."""
        if not content:
            return [""]
        try:
            chunks = self._chunk_by_markdown_sections(content)
        except Exception as e:
            logger.warning("Discord 章节分块失败，回退普通分块: %s", e)
            try:
                chunks = chunk_content_by_max_words(content, self._discord_chunk_limit, add_page_marker=False)
            except ValueError:
                chunks = [content]
        return self._add_part_markers(self._enforce_chunk_limit(chunks))

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
                parts = chunk_content_by_max_words(candidate, self._discord_chunk_limit)
            except ValueError:
                parts = [candidate]
            if len(parts) == 1:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""
            try:
                section_parts = chunk_content_by_max_words(section, self._discord_chunk_limit)
            except ValueError:
                section_parts = [section]
            chunks.extend(section_parts)

        if current:
            chunks.append(current)
        if not chunks:
            chunks = [normalized]
        return chunks

    def _enforce_chunk_limit(self, chunks: list[str]) -> list[str]:
        normalized: list[str] = []
        for chunk in chunks:
            normalized.extend(self._split_oversized_chunk(chunk))
        return normalized or [""]

    def _split_oversized_chunk(self, chunk: str) -> list[str]:
        if len(chunk) <= self._discord_chunk_limit:
            return [chunk]

        parts: list[str] = []
        current = ""
        for line in chunk.split("\n"):
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) <= self._discord_chunk_limit:
                current = candidate
                continue

            if current:
                parts.append(current)
                current = ""

            if len(line) <= self._discord_chunk_limit:
                current = line
                continue

            start = 0
            while start < len(line):
                end = start + self._discord_chunk_limit
                parts.append(line[start:end])
                start = end

        if current:
            parts.append(current)
        return parts or [chunk[:self._discord_chunk_limit]]

    def _add_part_markers(self, chunks: list[str]) -> list[str]:
        total = len(chunks)
        if total <= 1:
            return chunks

        marked: list[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            marker = f"\n\n(Part {idx}/{total})"
            available = self._discord_hard_char_limit - len(marker)
            marked.append(f"{chunk[:available]}{marker}")
        return marked

    @staticmethod
    def _send_chunks_in_order(chunks: list[str], send_func) -> bool:
        failed_indexes: list[int] = []
        for idx, chunk in enumerate(chunks, start=1):
            logger.info("Discord 发送分块 %d/%d（%d chars）", idx, len(chunks), len(chunk))
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
            
            if 200 <= response.status_code < 300:
                logger.info("Discord Webhook 消息发送成功: status=%s", response.status_code)
                return True
            else:
                logger.error("Discord Webhook 发送失败: status=%s body=%s", response.status_code, response.text)
                return False
        except Exception as e:
            logger.error("Discord Webhook 发送异常: %s", e)
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
            
            if 200 <= response.status_code < 300:
                logger.info("Discord Bot 消息发送成功: status=%s", response.status_code)
                return True
            else:
                logger.error("Discord Bot 发送失败: status=%s body=%s", response.status_code, response.text)
                return False
        except Exception as e:
            logger.error("Discord Bot 发送异常: %s", e)
            return False
