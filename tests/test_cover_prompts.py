"""封面图 Prompt 模板测试。"""

from datetime import date

from app.digest.cover_prompts import build_cover_prompt


class TestBuildCoverPrompt:
    """build_cover_prompt 测试。"""

    def test_normal_prompt(self) -> None:
        """正常构建包含标题和日期的 prompt。"""
        titles = ["OpenAI releases GPT-5", "DeepMind's new reasoning model", "EU AI Act"]
        result = build_cover_prompt(titles, date(2026, 3, 19))

        assert "智曦" in result
        assert "March 19, 2026" in result
        assert "OpenAI releases GPT-5" in result
        assert "DeepMind's new reasoning model" in result
        assert "EU AI Act" in result

    def test_empty_titles(self) -> None:
        """空标题列表仍生成有效 prompt。"""
        result = build_cover_prompt([], date(2026, 1, 1))

        assert "智曦" in result
        assert "January 01, 2026" in result

    def test_single_title(self) -> None:
        """单个标题正常工作。"""
        result = build_cover_prompt(["AI突破"], date(2026, 12, 25))

        assert "AI突破" in result
        assert "December 25, 2026" in result

    def test_titles_truncated_to_three(self) -> None:
        """超过 3 个标题只取前 3。"""
        titles = ["T1", "T2", "T3", "T4", "T5"]
        result = build_cover_prompt(titles, date(2026, 6, 15))

        assert "T1" in result
        assert "T2" in result
        assert "T3" in result
        assert "T4" not in result
        assert "T5" not in result
