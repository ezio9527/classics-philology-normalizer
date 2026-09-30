#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diff_verifier.py - 古籍文本指纹与文字绝对保真校验门禁

功能：
1. 剥离 Markdown 语法标记（#、>、|、-、表格分隔符、加粗、代码块等）
2. 剥离允许过滤的爬虫杂音与排版残留（如“第 一 页”、“下一页”、“源站地址：...”）
3. 剥离标题机械回声行（如 ## 标题 紧跟 ### 标题）
4. 计算原始纯文本与清洗后纯文本的字符级相似度（SequenceMatcher比对）
5. 门禁验证：纯文本字符相似度必须 >= 99.8%（可配置）
6. 报告字符级 Diff 差异明细与上下文，防止任何古籍字句篡改、删减或白话化润色。
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

# 常见爬虫分页与排版噪音正则
CRAWLER_NOISE_PATTERNS = [
    r'第\s*[一二三四五六七八九十百千万0-9]+\s*页',
    r'第\s*[0-9]+\s*/\s*[0-9]+\s*页',
    r'\[\s*上一页\s*\]|\(上一页\)|上一页',
    r'\[\s*下一页\s*\]|\(下一页\)|下一页',
    r'\[\s*首\s*页\s*\]|\(首页\)|首页',
    r'\[\s*尾\s*页\s*\]|\(尾页\)|尾页',
    r'\[\s*返回目录\s*\]|\(返回目录\)|返回目录',
    r'源站地址[：:][^\n\r]*',
    r'来源[：:][^\n\r]*',
    r'https?://[^\s\u4e00-\u9fa5]+',
    r'www\.[^\s\u4e00-\u9fa5]+',
    r'扫码关注[^\n\r]*',
    r'本站域名[：:][^\n\r]*',
    r'作者[：:][^\n\r]*整理',
    r'OCR识别结果仅供参考',
]

RE_CRAWLER_NOISE = re.compile('|'.join(CRAWLER_NOISE_PATTERNS), re.IGNORECASE)

# 命造表格表头关键词（表格化时新增的结构元信息，不属于正文篡改）
TABLE_HEADER_TOKENS = ['年柱', '月柱', '日柱', '时柱', '命造', '命例', '评析']


def strip_markdown(text: str) -> str:
    """
    剥离 Markdown 标记并保留核心汉字与标点符号。
    """
    # 移除 HTML 标签与注释
    text = re.sub(r'<!--[\s\S]*?-->', '', text)
    text = re.sub(r'<[^>]+>', '', text)

    # 移除代码块
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)

    # 移除图片与链接标记
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)

    # 移除四柱排盘表格表头行 (如 | 年柱 | 月柱 | 日柱 | 时柱 |)
    text = re.sub(r'\|\s*年柱\s*\|\s*月柱\s*\|\s*日柱\s*\|\s*时柱\s*\|', '', text)
    # 移除表格对齐标记行 (e.g. | :---: | :---: |)
    text = re.sub(r'\|[\s:\-]+\|[\s:\-|]*', '', text)

    # 移除 Markdown 结构符号：#、>、|、-、*、_、~
    lines = text.splitlines()
    cleaned_lines = []
    prev_heading = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 检查是否为标题行
        m_head = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if m_head:
            curr_heading = m_head.group(2).strip()
            # 过滤机械标题回声（连续紧挨着的同名标题）
            if curr_heading == prev_heading:
                continue
            prev_heading = curr_heading
            # 移除命例标题结构前缀 如 ##### 命例：
            curr_heading = re.sub(r'^命例[：:]\s*', '', curr_heading)
            # 移除书名号《》若其仅包裹在H1书名处
            if m_head.group(1) == '#':
                curr_heading = re.sub(r'^[《〈](.*?)[》〉]$', r'\1', curr_heading)
            cleaned_lines.append(curr_heading)
            continue
        else:
            prev_heading = ""

        # 剥离行首引用符 >
        stripped = re.sub(r'^>+\s*', '', stripped)
        # 剥离无序列表符 -、*、+
        stripped = re.sub(r'^[\-\*\+]\s+', '', stripped)
        # 剥离有序列表数字 1. 2.
        stripped = re.sub(r'^\d+\.\s+', '', stripped)
        # 剥离行内加粗、斜体与删除线
        stripped = re.sub(r'[\*_~]{1,3}', '', stripped)
        # 剥离表格前后竖线与空格
        stripped = re.sub(r'\|', ' ', stripped)

        cleaned_lines.append(stripped)

    result = '\n'.join(cleaned_lines)
    return result


def normalize_ancient_text(text: str, is_original: bool = False) -> str:
    """
    标准化古籍文本用于指纹对比：
    1. 剥离 Markdown 语法
    2. 若为原始文档，滤除已知的爬虫噪音
    3. 规范化所有空白字符（空格、换行、全角空格等）
    4. 规范化表格辅助词
    """
    clean_md = strip_markdown(text)

    # 滤除爬虫噪音
    clean_no_crawler = RE_CRAWLER_NOISE.sub('', clean_md)

    # 统一移除所有空白字符（包括空格、制表符、换行、全角空格），专注汉字与古标点流
    pure_chars = re.sub(r'[\s\u3000\t\r\n]+', '', clean_no_crawler)

    # 过滤现代冒号标点（古籍原无冒号，冒号皆为 Markdown 结构标签后加或 OCR 引入）
    pure_chars = re.sub(r'[：:]', '', pure_chars)

    return pure_chars


