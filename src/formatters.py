# -*- coding: utf-8 -*-
"""Formatting helpers for Markdown, notification text, and message chunks."""

import re
from typing import List

import markdown2

TRUNCATION_SUFFIX = "\n\n...(내용이 길어 일부만 표시합니다)"
PAGE_MARKER_PREFIX = "\n\n페이지"
PAGE_MARKER_SAFE_BYTES = 18
PAGE_MARKER_SAFE_LEN = 16
MIN_MAX_WORDS = 10
MIN_MAX_BYTES = 40

# Unicode code point ranges for special characters.
_SPECIAL_CHAR_RANGE = (0x10000, 0xFFFFF)
_SPECIAL_CHAR_REGEX = re.compile(r'[\U00010000-\U000FFFFF]')


def _page_marker(i: int, total: int) -> str:
    return f"{PAGE_MARKER_PREFIX} {i+1}/{total}"


def _is_special_char(c: str) -> bool:
    """Return whether a character is in the special wide code-point range.

    Args:
        c: Character to inspect.

    Returns:
        True when the character should count as special.
    """
    if len(c) != 1:
        return False
    cp = ord(c)
    return _SPECIAL_CHAR_RANGE[0] <= cp <= _SPECIAL_CHAR_RANGE[1]


def _count_special_chars(s: str) -> int:
    """
    Count special characters in a string.

    Args:
        s: Input string.
    """
    # reg find all (0x10000, 0xFFFFF)
    match = _SPECIAL_CHAR_REGEX.findall(s)
    return len(match)


def _effective_len(s: str, special_char_len: int = 2) -> int:
    """
    Calculate effective string length.

    Args:
        s: Input string.
        special_char_len: Effective width of each special character.

    Returns:
        Effective length.
    """
    n = len(s)
    n += _count_special_chars(s) * (special_char_len - 1)
    return n


def _slice_at_effective_len(s: str, effective_len: int, special_char_len: int = 2) -> tuple[str, str]:
    """
    Split a string by effective length.

    Args:
        s: Input string.
        effective_len: Target effective length.
        special_char_len: Effective width of each special character.

    Returns:
        A tuple of the leading slice and the remaining text.
    """
    if _effective_len(s, special_char_len) <= effective_len:
        return s, ""

    s_ = s[:effective_len]
    n_special_chars = _count_special_chars(s_)
    residual_lens = n_special_chars * (special_char_len - 1) + len(s_) - effective_len
    while residual_lens > 0:
        residual_lens -= special_char_len if _is_special_char(s_[-1]) else 1
        s_ = s_[:-1]
    return s_, s[len(s_):]


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


def markdown_to_plain_text(markdown_text: str) -> str:
    """
    Convert Markdown to plain text.

    Remove common Markdown markers while preserving readability.
    """
    text = markdown_text

    # Remove heading markers.
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove bold markers.
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)

    # Remove italic markers.
    text = re.sub(r'\*(.+?)\*', r'\1', text)

    # Remove blockquote markers.
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # Normalize list markers.
    text = re.sub(r'^[-*]\s+', '- ', text, flags=re.MULTILINE)

    # Normalize horizontal rules.
    text = re.sub(r'^---+$', '--------', text, flags=re.MULTILINE)

    # Remove table separator syntax.
    text = re.sub(r'\|[-:]+\|[-:|\s]+\|', '', text)
    text = re.sub(r'^\|(.+)\|$', r'\1', text, flags=re.MULTILINE)

    # Collapse repeated blank lines.
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _bytes(s: str) -> int:
    return len(s.encode('utf-8'))


def _chunk_by_max_bytes(content: str, max_bytes: int) -> List[str]:
    if _bytes(content) <= max_bytes:
        return [content]
    if max_bytes < MIN_MAX_BYTES:
        raise ValueError(f"max_bytes={max_bytes} < {MIN_MAX_BYTES}, chunking may loop indefinitely.")

    sections: List[str] = []
    suffix = TRUNCATION_SUFFIX
    effective_max_bytes = max_bytes - _bytes(suffix)
    if effective_max_bytes <= 0:
        effective_max_bytes = max_bytes
        suffix = ""

    while True:
        chunk, content = slice_at_max_bytes(content, effective_max_bytes)
        if content.strip() != "":
            sections.append(chunk + suffix)
        else:
            # Last chunk: append and exit.
            sections.append(chunk)
            break
    return sections


