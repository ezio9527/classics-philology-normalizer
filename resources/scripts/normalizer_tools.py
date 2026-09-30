#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalizer_tools.py - 古籍文献体例规范化与校勘辅助工具箱

功能：
1. detect-paradigm: 典籍编纂范式判定（范式A 汇编全书型 / 范式B 主干经注型 / 范式C 纲目矩阵型）
2. clean-crawler-noise: 清洗爬虫分页残留、来源链接与OCR无用水印
3. suppress-echoes: 消除机械标题回声行（如连续紧随出现的重名子标题）
4. correct-heading-runaway: 纠正长段正文嵌入标题的越位错误（如把 ### 【徐注】... 拆分为标题与正文段落）
5. format-bazi: 智能识别命理八字干支组合，规范化排盘为四柱标准 Markdown 表格
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

TIANGAN = "甲乙丙丁戊己庚辛壬癸"
DIZHI = "子丑寅卯辰巳午未申酉戌亥"
MONTH_BRANCHES = ["寅月", "卯月", "辰月", "巳月", "午月", "未月", "申月", "酉月", "戌月", "亥月", "子月", "丑月"]
DAY_MASTERS = [f"{g}日" for g in TIANGAN]

# 常见爬虫分页与排版噪音正则
CRAWLER_NOISE_REGEXES = [
    re.compile(r'^[ \t]*第\s*[一二三四五六七八九十百千万0-9]+\s*页[ \t]*$', re.MULTILINE),
    re.compile(r'^[ \t]*第\s*[0-9]+\s*/\s*[0-9]+\s*页[ \t]*$', re.MULTILINE),
    re.compile(r'^[ \t]*\[?\s*(?:上一页|下一页|首页|尾页|末页|返回目录)\s*\]?[ \t]*$', re.MULTILINE),
    re.compile(r'^[ \t]*(?:源站地址|来源|首发网站|下载地址)[：:][^\n\r]*$', re.MULTILINE),
    re.compile(r'^[ \t]*https?://[^\s\u4e00-\u9fa5]+[ \t]*$', re.MULTILINE),
    re.compile(r'^[ \t]*www\.[^\s\u4e00-\u9fa5]+[ \t]*$', re.MULTILINE),
    re.compile(r'^[ \t]*(?:扫码关注|关注公众号|本书由|校对整理者)[^\n\r]*$', re.MULTILINE),
    re.compile(r'^[ \t]*OCR识别结果仅供参考[^\n\r]*$', re.MULTILINE),
]


def detect_paradigm(text: str) -> Dict[str, Any]:
    """
    通过文本结构、标题与关键词自动判定典籍所属范式：
    - 范式 A【汇编全书型】（如《三命通会》《渊海子平》）：拓扑为 卷 -> 篇/章 -> 小节/歌赋
    - 范式 B【主干经注型】（如《滴天髓阐微》《子平真诠》）：拓扑为 卷/篇 -> 核心论章 -> 经文/原注/名家评注/命例
    - 范式 C【纲目矩阵型】（如《八字提要》《穷通宝鉴》）：拓扑为 月令(纲) -> 日主(目) -> 时辰(条)
    """
    score_a = 0
    score_b = 0
    score_c = 0

    reasons_a = []
    reasons_b = []
    reasons_c = []

    # 检查纲目矩阵特征 (范式 C)
    month_hits = sum(1 for m in MONTH_BRANCHES if m in text)
    day_hits = sum(1 for d in DAY_MASTERS if d in text)
    matrix_pattern_hits = len(re.findall(r'[寅卯辰巳午未申酉戌亥]月[甲乙丙丁戊己庚辛壬癸]日', text))

    if month_hits >= 6 and (day_hits >= 5 or matrix_pattern_hits >= 3):
        score_c += 80
        reasons_c.append(f"命中 {month_hits} 个月令纲目与 {day_hits} 个日主目节点，存在典型干支时辰矩阵结构")

    if "八字提要" in text or "穷通宝鉴" in text or "栏江网" in text:
        score_c += 50
        reasons_c.append("书名/文本高度关联经典纲目矩阵著作")

    # 检查主干经注型特征 (范式 B)
    commentary_tokens = ['原注', '任氏曰', '徐注', '任铁樵', '沈氏曰', '沈孝瞻', '先正云', '注曰']
    comm_hits = sum(len(re.findall(rf'【?{tok}】?', text)) for tok in commentary_tokens)
    if comm_hits >= 5:
        score_b += 40 + min(comm_hits * 3, 50)
        reasons_b.append(f"命中大量夹注与注疏评语标记（共 {comm_hits} 处），符合经注体例")

    if "滴天髓" in text or "子平真诠" in text:
        score_b += 50
        reasons_b.append("书名/文本高度关联主干经注文献")

    # 检查汇编全书型特征 (范式 A)
    juan_headings = len(re.findall(r'#+\s+卷[一二三四五六七八九十0-9]+', text))
    lun_headings = len(re.findall(r'#+\s+论[\u4e00-\u9fa5]+', text))
    if juan_headings >= 2:
        score_a += 30 + min(juan_headings * 5, 40)
        reasons_a.append(f"命中 {juan_headings} 个宏观卷容器标题")
    if lun_headings >= 5:
        score_a += 30
        reasons_a.append(f"命中 {lun_headings} 个论题篇章标题")

    if "三命通会" in text or "渊海子平" in text or "神峰通考" in text or "星平会海" in text:
        score_a += 50
        reasons_a.append("书名/文本高度关联集大成汇编全书")

    scores = [
        ("A", "汇编全书型", score_a, reasons_a, "# 书名 -> ## 卷 N (容器) -> ### 篇/章 (论题) -> #### 小节/歌赋"),
        ("B", "主干经注型", score_b, reasons_b, "# 书名 -> ## 宏观卷/篇 -> ### 核心论章 -> 经文/原注/名家评注/命例"),
        ("C", "纲目矩阵型", score_c, reasons_c, "# 书名 -> ## 月令 (纲容器) -> ### 日主 (目章节) -> #### 时辰条目 (条)"),
    ]

    scores.sort(key=lambda x: x[2], reverse=True)
    best = scores[0]

    return {
        "paradigm": best[0],
        "name": best[1],
        "score": best[2],
        "topology": best[4],
        "reasons": best[3],
        "all_scores": {s[0]: s[2] for s in scores}
    }


