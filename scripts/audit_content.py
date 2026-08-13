#!/usr/bin/env python3
"""Audit generated course Markdown for completeness and broken references."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"


def pdf_text_length(markdown: str) -> int:
    _, _, source = markdown.partition("## PDF 原文")
    source = re.sub(r"<!-- source-page: \d+ -->", "", source)
    source = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", source)
    source = re.sub(r"^#{1,6}\s+", "", source, flags=re.M)
    source = re.sub(r"^>\s?", "", source, flags=re.M)
    source = re.sub(r"\s+", "", source)
    return len(source)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    catalog = json.loads((CONTENT / "catalog.json").read_text(encoding="utf-8"))
    markdown_files = sorted(CONTENT.glob("*.md"))

    if len(catalog) != 50:
        errors.append(f"catalog 应为 50 课，实际 {len(catalog)}")
    if len(markdown_files) != 50:
        errors.append(f"Markdown 应为 50 篇，实际 {len(markdown_files)}")
    if sum(item["source_pages"] for item in catalog) != 941:
        errors.append("PDF 总页数不是已核验的 941 页")

    seen_ids: set[str] = set()
    total_md_chars = 0
    total_kept_chars = 0
    total_images = 0
    minimum_coverage = 1.0

    for item in catalog:
        lesson_id = item["id"]
        if lesson_id in seen_ids:
            errors.append(f"重复课程 ID: {lesson_id}")
        seen_ids.add(lesson_id)

        path = CONTENT / item["markdown"]
        if not path.exists():
            errors.append(f"缺少 Markdown: {path.name}")
            continue
        markdown = path.read_text(encoding="utf-8")
        if "## 学习前补齐（编者补充）" not in markdown:
            errors.append(f"缺少上下文补充: {path.name}")
        if "## PDF 原文" not in markdown:
            errors.append(f"缺少 PDF 原文区: {path.name}")
        if "防断更：97kt.com" in markdown:
            errors.append(f"残留重复水印: {path.name}")

        page_markers = re.findall(r"<!-- source-page: (\d+) -->", markdown)
        expected_pages = item["source_pages"]
        if len(page_markers) != expected_pages:
            errors.append(f"{path.name} 页码标记 {len(page_markers)}/{expected_pages}")
        elif page_markers != [str(number) for number in range(1, expected_pages + 1)]:
            errors.append(f"{path.name} 页码标记不连续")

        image_links = re.findall(r"!\[[^\]]*\]\(\.\/assets\/([^)]*)\)", markdown)
        if len(image_links) != item["image_count"]:
            errors.append(f"{path.name} 图片计数 {len(image_links)}/{item['image_count']}")
        for image in image_links:
            if not (CONTENT / "assets" / image).is_file():
                errors.append(f"{path.name} 引用缺失图片: {image}")

        md_chars = pdf_text_length(markdown)
        kept_chars = item.get("converted_chars_normalized", item.get("converted_chars", item["kept_chars"]))
        coverage = md_chars / kept_chars if kept_chars else 1
        minimum_coverage = min(minimum_coverage, coverage)
        total_md_chars += md_chars
        total_kept_chars += kept_chars
        total_images += len(image_links)
        # Markdown syntax accounts for the tiny remaining difference.
        if coverage < 0.985:
            errors.append(f"{path.name} 文本覆盖率过低: {coverage:.1%}")
        elif coverage < 0.995:
            warnings.append(f"{path.name} 文本覆盖率 {coverage:.1%}")

    actual_assets = {path.name for path in (CONTENT / "assets").iterdir() if path.is_file()}
    if len(actual_assets) != total_images:
        warnings.append(f"资源目录 {len(actual_assets)} 张，Markdown 共引用 {total_images} 张（可能有转换重跑遗留）")

    overall = total_md_chars / total_kept_chars if total_kept_chars else 1
    print(f"课程: {len(catalog)}")
    print(f"PDF 页: {sum(item['source_pages'] for item in catalog)}")
    print(f"Markdown: {len(markdown_files)}")
    print(f"课程图片: {total_images}")
    print(f"原文字符覆盖率: {overall:.2%}（单课最低 {minimum_coverage:.2%}）")
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"审计失败：{len(errors)} 个错误")
        return 1
    print("审计通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
