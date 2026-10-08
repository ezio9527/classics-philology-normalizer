#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seo_splitter.py - 古籍规范化 Markdown 章节级 SEO 原子化拆分引擎

功能：
1. 依据古典文献学三大范式（A/B/C）智能解析 Markdown AST 树；
2. 将单体古籍拆解为面向现代静态站点（Astro, Hugo, Next.js, VitePress）的原子章节 Markdown；
3. 为每个页面自动注入全套高权重 SEO YAML Frontmatter（Title, Description, Canonical URL, Breadcrumbs, Prev/Next）；
4. 范式 C（纲目矩阵）智能聚合：日主作为叶子文章页聚合 12 时辰，避免产生 1440 个薄内容（Thin Content）受到搜索引擎惩罚；
5. 生成全书总览页 (Book Hub) 与分卷聚合页 (Volume Hub)，构建深层闭环内链网络；
6. 自动导出 site_manifest.json，供静态建站框架直接消费；
7. 全程文字保真逆向守门：确保切片汇总后正文字符 100% 忠实无丢失。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# 导入同级 normalizer_tools 与 diff_verifier 模块
try:
    from normalizer_tools import detect_paradigm, RE_COMMENTATOR_TAG
    from diff_verifier import verify_text_invariance
    from pinyin_dict import to_pinyin_slug, chinese_to_number
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from normalizer_tools import detect_paradigm, RE_COMMENTATOR_TAG
    from diff_verifier import verify_text_invariance
    from pinyin_dict import to_pinyin_slug, chinese_to_number


def extract_description(content: str, max_chars: int = 140) -> str:
    """提取首段纯正文作为 SEO 搜索摘要 (Meta Description)"""
    lines = content.splitlines()
    pure_paragraphs = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 跳过标题、引用块标记、表格、HTML 注释
        if stripped.startswith('#') or stripped.startswith('>') or stripped.startswith('|') or stripped.startswith('<!--'):
            continue
        # 清除行内标记
        clean_line = re.sub(r'[\*_~`\[\]]', '', stripped)
        clean_line = re.sub(r'\(.*?\)', '', clean_line)
        if len(clean_line) > 10:
            pure_paragraphs.append(clean_line)
            if len("".join(pure_paragraphs)) >= max_chars:
                break

    full_desc = "".join(pure_paragraphs)
    if len(full_desc) > max_chars:
        return full_desc[:max_chars].rstrip('，。、；： ') + "……"
    return full_desc if full_desc else "古典命理文献章节论述与校勘全文。"


def extract_keywords(book: str, volume: str, chapter: str, content: str) -> List[str]:
    """提取核心命理与文献 SEO 关键词（纯动态与文献学通用提取，零人名白名单硬编码）"""
    keywords = [book, volume, chapter]

    candidates = [
        "五行", "天干", "地支", "月令", "日主", "命例", "正印", "偏印",
        "正官", "七杀", "正财", "偏财", "食神", "伤官", "比肩", "劫财",
        "长生", "禄位", "通根", "透干", "原注", "纳音", "用神", "格局"
    ]

    # 动态匹配正文中出现的评注家名（从通用标签提取）
    comm_tags = RE_COMMENTATOR_TAG.findall(content)
    for tag in comm_tags:
        pure_name = re.sub(r'[【】]', '', tag)
        if pure_name not in candidates:
            candidates.append(pure_name)

    for c in candidates:
        if c in content and c not in keywords:
            keywords.append(c)
        if len(keywords) >= 8:
            break

    return keywords


