#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_chunk_lifecycle.py - 大部头切片与拓扑装配生命周期测试
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "resources" / "scripts"))

from chunk_splitter import process_split
from chunk_merger import merge_chunks_from_manifest
from diff_verifier import verify_text_invariance


class TestChunkLifecycle(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.source_file = self.test_dir / "sample_book.md"

        # 创建包含前言与两个分卷的模拟古籍
        self.book_content = (
            "# 《三命通会》\n\n"
            "## 前言\n\n"
            "夫三命之作，肇端于上古，备于李虚中，精于徐子平。\n\n"
            "## 卷一\n\n"
            "### 论五行生成\n\n"
            "天一生水，地六成之；地二生火，天七成之；天三生木，地八成之。\n\n"
            "## 卷二\n\n"
            "### 论干支源流\n\n"
            "夫干者犹树之干，为阳；支者犹树之枝，为阴。大挠始作甲子以定岁辰。\n"
        )
        with open(self.source_file, 'w', encoding='utf-8') as f:
            f.write(self.book_content)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_split_and_merge_roundtrip(self):
        """测试切片分治、模拟清洗后拓扑合并全流程，并验证保真门禁"""
        chunks_dir = self.test_dir / "chunks"

        # 1. 强制切片（因为文本量较小）
        split_res = process_split(
            input_file=self.source_file,
            output_dir=chunks_dir,
            force=True
        )
        self.assertEqual(split_res["status"], "SUCCESS")
        self.assertEqual(split_res["chunk_count"], 3)  # 前言 + 卷一 + 卷二

        manifest_file = chunks_dir / "manifest.json"
        self.assertTrue(manifest_file.exists())

        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        self.assertEqual(len(manifest["chunks"]), 3)

        # 2. 模拟对各切片进行规范化（这里直接以切片为清洗文件）
        for c in manifest["chunks"]:
            slice_path = chunks_dir / c["slice_file"]
            clean_path = chunks_dir / f"clean_{c['slice_file']}"
            with open(slice_path, 'r', encoding='utf-8') as sf:
                c_content = sf.read()
            with open(clean_path, 'w', encoding='utf-8') as cf:
                cf.write(c_content)
            c["cleaned_file"] = clean_path.name
            c["status"] = "VERIFIED"

        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 3. 装配合并
        merged_file = self.test_dir / "merged_book.md"
        merge_res = merge_chunks_from_manifest(
            manifest_path=manifest_file,
            output_file=merged_file,
            source_file=self.source_file,
            threshold=0.998
        )

        self.assertEqual(merge_res["status"], "SUCCESS")
        self.assertTrue(merged_file.exists())

        with open(merged_file, 'r', encoding='utf-8') as mf:
            merged_content = mf.read()

        # 4. 验证合并后与原始文档完全保真
        report = verify_text_invariance(self.book_content, merged_content, threshold=0.998)
        self.assertTrue(report["passed"])
        self.assertGreaterEqual(report["similarity"], 0.998)


if __name__ == "__main__":
    unittest.main()
