"""token_estimator 单元测试（US-020）。"""

import math

from app.processor.token_estimator import (
    estimate_tokens_for_text,
    estimate_tokens_for_tweet,
    estimate_total_tokens,
)


class TestEstimateTokensForText:
    """文本 token 估算测试。"""

    def test_pure_chinese(self) -> None:
        """纯中文：每字 1/1.5 ≈ 0.667 token。"""
        text = "你好世界"  # 4 字
        result = estimate_tokens_for_text(text)
        expected = math.ceil(4 / 1.5)  # 2.667 → 3
        assert result == expected

    def test_pure_english(self) -> None:
        """纯英文：每字符 1/4 = 0.25 token。"""
        text = "hello world"  # 11 字符（含空格）
        result = estimate_tokens_for_text(text)
        expected = math.ceil(11 / 4)  # 2.75 → 3
        assert result == expected

    def test_mixed_text(self) -> None:
        """中英混合：中文按 1/1.5，英文按 1/4。"""
        text = "AI是人工智能"  # AI(2英文) + 是人工智能(4中文)
        result = estimate_tokens_for_text(text)
        cn_tokens = 4 / 1.5  # 2.667
        en_tokens = 2 / 4  # 0.5
        expected = math.ceil(cn_tokens + en_tokens)  # 3.167 → 4
        assert result == expected

    def test_empty_text(self) -> None:
        """空字符串 → 0。"""
        assert estimate_tokens_for_text("") == 0

    def test_whitespace_only(self) -> None:
        """纯空白字符按英文计算。"""
        text = "   "  # 3 个空格
        result = estimate_tokens_for_text(text)
        expected = math.ceil(3 / 4)  # 0.75 → 1
        assert result == expected

    def test_long_chinese_text(self) -> None:
        """长中文文本。"""
        text = "这是一段较长的中文文本用于测试估算准确性"  # 20 字
        result = estimate_tokens_for_text(text)
        expected = math.ceil(20 / 1.5)  # 13.33 → 14
        assert result == expected

    def test_punctuation_as_non_cjk(self) -> None:
        """标点符号按非 CJK 计算。"""
        text = "Hello, World!"  # 13 字符
        result = estimate_tokens_for_text(text)
        expected = math.ceil(13 / 4)  # 3.25 → 4
        assert result == expected


class TestEstimateTokensForTweet:
    """序列化推文 token 估算。"""

    def test_basic_tweet(self) -> None:
        """基本序列化推文的 token 估算。"""
        tweet = {
            "id": "t1",
            "author": "Test User",
            "text": "AI breakthrough",
            "likes": 100,
        }
        result = estimate_tokens_for_tweet(tweet)
        assert result > 0

    def test_tweet_with_chinese(self) -> None:
        """含中文内容的推文。"""
        tweet_cn: dict[str, object] = {"text": "人工智能突破"}
        tweet_en: dict[str, object] = {"text": "AI breakthrough"}
        cn_tokens = estimate_tokens_for_tweet(tweet_cn)
        en_tokens = estimate_tokens_for_tweet(tweet_en)
        # 中文文本相同语义通常更少字符但更多 token 密度
        assert cn_tokens > 0
        assert en_tokens > 0


class TestEstimateTotalTokens:
    """推文列表总 token 估算（含 Prompt 开销）。"""

    def test_includes_prompt_overhead(self) -> None:
        """总 token 应包含 Prompt 模板开销。"""
        tweets: list[dict[str, object]] = [{"id": "t1", "text": "test"}]
        total = estimate_total_tokens(tweets)
        single = estimate_tokens_for_tweet(tweets[0])
        # 总量应大于单条（因为有 Prompt 开销 + JSON 数组格式开销）
        assert total > single

    def test_empty_list(self) -> None:
        """空列表只有 Prompt 开销。"""
        total = estimate_total_tokens([])
        assert total > 0  # Prompt 开销

    def test_multiple_tweets(self) -> None:
        """多条推文的总 token。"""
        tweets: list[dict[str, object]] = [
            {"id": "t1", "text": "first tweet"},
            {"id": "t2", "text": "second tweet"},
        ]
        total = estimate_total_tokens(tweets)
        single1 = estimate_tokens_for_tweet(tweets[0])
        single2 = estimate_tokens_for_tweet(tweets[1])
        # 总量应大于两条之和（加了 Prompt 开销和数组格式开销）
        assert total > single1 + single2
