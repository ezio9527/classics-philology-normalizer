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
            "> **【任氏曰】**：帝载神功，即阴阳造化之妙也。\n"
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
        """测试纠正标题内嵌入长段评注正文，规整为引用块粗体按语（> **【某某注】**：...）"""
        raw = "### 【徐注】阴阳之说，最为深奥，学者若非深究其理，未易窥其门径。"
        cleaned, count = correct_heading_runaway(raw)
        self.assertEqual(count, 1)
        self.assertIn("> **【徐注】**：阴阳之说，最为深奥，学者若非深究其理，未易窥其门径。", cleaned)
        self.assertNotIn("#### 【徐注】", cleaned)

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

    def test_unseen_book_paradigm_detection_without_hardcoding(self):
        """测试对完全未知的书名，纯依靠 AST 拓扑结构正确判定范式（杜绝硬编码）"""
        # 未见汇编全书
        doc_a = (
            "# 《青囊玄髓大成》\n\n"
            "## 卷一\n\n"
            "### 论阴阳互根\n正文...\n"
            "### 论五行气数\n正文...\n"
            "## 卷二\n\n"
            "### 论四象配合\n正文...\n"
        )
        self.assertEqual(detect_paradigm(doc_a)["paradigm"], "A")

        # 未见经注本
        doc_b = (
            "# 《玄天古经解注》\n\n"
            "## 上篇\n\n"
            "### 天道玄微\n"
            "天道冲虚，至妙潜通。\n\n"
            "> **【原注】**：此明大道本原。\n\n"
            "> **【张楠曰】**：造化流行，莫非一气。\n\n"
            "> **【千里按】**：学者不可不察。\n"
        )
        self.assertEqual(detect_paradigm(doc_b)["paradigm"], "B")

        # 未见时令矩阵
        doc_c = (
            "# 《历代节令指南》\n\n"
            "## 寅月\n\n"
            "### 甲日\n初春木嫩。\n"
            "### 乙日\n初春喜火。\n"
            "## 卯月\n\n"
            "### 甲日\n仲春乘旺。\n"
        )
        self.assertEqual(detect_paradigm(doc_c)["paradigm"], "C")

    def test_generalized_commentator_runaway(self):
        """测试历代任意名家评注越位均可自适应纠正为引用块粗体（张楠曰、千里按、朱子曰、OCR错位符号）"""
        test_cases = [
            ("### 【张楠曰】阴阳顺逆之说，不可不知也。", "> **【张楠曰】**：", "阴阳顺逆之说，不可不知也。"),
            ("### 【千里按】此造日元极弱，全赖时支印绶化杀生身。", "> **【千里按】**：", "此造日元极弱，全赖时支印绶化杀生身。"),
            ("### 【朱子曰】易者，变易也，随天地气运而化生。", "> **【朱子曰】**：", "易者，变易也，随天地气运而化生。"),
            ("### 【先正云】官星佩印，贵不可言。", "> **【先正云】**：", "官星佩印，贵不可言。"),
            ("「任氏曰】：\n\n干为天元，支为地元，支中所藏为人元。", "> **【任氏曰】**：", "干为天元，支为地元，支中所藏为人元。"),
            ("#### 【任氏曰】\n\n帝载神功，即阴阳造化之妙也。", "> **【任氏曰】**：", "帝载神功，即阴阳造化之妙也。"),
        ]
        for raw, expected_tag, expected_body in test_cases:
            cleaned, count = correct_heading_runaway(raw)
            self.assertEqual(count, 1, f"Failed on: {raw}")
            self.assertIn(expected_tag, cleaned)
            self.assertIn(expected_body, cleaned)
            self.assertNotIn("####", cleaned)

    def test_generalized_bazi_prefixes(self):
        """测试多样化历史命例前缀均可自适应识别与四柱表格排盘"""
        samples = [
            ("某尚书造 丙寅 庚寅 丙申 己丑 评析：木火通明之格。", "##### 命例：某尚书造"),
            ("坤造 乙丑 己卯 戊子 癸亥 评析：财官双美。", "##### 命例：坤造"),
            ("一富商造 壬子 壬子 壬子 壬子 评析：润下成格。", "##### 命例：一富商造"),
            ("岳武穆命 癸未 乙卯 甲子 己巳 评析：精忠报国之造。", "##### 命例：岳武穆命"),
            ("又一造 甲子 丙子 戊子 庚申 评析：地支一气。", "##### 命例：又一造"),
        ]
        for raw, expected_heading in samples:
            formatted, count = format_bazi_cases(raw)
            self.assertEqual(count, 1, f"Failed on: {raw}")
            self.assertIn(expected_heading, formatted)
            self.assertIn("| 年柱 | 月柱 | 日柱 | 时柱 |", formatted)


if __name__ == "__main__":
    unittest.main()
