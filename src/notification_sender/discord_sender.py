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
        )
        hidden_inline_prefix = (
            "> 报告时间(report_generated_at):",
            "> 市场时间(market_timestamp):",
            "> 交易日(market_session_date):",
            "> 会话类型(session_type):",
            "report_generated_at:",
            "market_timestamp:",
            "market_session_date:",
            "session_type:",
            "**Alpha Vantage 补充指标**:",
            "**筹码**: 美股暂不支持该指标",
        )
        key_row_tokens = (
            "当前价", "涨跌幅", "最高", "最低", "成交量",
            "ma5", "ma10", "ma20", "支撑", "压力",
            "理想买入", "止损", "目标", "仓位",
            "空仓", "持仓",
        )

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
                                table_rows.append(f"- {k}: {v}")
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
            if "检查清单" in stripped:
                out.append("检查清单: 详见完整报告")
                idx += 1
                continue
            if stripped.startswith("- ") and out and out[-1] == "检查清单: 详见完整报告":
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
