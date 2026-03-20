"""Markdown 渲染器测试 — US-025 + US-052。

纯函数测试，不需要 DB。构造 ORM 对象用正常构造函数。
"""

import json
from datetime import date, datetime

from app.digest.renderer import render_markdown
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem

# ── 辅助函数 ──


def _make_digest(
    digest_date: date = date(2026, 3, 20),
    summary: str | None = "今日 AI 焦点：GPT-5 发布引发行业震动。",
) -> DailyDigest:
    """构造测试用 DailyDigest。"""
    return DailyDigest(
        id=1,
        digest_date=digest_date,
        version=1,
        is_current=True,
        status="draft",
        summary=summary,
        item_count=0,
    )


def _make_tweet_item(
    *,
    item_id: int = 1,
    display_order: int = 1,
    title: str = "GPT-5 正式发布",
    translation: str = "OpenAI 今日发布了 GPT-5 模型。",
    comment: str = "这是 AI 领域的重大突破。",
    heat_score: float = 90.0,
    author_name: str = "Sam Altman",
    author_handle: str = "sama",
    tweet_url: str = "https://x.com/sama/status/123",
    tweet_time: datetime = datetime(2026, 3, 19, 10, 0, 0),
    is_pinned: bool = False,
    is_excluded: bool = False,
) -> DigestItem:
    """构造 tweet 类型 DigestItem。"""
    return DigestItem(
        id=item_id,
        digest_id=1,
        item_type="tweet",
        item_ref_id=item_id * 10,
        display_order=display_order,
        is_pinned=is_pinned,
        is_excluded=is_excluded,
        snapshot_title=title,
        snapshot_translation=translation,
        snapshot_comment=comment,
        snapshot_heat_score=heat_score,
        snapshot_author_name=author_name,
        snapshot_author_handle=author_handle,
        snapshot_tweet_url=tweet_url,
        snapshot_tweet_time=tweet_time,
    )


def _make_aggregated_item(
    *,
    item_id: int = 10,
    display_order: int = 1,
    title: str = "GPT-5 多方讨论",
    summary: str = "业界多位大V对 GPT-5 发表了看法。",
    perspectives_list: list[dict[str, str]] | None = None,
    comment: str = "这场讨论反映了行业对 GPT-5 的高度关注。",
    heat_score: float = 85.0,
    source_tweets_list: list[dict[str, str]] | None = None,
    is_pinned: bool = False,
    is_excluded: bool = False,
) -> DigestItem:
    """构造 aggregated topic 类型 DigestItem。"""
    if perspectives_list is None:
        perspectives_list = [
            {"author": "Sam Altman", "handle": "sama", "viewpoint": "GPT-5 是里程碑。"},
            {"author": "Yann LeCun", "handle": "ylecun", "viewpoint": "仍需更多评测。"},
        ]
    if source_tweets_list is None:
        source_tweets_list = [
            {"handle": "sama", "tweet_url": "https://x.com/sama/status/100"},
            {"handle": "ylecun", "tweet_url": "https://x.com/ylecun/status/101"},
        ]
    return DigestItem(
        id=item_id,
        digest_id=1,
        item_type="topic",
        item_ref_id=item_id * 10,
        display_order=display_order,
        is_pinned=is_pinned,
        is_excluded=is_excluded,
        snapshot_title=title,
        snapshot_summary=summary,
        snapshot_comment=comment,
        snapshot_perspectives=json.dumps(perspectives_list, ensure_ascii=False),
        snapshot_heat_score=heat_score,
        snapshot_source_tweets=json.dumps(source_tweets_list, ensure_ascii=False),
        snapshot_topic_type="aggregated",
    )