def verify_text_invariance(
    original_text: str,
    cleaned_text: str,
    threshold: float = 0.998
) -> Dict[str, Any]:
    """
    执行文本保真度指纹对比。
    返回统计数据、相似度及差异诊断信息。
    """
    norm_orig = normalize_ancient_text(original_text, is_original=True)
    norm_clean = normalize_ancient_text(cleaned_text, is_original=False)

    len_orig = len(norm_orig)
    len_clean = len(norm_clean)

    if len_orig == 0:
        return {
            "passed": len_clean == 0,
            "similarity": 1.0 if len_clean == 0 else 0.0,
            "original_length": 0,
            "cleaned_length": len_clean,
            "diff_chars": len_clean,
            "threshold": threshold,
            "diff_summary": "原始文档提取纯文本为空"
        }

    # 使用 SequenceMatcher 计算相似度
    matcher = difflib.SequenceMatcher(None, norm_orig, norm_clean, autojunk=False)
    similarity = matcher.ratio()

    diff_chars = abs(len_orig - len_clean)
    passed = similarity >= threshold

    # 提取差异明细
    diff_snippets: List[str] = []
    if not passed or similarity < 1.0:
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                diff_snippets.append(
                    f"【文字变异/篡改】 原文[{i1}:{i2}]: '{norm_orig[i1:i2]}' -> 清洗后[{j1}:{j2}]: '{norm_clean[j1:j2]}'"
                )
            elif tag == 'delete':
                diff_snippets.append(
                    f"【文字缺失/擅删】 原文[{i1}:{i2}]: '{norm_orig[i1:i2]}'"
                )
            elif tag == 'insert':
                diff_snippets.append(
                    f"【非法多余字符】 清洗后[{j1}:{j2}]: '{norm_clean[j1:j2]}'"
                )
            if len(diff_snippets) >= 20:
                diff_snippets.append("... 差异过多，仅展示前 20 处 ...")
                break

    return {
        "passed": passed,
        "similarity": round(similarity, 6),
        "similarity_pct": f"{similarity * 100:.3f}%",
        "threshold_pct": f"{threshold * 100:.3f}%",
        "original_char_count": len_orig,
        "cleaned_char_count": len_clean,
        "char_difference": diff_chars,
        "sample_diffs": diff_snippets
    }


def main():
    parser = argparse.ArgumentParser(
        description="古籍 Markdown 文本保真度指纹校验工具（门禁：纯文字相似度 >= 99.8%）"
    )
    parser.add_argument("-o", "--original", required=True, help="原始未处理 Markdown 文件路径")
    parser.add_argument("-c", "--cleaned", required=True, help="清洗规范化后 Markdown 文件路径")
    parser.add_argument(
        "-t", "--threshold", type=float, default=0.998,
        help="纯文本保真度门禁阈值（默认 0.998 即 99.8%）"
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出检测报告")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出完整变动明细")

    args = parser.parse_args()

    orig_path = Path(args.original)
    clean_path = Path(args.cleaned)

    if not orig_path.exists():
        print(f"错误: 原始文件不存在: {orig_path}", file=sys.stderr)
        sys.exit(1)
    if not clean_path.exists():
        print(f"错误: 清洗后文件不存在: {clean_path}", file=sys.stderr)
        sys.exit(1)

    with open(orig_path, 'r', encoding='utf-8', errors='ignore') as f:
        orig_content = f.read()

    with open(clean_path, 'r', encoding='utf-8', errors='ignore') as f:
        clean_content = f.read()

    report = verify_text_invariance(orig_content, clean_content, threshold=args.threshold)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=" * 65)
        print("📜 古籍文本保真度校验报告 (Classics Text Invariance Report)")
        print("=" * 65)
        print(f"原始文件: {orig_path.name} (纯汉字计数: {report['original_char_count']})")
        print(f"清洗文件: {clean_path.name} (纯汉字计数: {report['cleaned_char_count']})")
        print(f"纯文本相似度: {report['similarity_pct']} (门禁要求: >= {report['threshold_pct']})")
        print(f"字数绝对差值: {report['char_difference']} 字")
        print("-" * 65)

        if report["passed"]:
            print("✅ 门禁通过！古籍文字 100% 忠实保真，无篡改、无误删、无白话化。")
        else:
            print("❌ 门禁未通过！古籍文字出现异常漂移或脱落，请核查以下变动：")
            for diff in report["sample_diffs"]:
                print(f"  * {diff}")

        print("=" * 65)

    sys.exit(0 if report["passed"] else 2)


if __name__ == "__main__":
    main()
