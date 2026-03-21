"""封面图 Prompt 模板（R.1.7）。"""

from datetime import date

# R.1.7 封面图 Prompt 模板
COVER_PROMPT_TEMPLATE = """Generate a visually striking cover image for a daily AI news digest.
Today's top AI headlines: {top_headlines}
Requirements:
- Modern, tech-inspired aesthetic
- Include the text "智曦" prominently
- Include today's date: {date}
- Aspect ratio: 2.35:1 (900x383px)
- No faces of real people
- Vibrant and eye-catching"""

# 取前 N 条标题
_TOP_N_TITLES = 3


def build_cover_prompt(top_titles: list[str], digest_date: date) -> str:
    """构建封面图生成 Prompt。

    Args:
        top_titles: heat_score 前 N 条的 snapshot_title 列表
        digest_date: 日报日期

    Returns:
        格式化后的 prompt 字符串
    """
    headlines = "\n".join(
        f"{i}. {title}" for i, title in enumerate(top_titles[:_TOP_N_TITLES], start=1)
    )
    date_str = digest_date.strftime("%B %d, %Y")
    return COVER_PROMPT_TEMPLATE.format(top_headlines=headlines, date=date_str)
