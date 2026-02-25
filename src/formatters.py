# -*- coding: utf-8 -*-
"""
===================================
格式化工具模块
===================================

提供各种内容格式化工具函数，用于将通用格式转换为平台特定格式。
"""

import re
import time
from typing import List, Callable

import markdown2


TRUNCATION_SUFFIX = "\n\n...(本段内容过长已截断)"

# Unicode code point ranges for emoji (symbols that count as 2 for effective length).
_EMOJI_RANGES = [
    (0x2600, 0x26FF),   # Misc symbols
    (0x2700, 0x27BF),   # Dingbats
    (0x1F300, 0x1F5FF), # Misc Symbols and Pictographs
    (0x1F600, 0x1F64F), # Emoticons
    (0x1F650, 0x1F67F),
    (0x1F680, 0x1F6FF), # Transport and Map
    (0x1F900, 0x1F9FF), # Supplemental Symbols and Pictographs
    (0x1F1E0, 0x1F1FF), # Flags
]


def _is_emoji(c: str) -> bool:
    """判断字符是否为 emoji
    
    Args:
        c: 字符
        
    Returns:
        True 如果字符为 emoji，False 否则
    """
    if len(c) != 1:
        return False
    cp = ord(c)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def _effective_len(s: str, emoji_len: int = 2) -> int:
    """
    计算字符串的有效长度
    
    Args:
        s: 字符串
        emoji_len: 每个 emoji 的长度，默认为 2
        
    Returns:
        s 的有效长度
    """
    n = len(s)
    n += sum(emoji_len - 1 for c in s if _is_emoji(c))
    return n


def _slice_at_effective_len(s: str, max_effective: int, emoji_len: int = 2) -> tuple[str, str]:
    """
    按有效长度分割字符串
    
    Args:
        s: 字符串
        max_effective: 最大有效长度
        emoji_len: 每个 emoji 的长度，默认为 2
        
    Returns:
        分割后的前、后部分字符串
    """
    if _effective_len(s, emoji_len) <= max_effective:
        return s, ""
    eff = 0
    for i, c in enumerate(s):
        eff += emoji_len if _is_emoji(c) else 1 
        if eff > max_effective:
            return s[:i], s[i:]
    return s, ""