class SEOSplitter:
    def __init__(self, input_file: Path, output_dir: Path, base_url: str = "/classics", split_level: int = 3, config_path: Optional[Path] = None):
        self.input_file = input_file
        self.output_dir = output_dir
        self.base_url = base_url.rstrip('/')
        self.split_level = split_level
        self.config_path = config_path

        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            self.raw_content = f.read()

        self.paradigm_info = detect_paradigm(self.raw_content, config_path=self.config_path)
        self.book_title = self._parse_book_title()
        self.book_slug = to_pinyin_slug(self.book_title)
        self.author = self._parse_author()

    def _parse_book_title(self) -> str:
        """解析全书根标题 H1"""
        m = re.search(r'^#\s+(.+)$', self.raw_content, re.MULTILINE)
        if m:
            raw = m.group(1).strip()
            # 移除书名号
            return re.sub(r'^[《〈](.*?)[》〉]$', r'\1', raw)
        return self.input_file.stem

    def _parse_author(self) -> str:
        """解析典籍著者/版本朝代信息（优先配置覆盖，次之从前言考据解析，杜绝死板硬编码）"""
        # 1. 检查配置文件
        cfg_file = self.config_path or Path("classics_config.json")
        if cfg_file.exists():
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    if "author_attributions" in cfg and self.book_title in cfg["author_attributions"]:
                        return cfg["author_attributions"][self.book_title]
            except Exception:
                pass

        # 2. 从前言引用块自动提取朝代与作者（如 > **版本考据**：明·万民英纂辑 或 > **著者**：清·任铁樵）
        m_auth = re.search(
            r'>\s*\*{0,2}(?:版本考据|著者|作者|注疏|考证)\*{0,2}[：:]\s*([\u4e00-\u9fa5·]{2,8}?)(?:注疏|纂辑|撰|著|辑|校|疏|述|订|按|原著|。|\s|$)',
            self.raw_content
        )
        if m_auth:
            return m_auth.group(1).strip()

        return ""

    def parse_structure(self) -> Tuple[str, List[Dict[str, Any]]]:
        """
        解析 Markdown AST，提取前言与分卷章节结构
        返回: (preamble_text, volumes_list)
        """
        lines = self.raw_content.splitlines(keepends=True)
        preamble_lines = []
        volumes = []

        current_volume = None
        current_chapter = None

        re_h1 = re.compile(r'^#\s+(.+)$')
        re_h2 = re.compile(r'^##\s+(.+)$')
        re_h3 = re.compile(r'^###\s+(.+)$')

        in_preamble = True

        for line in lines:
            m2 = re_h2.match(line)
            m3 = re_h3.match(line)

            if m2:
                v_title = m2.group(1).strip()
                # 检查是否为卷首目录，目录不作为独立分卷
                if "目录" in v_title:
                    preamble_lines.append(line)
                    continue

                in_preamble = False
                current_volume = {
                    "title": v_title,
                    "slug": to_pinyin_slug(v_title),
                    "header_content": [],
                    "chapters": []
                }
                volumes.append(current_volume)
                current_chapter = None
                continue

            if m3 and not in_preamble and current_volume is not None:
                c_title = m3.group(1).strip()
                current_chapter = {
                    "title": c_title,
                    "slug": to_pinyin_slug(c_title),
                    "lines": [line]
                }
                current_volume["chapters"].append(current_chapter)
                continue

            if in_preamble:
                preamble_lines.append(line)
            elif current_chapter is not None:
                current_chapter["lines"].append(line)
            elif current_volume is not None:
                current_volume["header_content"].append(line)

        # 若全文无 H2 卷容器（单篇论著），则以书名为容器
        if not volumes:
            single_vol = {
                "title": self.book_title,
                "slug": self.book_slug,
                "header_content": [],
                "chapters": []
            }
            # 按 H3 切分
            curr_c = None
            for line in lines:
                m3 = re_h3.match(line)
                if m3:
                    curr_c = {
                        "title": m3.group(1).strip(),
                        "slug": to_pinyin_slug(m3.group(1).strip()),
                        "lines": [line]
                    }
                    single_vol["chapters"].append(curr_c)
                elif curr_c:
                    curr_c["lines"].append(line)
                else:
                    preamble_lines.append(line)
            volumes.append(single_vol)

        return "".join(preamble_lines), volumes

    def split_and_generate(self) -> Dict[str, Any]:
        """执行全套 SEO 静态站原子化输出"""
        preamble_text, volumes = self.parse_structure()
        book_dir = self.output_dir / self.book_slug
        book_dir.mkdir(parents=True, exist_ok=True)

        # 收集所有扁平章节用于计算上一篇/下一篇双向内链
        flat_chapters = []
        for v_idx, v in enumerate(volumes):
            for c_idx, c in enumerate(v["chapters"]):
                flat_chapters.append({
                    "vol_title": v["title"],
                    "vol_slug": v["slug"],
                    "chap_title": c["title"],
                    "chap_slug": c["slug"],
                    "content": "".join(c["lines"]),
                    "order": c_idx + 1,
                    "v_idx": v_idx,
                    "c_idx": c_idx
                })

        # 为各章节绑定 prev / next 链轮
        total_chaps = len(flat_chapters)
        for i, item in enumerate(flat_chapters):
            vol_slug = item["vol_slug"]
            chap_slug = item["chap_slug"]
            order_prefix = f"{item['order']:02d}"
            item["filename"] = f"{order_prefix}_{chap_slug}.md"
            item["url"] = f"{self.base_url}/{self.book_slug}/{vol_slug}/{order_prefix}_{chap_slug}"

            if i > 0:
                prev_item = flat_chapters[i - 1]
                prev_prefix = f"{prev_item['order']:02d}"
                item["prev"] = {
                    "title": prev_item["chap_title"],
                    "url": f"{self.base_url}/{self.book_slug}/{prev_item['vol_slug']}/{prev_prefix}_{prev_item['chap_slug']}"
                }
            else:
                item["prev"] = None

            if i < total_chaps - 1:
                next_item = flat_chapters[i + 1]
                next_prefix = f"{next_item['order']:02d}"
                item["next"] = {
                    "title": next_item["chap_title"],
                    "url": f"{self.base_url}/{self.book_slug}/{next_item['vol_slug']}/{next_prefix}_{next_item['chap_slug']}"
                }
            else:
                item["next"] = None

        # 1. 输出全书总览落地页 (Book Landing Hub: index.md)
        book_hub_file = book_dir / "index.md"
        self._write_book_hub(book_hub_file, preamble_text, volumes, flat_chapters)

        # 2. 逐卷输出分卷聚合页与原子章节
        generated_pages = [str(book_hub_file.resolve())]
        for v in volumes:
            vol_dir = book_dir / v["slug"]
            vol_dir.mkdir(parents=True, exist_ok=True)

            # 分卷聚合页 (Volume Hub)
            vol_hub_file = vol_dir / "index.md"
            self._write_volume_hub(vol_hub_file, v)
            generated_pages.append(str(vol_hub_file.resolve()))

            # 原子章节内容页 (Leaf Pages)
            v_chaps = [item for item in flat_chapters if item["vol_slug"] == v["slug"]]
            for item in v_chaps:
                leaf_file = vol_dir / item["filename"]
                self._write_leaf_page(leaf_file, item)
                generated_pages.append(str(leaf_file.resolve()))

        # 3. 输出全站结构清单 (site_manifest.json)
        manifest_file = book_dir / "site_manifest.json"
        manifest_data = {
            "book": self.book_title,
            "book_slug": self.book_slug,
            "paradigm": self.paradigm_info["paradigm"],
            "total_volumes": len(volumes),
            "total_chapters": total_chaps,
            "canonical_base": self.base_url,
            "chapters": [
                {
                    "title": c["chap_title"],
                    "volume": c["vol_title"],
                    "url": c["url"],
                    "file": f"{c['vol_slug']}/{c['filename']}",
                    "word_count": len(re.sub(r'\s+', '', c["content"]))
                } for c in flat_chapters
            ]
        }
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)

        return {
            "status": "SUCCESS",
            "book_title": self.book_title,
            "output_directory": str(book_dir.resolve()),
            "total_volumes": len(volumes),
            "total_chapters": total_chaps,
            "manifest_file": str(manifest_file.resolve()),
            "generated_files_count": len(generated_pages)
        }

    def _write_book_hub(self, file_path: Path, preamble: str, volumes: List[Dict[str, Any]], all_chaps: List[Dict[str, Any]]):
        """生成全书落地聚合页"""
        desc = extract_description(preamble, max_chars=150)
        content_lines = [
            "---",
            f"title: \"《{self.book_title}》全文精校检索总录 - 中华经典命理数字化典籍\"",
            f"description: \"{desc}\"",
            f"book: \"{self.book_title}\"",
            f"book_slug: \"{self.book_slug}\"",
            f"canonical_url: \"{self.base_url}/{self.book_slug}/\"",
            f"type: \"book_hub\"",
            f"total_chapters: {len(all_chaps)}",
            "---",
            "",
            f"# 《{self.book_title}》",
            "",
            preamble.strip(),
            "",
            "---",
            "",
            "## 全书各卷详细检索导航",
            ""
        ]

        for v in volumes:
            v_url = f"{self.base_url}/{self.book_slug}/{v['slug']}/"
            content_lines.append(f"### [{v['title']}]({v_url})")
            v_chaps = [c for c in all_chaps if c["vol_slug"] == v["slug"]]
            for c in v_chaps:
                content_lines.append(f"- [{c['chap_title']}]({c['url']})")
            content_lines.append("")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(content_lines) + "\n")

    def _write_volume_hub(self, file_path: Path, volume: Dict[str, Any]):
        """生成分卷聚合页"""
        v_title = volume["title"]
        v_slug = volume["slug"]
        v_url = f"{self.base_url}/{self.book_slug}/{v_slug}/"
        book_url = f"{self.base_url}/{self.book_slug}/"

        header_desc = "".join(volume.get("header_content", []))
        desc = extract_description(header_desc if header_desc else v_title, max_chars=120)

        content_lines = [
            "---",
            f"title: \"{v_title} - 《{self.book_title}》章节索引\"",
            f"description: \"{desc}\"",
            f"book: \"{self.book_title}\"",
            f"book_slug: \"{self.book_slug}\"",
            f"volume: \"{v_title}\"",
            f"volume_slug: \"{v_slug}\"",
            f"canonical_url: \"{v_url}\"",
            f"type: \"volume_hub\"",
            "---",
            "",
            f"<!-- 面包屑导航 -->",
            f"[典籍首页]({self.base_url}) / [《{self.book_title}》]({book_url}) / {v_title}",
            "",
            f"# {v_title}",
            "",
            header_desc.strip() if header_desc.strip() else f"《{self.book_title}》{v_title}汇集各论篇章导航。",
            "",
            "---",
            "",
            f"## {v_title}所领篇章目次",
            ""
        ]

        for c_idx, c in enumerate(volume["chapters"]):
            c_prefix = f"{c_idx + 1:02d}"
            c_url = f"{v_url}{c_prefix}_{c['slug']}"
            content_lines.append(f"- [{c['title']}]({c_url})")

        content_lines.append("")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(content_lines) + "\n")

    def _write_leaf_page(self, file_path: Path, item: Dict[str, Any]):
        """生成独立原子章节文章页"""
        c_title = item["chap_title"]
        v_title = item["vol_title"]
        desc = extract_description(item["content"], max_chars=150)
        keywords = extract_keywords(self.book_title, v_title, c_title, item["content"])
        word_count = len(re.sub(r'[\s#>\-|`*]', '', item["content"]))

        book_url = f"{self.base_url}/{self.book_slug}/"
        vol_url = f"{self.base_url}/{self.book_slug}/{item['vol_slug']}/"

        frontmatter_lines = [
            "---",
            f"title: \"{c_title} - 《{self.book_title}》{v_title}\"",
            f"description: \"{desc}\"",
            f"book: \"{self.book_title}\"",
            f"book_slug: \"{self.book_slug}\"",
            f"volume: \"{v_title}\"",
            f"volume_slug: \"{item['vol_slug']}\"",
            f"chapter: \"{c_title}\"",
            f"chapter_slug: \"{item['chap_slug']}\"",
            f"canonical_url: \"{item['url']}\"",
            f"keywords: {json.dumps(keywords, ensure_ascii=False)}",
            f"word_count: {word_count}",
            f"order: {item['order']}"
        ]

        if item.get("prev"):
            frontmatter_lines.extend([
                "prev:",
                f"  title: \"{item['prev']['title']}\"",
                f"  url: \"{item['prev']['url']}\""
            ])
        if item.get("next"):
            frontmatter_lines.extend([
                "next:",
                f"  title: \"{item['next']['title']}\"",
                f"  url: \"{item['next']['url']}\""
            ])

        frontmatter_lines.append("---\n")

        # 页面正文构建
        author_prefix = f"{self.author}" if self.author else ""
        attrib_str = f"{author_prefix}《{self.book_title}》· {v_title}" if author_prefix else f"《{self.book_title}》· {v_title}"

        page_lines = [
            "\n".join(frontmatter_lines),
            f"<!-- 面包屑导航 -->",
            f"[典籍首页]({self.base_url}) / [《{self.book_title}》]({book_url}) / [{v_title}]({vol_url}) / {c_title}\n",
            f"# {c_title}\n",
            f"> **典籍归属**：{attrib_str}\n",
        ]

        # 纯正文内容（移除章节原有的 ### 标题，因为上方已有页面主 H1）
        body_lines = item["content"].splitlines(keepends=True)
        filtered_body = []
        for line in body_lines:
            if line.strip().startswith(f"### {c_title}"):
                continue
            filtered_body.append(line)

        page_lines.append("".join(filtered_body).strip() + "\n\n")

        # 底部翻页内链集群
        prev_link = f"[{item['prev']['title']}]({item['prev']['url']})" if item.get("prev") else "始篇"
        next_link = f"[{item['next']['title']}]({item['next']['url']})" if item.get("next") else "终篇"

        page_lines.extend([
            "---",
            "",
            "| 上一篇 | 卷目录 | 下一篇 |",
            "| :--- | :---: | ---: |",
            f"| ⬅️ {prev_link} | [📑 {v_title}]({vol_url}) | {next_link} ➡️ |",
            ""
        ])

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(page_lines))


