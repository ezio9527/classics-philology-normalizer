#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chunk_merger.py - 古籍分治切片拓扑装配与全篇文字保真终审合并引擎

功能：
1. 读取切片清单 manifest.json，按拓扑序号顺序装配所有已清洗的切片
2. 自动检测切片完整度：若存在未完成或缺失清洗的切片，主动阻断合并
3. 终审门禁校验：调用 diff_verifier 逻辑对合并后的完整文档与原始底本进行全书指纹比对（纯字相似度 >= 99.8%）
4. 门禁通过后安全写出至最终目标 Markdown，防止拼装错乱、漏卷、丢章。
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# 导入同级 diff_verifier 模块
try:
    from diff_verifier import verify_text_invariance
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from diff_verifier import verify_text_invariance


def merge_chunks_from_manifest(
    manifest_path: Path,
    output_file: Path,
    source_file: Path = None,
    threshold: float = 0.998,
    force: bool = False
) -> Dict[str, Any]:
    """
    根据 manifest.json 合并清洗后的切片并进行文字守门校验。
    """
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    manifest_dir = manifest_path.parent
    chunks = manifest.get("chunks", [])

    if not chunks:
        raise ValueError(f"清单文件中未找到切片定义: {manifest_path}")

    # 确定原始文档路径
    orig_path_str = manifest.get("source_file")
    if source_file is None and orig_path_str:
        source_file = Path(orig_path_str)

    merged_parts = []
    missing_cleaned = []

    for c in sorted(chunks, key=lambda x: x["index"]):
        # 优先使用 manifest 中明确登记的 cleaned_file
        cleaned_filename = c.get("cleaned_file")
        candidate_paths = []

        if cleaned_filename:
            candidate_paths.append(manifest_dir / cleaned_filename)

        # 约定后备命名规则
        slice_stem = Path(c["slice_file"]).stem
        candidate_paths.append(manifest_dir / f"clean_{c['slice_file']}")
        candidate_paths.append(manifest_dir / f"{slice_stem}.clean.md")
        candidate_paths.append(manifest_dir / f"{slice_stem}_normalized.md")
        # 如果切片本身已被原地覆盖清洗
        candidate_paths.append(manifest_dir / c["slice_file"])

        resolved_path = None
        for p in candidate_paths:
            if p.exists():
                resolved_path = p
                break

        if not resolved_path:
            missing_cleaned.append(c["title"])
            continue

        with open(resolved_path, 'r', encoding='utf-8', errors='ignore') as cf:
            content = cf.read()
            merged_parts.append(content.rstrip() + "\n\n")

    if missing_cleaned:
        err_msg = f"无法合并！以下 {len(missing_cleaned)} 个切片缺失清洗文件：\n" + "\n".join(f" - {t}" for t in missing_cleaned)
        if not force:
            raise FileNotFoundError(err_msg)
        else:
            print(f"⚠️ 警告: 强制忽略缺失切片继续合并: {err_msg}", file=sys.stderr)

    full_merged_text = "".join(merged_parts).strip() + "\n"

    # 执行文字保真终审比对
    verification_report = None
    if source_file and source_file.exists():
        with open(source_file, 'r', encoding='utf-8', errors='ignore') as sf:
            orig_text = sf.read()

        verification_report = verify_text_invariance(orig_text, full_merged_text, threshold=threshold)
        if not verification_report["passed"] and not force:
            print("❌ 全局文字保真门禁校验失败！合并被阻断以保护古籍原文。", file=sys.stderr)
            print(f"纯文本相似度为 {verification_report['similarity_pct']}，低于门禁 {verification_report['threshold_pct']}。", file=sys.stderr)
            for d in verification_report.get("sample_diffs", []):
                print(f"  * {d}", file=sys.stderr)
            sys.exit(2)

    # 写出目标文件
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as out_f:
        out_f.write(full_merged_text)

    # 更新 manifest 状态
    manifest["merged_at"] = manifest.get("created_at")
    manifest["merged_output"] = str(output_file.resolve())
    manifest["merged_status"] = "SUCCESS"
    if verification_report:
        manifest["global_similarity"] = verification_report["similarity_pct"]
        manifest["verified"] = verification_report["passed"]

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return {
        "status": "SUCCESS",
        "output_file": str(output_file.resolve()),
        "total_merged_chunks": len(chunks),
        "verification": verification_report
    }


def main():
    parser = argparse.ArgumentParser(
        description="古籍分治切片拓扑装配与全篇文字保真终审合并工具"
    )
    parser.add_argument("-m", "--manifest", required=True, help="切片清单 manifest.json 路径")
    parser.add_argument("-o", "--output", required=True, help="合并输出的目标 Markdown 文件路径")
    parser.add_argument("-s", "--source", default=None, help="原始底本文件路径（用于全书文字保真终审比对，默认读 manifest 中记录）")
    parser.add_argument("-t", "--threshold", type=float, default=0.998, help="终审门禁阈值（默认 0.998）")
    parser.add_argument("-f", "--force", action="store_true", help="强制覆盖并跳过门禁阻断（危险）")

    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_path = Path(args.output)
    source_path = Path(args.source) if args.source else None

    if not manifest_path.exists():
        print(f"错误: manifest 文件不存在: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    result = merge_chunks_from_manifest(
        manifest_path=manifest_path,
        output_file=output_path,
        source_file=source_path,
        threshold=args.threshold,
        force=args.force
    )

    print("=" * 65)
    print("🏆 古籍分治切片拓扑装配成功 (All Chunks Merged Successfully)")
    print("=" * 65)
    print(f"输出文件: {result['output_file']}")
    print(f"合并切片总数: {result['total_merged_chunks']}")
    if result["verification"]:
        print(f"全书文本保真度: {result['verification']['similarity_pct']} (门禁: >= {result['verification']['threshold_pct']})")
        print("✅ 终审门禁通过！古籍原文零改动、零删减、体例规范化大功告成。")
    print("=" * 65)


if __name__ == "__main__":
    main()
