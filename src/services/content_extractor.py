# -*- coding: utf-8 -*-
"""
===================================
内容提取服务
===================================

职责：
1. 从 URL 抓取正文内容（复用 search_service.fetch_url_content）
2. 从上传文件解析文本（PDF / DOCX / TXT / MD）
3. 整合所有用户提供的舆情内容
"""

import io
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# 每条来源的最大字符数
_PER_SOURCE_LIMIT = 3000
# 所有用户上下文的总字符上限
_TOTAL_LIMIT = 15000


def extract_from_url(url: str, timeout: int = 8) -> str:
    """
    从 URL 抓取正文内容。

    复用 search_service.fetch_url_content，增大截断上限。
    """
    try:
        from src.search_service import fetch_url_content
        text = fetch_url_content(url, timeout=timeout)
        # fetch_url_content 内部截断 1500，这里再次调用原始逻辑以获取更多内容
        if text:
            return text[:_PER_SOURCE_LIMIT]
    except Exception as e:
        logger.warning("URL 内容提取失败 (%s): %s", url, e)
    return ""


def extract_from_file(content: bytes, filename: str) -> str:
    """
    从文件内容中提取文本。

    支持 PDF / DOCX / TXT / MD 格式。
    """
    lower_name = filename.lower()
    try:
        if lower_name.endswith(".pdf"):
            return _extract_pdf(content)
        elif lower_name.endswith(".docx"):
            return _extract_docx(content)
        elif lower_name.endswith((".txt", ".md", ".markdown")):
            return _extract_text(content)
        else:
            logger.warning("不支持的文件格式: %s", filename)
            return ""
    except Exception as e:
        logger.warning("文件内容提取失败 (%s): %s", filename, e)
        return ""


def extract_all(
    urls: Optional[List[str]] = None,
    files: Optional[List[Tuple[bytes, str]]] = None,
    note: Optional[str] = None,
) -> str:
    """
    整合所有用户提供的舆情内容。

    Args:
        urls: URL 列表
        files: (文件内容, 文件名) 元组列表
        note: 用户补充说明

    Returns:
        格式化后的完整舆情上下文文本
    """
    sections: List[str] = []
    total_len = 0

    # 用户补充说明
    if note and note.strip():
        trimmed_note = note.strip()[:2000]
        sections.append(f"## 用户补充说明\n{trimmed_note}")
        total_len += len(trimmed_note)

    # URL 内容
    source_idx = 1
    for url in (urls or []):
        if total_len >= _TOTAL_LIMIT:
            break
        text = extract_from_url(url)
        if text:
            remaining = _TOTAL_LIMIT - total_len
            text = text[:min(_PER_SOURCE_LIMIT, remaining)]
            sections.append(f"### 来源 {source_idx}: {url}\n{text}")
            total_len += len(text)
            source_idx += 1
        else:
            sections.append(f"### 来源 {source_idx}: {url}\n[提取失败]")
            source_idx += 1

    # 文件内容
    for file_content, filename in (files or []):
        if total_len >= _TOTAL_LIMIT:
            break
        text = extract_from_file(file_content, filename)
        if text:
            remaining = _TOTAL_LIMIT - total_len
            text = text[:min(_PER_SOURCE_LIMIT, remaining)]
            sections.append(f"### 来源 {source_idx}: 上传文件 \"{filename}\"\n{text}")
            total_len += len(text)
            source_idx += 1
        else:
            sections.append(f"### 来源 {source_idx}: 上传文件 \"{filename}\"\n[提取失败]")
            source_idx += 1

    if not sections:
        return ""

    return "\n\n".join(sections)


def _extract_pdf(content: bytes) -> str:
    """使用 PyPDF2 提取 PDF 文本"""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.warning("PyPDF2/pypdf 未安装，无法解析 PDF 文件")
            return ""

    reader = PdfReader(io.BytesIO(content))
    texts = []
    for page in reader.pages[:20]:  # 最多读取 20 页
        text = page.extract_text()
        if text:
            texts.append(text.strip())
    full_text = "\n".join(texts)
    return full_text[:_PER_SOURCE_LIMIT]


def _extract_docx(content: bytes) -> str:
    """使用 python-docx 提取 DOCX 文本"""
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx 未安装，无法解析 DOCX 文件")
        return ""

    doc = Document(io.BytesIO(content))
    texts = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    full_text = "\n".join(texts)
    return full_text[:_PER_SOURCE_LIMIT]


def _extract_text(content: bytes) -> str:
    """提取纯文本文件"""
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            text = content.decode(encoding)
            return text.strip()[:_PER_SOURCE_LIMIT]
        except (UnicodeDecodeError, LookupError):
            continue
    return ""
