#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chunk_splitter.py - 大部头古籍 Markdown AST 分治切片引擎

功能：
1. 识别典籍规模：若全文字符数 > 30,000 字，触发分治切片（避免大模型单次生成 Token 截断与注意力衰减）
2. 依据古典拓扑（## 卷、## 篇、## 月令等 H2 容器）解析 Markdown AST 并切分为独立处理切片
3. 提取全局 H1、序言与目录至首个切片（chunk_00_preamble.md）
4. 输出元数据清单 manifest.json，精确记录各切片标题、字数、切片文件路径与校验状态
5. 配合 normalizer 流程与 chunk_merger.py 实现全流程无损还原
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any


def compute_text_fingerprint(text: str) -> str:
    """计算文本内容的 SHA256 指纹（剔除空白后计算）"""
    compact = re.sub(r'\s+', '', text)
    return hashlib.sha256(compact.encode('utf-8')).hexdigest()[:16]


def split_document_by_headings(
    content: str,
    heading_pattern: str = r'^##\s+(.+)$'
) -> List[Dict[str, Any]]:
    """
    按照指定级别的 Markdown 标题将文档切分为若干片段。
    首段（首个匹配标题之前的内容）作为序言容器。
    """
    lines = content.splitlines(keepends=True)
    chunks = []

    current_title = "前言与目录"
    current_lines = []
    chunk_index = 0

    re_heading = re.compile(heading_pattern)

    for line in lines:
        match = re_heading.match(line)
        if match:
            # 遇到新的匹配标题
            if current_lines:
                chunk_text = "".join(current_lines)
                # 若此前仅积累了全局根标题 H1 或极短空白，则将其并入首个切片容器，不单独割裂成无意义微切片
                pure_accum = re.sub(r'[\s#《》]+', '', chunk_text)
                if chunk_index == 0 and len(pure_accum) < 30:
                    current_title = match.group(1).strip()
                    current_lines.append(line)
                    continue

                chunks.append({
                    "index": chunk_index,
                    "id": f"chunk_{chunk_index:02d}",
                    "title": current_title,
                    "content": chunk_text,
                    "char_count": len(chunk_text),
                    "fingerprint": compute_text_fingerprint(chunk_text)
                })
                chunk_index += 1
                current_lines = []

            current_title = match.group(1).strip()
            current_lines.append(line)
        else:
            current_lines.append(line)

    # 追加最后一个切片
    if current_lines:
        chunk_text = "".join(current_lines)
        chunks.append({
            "index": chunk_index,
            "id": f"chunk_{chunk_index:02d}",
            "title": current_title,
            "content": chunk_text,
            "char_count": len(chunk_text),
            "fingerprint": compute_text_fingerprint(chunk_text)
        })

    return chunks


def process_split(
    input_file: Path,
    output_dir: Path,
    max_chars: int = 30000,
    heading_regex: str = r'^##\s+(.+)$',
    force: bool = False
) -> Dict[str, Any]:
    """
    执行切片并将切片文件与 manifest.json 写入目标目录。
    """
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    total_chars = len(content)
    output_dir.mkdir(parents=True, exist_ok=True)

    if total_chars <= max_chars and not force:
        print(f"ℹ️ 文档总字数为 {total_chars} 字，低于单次分片阈值 {max_chars} 字。无需强制切片。")
        print("💡 如需强制切片，请追加参数 `--force`。")
        return {
            "status": "SKIPPED",
            "message": "文档规模未超阈值",
            "total_chars": total_chars
        }

    raw_chunks = split_document_by_headings(content, heading_pattern=heading_regex)

    manifest_chunks = []
    for c in raw_chunks:
        safe_title = re.sub(r'[\s/\\:\*\?"<>\|]+', '_', c["title"])[:20]
        slice_filename = f"{c['id']}_{safe_title}.md"
        slice_path = output_dir / slice_filename

        with open(slice_path, 'w', encoding='utf-8') as f:
            f.write(c["content"])

        manifest_chunks.append({
            "index": c["index"],
            "id": c["id"],
            "title": c["title"],
            "slice_file": slice_filename,
            "cleaned_file": None,
            "char_count": c["char_count"],
            "fingerprint": c["fingerprint"],
            "status": "PENDING",  # PENDING -> NORMALIZED -> VERIFIED
            "verified": False,
            "similarity": None
        })

    manifest = {
        "version": "1.0.0",
        "source_file": str(input_file.resolve()),
        "created_at": datetime.datetime.now().isoformat(),
        "total_characters": total_chars,
        "chunk_count": len(manifest_chunks),
        "split_pattern": heading_regex,
        "chunks": manifest_chunks
    }

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return {
        "status": "SUCCESS",
        "output_dir": str(output_dir.resolve()),
        "manifest_file": str(manifest_path.resolve()),
        "chunk_count": len(manifest_chunks),
        "total_characters": total_chars
    }


def main():
    parser = argparse.ArgumentParser(
        description="古籍 Markdown 大文件切片分治推进工具"
    )
    parser.add_argument("-i", "--input", required=True, help="待切片的古籍 Markdown 文件路径")
    parser.add_argument("-o", "--output-dir", default="temp/chunks", help="切片输出目录（默认 temp/chunks）")
    parser.add_argument("-m", "--max-chars", type=int, default=30000, help="触发切片的字符数上限门禁（默认 30000）")
    parser.add_argument("-r", "--regex", default=r'^##\s+(.+)$', help="用于切片的标题正则（默认匹配二级标题 ## 卷/篇/章）")
    parser.add_argument("-f", "--force", action="store_true", help="强制切片（无论字数是否超阈值）")

    args = parser.parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    result = process_split(
        input_file=input_path,
        output_dir=output_dir,
        max_chars=args.max_chars,
        heading_regex=args.regex,
        force=args.force
    )

    if result["status"] == "SUCCESS":
        print("=" * 65)
        print("🔪 大文件切片分治完成 (Large File Chunking Succeeded)")
        print("=" * 65)
        print(f"源文件: {input_path.name} (总字数: {result['total_characters']})")
        print(f"生成切片数: {result['chunk_count']}")
        print(f"输出清单: {result['manifest_file']}")
        print("=" * 65)
    elif result["status"] == "SKIPPED":
        pass


if __name__ == "__main__":
    main()