def clean_crawler_noise(text: str) -> Tuple[str, int]:
    """
    清除页面爬虫残留标记与无用链接。
    保持所有实际正文完全不受干扰。
    """
    total_removed = 0
    cleaned = text
    for rx in CRAWLER_NOISE_REGEXES:
        cleaned, count = rx.subn('', cleaned)
        total_removed += count

    # 清理多余空行（保留最多连续两个换行）
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned, total_removed


def suppress_echoes(text: str) -> Tuple[str, int]:
    """
    消除因采集或复制导致的机械标题回声。
    例如：
    ## 论五行生成
    ### 论五行生成  <-- 删除此重复行
    """
    lines = text.splitlines(keepends=True)
    out_lines = []
    echo_count = 0

    re_heading = re.compile(r'^(#{1,6})\s+(.*)$')
    prev_title = None

    for line in lines:
        stripped = line.strip()
        m = re_heading.match(stripped)
        if m:
            curr_title = m.group(2).strip()
            # 剔除符号以便纯文字比较
            pure_curr = re.sub(r'[\s、，。：:《》【】\[\]]+', '', curr_title)
            pure_prev = re.sub(r'[\s、，。：:《》【】\[\]]+', '', prev_title) if prev_title else ""

            if pure_prev and pure_curr == pure_prev:
                # 出现机械回声标题，予以消除
                echo_count += 1
                continue

            prev_title = curr_title
            out_lines.append(line)
        else:
            if stripped:
                prev_title = None  # 遇到正文后重置前置标题
            out_lines.append(line)

    return "".join(out_lines), echo_count


def correct_heading_runaway(text: str) -> Tuple[str, int]:
    """
    纠正标题越位与降级错误：
    例如将长篇正文整段放在标题后面的情况：
    ### 【徐注】阴阳之说，最为深奥，若非熟读阴阳五行……
    纠正为：
    #### 【徐注】

    阴阳之说，最为深奥，若非熟读阴阳五行……
    """
    lines = text.splitlines(keepends=True)
    out_lines = []
    fixed_count = 0

    # 匹配标题中嵌入评注且后跟长正文（超过15字或带有标点）
    re_runaway = re.compile(r'^(#{1,6})\s+(【(?:徐注|任氏曰|沈注|注|原注|评)】)([\u4e00-\u9fa5，。、；！].*)$')

    for line in lines:
        stripped = line.strip()
        m = re_runaway.match(stripped)
        if m:
            tag = m.group(2)
            body = m.group(3).strip()
            if len(body) > 6:
                # 标题降为四级规范评注标题，正文成段
                out_lines.append(f"#### {tag}\n\n{body}\n\n")
                fixed_count += 1
                continue

        out_lines.append(line)

    return "".join(out_lines), fixed_count


