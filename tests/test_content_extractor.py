# -*- coding: utf-8 -*-
"""
内容提取服务单元测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestExtractFromFile:
    """测试文件内容提取"""

    def test_extract_text_utf8(self):
        from src.services.content_extractor import extract_from_file
        content = "这是一段测试文本\n第二行内容".encode("utf-8")
        result = extract_from_file(content, "test.txt")
        assert "测试文本" in result
        assert "第二行" in result

    def test_extract_text_gbk(self):
        from src.services.content_extractor import extract_from_file
        content = "中文GBK编码".encode("gbk")
        result = extract_from_file(content, "test.txt")
        assert "GBK" in result

    def test_extract_markdown(self):
        from src.services.content_extractor import extract_from_file
        content = "# 标题\n\n这是正文内容".encode("utf-8")
        result = extract_from_file(content, "report.md")
        assert "标题" in result
        assert "正文" in result

    def test_unsupported_format(self):
        from src.services.content_extractor import extract_from_file
        result = extract_from_file(b"data", "image.png")
        assert result == ""

    def test_empty_content(self):
        from src.services.content_extractor import extract_from_file
        result = extract_from_file(b"", "empty.txt")
        assert result == ""

    def test_per_source_limit(self):
        from src.services.content_extractor import extract_from_file, _PER_SOURCE_LIMIT
        long_text = "A" * 10000
        result = extract_from_file(long_text.encode("utf-8"), "long.txt")
        assert len(result) <= _PER_SOURCE_LIMIT


class TestExtractAll:
    """测试整合提取"""

    def test_note_only(self):
        from src.services.content_extractor import extract_all
        result = extract_all(note="关注新能源板块")
        assert "关注新能源" in result
        assert "补充说明" in result

    def test_note_truncation(self):
        from src.services.content_extractor import extract_all
        long_note = "A" * 3000
        result = extract_all(note=long_note)
        # note 应被截断至 2000
        assert len(result) < 3000

    def test_files_only(self):
        from src.services.content_extractor import extract_all
        files = [(b"file content here", "report.txt")]
        result = extract_all(files=files)
        assert "report.txt" in result
        assert "file content" in result

    def test_empty_input(self):
        from src.services.content_extractor import extract_all
        result = extract_all()
        assert result == ""

    def test_total_limit(self):
        from src.services.content_extractor import extract_all, _TOTAL_LIMIT
        # 提供大量内容，验证总量限制
        files = [(("X" * 5000).encode("utf-8"), f"file{i}.txt") for i in range(10)]
        result = extract_all(files=files)
        # 结果应该在合理范围内（标注文本 + 截断内容）
        assert len(result) <= _TOTAL_LIMIT + 2000  # 允许标注头的额外空间

    def test_failed_url_still_noted(self, monkeypatch):
        from src.services import content_extractor
        from src.services.content_extractor import extract_all
        # Mock URL extraction to return empty
        monkeypatch.setattr(content_extractor, "extract_from_url", lambda url, **kw: "")
        result = extract_all(urls=["https://example.com/article"])
        assert "[提取失败]" in result