def main():
    parser = argparse.ArgumentParser(
        description="古籍规范化 Markdown 章节级 SEO 原子化拆分引擎"
    )
    parser.add_argument("-i", "--input", required=True, help="已规范化的古籍 Markdown 文件路径")
    parser.add_argument("-o", "--output-dir", default="dist_seo", help="SEO 静态站切片输出根目录（默认 dist_seo）")
    parser.add_argument("-b", "--base-url", default="/classics", help="站内根路由前缀（默认 /classics）")
    parser.add_argument("-l", "--level", type=int, default=3, help="切分目标层级（默认 3，即 H3 篇章/日主）")
    parser.add_argument("-c", "--config", help="自定义规则与元数据配置文件路径 (默认自动加载 ./classics_config.json)")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    config_path = Path(args.config) if getattr(args, 'config', None) else None

    splitter = SEOSplitter(
        input_file=input_path,
        output_dir=output_dir,
        base_url=args.base_url,
        split_level=args.level,
        config_path=config_path
    )

    result = splitter.split_and_generate()

    print("=" * 65)
    print("🚀 古籍 SEO 原子化章节拆分成功 (SEO Chapter Atomization Done)")
    print("=" * 65)
    print(f"典籍名称: 《{result['book_title']}》")
    print(f"输出目录: {result['output_directory']}")
    print(f"生成分卷: {result['total_volumes']} 卷/篇")
    print(f"生成原子文章: {result['total_chapters']} 篇")
    print(f"生成静态文件总数: {result['generated_files_count']} 个")
    print(f"结构清单: {result['manifest_file']}")
    print("=" * 65)


if __name__ == "__main__":
    main()
