"""配置模块测试。"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time


class TestGetTodayDigestDate:
    """get_today_digest_date 测试。"""

    @freeze_time("2026-03-19 10:00:00+08:00")
    def test_returns_beijing_date(self) -> None:
        from app.config import get_today_digest_date

        result = get_today_digest_date()
        assert result == date(2026, 3, 19)

    @freeze_time("2026-03-19 23:30:00+08:00")
    def test_late_night_beijing(self) -> None:
        from app.config import get_today_digest_date

        result = get_today_digest_date()
        assert result == date(2026, 3, 19)

    @freeze_time("2026-03-20 01:00:00+08:00")
    def test_early_morning_beijing(self) -> None:
        from app.config import get_today_digest_date

        result = get_today_digest_date()
        assert result == date(2026, 3, 20)


class TestGetFetchWindow:
    """get_fetch_window 测试。"""

    def test_window_covers_correct_range(self) -> None:
        from app.config import get_fetch_window

        digest_date = date(2026, 3, 19)
        since, until = get_fetch_window(digest_date)

        bj = ZoneInfo("Asia/Shanghai")
        expected_since = datetime(2026, 3, 18, 6, 0, 0, tzinfo=bj)
        expected_until = datetime(2026, 3, 19, 5, 59, 59, tzinfo=bj)

        assert since == expected_since.astimezone(ZoneInfo("UTC"))
        assert until == expected_until.astimezone(ZoneInfo("UTC"))

    def test_window_returns_utc(self) -> None:
        from app.config import get_fetch_window

        since, until = get_fetch_window(date(2026, 3, 19))
        utc = ZoneInfo("UTC")
        assert since.tzinfo == utc or str(since.tzinfo) == "UTC"
        assert until.tzinfo == utc or str(until.tzinfo) == "UTC"

    def test_since_before_until(self) -> None:
        from app.config import get_fetch_window

        since, until = get_fetch_window(date(2026, 3, 19))
        assert since < until

    def test_window_is_almost_24_hours(self) -> None:
        from app.config import get_fetch_window

        since, until = get_fetch_window(date(2026, 3, 19))
        diff = until - since
        assert diff == timedelta(hours=23, minutes=59, seconds=59)


class TestSettings:
    """Settings 基本验证。"""

    def test_settings_loads(self) -> None:
        from app.config import settings

        assert settings.LOG_LEVEL == "INFO"
        assert settings.TIMEZONE == "Asia/Shanghai"
        assert settings.DATABASE_URL == "sqlite:///data/zhixi.db"

    def test_required_fields_exist(self) -> None:
        from app.config import settings

        assert hasattr(settings, "X_API_BEARER_TOKEN")
        assert hasattr(settings, "ANTHROPIC_API_KEY")
        assert settings.JWT_SECRET_KEY

    def test_default_values(self) -> None:
        from app.config import settings

        assert settings.CLAUDE_MODEL == "claude-sonnet-4-20250514"
        assert settings.JWT_EXPIRE_HOURS == 72
        assert settings.DEBUG is False
        assert settings.API_PORT == 8000
        assert pytest.approx(3.0) == settings.CLAUDE_INPUT_PRICE_PER_MTOK
        assert pytest.approx(15.0) == settings.CLAUDE_OUTPUT_PRICE_PER_MTOK


class TestGetSystemConfig:
    """get_system_config 测试。"""

    async def test_existing_key_returns_value(self, seeded_db) -> None:
        """key 存在时返回对应 value。"""
        from app.config import get_system_config

        result = await get_system_config(seeded_db, "push_time")
        assert result == "08:00"

    async def test_missing_key_returns_default(self, seeded_db) -> None:
        """key 不存在时返回 default。"""
        from app.config import get_system_config

        result = await get_system_config(seeded_db, "nonexistent_key", "fallback")
        assert result == "fallback"

    async def test_missing_key_empty_default(self, seeded_db) -> None:
        """key 不存在且未指定 default 时返回空字符串。"""
        from app.config import get_system_config

        result = await get_system_config(seeded_db, "nonexistent_key")
        assert result == ""
