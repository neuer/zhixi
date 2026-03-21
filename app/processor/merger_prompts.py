"""多批去重 Prompt 模板与 Schema（R.1.5b，US-020）。

仅当分批策略产生 >=2 批时使用，单批不触发。
"""

from app.processor.analyzer_prompts import GLOBAL_ANALYSIS_SCHEMA

# ──────────────────────────────────────────────────
# R.1.5b 多批去重 Prompt
# ──────────────────────────────────────────────────

DEDUP_PROMPT = """\
你是 智曦的内容总编辑。以下是多批独立分析的合并结果，可能存在重复话题。
请识别并合并重复项。

## 规则
- 如果两个话题讨论同一事件或同一观点，合并为一个，保留 ai_importance_score 较高者
- 合并时 tweet_ids 取并集
- 不重复的话题原样保留
- 不要修改 filtered_ids

## 输入
{merged_analysis_json}

## 输出格式
与全局分析输出格式完全一致：
{{"filtered_ids": [...], "filtered_count": N, "topics": [...]}}"""

# 输出 Schema 与全局分析完全一致
DEDUP_SCHEMA: dict[str, object] = GLOBAL_ANALYSIS_SCHEMA