def chunk_content_by_max_bytes(content: str, max_bytes: int, add_page_marker: bool = False) -> List[str]:
    """
    Split message content by byte limit using natural boundaries.

    Args:
        content: Full message content.
        max_bytes: Maximum bytes per message.
        add_page_marker: Whether to append page markers.

    Returns:
        List of chunks.
    """
    def _chunk(content: str, max_bytes: int) -> List[str]:
        # Prefer separators/headings for natural pagination.
        if max_bytes < MIN_MAX_BYTES:
            raise ValueError(f"max_bytes={max_bytes} < {MIN_MAX_BYTES}, chunking may loop indefinitely.")

        if _bytes(content) <= max_bytes:
            return [content]

        sections, separator = _chunk_by_separators(content)
        if separator == "" and len(sections) == 1:
            # Fall back to hard byte-based splitting.
            return _chunk_by_max_bytes(content, max_bytes)

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_bytes = 0
        separator_bytes = _bytes(separator) if separator else 0
        effective_max_bytes = max_bytes - separator_bytes

        for section in sections:
            section += separator
            section_bytes = _bytes(section)

            # Hard-split a section that is too large by itself.
            if section_bytes > effective_max_bytes:
                # Flush the accumulated chunk first.
                if current_chunk:
                    chunks.append("".join(current_chunk))
                    current_chunk = []
                    current_bytes = 0

                # Split by bytes so the entire section is not dropped.
                section_chunks = _chunk(
                    section[:-separator_bytes], effective_max_bytes
                )
                section_chunks[-1] = section_chunks[-1] + separator
                chunks.extend(section_chunks)
                continue

            # Check whether adding the section would exceed the limit.
            if current_bytes + section_bytes > effective_max_bytes:
                # Save the current chunk and start a new one.
                if current_chunk:
                    chunks.append("".join(current_chunk))
                current_chunk = [section]
                current_bytes = section_bytes
            else:
                current_chunk.append(section)
                current_bytes += section_bytes

        # Append the final chunk.
        if current_chunk:
            chunks.append("".join(current_chunk))

        # Remove the trailing separator from the final chunk.
        if (chunks and
            len(chunks[-1]) > separator_bytes and
            chunks[-1][-separator_bytes:] == separator
        ):
            chunks[-1] = chunks[-1][:-separator_bytes]

        return chunks

    if add_page_marker:
        max_bytes = max_bytes - PAGE_MARKER_SAFE_BYTES

    chunks = _chunk(content, max_bytes)
    if add_page_marker:
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            chunks[i] = chunk + _page_marker(i, total_chunks)
    return chunks