def _make_thread_item(
    *,
    item_id: int = 20,
    display_order: int = 1,
    title: str = "LLM 训练新范式",
    translation: str = "这是一个完整的 Thread 翻译内容。",
    comment: str = "Thread 深入探讨了训练方法的革新。",
    heat_score: float = 80.0,
    author_name: str = "Andrej Karpathy",
    author_handle: str = "karpathy",
    tweet_url: str = "https://x.com/karpathy/status/200",
    is_pinned: bool = False,
    is_excluded: bool = False,
) -> DigestItem:
    """构造 thread topic 类型 DigestItem。"""
    return DigestItem(
        id=item_id,
        digest_id=1,
        item_type="topic",
        item_ref_id=item_id * 10,
        display_order=display_order,
        is_pinned=is_pinned,
        is_excluded=is_excluded,
        snapshot_title=title,
        snapshot_translation=translation,
        snapshot_comment=comment,
        snapshot_heat_score=heat_score,
        snapshot_author_name=author_name,
        snapshot_author_handle=author_handle,
        snapshot_tweet_url=tweet_url,
        snapshot_topic_type="thread",
    )


# ── 测试 ──


class TestRenderHeader:
    """标题和底部固定文案。"""

    def test_header_contains_date(self) -> None:
        digest = _make_digest(digest_date=date(2026, 3, 20))
        result = render_markdown(digest, [])
        assert "3月20日" in result

    def test_header_format(self) -> None:
        digest = _make_digest(digest_date=date(2026, 12, 5))
        result = render_markdown(digest, [])
        assert "# 🔥 智曦 · 12月5日" in result

    def test_footer_present(self) -> None:
        digest = _make_digest()
        result = render_markdown(digest, [])
        assert "智曦 - 每天一束AI之光" in result
        assert "点击关注" in result


class TestRenderSummary:
    """导读摘要。"""

    def test_summary_rendered(self) -> None:
        digest = _make_digest(summary="今日焦点：GPT-5 发布。")
        result = render_markdown(digest, [])
        assert "今日焦点：GPT-5 发布。" in result

    def test_no_summary(self) -> None:
        digest = _make_digest(summary=None)
        result = render_markdown(digest, [])
        # 应该不报错，正常渲染
        assert "智曦" in result


class TestRenderTweet:
    """单条推文渲染。"""

    def test_basic_tweet(self) -> None:
        digest = _make_digest()
        item = _make_tweet_item()
        result = render_markdown(digest, [item])
        assert "GPT-5 正式发布" in result
        assert "OpenAI 今日发布了 GPT-5 模型。" in result
        assert "这是 AI 领域的重大突破。" in result
        assert "https://x.com/sama/status/123" in result
        assert "Sam Altman" in result
        assert "@sama" in result

    def test_tweet_has_rank(self) -> None:
        digest = _make_digest()
        item = _make_tweet_item()
        result = render_markdown(digest, [item])
        assert "TOP 1" in result


class TestRenderAggregated:
    """聚合话题渲染。"""

    def test_aggregated_contains_summary(self) -> None:
        digest = _make_digest()
        item = _make_aggregated_item()
        result = render_markdown(digest, [item])
        assert "业界多位大V对 GPT-5 发表了看法。" in result

    def test_aggregated_contains_perspectives(self) -> None:
        digest = _make_digest()
        item = _make_aggregated_item()
        result = render_markdown(digest, [item])
        assert "Sam Altman" in result
        assert "GPT-5 是里程碑。" in result
        assert "Yann LeCun" in result
        assert "仍需更多评测。" in result

    def test_aggregated_contains_source_links(self) -> None:
        digest = _make_digest()
        item = _make_aggregated_item()
        result = render_markdown(digest, [item])
        assert "https://x.com/sama/status/100" in result
        assert "https://x.com/ylecun/status/101" in result

    def test_aggregated_shows_hot_topic_label(self) -> None:
        digest = _make_digest()
        item = _make_aggregated_item()
        result = render_markdown(digest, [item])
        assert "热门话题" in result


class TestRenderThread:
    """Thread 渲染（使用单条模板）。"""

    def test_thread_uses_single_template(self) -> None:
        digest = _make_digest()
        item = _make_thread_item()
        result = render_markdown(digest, [item])
        assert "LLM 训练新范式" in result
        assert "这是一个完整的 Thread 翻译内容。" in result
        assert "Thread 深入探讨了训练方法的革新。" in result
        assert "Andrej Karpathy" in result
        assert "@karpathy" in result
        assert "https://x.com/karpathy/status/200" in result


