#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_normalizer_tools.py - normalizer_tools.py 单元测试
"""

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "resources" / "scripts"))

from normalizer_tools import (
    detect_paradigm,
    clean_crawler_noise,
    suppress_echoes,
    correct_heading_runaway,
    format_bazi_cases,
    expand_document_toc,
)


class TestNormalizerTools(unittest.TestCase):

    def test_detect_paradigm_a(self):
        """测试范式 A【汇编全书型】识别（如三命通会）"""
        text = (
            "# 《三命通会》\n\n"
            "## 卷一\n\n"
            "### 论五行生成\n"
            "### 论干支源流\n\n"
            "## 卷二\n\n"
            "### 论十干分配天文\n"
            "### 论十二支分配地理\n"
        )
        info = detect_paradigm(text)
        self.assertEqual(info["paradigm"], "A")
        self.assertEqual(info["name"], "汇编全书型")

    def test_detect_paradigm_b(self):
        """测试范式 B【主干经注型】识别（如滴天髓阐微）"""
        text = (
            "# 《滴天髓阐微》\n\n"
            "## 通天论\n\n"
            "### 论天道\n\n"
            "欲识三元万法宗，先观帝载与神功。\n\n"
            "> **【原注】**：天有阴阳，地有刚柔。\n\n"
            "#### 【任氏曰】\n\n"
            "帝载神功，即阴阳造化之妙也。\n"
        )
        info = detect_paradigm(text)
        self.assertEqual(info["paradigm"], "B")
        self.assertEqual(info["name"], "主干经注型")

    def test_detect_paradigm_c(self):
        """测试范式 C【纲目矩阵型】识别（如八字提要）"""
        text = (
            "# 《八字提要》\n\n"
            "## 寅月\n"
            "### 甲日\n"
            "#### 甲子时\n"
            "### 乙日\n"
            "## 卯月\n"
            "### 甲日\n"
            "## 辰月\n"
            "## 巳月\n"
            "## 午月\n"
            "## 未月\n"
        )
        info = detect_paradigm(text)
        self.assertEqual(info["paradigm"], "C")
        self.assertEqual(info["name"], "纲目矩阵型")

    def test_clean_crawler_noise(self):
        """测试清洗爬虫分页与来源噪音"""
        raw = (
            "天一生水，地六成之。\n"
            "第 1 页\n"
            "下一页\n"
            "源站地址：http://www.test-source.com/book/123\n"
            "地二生火，天七成之。"
        )
        cleaned, count = clean_crawler_noise(raw)
        self.assertGreaterEqual(count, 3)
        self.assertNotIn("第 1 页", cleaned)
        self.assertNotIn("下一页", cleaned)
        self.assertNotIn("http://", cleaned)
        self.assertIn("天一生水", cleaned)
        self.assertIn("地二生火", cleaned)

    def test_suppress_echoes(self):
        """测试消除紧邻的同名标题回声"""
        raw = (
            "## 论五行生成\n"
            "### 论五行生成\n"
            "天一生水，地六成之。"
        )
        cleaned, count = suppress_echoes(raw)
        self.assertEqual(count, 1)
        self.assertIn("## 论五行生成", cleaned)
        self.assertNotIn("### 论五行生成", cleaned)
        self.assertIn("天一生水，地六成之。", cleaned)

    def test_correct_heading_runaway(self):
        """测试纠正标题内嵌入长段评注正文的越位错误"""
        raw = "### 【徐注】阴阳之说，最为深奥，学者若非深究其理，未易窥其门径。"
        cleaned, count = correct_heading_runaway(raw)
        self.assertEqual(count, 1)
        self.assertIn("#### 【徐注】", cleaned)
        self.assertIn("阴阳之说，最为深奥，学者若非深究其理，未易窥其门径。", cleaned)

    def test_format_bazi_cases(self):
        """测试命例干支自动四柱排盘"""
        raw = "某官造 壬寅 丁未 己卯 乙亥 评析：己土虽通根月令，而见木之势盛。"
        formatted, count = format_bazi_cases(raw)
        self.assertEqual(count, 1)
        self.assertIn("##### 命例：某官造", formatted)
        self.assertIn("| 年柱 | 月柱 | 日柱 | 时柱 |", formatted)
        self.assertIn("| 壬寅 | 丁未 | 己卯 | 乙亥 |", formatted)
        self.assertIn("**评析**：", formatted)

    def test_expand_document_toc(self):
        """测试根据 Markdown AST 自动提取并扩展多级目录 (H2->H3)"""
        doc = (
            "# 《三命通会》\n\n"
            "## 目录\n"
            "- [卷一](#卷一)\n\n"
            "## 卷一\n\n"
            "### 论五行生成\n"
            "天一生水。\n\n"
            "### 论干支源流\n"
            "夫干者木之干也。\n\n"
            "## 卷二\n\n"
            "### 论十干分配天文\n"
            "甲木为雷。\n"
        )
        updated, ok = expand_document_toc(doc, max_depth=3)
        self.assertTrue(ok)
        self.assertIn("- [卷一](#卷一)", updated)
        self.assertIn("  - [论五行生成](#论五行生成)", updated)
        self.assertIn("  - [论干支源流](#论干支源流)", updated)
        self.assertIn("- [卷二](#卷二)", updated)
        self.assertIn("  - [论十干分配天文](#论十干分配天文)", updated)


if __name__ == "__main__":
    unittest.main()