def slice_at_max_bytes(text: str, max_bytes: int) -> tuple[str, str]:
    """
    Truncate a string by byte count without splitting UTF-8 characters.

    Args:
        text: Input text.
        max_bytes: Maximum byte length.

    Returns:
        Tuple of truncated text and remaining text.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, ""

    # Walk back to a valid UTF-8 boundary.
    truncated = encoded[:max_bytes]
    while truncated and (truncated[-1] & 0xC0) == 0x80:
        truncated = truncated[:-1]

    truncated = truncated.decode('utf-8', errors='ignore')
    return truncated, text[len(truncated):]


def format_feishu_markdown(content: str) -> str:
    """
    Convert generic Markdown into a Feishu-friendly Markdown format.

    Conversion rules:
    - Convert headings to bold text.
    - Convert blockquotes to quoted lines.
    - Normalize horizontal rules.
    - Convert tables to list-like rows.

    Args:
        content: Raw Markdown content.

    Returns:
        Feishu-friendly Markdown text.
    """
    def _flush_table_rows(buffer: List[str], output: List[str]) -> None:
        """Convert buffered table rows to Feishu-friendly lines."""
        if not buffer:
            return

        def _parse_row(row: str) -> List[str]:
            """Parse a Markdown table row into cells."""
            cells = [c.strip() for c in row.strip().strip('|').split('|')]
            return [c for c in cells if c]

        rows = []
        for raw in buffer:
            # Skip Markdown table divider rows.
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
                key = header[idx] if idx < len(header) else f"Column {idx + 1}"
                pairs.append(f"{key}: {cell}")
            output.append(f"- {' | '.join(pairs)}")

    lines = []
    table_buffer: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        # Buffer table rows so they can be converted together.
        if line.strip().startswith('|'):
            table_buffer.append(line)
            continue

        # Flush any buffered table before handling a normal line.
        if table_buffer:
            _flush_table_rows(table_buffer, lines)
            table_buffer = []

        # Convert Markdown headings.
        if re.match(r'^#{1,6}\s+', line):
            title = re.sub(r'^#{1,6}\s+', '', line).strip()
            line = f"**{title}**" if title else ""
        # Convert blockquote lines.
        elif line.startswith('> '):
            quote = line[2:].strip()
            line = f"> {quote}" if quote else ""
        # Normalize horizontal rules.
        elif line.strip() == '---':
            line = '--------'
        # Normalize list items.
        elif line.startswith('- '):
            line = f"- {line[2:].strip()}"

        lines.append(line)

    # Flush a trailing table.
    if table_buffer:
        _flush_table_rows(table_buffer, lines)

    return "\n".join(lines).strip()


def _chunk_by_separators(content: str) -> tuple[list[str], str]:
    """
    通过分割线等特殊字符将消息内容分割为多个区块

    Args:
        content: 完整消息内容

    Returns:
        sections: 分割后的区块列表
        separator: 区块之间的分隔符，None 表示无法分割
    """
    # Prefer stock/report boundaries before falling back to line-based chunks.
    # Headings are checked in descending specificity below.
    if "\n---\n" in content:
        sections = content.split("\n---\n")
        separator = "\n---\n"
    elif "\n# " in content:
        # Split on top-level headings.
        parts = content.split("\n## ")
        sections = [parts[0]] + [f"## {p}" for p in parts[1:]]
        separator = "\n"
    elif "\n## " in content:
        # Split on second-level headings.
        parts = content.split("\n## ")
        sections = [parts[0]] + [f"## {p}" for p in parts[1:]]
        separator = "\n"
    elif "\n### " in content:
        # Split on third-level headings.
        parts = content.split("\n### ")
        sections = [parts[0]] + [f"### {p}" for p in parts[1:]]
        separator = "\n"
    elif "\n**" in content:
        # Split on bold pseudo-headings.
        parts = content.split("\n**")
        sections = [parts[0]] + [f"**{p}" for p in parts[1:]]
        separator = "\n"
    elif "\n" in content:
        # Split by line as the final natural boundary.
        sections = content.split("\n")
        separator = "\n"
    else:
        return [content], ""
    return sections, separator


def _chunk_by_max_words(content: str, max_words: int, special_char_len: int = 2) -> list[str]:
    """
    Split message content by effective character length.

    Args:
        content: Full message content.
        max_words: Maximum effective character length per chunk.
        special_char_len: Effective width of each special character.

    Returns:
        List of chunks.
    """
    if _effective_len(content, special_char_len) <= max_words:
        return [content]
    if max_words < MIN_MAX_WORDS:
        raise ValueError(
            f"max_words={max_words} < {MIN_MAX_WORDS}, chunking may loop indefinitely."
        )

    sections = []
    suffix = TRUNCATION_SUFFIX
    effective_max_words = max_words - len(suffix)
    if effective_max_words <= 0:
        effective_max_words = max_words
        suffix = ""

    while True:
        chunk, content = _slice_at_effective_len(content, effective_max_words, special_char_len)
        if content.strip() != "":
            sections.append(chunk + suffix)
        else:
            # Last chunk: append and exit.
            sections.append(chunk)
            break
    return sections


def chunk_content_by_max_words(
    content: str,
    max_words: int,
    special_char_len: int = 2,
    add_page_marker: bool = False
    ) -> list[str]:
    """
    Split message content by effective character length.

    Args:
        content: Full message content.
        max_words: Maximum effective character length per chunk.
        special_char_len: Effective width of each special character.
        add_page_marker: Whether to append page markers.

    Returns:
        List of chunks.
    """
    def _chunk(content: str, max_words: int, special_char_len: int = 2) -> list[str]:
        if max_words < MIN_MAX_WORDS:
            # Guard against non-progressing recursive chunking.
            raise ValueError(f"max_words={max_words} < {MIN_MAX_WORDS}, chunking may loop indefinitely.")

        if _effective_len(content, special_char_len) <= max_words:
            return [content]

        sections, separator = _chunk_by_separators(content)
        if separator == "" and len(sections) == 1:
            # Fall back to hard effective-length splitting.
            return _chunk_by_max_words(content, max_words, special_char_len)

        chunks = []
        current_chunk = []
        current_word_len = 0
        separator_len = len(separator) if separator else 0
        effective_max_words = max_words - separator_len

        for section in sections:
            section += separator
            section_word_len = _effective_len(section, special_char_len)

            # Hard-split a section that is too large by itself.
            if section_word_len > max_words:
                # Flush the accumulated chunk first.
                if current_chunk:
                    chunks.append("".join(current_chunk))

                # Hard-split this oversized section.
                section_chunks = _chunk(
                    section[:-separator_len], effective_max_words, special_char_len
                    )
                section_chunks[-1] = section_chunks[-1] + separator
                chunks.extend(section_chunks)
                continue

            # Check whether adding the section would exceed the limit.
            if current_word_len + section_word_len > max_words:
                # Save the current chunk and start a new one.
                if current_chunk:
                    chunks.append("".join(current_chunk))
                current_chunk = [section]
                current_word_len = section_word_len
            else:
                current_chunk.append(section)
                current_word_len += section_word_len

        # Append the final chunk.
        if current_chunk:
            chunks.append("".join(current_chunk))

        # Remove the trailing separator from the final chunk.
        if (chunks and
            len(chunks[-1]) > separator_len and
            chunks[-1][-separator_len:] == separator
        ):
            chunks[-1] = chunks[-1][:-separator_len]
        return chunks


    if add_page_marker:
        max_words = max_words - PAGE_MARKER_SAFE_LEN

    chunks = _chunk(content, max_words, special_char_len)
    if add_page_marker:
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            chunks[i] = chunk + _page_marker(i, total_chunks)
    return chunks