def format_bazi_cases(text: str) -> Tuple[str, int]:
    """
    识别八字命造并标准化为四柱 Markdown 表格排盘。
    标准结构：
    ##### 命例：某官造

    | 年柱 | 月柱 | 日柱 | 时柱 |
    | :---: | :---: | :---: | :---: |
    | 壬寅 | 丁未 | 己卯 | 乙亥 |

    **评析**：……
    """
    count = 0

    # 匹配四柱干支模式：如 "壬寅 丁未 己卯 乙亥" 或 "壬寅、丁未、己卯、乙亥"
    gz = f"[{TIANGAN}][{DIZHI}]"
    sep = r'[\s、，\t]+'
    re_four_pillars = re.compile(
        rf'(?:([乾坤]造|某[官士商儒人]?造|命造|例[：:]|如|又)?[\s：:]*)?'
        rf'({gz}){sep}({gz}){sep}({gz}){sep}({gz})'
    )

    lines = text.splitlines(keepends=True)
    out_lines = []

    for line in lines:
        # 如果当前行已经是表格形式，则跳过
        if '|' in line and ('年柱' in line or '---' in line):
            out_lines.append(line)
            continue

        m = re_four_pillars.search(line)
        if m:
            prefix = line[:m.start()].strip()
            title_tag = m.group(1) or "命造"
            year_gz = m.group(2)
            month_gz = m.group(3)
            day_gz = m.group(4)
            hour_gz = m.group(5)
            postfix = line[m.end():].strip()

            table_block = []
            if prefix:
                table_block.append(f"{prefix}\n\n")

            table_block.append(f"##### 命例：{title_tag}\n\n")
            table_block.append("| 年柱 | 月柱 | 日柱 | 时柱 |\n")
            table_block.append("| :---: | :---: | :---: | :---: |\n")
            table_block.append(f"| {year_gz} | {month_gz} | {day_gz} | {hour_gz} |\n\n")

            if postfix:
                table_block.append(f"**评析**：{postfix}\n")

            out_lines.append("".join(table_block))
            count += 1
        else:
            out_lines.append(line)

    return "".join(out_lines), count


def main():
    parser = argparse.ArgumentParser(
        description="古籍文献体例规范化与校勘辅助工具箱"
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # detect-paradigm
    p_detect = subparsers.add_parser("detect-paradigm", help="判定古籍文献典籍编纂范式")
    p_detect.add_argument("-i", "--input", required=True, help="古籍 Markdown 文件路径")

    # suppress-echoes
    p_echo = subparsers.add_parser("suppress-echoes", help="消除机械标题回声")
    p_echo.add_argument("-i", "--input", required=True, help="输入 Markdown 文件路径")
    p_echo.add_argument("-o", "--output", required=True, help="输出 Markdown 文件路径")

    # clean-crawler-noise
    p_crawler = subparsers.add_parser("clean-crawler-noise", help="清理爬虫残余标记与无用链接")
    p_crawler.add_argument("-i", "--input", required=True, help="输入 Markdown 文件路径")
    p_crawler.add_argument("-o", "--output", required=True, help="输出 Markdown 文件路径")

    # format-bazi
    p_bazi = subparsers.add_parser("format-bazi", help="将干支四柱规范化为标准 Markdown 表格排盘")
    p_bazi.add_argument("-i", "--input", required=True, help="输入 Markdown 文件路径")
    p_bazi.add_argument("-o", "--output", required=True, help="输出 Markdown 文件路径")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    if args.command == "detect-paradigm":
        info = detect_paradigm(content)
        print("=" * 65)
        print("🏛️ 典籍编纂范式判定报告 (Typology Classification)")
        print("=" * 65)
        print(f"推荐范式: 范式 {info['paradigm']} 【{info['name']}】 (得分: {info['score']})")
        print(f"标准拓扑: {info['topology']}")
        print("判定理由:")
        for r in info["reasons"]:
            print(f"  * {r}")
        print("=" * 65)

    elif args.command == "suppress-echoes":
        cleaned, count = suppress_echoes(content)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print(f"✅ 成功消除 {count} 处机械标题回声行。已保存至: {output_path}")

    elif args.command == "clean-crawler-noise":
        cleaned, count = clean_crawler_noise(content)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print(f"✅ 成功清理 {count} 处爬虫噪音与页面残留标记。已保存至: {output_path}")

    elif args.command == "format-bazi":
        cleaned, count = format_bazi_cases(content)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print(f"✅ 成功格式化 {count} 处命例八字排盘表格。已保存至: {output_path}")


if __name__ == "__main__":
    main()