class TestExcludedItems:
    """被剔除的条目不渲染。"""

    def test_excluded_not_in_output(self) -> None:
        digest = _make_digest()
        items = [
            _make_tweet_item(item_id=1, display_order=1, title="可见条目"),
            _make_tweet_item(item_id=2, display_order=2, title="被剔除条目", is_excluded=True),
        ]
        result = render_markdown(digest, items)
        assert "可见条目" in result
        assert "被剔除条目" not in result


class TestTopNLimit:
    """top_n 限制渲染条目数。"""

    def test_top_n_limits_items(self) -> None:
        digest = _make_digest()
        items = [
            _make_tweet_item(item_id=i, display_order=i, title=f"条目{i}") for i in range(1, 6)
        ]
        result = render_markdown(digest, items, top_n=3)
        assert "条目1" in result
        assert "条目2" in result
        assert "条目3" in result
        assert "条目4" not in result
        assert "条目5" not in result

    def test_excluded_not_counted_in_top_n(self) -> None:
        """excluded 先过滤，再取 top_n。"""
        digest = _make_digest()
        items = [
            _make_tweet_item(item_id=1, display_order=1, title="第一条"),
            _make_tweet_item(item_id=2, display_order=2, title="被剔除", is_excluded=True),
            _make_tweet_item(item_id=3, display_order=3, title="第三条"),
            _make_tweet_item(item_id=4, display_order=4, title="第四条"),
        ]
        result = render_markdown(digest, items, top_n=3)
        assert "第一条" in result
        assert "第三条" in result
        assert "第四条" in result
        assert "被剔除" not in result


class TestHeatRanking:
    """热度榜。"""

    def test_ranking_lists_titles(self) -> None:
        digest = _make_digest()
        items = [
            _make_tweet_item(item_id=1, display_order=1, title="头条新闻", heat_score=90.0),
            _make_tweet_item(item_id=2, display_order=2, title="次要新闻", heat_score=70.0),
        ]
        result = render_markdown(digest, items)
        assert "今日热度榜" in result
        assert "头条新闻" in result
        assert "次要新闻" in result

    def test_ranking_shows_score(self) -> None:
        digest = _make_digest()
        items = [
            _make_tweet_item(item_id=1, display_order=1, heat_score=85.0),
        ]
        result = render_markdown(digest, items)
        assert "🔥85" in result


class TestEmptyItems:
    """空列表。"""

    def test_empty_renders_header_and_footer(self) -> None:
        digest = _make_digest()
        result = render_markdown(digest, [])
        assert "智曦" in result
        assert "每天一束AI之光" in result


class TestMixedContent:
    """混合内容完整渲染。"""

    def test_mixed_tweet_aggregated_thread(self) -> None:
        digest = _make_digest()
        items = [
            _make_aggregated_item(item_id=10, display_order=1, title="热门话题标题"),
            _make_tweet_item(item_id=2, display_order=2, title="单条推文标题"),
            _make_thread_item(item_id=20, display_order=3, title="Thread标题"),
        ]
        result = render_markdown(digest, items)
        # 三种类型都应出现
        assert "热门话题标题" in result
        assert "单条推文标题" in result
        assert "Thread标题" in result
        # 聚合专有元素
        assert "各方观点" in result
        assert "来源推文" in result
        # 热度榜含三条
        lines = result.split("\n")
        ranking_lines = [line for line in lines if line.strip().startswith(("1.", "2.", "3."))]
        assert len(ranking_lines) >= 3


class TestPinnedItems:
    """置顶条目。"""

    def test_pinned_first_in_output(self) -> None:
        """置顶条目应排在详细资讯最前面。"""
        digest = _make_digest()
        items = [
            _make_tweet_item(item_id=1, display_order=1, title="普通条目"),
            _make_tweet_item(item_id=2, display_order=0, title="置顶条目", is_pinned=True),
        ]
        result = render_markdown(digest, items)
        # 置顶条目应先出现
        pos_pinned = result.index("置顶条目")
        pos_normal = result.index("普通条目")
        assert pos_pinned < pos_normal
