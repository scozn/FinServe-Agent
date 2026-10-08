"""
知识库加载器 — 按章节切分 Markdown 文档
"""

from __future__ import annotations

import re
from pathlib import Path


def chunk_markdown(md_path: str) -> list[dict]:
    """
    解析 Markdown 文件，按 ## 二级标题分块。

    分块策略：
    - 每个 ## 二级标题及其下方内容作为一个独立文档块
    - 标题作为 content 的一部分保留，帮助语义检索
    - 表格内容保持原格式

    返回:
        [
            {"content": "## 标题\n\n内容...", "source": "knowledge_base.md", "section": "标题"},
            ...
        ]
    """
    md_text = Path(md_path).read_text(encoding="utf-8")

    # 去掉一级标题（文件标题）和模块扉页
    # 按 ## 分割，每个 ## 是一个文档块
    # 匹配以 ## 开头（但不是 ### 或 ####）的行
    pattern = r"(?=^## [^\n]+\n)"

    parts = re.split(pattern, md_text, flags=re.MULTILINE)

    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 提取第一个二级标题作为 section 名
        match = re.match(r"^## (.+)", part)
        section_name = match.group(1).strip() if match else "未分类"

        # 跳过不在正文范围内的部分（只保留内容块）
        if len(part) < 20:
            continue

        chunks.append({
            "content": part,
            "source": Path(md_path).name,
            "section": section_name,
        })

    return chunks
