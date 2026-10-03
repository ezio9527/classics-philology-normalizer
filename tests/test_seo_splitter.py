#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_seo_splitter.py - seo_splitter.py 单元测试
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "resources" / "scripts"))

from seo_splitter import SEOSplitter, to_pinyin_slug, extract_description


class TestSEOSplitter(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.sample_book = self.test_dir / "san_ming_tong_hui.md"
        self.output_dir = self.test_dir / "dist_seo"

        self.book_text = (
            "# 《三命通会》\n\n"
            "> **版本考据**：明·万民英纂辑。\n\n"
            "## 目录\n"
            "- [卷一](#卷一)\n"
            "  - [论五行生成](#论五行生成)\n"
            "  - [论干支源流](#论干支源流)\n"
            "- [卷二](#卷二)\n"
            "  - [论十干分配天文](#论十干分配天文)\n\n"
            "## 卷一\n\n"
            "### 论五行生成\n\n"
            "五行者，往来乎天地之间而穷历四时者也。天一生水，地六成之；地二生火，天七成之。\n\n"
            "### 论干支源流\n\n"
            "夫干者木之干，强而为阳；支者木之枝，弱而为阴。大挠作甲子以定岁辰。\n\n"
            "## 卷二\n\n"
            "### 论十干分配天文\n\n"
            "甲木为雷，震也。乙木为风，巽也。丙火为日，丁火为星。\n"
        )
        with open(self.sample_book, 'w', encoding='utf-8') as f:
            f.write(self.book_text)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_pinyin_slug_and_description(self):
        """测试 Pinyin Slug 生成与中文摘要提取"""
        self.assertEqual(to_pinyin_slug("三命通会"), "san-ming-tong-hui")
        self.assertEqual(to_pinyin_slug("卷一"), "juan-01")
        self.assertEqual(to_pinyin_slug("论五行生成"), "lun-wu-xing-sheng-cheng")

        desc = extract_description(
            "# 论五行生成\n\n> 引用块\n\n五行者，往来乎天地之间而穷历四时者也。天一生水，地六成之。"
        )
        self.assertTrue(desc.startswith("五行者，往来乎天地之间"))

    def test_seo_chapter_splitting_pipeline(self):
        """测试全套 SEO 原子化拆分、目录层级、Frontmatter 与双向内链生成"""
        splitter = SEOSplitter(
            input_file=self.sample_book,
            output_dir=self.output_dir,
            base_url="/classics"
        )
        res = splitter.split_and_generate()

        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["book_title"], "三命通会")
        self.assertEqual(res["total_volumes"], 2)
        self.assertEqual(res["total_chapters"], 3)

        book_dir = self.output_dir / "san-ming-tong-hui"
        self.assertTrue(book_dir.exists())

        # 1. 验证全书 Hub 落地页
        book_hub = book_dir / "index.md"
        self.assertTrue(book_hub.exists())
        with open(book_hub, 'r', encoding='utf-8') as f:
            hub_content = f.read()
        self.assertIn("type: \"book_hub\"", hub_content)
        self.assertIn("total_chapters: 3", hub_content)
        self.assertIn("全书各卷详细检索导航", hub_content)

        # 2. 验证分卷 Hub 页与章节文件
        vol1_dir = book_dir / "juan-01"
        self.assertTrue(vol1_dir.exists())
        vol1_hub = vol1_dir / "index.md"
        self.assertTrue(vol1_hub.exists())
        with open(vol1_hub, 'r', encoding='utf-8') as f:
            v_content = f.read()
        self.assertIn("type: \"volume_hub\"", v_content)
        self.assertIn("卷一所领篇章目次", v_content)

        chap1_file = vol1_dir / "01_lun-wu-xing-sheng-cheng.md"
        chap2_file = vol1_dir / "02_lun-gan-zhi-yuan-liu.md"
        self.assertTrue(chap1_file.exists())
        self.assertTrue(chap2_file.exists())

        # 3. 验证原子叶子页的 Frontmatter 与内链
        with open(chap1_file, 'r', encoding='utf-8') as f:
            c1_text = f.read()

        self.assertIn("title: \"论五行生成 - 《三命通会》卷一\"", c1_text)
        self.assertIn("canonical_url: \"/classics/san-ming-tong-hui/juan-01/01_lun-wu-xing-sheng-cheng\"", c1_text)
        self.assertIn("order: 1", c1_text)
        self.assertIn("next:", c1_text)
        self.assertIn("title: \"论干支源流\"", c1_text)
        self.assertIn("五行者，往来乎天地之间", c1_text)
        self.assertIn("[典籍首页](/classics) / [《三命通会》](/classics/san-ming-tong-hui/)", c1_text)

        # 4. 验证第二卷及跨卷翻页链轮
        vol2_dir = book_dir / "juan-02"
        chap3_file = vol2_dir / "01_lun-shi-gan-fen-pei-tian-wen.md"
        self.assertTrue(chap3_file.exists())

        with open(chap3_file, 'r', encoding='utf-8') as f:
            c3_text = f.read()
        self.assertIn("prev:", c3_text)
        self.assertIn("title: \"论干支源流\"", c3_text)
        self.assertIn("/classics/san-ming-tong-hui/juan-01/02_lun-gan-zhi-yuan-liu", c3_text)

        # 5. 验证 site_manifest.json
        manifest_file = book_dir / "site_manifest.json"
        self.assertTrue(manifest_file.exists())
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        self.assertEqual(manifest["book"], "三命通会")
        self.assertEqual(len(manifest["chapters"]), 3)

    def test_paradigm_c_aggregation(self):
        """测试范式 C（纲目矩阵型）智能聚合至日主 H3 页面，包含多个 H4 时辰断语，避免 Thin Content"""
        matrix_file = self.test_dir / "ba_zi_ti_yao.md"
        matrix_text = (
            "# 《八字提要》\n\n"
            "## 寅月\n\n"
            "### 甲日\n\n"
            "#### 甲子时\n"
            "甲木得禄于寅，又见子水相生。\n\n"
            "#### 乙丑时\n"
            "甲生寅月，时临乙丑，劫财透干。\n\n"
            "### 乙日\n\n"
            "#### 丙子时\n"
            "乙木生于初春，见丙火解冻。\n"
        )
        with open(matrix_file, 'w', encoding='utf-8') as f:
            f.write(matrix_text)

        matrix_out = self.test_dir / "dist_matrix"
        splitter = SEOSplitter(
            input_file=matrix_file,
            output_dir=matrix_out,
            base_url="/classics"
        )
        res = splitter.split_and_generate()
        self.assertEqual(res["total_volumes"], 1)  # 寅月
        self.assertEqual(res["total_chapters"], 2)  # 甲日, 乙日

        book_dir = matrix_out / "ba-zi-ti-yao"
        vol_dir = book_dir / "yin-yue"
        self.assertTrue(vol_dir.exists())

        jia_ri_file = vol_dir / "01_jia-ri.md"
        self.assertTrue(jia_ri_file.exists())
        with open(jia_ri_file, 'r', encoding='utf-8') as f:
            c_text = f.read()

        # 验证 H4 时辰完整聚合在甲日页面内
        self.assertIn("#### 甲子时", c_text)
        self.assertIn("#### 乙丑时", c_text)
        self.assertIn("甲木得禄于寅", c_text)


if __name__ == "__main__":
    unittest.main()
