"""Markdown 渲染器 — 从 digest_items 快照生成最终 Markdown。

完全基于 snapshot 字段渲染，不回查 tweets/topics 源表。
模板规范见 docs/spec/prompts.md R.2。
"""

import json
from datetime import date

from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem


def render_markdown(
    digest: DailyDigest,
    items: list[DigestItem],
    top_n: int = 10,
) -> str:
    """渲染 Markdown 内容。

    参数:
        digest: 日报对象（取 digest_date, summary）
        items: DigestItem 列表（已含 snapshot 字段）
        top_n: 最终渲染条目数上限（先过滤 excluded，再取前 top_n）
    """
    # 1. 过滤 excluded
    active_items = [i for i in items if not i.is_excluded]

    # 2. 按 display_order 排序（pinned 自然在前，因 display_order 更小）
    active_items.sort(key=lambda i: i.display_order)

    # 3. 取前 top_n 条
    rendered_items = active_items[:top_n]

    # 4. 组装各段
    sections: list[str] = []
    sections.append(_render_header(digest.digest_date))
    sections.append(_render_summary(digest.summary))

    if rendered_items:
        sections.append(_render_ranking(rendered_items))
        sections.append(_render_details(rendered_items))

    sections.append(_render_footer())

    return "\n".join(sections)


def _render_header(digest_date: date) -> str:
    """标题行。"""
    return f"# 🔥 智曦 · {digest_date.month}月{digest_date.day}日\n"


def _render_summary(summary: str | None) -> str:
    """导读摘要。"""
    if not summary:
        return ""
    return f"{summary}\n\n---\n"


def _render_ranking(items: list[DigestItem]) -> str:
    """热度榜。"""
    lines: list[str] = ["## 🏆 今日热度榜\n"]
    for idx, item in enumerate(items, start=1):
        title = item.snapshot_title or "未命名"
        score = round(item.snapshot_heat_score)
        lines.append(f"{idx}. {title} 🔥{score}")
    lines.append("\n---\n")
    return "\n".join(lines)


def _render_details(items: list[DigestItem]) -> str:
    """详细资讯区。"""
    lines: list[str] = ["## 📰 详细资讯\n"]
    for idx, item in enumerate(items, start=1):
        lines.append(_render_detail_item(item, idx))
    return "\n".join(lines)


def _render_detail_item(item: DigestItem, rank: int) -> str:
    """渲染单条详细资讯（分发到对应模板）。"""
    if item.item_type == "topic" and item.snapshot_topic_type == "aggregated":
        return _render_aggregated(item, rank)
    # tweet 和 thread 都用单条模板
    return _render_single(item, rank)


def _render_aggregated(item: DigestItem, rank: int) -> str:
    """聚合话题模板。"""
    title = item.snapshot_title or "未命名话题"
    score = round(item.snapshot_heat_score)
    summary = item.snapshot_summary or ""
    comment = item.snapshot_comment or ""

    lines: list[str] = [
        f"### 【TOP {rank}】🔥 热门话题 · 热度{score}",
        f"📌 {title}\n",
        f"{summary}\n",
    ]

    # 各方观点
    perspectives = _parse_json_list(item.snapshot_perspectives)
    if perspectives:
        lines.append("💬 **各方观点**：")
        for p in perspectives:
            author = p.get("author", "")
            handle = p.get("handle", "")
            viewpoint = p.get("viewpoint", "")
            lines.append(f"- **{author}**（@{handle}）：{viewpoint}")
        lines.append("")

    # AI 点评
    if comment:
        lines.append(f"💡 **AI点评**：{comment}\n")

    # 来源推文
    sources = _parse_json_list(item.snapshot_source_tweets)
    if sources:
        lines.append("📎 来源推文：")
        for s in sources:
            handle = s.get("handle", "")
            url = s.get("tweet_url", "")
            lines.append(f"- @{handle}: {url}")
        lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


def _render_single(item: DigestItem, rank: int) -> str:
    """单条推文 / Thread 模板。"""
    title = item.snapshot_title or "未命名"
    score = round(item.snapshot_heat_score)
    author_name = item.snapshot_author_name or ""
    author_handle = item.snapshot_author_handle or ""
    translation = item.snapshot_translation or ""
    comment = item.snapshot_comment or ""
    tweet_url = item.snapshot_tweet_url or ""

    # 时间显示（仅 tweet 有 snapshot_tweet_time）
    time_str = ""
    if item.snapshot_tweet_time:
        t = item.snapshot_tweet_time
        time_str = f" · {t.month}月{t.day}日"

    lines: list[str] = [
        f"### 【TOP {rank}】{author_name}（@{author_handle}）{time_str} · 🔥热度{score}",
        f"📌 {title}\n",
    ]

    if translation:
        lines.append(f"🇨🇳 {translation}\n")

    if comment:
        lines.append(f"💡 **AI点评**：{comment}\n")

    if tweet_url:
        lines.append(f"🔗 [查看原文]({tweet_url})\n")

    lines.append("---\n")
    return "\n".join(lines)


def _render_footer() -> str:
    """底部固定文案。"""
    return "> 智曦 - 每天一束AI之光\n> 👆 点击关注，不错过每一条重要资讯"


def _parse_json_list(json_str: str | None) -> list[dict[str, str]]:
    """安全解析 JSON 数组字符串。"""
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return []
