# -*- coding: utf-8 -*-
"""
Wechat 发送提醒服务

职责：
1. 通过企业微信 Webhook 发送文本消息
2. 通过企业微信 Webhook 发送图片消息
"""
import logging
import base64
import hashlib
import requests

from src.config import Config
from src.formatters import slice_at_max_bytes


logger = logging.getLogger(__name__)


# WeChat Work image msgtype limit ~2MB (base64 payload)
WECHAT_IMAGE_MAX_BYTES = 2 * 1024 * 1024

class WechatSender:
    
    def __init__(self, config: Config):
        """
        初始化企业微信配置

        Args:
            config: 配置对象
        """
        self._wechat_url = config.wechat_webhook_url
        self._wechat_max_bytes = getattr(config, 'wechat_max_bytes', 4000)
        self._wechat_msg_type = getattr(config, 'wechat_msg_type', 'markdown')
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)
        
    def send_to_wechat(self, content: str) -> bool:
        """
        推送消息到企业微信机器人
        
        企业微信 Webhook 消息格式：
        支持 markdown 类型以及 text 类型, markdown 类型在微信中无法展示，可以使用 text 类型,
        markdown 类型会解析 markdown 格式,text 类型会直接发送纯文本。

        markdown 类型示例：
        {
            "msgtype": "markdown",
            "markdown": {
                "content": "## 标题\n\n内容"
            }
        }
        
        text 类型示例：
        {
            "msgtype": "text",
            "text": {
                "content": "内容"
            }
        }

        注意：企业微信 Markdown 限制 4096 字节（非字符）, Text 类型限制 2048 字节，超长内容会自动分批发送
        可通过环境变量 WECHAT_MAX_BYTES 调整限制值
        
        Args:
            content: Markdown 格式的消息内容
            
        Returns:
            是否发送成功
        """
        if not self._wechat_url:
            logger.warning("企业微信 Webhook 未配置，跳过推送")
            return False
        
        # 根据消息类型动态限制上限，避免 text 类型超过企业微信 2048 字节限制
        if self._wechat_msg_type == 'text':
            max_bytes = min(self._wechat_max_bytes, 2000)  # 预留一定字节给系统/分页标记
        else:
            max_bytes = self._wechat_max_bytes  # markdown 默认 4000 字节
        
        # 检查字节长度，超长则分批发送
        content_bytes = len(content.encode('utf-8'))
        if content_bytes > max_bytes:
            logger.info(f"消息内容超长({content_bytes}字节/{len(content)}字符)，将分批发送")
            return self._send_wechat_chunked(content, max_bytes)
        
        try:
            return self._send_wechat_message(content)
        except Exception as e:
            logger.error(f"发送企业微信消息失败: {e}")
            return False

    def _send_wechat_image(self, image_bytes: bytes) -> bool:
        """Send image via WeChat Work webhook msgtype image (Issue #289)."""
        if not self._wechat_url:
            return False
        if len(image_bytes) > WECHAT_IMAGE_MAX_BYTES:
            logger.warning(
                "企业微信图片超限 (%d > %d bytes)，拒绝发送，调用方应 fallback 为文本",
                len(image_bytes), WECHAT_IMAGE_MAX_BYTES,
            )
            return False
        try:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            md5_hash = hashlib.md5(image_bytes).hexdigest()
            payload = {
                "msgtype": "image",
                "image": {"base64": b64, "md5": md5_hash},
            }
            response = requests.post(
                self._wechat_url, json=payload, timeout=30, verify=self._webhook_verify_ssl
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    logger.info("企业微信图片发送成功")
                    return True
                logger.error("企业微信图片发送失败: %s", result.get("errmsg", ""))
            else:
                logger.error("企业微信请求失败: HTTP %s", response.status_code)
            return False
        except Exception as e:
            logger.error("企业微信图片发送异常: %s", e)
            return False

    def _send_wechat_chunked(self, content: str, max_bytes: int) -> bool:
        """
        分批发送长消息到企业微信
        
        按股票分析块（以 --- 或 ### 分隔）智能分割，确保每批不超过限制
        
        Args:
            content: 完整消息内容
            max_bytes: 单条消息最大字节数
            
        Returns:
            是否全部发送成功
        """
        import time
        
        def get_bytes(s: str) -> int:
            """获取字符串的 UTF-8 字节数"""
            return len(s.encode('utf-8'))
        
        # 智能分割：优先按 "---" 分隔（股票之间的分隔线）
        # 其次尝试各级标题分割
        if "\n---\n" in content:
            sections = content.split("\n---\n")
            separator = "\n---\n"
        elif "\n### " in content:
            # 按 ### 分割
            parts = content.split("\n### ")
            sections = [parts[0]] + [f"### {p}" for p in parts[1:]]
            separator = "\n"
        elif "\n## " in content:
            # 按 ## 分割 (兼容二级标题)
            parts = content.split("\n## ")
            sections = [parts[0]] + [f"## {p}" for p in parts[1:]]
            separator = "\n"
        elif "\n**" in content:
            # 按 ** 加粗标题分割 (兼容 AI 未输出标准 Markdown 标题的情况)
            parts = content.split("\n**")
            sections = [parts[0]] + [f"**{p}" for p in parts[1:]]
            separator = "\n"
        else:
            # 无法智能分割，按字符强制分割
            return self._send_wechat_force_chunked(content, max_bytes)
        
        chunks = []
        current_chunk = []
        current_bytes = 0
        separator_bytes = get_bytes(separator)
        effective_max_bytes = max_bytes - 50  # 预留分页标记空间，避免边界超限
        
        for section in sections:
            section_bytes = get_bytes(section) + separator_bytes
            
            # 如果单个 section 就超长，需要强制截断
            if section_bytes > effective_max_bytes:
                # 先发送当前积累的内容
                if current_chunk:
                    chunks.append(separator.join(current_chunk))
                    current_chunk = []
                    current_bytes = 0
                
                # 强制截断这个超长 section（按字节截断）
                truncated, _ = slice_at_max_bytes(section, effective_max_bytes - 200)
                truncated += "\n\n...(本段内容过长已截断)"
                chunks.append(truncated)
                continue
            
            # 检查加入后是否超长
            if current_bytes + section_bytes > effective_max_bytes:
                # 保存当前块，开始新块
                if current_chunk:
                    chunks.append(separator.join(current_chunk))
                current_chunk = [section]
                current_bytes = section_bytes
            else:
                current_chunk.append(section)
                current_bytes += section_bytes
        
        # 添加最后一块
        if current_chunk:
            chunks.append(separator.join(current_chunk))
        
        # 分批发送
        total_chunks = len(chunks)
        success_count = 0
        
        logger.info(f"企业微信分批发送：共 {total_chunks} 批")
        
        for i, chunk in enumerate(chunks):
            # 添加分页标记
            if total_chunks > 1:
                page_marker = f"\n\n📄 *({i+1}/{total_chunks})*"
                chunk_with_marker = chunk + page_marker
            else:
                chunk_with_marker = chunk
            
            try:
                if self._send_wechat_message(chunk_with_marker):
                    success_count += 1
                    logger.info(f"企业微信第 {i+1}/{total_chunks} 批发送成功")
                else:
                    logger.error(f"企业微信第 {i+1}/{total_chunks} 批发送失败")
            except Exception as e:
                logger.error(f"企业微信第 {i+1}/{total_chunks} 批发送异常: {e}")

            # 批次间隔，避免触发频率限制
            if i < total_chunks - 1:
                time.sleep(2.5)  # 增加到 2.5s，避免企业微信限流

        return success_count == total_chunks
    
    def _send_wechat_force_chunked(self, content: str, max_bytes: int) -> bool:
        """
        强制按字节分割发送（无法智能分割时的 fallback）
        
        Args:
            content: 完整消息内容
            max_bytes: 单条消息最大字节数
        """
        import time
        
        chunks = []
        current_chunk = ""
        
        # 按行分割，确保不会在多字节字符中间截断
        lines = content.split('\n')
        
        for line in lines:
            test_chunk = current_chunk + ('\n' if current_chunk else '') + line
            if len(test_chunk.encode('utf-8')) > max_bytes - 100:  # 预留空间给分页标记
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk = test_chunk
        
        if current_chunk:
            chunks.append(current_chunk)
        
        total_chunks = len(chunks)
        success_count = 0
        
        logger.info(f"企业微信强制分批发送：共 {total_chunks} 批")
        
        for i, chunk in enumerate(chunks):
            page_marker = f"\n\n📄 *({i+1}/{total_chunks})*" if total_chunks > 1 else ""
            
            try:
                if self._send_wechat_message(chunk + page_marker):
                    success_count += 1
            except Exception as e:
                logger.error(f"企业微信第 {i+1}/{total_chunks} 批发送异常: {e}")
            
            if i < total_chunks - 1:
                time.sleep(1)
        
        return success_count == total_chunks
    
    def _send_wechat_message(self, content: str) -> bool:
        """发送企业微信消息"""
        payload = self._gen_wechat_payload(content)
        
        response = requests.post(
            self._wechat_url,
            json=payload,
            timeout=10,
            verify=self._webhook_verify_ssl
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("企业微信消息发送成功")
                return True
            else:
                logger.error(f"企业微信返回错误: {result}")
                return False
        else:
            logger.error(f"企业微信请求失败: {response.status_code}")
            return False
        
    def _gen_wechat_payload(self, content: str) -> dict:
        """生成企业微信消息 payload"""
        if self._wechat_msg_type == 'text':
            return {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
        else:
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
