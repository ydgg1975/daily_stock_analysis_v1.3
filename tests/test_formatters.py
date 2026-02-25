# -*- coding: utf-8 -*-
"""
Unit tests for formatters.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.formatters import chunk_content_by_max_words, TRUNCATION_SUFFIX


class TestChunkContentByMaxWords(unittest.TestCase):
    """Tests for chunk_content_by_max_words."""

    def test_empty_string_returns_single_empty_chunk(self):
        result = chunk_content_by_max_words("", 100)
        self.assertEqual(result, [""])

    def test_short_content_no_separators_returns_single_chunk(self):
        text = "Short message without separators."
        result = chunk_content_by_max_words(text, 100)
        self.assertEqual(result, [text])

    def test_content_with_dash_separator_fits_in_one_chunk(self):
        text = "Part A\n---\nPart B"
        result = chunk_content_by_max_words(text, 500)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_content_with_dash_separator_exceeds_max_splits_into_chunks(self):
        # Use small max_words so the two parts together exceed limit
        part_a = "A" * 50
        part_b = "B" * 50
        text = f"{part_a}\n---\n{part_b}"
        result = chunk_content_by_max_words(text, 60)
        self.assertGreaterEqual(len(result), 2)
        self.assertEqual("".join(result), text)

    def test_long_content_without_separators_gets_force_split_with_suffix(self):
        long_text = "X" * 200
        result = chunk_content_by_max_words(long_text, 50)
        self.assertGreater(len(result), 1)
        # First chunks should end with the truncation suffix
        self.assertIn(TRUNCATION_SUFFIX, result[0])
        
    def test_content_with_dash_separator_with_long_sections(self):
        part_a = "A" * 80
        part_b = "B" * 80
        text = f"{part_a}\n---\n{part_b}"
        result = chunk_content_by_max_words(text, 40)
        content = ""
        for r in result[:-1]:
            content += r.replace(TRUNCATION_SUFFIX, "")
            self.assertTrue(TRUNCATION_SUFFIX in r or "\n---\n" in r)
            self.assertLessEqual(len(r), 40)
        self.assertEqual(content + result[-1], text)
        
    def test_chunk_with_emoji(self):
        text = "A" * 79 + "🎯"
        result = chunk_content_by_max_words(text, 80, emoji_len=2)
        self.assertEqual(len(result), 2)