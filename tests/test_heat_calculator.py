"""热度分计算测试（US-022 + US-049）。"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.processor.heat_calculator import (
    calculate_base_score,
    calculate_heat_score,
    calculate_hours_since_post,
    get_reference_time,
    normalize_scores,
)

UTC = ZoneInfo("UTC")
BEIJING = ZoneInfo("Asia/Shanghai")


class TestGetReferenceTime:
    """参考时间点：digest_date 当日北京时间 06:00 → UTC。"""

    def test_reference_time(self):
        ref = get_reference_time(date(2026, 3, 18))
        # 北京 06:00 = UTC 22:00（前一天）
        expected = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        assert ref == expected

    def test_reference_time_dst_safe(self):
        """中国无 DST，但验证时区转换正确。"""
        ref = get_reference_time(date(2026, 7, 15))
        expected = datetime(2026, 7, 14, 22, 0, 0, tzinfo=UTC)
        assert ref == expected


class TestCalculateHoursSincePost:
    """计算推文发布到参考时间点的小时数。"""

    def test_exact_hours(self):
        ref = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        tweet_time = datetime(2026, 3, 17, 20, 0, 0, tzinfo=UTC)
        assert calculate_hours_since_post(tweet_time, ref) == 2.0

    def test_fractional_hours(self):
        ref = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        tweet_time = datetime(2026, 3, 17, 20, 30, 0, tzinfo=UTC)
        assert calculate_hours_since_post(tweet_time, ref) == 1.5

    def test_zero_hours(self):
        ref = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        assert calculate_hours_since_post(ref, ref) == 0.0


class TestCalculateBaseScore:
    """base_score = (likes*1 + retweets*3 + replies*2) * author_weight * exp(-0.05*hours)。"""

    def test_basic_calculation(self):
        # engagement = 150*1 + 30*3 + 12*2 = 150 + 90 + 24 = 264
        # base_score = 264 * 1.0 * exp(-0.05 * 0) = 264 * 1 = 264
        score = calculate_base_score(likes=150, retweets=30, replies=12, author_weight=1.0, hours=0)
        assert score == 264.0

    def test_author_weight(self):
        score_w1 = calculate_base_score(
            likes=100, retweets=10, replies=5, author_weight=1.0, hours=0
        )
        score_w2 = calculate_base_score(
            likes=100, retweets=10, replies=5, author_weight=2.0, hours=0
        )
        assert score_w2 == score_w1 * 2

    def test_time_decay(self):
        import math

        score_0h = calculate_base_score(
            likes=100, retweets=10, replies=5, author_weight=1.0, hours=0
        )
        score_10h = calculate_base_score(
            likes=100, retweets=10, replies=5, author_weight=1.0, hours=10
        )
        # exp(-0.05 * 10) = exp(-0.5) ≈ 0.6065
        expected_ratio = math.exp(-0.5)
        assert abs(score_10h / score_0h - expected_ratio) < 0.0001

    def test_zero_engagement(self):
        score = calculate_base_score(likes=0, retweets=0, replies=0, author_weight=1.5, hours=5)
        assert score == 0.0

    # I-46: 负值输入边界测试
    def test_negative_likes(self):
        """负 likes 不应导致异常（数据异常兜底）。"""
        score = calculate_base_score(likes=-10, retweets=5, replies=2, author_weight=1.0, hours=0)
        # engagement = -10 + 15 + 4 = 9，仍可计算
        assert isinstance(score, float)

    def test_negative_retweets(self):
        """负 retweets 不应导致异常。"""
        score = calculate_base_score(likes=10, retweets=-5, replies=2, author_weight=1.0, hours=0)
        assert isinstance(score, float)

    # I-46: 极大值输入边界测试
    def test_extreme_large_engagement(self):
        """极大互动量不应溢出。"""
        score = calculate_base_score(
            likes=10_000_000, retweets=5_000_000, replies=2_000_000, author_weight=3.0, hours=0
        )
        assert score > 0
        assert isinstance(score, float)

    def test_extreme_large_hours(self):
        """极大时间衰减应趋近于零但不为负。"""
        score = calculate_base_score(
            likes=1000, retweets=100, replies=50, author_weight=1.0, hours=10000
        )
        assert score >= 0

    def test_large_hours_decay(self):
        score = calculate_base_score(
            likes=100, retweets=10, replies=5, author_weight=1.0, hours=100
        )
        # exp(-0.05 * 100) = exp(-5) ≈ 0.0067 → 非常小但不为零
        assert score > 0
        assert score < 1


class TestNormalizeScores:
    """min-max 归一化到 0-100。"""

    def test_multiple_scores(self):
        scores = [0.0, 50.0, 100.0]
        result = normalize_scores(scores)
        assert result == [0.0, 50.0, 100.0]

    def test_single_score(self):
        result = normalize_scores([42.0])
        assert result == [50.0]

    def test_all_same(self):
        result = normalize_scores([10.0, 10.0, 10.0])
        assert result == [50.0, 50.0, 50.0]

    def test_empty_list(self):
        result = normalize_scores([])
        assert result == []

    def test_two_scores(self):
        result = normalize_scores([20.0, 80.0])
        assert result[0] == 0.0
        assert result[1] == 100.0

    def test_varied_scores(self):
        scores = [10.0, 30.0, 50.0, 70.0, 90.0]
        result = normalize_scores(scores)
        # min=10, max=90, range=80
        # (10-10)/80*100 = 0, (30-10)/80*100 = 25, (50-10)/80*100 = 50, etc.
        assert result[0] == 0.0
        assert result[1] == 25.0
        assert result[2] == 50.0
        assert result[3] == 75.0
        assert result[4] == 100.0


class TestCalculateHeatScore:
    """heat_score = normalized_base * 0.7 + ai_importance * 0.3。"""

    def test_basic(self):
        score = calculate_heat_score(normalized_base=80.0, ai_importance=60.0)
        # 80 * 0.7 + 60 * 0.3 = 56 + 18 = 74.0
        assert score == 74.0

    def test_precision(self):
        score = calculate_heat_score(normalized_base=33.33, ai_importance=66.67)
        # 33.33 * 0.7 + 66.67 * 0.3 = 23.331 + 20.001 = 43.332
        assert score == 43.33

    def test_max_scores(self):
        score = calculate_heat_score(normalized_base=100.0, ai_importance=100.0)
        assert score == 100.0

    def test_zero_scores(self):
        score = calculate_heat_score(normalized_base=0.0, ai_importance=0.0)
        assert score == 0.0


class TestIntegration:
    """端到端集成：多条推文 → base_score → normalize → heat_score。"""

    def test_multi_tweet_flow(self):
        """多条推文正常流程。"""
        ref = get_reference_time(date(2026, 3, 18))

        # 推文 A: 高互动，2 小时前
        tweet_a_time = datetime(2026, 3, 17, 20, 0, 0, tzinfo=UTC)
        hours_a = calculate_hours_since_post(tweet_a_time, ref)
        base_a = calculate_base_score(
            likes=500, retweets=100, replies=50, author_weight=1.5, hours=hours_a
        )

        # 推文 B: 低互动，10 小时前
        tweet_b_time = datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC)
        hours_b = calculate_hours_since_post(tweet_b_time, ref)
        base_b = calculate_base_score(
            likes=10, retweets=2, replies=1, author_weight=1.0, hours=hours_b
        )

        # 推文 C: 中等互动，5 小时前
        tweet_c_time = datetime(2026, 3, 17, 17, 0, 0, tzinfo=UTC)
        hours_c = calculate_hours_since_post(tweet_c_time, ref)
        base_c = calculate_base_score(
            likes=100, retweets=20, replies=10, author_weight=1.2, hours=hours_c
        )

        # 归一化
        normalized = normalize_scores([base_a, base_b, base_c])
        assert normalized[0] == 100.0  # A 最高
        assert normalized[1] == 0.0  # B 最低
        assert 0 < normalized[2] < 100  # C 中间

        # heat_score
        heat_a = calculate_heat_score(normalized[0], ai_importance=85)
        heat_b = calculate_heat_score(normalized[1], ai_importance=30)
        heat_c = calculate_heat_score(normalized[2], ai_importance=70)

        assert heat_a > heat_c > heat_b

    def test_topic_avg_flow(self):
        """聚合话题：AVG → 一起归一化。"""
        # 话题成员推文 base_score
        topic_member_scores = [100.0, 200.0, 150.0]
        topic_avg = sum(topic_member_scores) / len(topic_member_scores)  # 150.0

        # 单条推文 base_score
        single_scores = [50.0, 300.0]

        # 放在一起归一化
        all_scores = single_scores + [topic_avg]  # [50, 300, 150]
        normalized = normalize_scores(all_scores)

        # min=50, max=300, range=250
        assert normalized[0] == 0.0  # 50 → 0
        assert normalized[1] == 100.0  # 300 → 100
        assert normalized[2] == 40.0  # (150-50)/250*100 = 40
