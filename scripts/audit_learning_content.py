#!/usr/bin/env python3
"""Fail when the independent edition leaks source artifacts or loses structure."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEARNING = ROOT / "learning"
SOURCE = ROOT / "content"
BANNED = (
    "97kt",
    "xingkeit",
    "优质IT",
    "防断更",
    "面试",
    "PDF 原文",
    "课程图",
    "邓明",
    "后端工程师的高阶面经",
    "offer",
    "极客时间",
    "训练营",
    "欢迎你的加入",
)


def main() -> None:
    files = sorted(LEARNING.glob("*.md"))
    source_files = sorted(SOURCE.glob("*.md"))
    errors: list[str] = []

    if len(files) != 50:
        errors.append(f"课程数量异常 learning={len(files)} source={len(source_files)}")

    learning_ids = {path.stem for path in files}
    source_ids = {path.stem for path in source_files}
    if source_ids and learning_ids != source_ids:
        errors.append(f"课程 ID 不一致 missing={sorted(source_ids-learning_ids)} extra={sorted(learning_ids-source_ids)}")

    titles: set[str] = set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
        title = title_match.group(1) if title_match else ""
        checks = {
            "正文不足 2200 字符": len(text) >= 2200,
            "缺少唯一 H1": len(re.findall(r"^# ", text, re.MULTILINE)) == 1,
            "缺少机制精讲": "## 本节精讲" in text,
            "缺少带数字推演": "### 一次带数字的完整推演" in text,
            "缺少边界": "## 误区与失效边界" in text,
            "缺少讲解链": "## 按讲解顺序重建知识链" in text,
            "缺少 Mermaid": "```mermaid" in text,
            "缺少自测": "## 自我检查" in text and "<details>" in text,
            "缺少来源稿链接": f"../content/{path.name}" in text,
            "引用了原始图片": "./assets/" not in text and not re.search(r"!\[[^]]*]\(", text),
        }
        for label, passed in checks.items():
            if not passed:
                errors.append(f"{path.name}: {label}")
        for phrase in BANNED:
            if phrase.casefold() in text.casefold():
                errors.append(f"{path.name}: 含禁用来源痕迹 {phrase}")
        if re.search(r"[\ue000-\uf8ff]", text):
            errors.append(f"{path.name}: 含 PDF 私有区图标字符")
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
            errors.append(f"{path.name}: 含不可见控制字符")
        if title in titles:
            errors.append(f"{path.name}: 标题重复 {title}")
        titles.add(title)

    if errors:
        raise SystemExit("学习稿审计失败：\n- " + "\n- ".join(errors))
    print(f"learning audit passed: {len(files)} original notes, no watermark/image leak")


if __name__ == "__main__":
    main()