def markdown_to_html_document(markdown_text: str) -> str:
    """
    Convert Markdown to a complete HTML document (for email, md2img, etc.).

    Uses markdown2 with table and code block support, wraps with inline CSS
    for compact, readable layout. Reused by notification email and md2img.

    Args:
        markdown_text: Raw Markdown content.

    Returns:
        Full HTML document string with DOCTYPE, head, and body.
    """
    html_content = markdown2.markdown(
        markdown_text,
        extras=["tables", "fenced-code-blocks", "break-on-newline", "cuddled-lists"],
    )

    css_style = """
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                line-height: 1.5;
                color: #24292e;
                font-size: 14px;
                padding: 15px;
                max-width: 900px;
                margin: 0 auto;
            }
            h1 {
                font-size: 20px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.2em;
                margin-bottom: 0.8em;
                color: #0366d6;
            }
            h2 {
                font-size: 18px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.0em;
                margin-bottom: 0.6em;
            }
            h3 {
                font-size: 16px;
                margin-top: 0.8em;
                margin-bottom: 0.4em;
            }
            p {
                margin-top: 0;
                margin-bottom: 8px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 12px 0;
                display: block;
                overflow-x: auto;
                font-size: 13px;
            }
            th, td {
                border: 1px solid #dfe2e5;
                padding: 6px 10px;
                text-align: left;
            }
            th {
                background-color: #f6f8fa;
                font-weight: 600;
            }
            tr:nth-child(2n) {
                background-color: #f8f8f8;
            }
            tr:hover {
                background-color: #f1f8ff;
            }
            blockquote {
                color: #6a737d;
                border-left: 0.25em solid #dfe2e5;
                padding: 0 1em;
                margin: 0 0 10px 0;
            }
            code {
                padding: 0.2em 0.4em;
                margin: 0;
                font-size: 85%;
                background-color: rgba(27,31,35,0.05);
                border-radius: 3px;
                font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            }
            pre {
                padding: 12px;
                overflow: auto;
                line-height: 1.45;
                background-color: #f6f8fa;
                border-radius: 3px;
                margin-bottom: 10px;
            }
            hr {
                height: 0.25em;
                padding: 0;
                margin: 16px 0;
                background-color: #e1e4e8;
                border: 0;
            }
            ul, ol {
                padding-left: 20px;
                margin-bottom: 10px;
            }
            li {
                margin: 2px 0;
            }
        """

    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                {css_style}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """


def format_feishu_markdown(content: str) -> str:
    """
    将通用 Markdown 转换为飞书 lark_md 更友好的格式
    
    转换规则：
    - 飞书不支持 Markdown 标题（# / ## / ###），用加粗代替
    - 引用块使用前缀替代
    - 分隔线统一为细线
    - 表格转换为条目列表
    
    Args:
        content: 原始 Markdown 内容
        
    Returns:
        转换后的飞书 Markdown 格式内容
        
    Example:
        >>> markdown = "# 标题\\n> 引用\\n| 列1 | 列2 |"
        >>> formatted = format_feishu_markdown(markdown)
        >>> print(formatted)
        **标题**
        💬 引用
        • 列1：值1 | 列2：值2
    """
    def _flush_table_rows(buffer: List[str], output: List[str]) -> None:
        """将表格缓冲区中的行转换为飞书格式"""
        if not buffer:
            return

        def _parse_row(row: str) -> List[str]:
            """解析表格行，提取单元格"""
            cells = [c.strip() for c in row.strip().strip('|').split('|')]
            return [c for c in cells if c]

        rows = []
        for raw in buffer:
            # 跳过分隔行（如 |---|---|）
            if re.match(r'^\s*\|?\s*[:-]+\s*(\|\s*[:-]+\s*)+\|?\s*$', raw):
                continue
            parsed = _parse_row(raw)
            if parsed:
                rows.append(parsed)

        if not rows:
            return

        header = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []
        for row in data_rows:
            pairs = []
            for idx, cell in enumerate(row):
                key = header[idx] if idx < len(header) else f"列{idx + 1}"
                pairs.append(f"{key}：{cell}")
            output.append(f"• {' | '.join(pairs)}")

    lines = []
    table_buffer: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        # 处理表格行
        if line.strip().startswith('|'):
            table_buffer.append(line)
            continue

        # 刷新表格缓冲区
        if table_buffer:
            _flush_table_rows(table_buffer, lines)
            table_buffer = []

        # 转换标题（# ## ### 等）
        if re.match(r'^#{1,6}\s+', line):
            title = re.sub(r'^#{1,6}\s+', '', line).strip()
            line = f"**{title}**" if title else ""
        # 转换引用块
        elif line.startswith('> '):
            quote = line[2:].strip()
            line = f"💬 {quote}" if quote else ""
        # 转换分隔线
        elif line.strip() == '---':
            line = '────────'
        # 转换列表项
        elif line.startswith('- '):
            line = f"• {line[2:].strip()}"

        lines.append(line)

    # 处理末尾的表格
    if table_buffer:
        _flush_table_rows(table_buffer, lines)

    return "\n".join(lines).strip()


def _chunk_by_lines(content: str, max_bytes: int, send_func: Callable[[str], bool]) -> bool:
    """
    强制按行分割发送（无法智能分割时的 fallback）
    
    Args:
        content: 完整消息内容
        max_bytes: 单条消息最大字节数
        send_func: 发送单条消息的函数
        
    Returns:
        是否全部发送成功
    """
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
    
    for i, chunk in enumerate(chunks):
        # 添加分页标记
        page_marker = f"\n\n📄 ({i+1}/{total_chunks})" if total_chunks > 1 else ""
        
        try:
            if send_func(chunk + page_marker):
                success_count += 1
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"飞书第 {i+1}/{total_chunks} 批发送异常: {e}")
        
        # 批次间隔，避免触发频率限制
        if i < total_chunks - 1:
            time.sleep(1)
    
    return success_count == total_chunks


def chunk_feishu_content(content: str, max_bytes: int, send_func: Callable[[str], bool]) -> bool:
    """
    将超长内容分段发送到飞书
    
    智能分割策略：
    1. 优先按 "---" 分隔（股票之间的分隔线）
    2. 其次按 "### " 标题分割（每只股票的标题）
    3. 最后按行强制分割
    
    Args:
        content: 完整消息内容
        max_bytes: 单条消息最大字节数
        send_func: 发送单条消息的函数，接收内容字符串，返回是否成功
        
    Returns:
        是否全部发送成功
    """
    def get_bytes(s: str) -> int:
        """获取字符串的 UTF-8 字节数"""
        return len(s.encode('utf-8'))
    
    def _truncate_to_bytes(text: str, max_bytes: int) -> str:
        """按字节截断文本，确保不会在多字节字符中间截断"""
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
        
        # 从最大字节数开始向前查找，找到完整的 UTF-8 字符边界
        truncated = encoded[:max_bytes]
        while truncated and (truncated[-1] & 0xC0) == 0x80:
            truncated = truncated[:-1]
        
        return truncated.decode('utf-8', errors='ignore')
    
    # 智能分割：优先按 "---" 分隔（股票之间的分隔线）
    # 如果没有分隔线，按 "### " 标题分割（每只股票的标题）
    if "\n---\n" in content:
        sections = content.split("\n---\n")
        separator = "\n---\n"
    elif "\n### " in content:
        # 按 ### 分割，但保留 ### 前缀
        parts = content.split("\n### ")
        sections = [parts[0]] + [f"### {p}" for p in parts[1:]]
        separator = "\n"
    else:
        # 无法智能分割，按行强制分割
        return _chunk_by_lines(content, max_bytes, send_func)
    
    chunks = []
    current_chunk = []
    current_bytes = 0
    separator_bytes = get_bytes(separator)
    
    for section in sections:
        section_bytes = get_bytes(section) + separator_bytes
        
        # 如果单个 section 就超长，需要强制截断
        if section_bytes > max_bytes:
            # 先发送当前积累的内容
            if current_chunk:
                chunks.append(separator.join(current_chunk))
                current_chunk = []
                current_bytes = 0
            
            # 强制截断这个超长 section（按字节截断）
            truncated = _truncate_to_bytes(section, max_bytes - 200)
            truncated += "\n\n...(本段内容过长已截断)"
            chunks.append(truncated)
            continue
        
        # 检查加入后是否超长
        if current_bytes + section_bytes > max_bytes:
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
    
    for i, chunk in enumerate(chunks):
        # 添加分页标记
        if total_chunks > 1:
            page_marker = f"\n\n📄 ({i+1}/{total_chunks})"
            chunk_with_marker = chunk + page_marker
        else:
            chunk_with_marker = chunk
        
        try:
            if send_func(chunk_with_marker):
                success_count += 1
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"飞书第 {i+1}/{total_chunks} 批发送异常: {e}")
        
        # 批次间隔，避免触发频率限制
        if i < total_chunks - 1:
            time.sleep(1)
    
    return success_count == total_chunks

def _chunk_by_separators(content: str) -> tuple[list[str], str]:
    """
    通过分割线等特殊字符将消息内容分割为多个区块
    
    Args:
        content: 完整消息内容
        
    Returns:
        sections: 分割后的区块列表
        separator: 区块之间的分隔符，None 表示无法分割
    """
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
        return [content], ""
    return sections, separator

def _chunk_by_max_words(content: str, max_words: int, emoji_len: int = 2) -> list[str]:
    """
    按字数分割消息内容
    
    Args:
        content: 完整消息内容
        max_words: 单条消息最大字数
        emoji_len: 每个 emoji 的长度，默认为 2
        
    Returns:
        分割后的区块列表
    """
    if _effective_len(content, emoji_len) <= max_words:
        return [content]
    if max_words <= 1:
        raise ValueError("max_words must be greater than 1")

    sections = []
    suffix = TRUNCATION_SUFFIX
    effective_max_words = max_words - len(suffix)  # 预留后缀，避免边界超限
    if effective_max_words <= 0:
        effective_max_words = max_words
        suffix = ""

    while True:
        chunk, content = _slice_at_effective_len(content, effective_max_words, emoji_len)
        sections.append(chunk + suffix)
        if _effective_len(content, emoji_len) <= effective_max_words:
            sections.append(content)
            break
    return sections

def chunk_content_by_max_words(content: str, max_words: int, emoji_len: int = 2) -> list[str]:
    """
    按字数智能分割消息内容
    
    Args:
        content: 完整消息内容
        max_words: 单条消息最大字数
        emoji_len: 每个 emoji 的长度，默认为 2
        
    Returns:
        分割后的区块列表
    """
    sections, separator = _chunk_by_separators(content)
    if separator == "":
        # 无法智能分割，则强制按字数分割
        return _chunk_by_max_words(content, max_words, emoji_len)

    chunks = []
    current_chunk = []
    current_word_len = 0
    separator_len = len(separator) if separator else 0
    effective_max_words = max_words - separator_len # 预留分割符长度，避免边界超限

    for section in sections:
        section = section + separator
        section_word_len = _effective_len(section, emoji_len)

        # 如果单个 section 就超长，需要强制截断
        if section_word_len > max_words:
            # 先保存当前积累的内容
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_word_len = 0

            # 强制截断这个超长 section
            section_chunks = chunk_content_by_max_words(
                section[:-separator_len], effective_max_words, emoji_len
                )
            section_chunks[-1] = section_chunks[-1] + separator
            chunks.extend(section_chunks)
            continue

        # 检查加入后是否超长
        if current_word_len + section_word_len > max_words:
            # 保存当前块，开始新块
            if current_chunk:
                chunks.append("".join(current_chunk))
            current_chunk = [section]
            current_word_len = section_word_len
        else:
            current_chunk.append(section)
            current_word_len += section_word_len

    # 添加最后一块
    if current_chunk:
        chunks.append("".join(current_chunk))

    # 移除最后一个块的分割符
    if chunks and chunks[-1][-separator_len:] == separator:
        chunks[-1] = chunks[-1][:-separator_len]
    return chunks
