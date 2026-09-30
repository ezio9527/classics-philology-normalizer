#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_diff_verifier.py - diff_verifier.py 单元测试
"""

import sys
import unittest
from pathlib import Path

# 添加 resources/scripts 路径
sys.path.append(str(Path(__file__).parent.parent / "resources" / "scripts"))

from diff_verifier import verify_text_invariance, strip_markdown, normalize_ancient_text


class TestDiffVerifier(unittest.TestCase):

    def test_identical_text(self):
        """测试完全相同的古籍文本相似度为 100%"""
        text = "五行者，往来乎天地之间而穷历四时者也。天一生水，地六成之。"
        report = verify_text_invariance(text, text, threshold=0.998)
        self.assertTrue(report["passed"])
        self.assertEqual(report["similarity"], 1.0)
        self.assertEqual(report["char_difference"], 0)

    def test_markdown_formatting_does_not_break_invariance(self):
        """测试规范化引入的 Markdown 标记（标题、引用、加粗、表格）不影响纯文本保真度"""
        original = (
            "三命通会\n"
            "卷一\n"
            "论五行生成\n"
            "五行者，往来乎天地之间而穷历四时者也。天一生水，地六成之；地二生火，天七成之；"
            "天三生木，地八成之；地四生金，天九成之；天五生土，地十成之。\n"
            "命造壬寅丁未己卯乙亥评析己土虽通根月令，而见木之势盛，必须顺其气势以求中和。"
        )

        cleaned = (
            "# 《三命通会》\n\n"
            "## 卷一\n\n"
            "### 论五行生成\n\n"
            "> 五行者，往来乎天地之间而穷历四时者也。天一生水，地六成之；地二生火，天七成之；"
            "天三生木，地八成之；地四生金，天九成之；天五生土，地十成之。\n\n"
            "##### 命例：命造\n\n"
            "| 年柱 | 月柱 | 日柱 | 时柱 |\n"
            "| :---: | :---: | :---: | :---: |\n"
            "| 壬寅 | 丁未 | 己卯 | 乙亥 |\n\n"
            "**评析**：己土虽通根月令，而见木之势盛，必须顺其气势以求中和。\n"
        )

        report = verify_text_invariance(original, cleaned, threshold=0.998)
        self.assertTrue(report["passed"], f"Expected pass, got: {report}")
        self.assertGreaterEqual(report["similarity"], 0.998)

    def test_crawler_noise_filtering(self):
        """测试原文本中的爬虫与分页噪音被允许滤除且不拉低保真门禁"""
        original_with_crawler = (
            "天一生水，地六成之；地二生火，天七成之。\n"
            "第 1 页\n"
            "上一页 下一页\n"
            "源站地址：http://www.ancient-books-crawler.com/view/123\n"
            "天三生木，地八成之；地四生金，天九成之。"
        )

        cleaned_pure = (
            "天一生水，地六成之；地二生火，天七成之。\n"
            "天三生木，地八成之；地四生金，天九成之。"
        )

        report = verify_text_invariance(original_with_crawler, cleaned_pure, threshold=0.998)
        self.assertTrue(report["passed"], f"Expected pass, got: {report}")
        self.assertGreaterEqual(report["similarity"], 0.998)

    def test_text_tampering_fails_threshold(self):
        """测试擅自修改、润色或删减正文字句会被门禁严格拦截"""
        original = "欲识三元万法宗，先观帝载与神功。天有阴阳，地有刚柔，人道得之。"
        # 现代白话文改写了古籍（篡改）
        tampered = "想要了解命运法则的宗旨，首先要观察大自然的规律与奇妙力量。"

        report = verify_text_invariance(original, tampered, threshold=0.998)
        self.assertFalse(report["passed"])
        self.assertLess(report["similarity"], 0.998)
        self.assertTrue(len(report["sample_diffs"]) > 0)


if __name__ == "__main__":
    unittest.main()
