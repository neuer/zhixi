"""AI 加工 Prompt 模板与 JSON Schema（R.1.3 / R.1.4 / R.1.5）。"""

# ──────────────────────────────────────────────────
# R.1.3 单条推文加工 Prompt
# ──────────────────────────────────────────────────

SINGLE_TWEET_PROMPT = """\
你是 智曦的内容编辑。

请对以下推文完成三项任务：

### 任务1：生成中文标题
- 一句话概括核心内容，15字以内
- 中文为主，AI关键术语保留英文（如 LLM、GPT、Transformer）

### 任务2：中文翻译
- 准确流畅，符合中文阅读习惯
- 专业术语格式："中文（English）"
- 保持原文语气

### 任务3：AI点评
- 说明这条信息为什么重要，对行业有什么影响
- 长度根据内容重要性灵活调整：
  - 一般资讯：1句话，30-50字
  - 重要资讯：2-3句话，80-150字
- 要有具体观点，不要空泛

推文信息：
- 作者：{author_name}（@{author_handle}）
- 作者简介：{author_bio}
- 发布时间：{tweet_time}
- 互动：{likes}赞 / {retweets}转 / {replies}评
- 原文：{original_text}

请严格按以下JSON格式输出：
{{
  "title": "中文标题",
  "translation": "中文翻译",
  "comment": "AI点评"
}}"""

SINGLE_TWEET_SCHEMA: dict[str, object] = {
    "required": ["title", "translation", "comment"],
    "properties": {
        "title": {"type": "string"},
        "translation": {"type": "string"},
        "comment": {"type": "string"},
    },
}

# ──────────────────────────────────────────────────
# R.1.4 聚合话题加工 Prompt
# ──────────────────────────────────────────────────

TOPIC_PROMPT = """\
你是 智曦的内容编辑。

以下多条推文讨论同一话题/事件，请聚合加工：

### 任务1：话题标题（15字以内，中文为主）
### 任务2：综合摘要（200-300字）
### 任务3：各方观点（每人1-2句话，标注大V名称）
### 任务4：编辑点评（2-3句话，100-200字，有深度）

相关推文：
{tweets_json}

请严格按以下JSON格式输出：
{{
  "title": "话题标题",
  "summary": "综合摘要",
  "perspectives": [
    {{"author": "Sam Altman", "handle": "sama", "viewpoint": "观点概述"}}
  ],
  "comment": "编辑点评"
}}"""

TOPIC_SCHEMA: dict[str, object] = {
    "required": ["title", "summary", "perspectives", "comment"],
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "perspectives": {
            "type": "array",
            "items": {
                "required": ["author", "handle", "viewpoint"],
                "properties": {
                    "author": {"type": "string"},
                    "handle": {"type": "string"},
                    "viewpoint": {"type": "string"},
                },
            },
        },
        "comment": {"type": "string"},
    },
}

# ──────────────────────────────────────────────────
# R.1.5 Thread 专用 Prompt
# ──────────────────────────────────────────────────

THREAD_PROMPT = """\
你是 智曦的内容编辑。

以下是同一作者的一组连续推文（Thread），构成一个完整的论述。
请将其作为一个整体来理解和加工，而非独立的多条推文。

### 任务1：生成中文标题（15字以内，中文为主，AI术语保留英文）
### 任务2：中文翻译（保留论述逻辑结构，专业术语"中文（English）"格式）
### 任务3：AI点评（核心观点及行业影响，80-200字）

Thread 信息：
- 作者：{author_name}（@{author_handle}）
- 作者简介：{author_bio}
- 发布时间：{thread_start_time} ~ {thread_end_time}
- Thread 条数：{tweet_count}
- 总互动：{total_likes}赞 / {total_retweets}转 / {total_replies}评

Thread 全文（按时间顺序）：
{merged_text}

请严格按以下JSON格式输出：
{{
  "title": "中文标题",
  "translation": "中文翻译（完整Thread）",
  "comment": "AI点评"
}}"""

# Thread Schema 与单条推文相同
THREAD_SCHEMA = SINGLE_TWEET_SCHEMA
