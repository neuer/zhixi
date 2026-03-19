# 数据模型

> 所有数据库表结构、Pydantic 类型定义、实体关系、状态机和设计决策。

---

## 实体关系

```
twitter_accounts 1──N tweets N──1 topics
                              │ (通过 item_ref_id)
                              ▼
daily_digest 1──N digest_items
      │
      └── N──1 job_runs ──1──N api_cost_log
                          ──1──N fetch_log
system_config （独立键值表）
```

---

## 产品决策记录

| 编号 | 问题 | 确认结果 |
|------|------|----------|
| A1 | 聚合话题热度分计算 | `topic.base_score = AVG(成员推文 base_score)` |
| A2 | 编辑操作数据写入 | 只改快照：源表 tweets/topics 保持 AI 原始值不变 |
| A3 | `push_time` 作用 | 纯展示参考值，不触发任何后端逻辑 |
| A4 | `/manual/process` 接口 | 砍掉，只保留 `regenerate` |
| A5 | 补录推文 AI 重要性分 | 固定 50 分 |
| A6 | Thread 第二步 Prompt | 新建 Thread 专用 Prompt |
| A7 | 预览签名链接返回格式 | 返回 JSON，由前端 SPA 渲染 |
| A8 | JWT logout 后端行为 | 后端无操作，前端清除 token |

---

## 表结构

### twitter_accounts

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| twitter_handle | String(100) | NOT NULL, UNIQUE | 不含@ |
| twitter_user_id | String(50) | nullable | X平台ID |
| display_name | String(200) | NOT NULL | |
| avatar_url | String(500) | nullable | |
| bio | String(1000) | nullable | |
| followers_count | Integer | default 0 | |
| weight | Float | default 1.0 | 0.1-5.0 |
| is_active | Boolean | default True | |
| last_fetch_at | DateTime | nullable | UTC |
| created_at | DateTime | default utcnow | |
| updated_at | DateTime | default utcnow | |

### tweets

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| tweet_id | String(50) | NOT NULL, UNIQUE | |
| account_id | Integer | FK→twitter_accounts.id | |
| digest_date | Date | nullable | 北京时间自然日 |
| original_text | Text | NOT NULL | |
| media_urls | Text | nullable | JSON数组 |
| translated_text | Text | nullable | AI翻译 |
| title | String(200) | nullable | AI标题（源表保持AI原始值）|
| ai_comment | Text | nullable | AI点评（源表保持AI原始值）|
| base_heat_score | Float | default 0 | |
| ai_importance_score | Float | default 0 | 手动补录固定50 |
| heat_score | Float | default 0 | |
| likes | Integer | default 0 | |
| retweets | Integer | default 0 | |
| replies | Integer | default 0 | |
| tweet_url | String(500) | nullable | |
| tweet_time | DateTime | NOT NULL | UTC |
| quoted_text | Text | nullable | quote tweet 时存被引用推文原文 |
| is_quote_tweet | Boolean | default False | |
| is_self_thread_reply | Boolean | default False | |
| is_ai_relevant | Boolean | default True | |
| is_processed | Boolean | default False | |
| topic_id | Integer | FK→topics.id, nullable | |
| source | String(20) | default 'auto' | auto/manual |
| created_at | DateTime | default utcnow | |

**索引**: heat_score DESC, digest_date, is_processed, topic_id

### topics

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| digest_date | Date | NOT NULL | |
| type | String(20) | NOT NULL | aggregated/thread |
| title | String(200) | nullable | |
| topic_label | String(200) | nullable | |
| summary | Text | nullable | aggregated: 综合摘要; thread: 中文翻译 |
| perspectives | Text | nullable | JSON `[{author,handle,viewpoint}]`，仅aggregated |
| ai_comment | Text | nullable | |
| heat_score | Float | default 0 | AVG公式 |
| ai_importance_score | Float | default 0 | |
| merge_reason | Text | nullable | |
| tweet_count | Integer | default 0 | |
| version | Integer | default 1 | 预留字段，MVP始终为1 |
| created_at | DateTime | default utcnow | |

### daily_digest

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| digest_date | Date | NOT NULL | 非UNIQUE（多版本）|
| version | Integer | default 1 | |
| is_current | Boolean | default True | |
| title | String(200) | nullable | |
| summary | Text | nullable | 导读摘要 |
| content_markdown | Text | nullable | |
| content_html | Text | nullable | 预留 |
| cover_image_path | String(500) | nullable | |
| item_count | Integer | default 0 | |
| status | String(20) | default 'draft' | draft/published/failed |
| publish_mode | String(20) | default 'manual' | |
| error_message | Text | nullable | |
| job_run_id | Integer | FK→job_runs.id | |
| preview_token | String(100) | nullable | |
| preview_expires_at | DateTime | nullable | |
| reviewed_at | DateTime | nullable | 预留字段，MVP暂不写入 |
| published_at | DateTime | nullable | |
| created_at | DateTime | default utcnow | |
| updated_at | DateTime | default utcnow | |

**约束**: 同日最多1个 is_current=true, 最多1个 status='published'

**is_current 唯一性保证**（代码层面）: SQLite 不支持 partial unique index，在 digest_service 中用事务保证——同一事务内先 `UPDATE SET is_current=false WHERE digest_date=? AND is_current=true`，再 INSERT。

### digest_items

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| digest_id | Integer | FK→daily_digest.id, NOT NULL | |
| item_type | String(20) | NOT NULL | tweet/topic |
| item_ref_id | Integer | NOT NULL | →tweets.id或topics.id |
| display_order | Integer | NOT NULL | |
| is_pinned | Boolean | default False | |
| is_excluded | Boolean | default False | |
| snapshot_title | String(200) | nullable | |
| snapshot_summary | Text | nullable | topic用 |
| snapshot_translation | Text | nullable | tweet用 |
| snapshot_comment | Text | nullable | |
| snapshot_perspectives | Text | nullable | topic用，JSON |
| snapshot_heat_score | Float | default 0 | |
| snapshot_author_name | String(200) | nullable | |
| snapshot_author_handle | String(100) | nullable | |
| snapshot_tweet_url | String(500) | nullable | tweet用 |
| snapshot_source_tweets | Text | nullable | topic用，JSON `[{handle,tweet_url}]` |
| snapshot_topic_type | String(20) | nullable | topic用：aggregated/thread |
| snapshot_tweet_time | DateTime | nullable | tweet用：UTC |
| created_at | DateTime | default utcnow | |

**关键规则**: 管理员编辑只修改 snapshot_* 字段。渲染 Markdown 从 snapshot 读取。源表保持 AI 原始值。

**item_ref_id**: 逻辑外键（polymorphic），不设 DB 级外键约束。严禁直接 DELETE tweets/topics。

**联合唯一约束**: `UNIQUE(digest_id, item_type, item_ref_id)`

#### Snapshot 字段映射表

| snapshot 字段 | tweet 类型 | topic (aggregated) | topic (thread) |
|--------------|-----------|-------------------|----------------|
| snapshot_title | tweets.title | topics.title | topics.title |
| snapshot_translation | tweets.translated_text | null | topics.summary |
| snapshot_summary | null | topics.summary | null |
| snapshot_comment | tweets.ai_comment | topics.ai_comment | topics.ai_comment |
| snapshot_perspectives | null | topics.perspectives | null |
| snapshot_heat_score | tweets.heat_score | topics.heat_score | topics.heat_score |
| snapshot_author_name | accounts.display_name | null | Thread第一条作者 |
| snapshot_author_handle | accounts.twitter_handle | null | Thread第一条handle |
| snapshot_tweet_url | tweets.tweet_url | null | Thread第一条url |
| snapshot_source_tweets | null | `[{handle,tweet_url}]` | null |
| snapshot_topic_type | null | "aggregated" | "thread" |
| snapshot_tweet_time | tweets.tweet_time | null | null |

#### Thread 数据流说明

1. 第一步全局分析输出 `merged_text`（原始英文拼接文本），**不持久化到 DB**，仅在内存中传递给第二步
2. 第二步 Thread Prompt 输入 `{merged_text}` = 第一步输出的 `merged_text`
3. 第二步输出 `{title, translation, comment}` 写入 topics 表：`title` → `topics.title`，`translation` → `topics.summary`，`comment` → `topics.ai_comment`
4. 创建 digest_item 时，`snapshot_translation` 读自 `topics.summary`（对 Thread 来说存的是中文翻译）

### system_config

| key | 默认 value | 说明 |
|-----|-----------|------|
| push_time | 08:00 | 纯展示参考 |
| push_days | 1,2,3,4,5,6,7 | 1=周一...7=周日 |
| top_n | 10 | 推送条数上限 |
| min_articles | 1 | 低于此值黄色提示 |
| display_mode | simple | 预留，MVP 固定 |
| publish_mode | manual | api/manual |
| enable_cover_generation | false | |
| cover_generation_timeout | 30 | 秒 |
| notification_webhook_url | | 企业微信webhook |
| admin_password_hash | | bcrypt，/setup写入 |

### job_runs

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| job_type | String(50) NOT NULL | pipeline/fetch/process/digest/backup/cleanup |
| digest_date | Date nullable | |
| trigger_source | String(20) NOT NULL | cron/manual/regenerate |
| status | String(20) default 'running' | running/completed/failed/skipped |
| error_message | Text nullable | |
| started_at | DateTime NOT NULL | |
| finished_at | DateTime nullable | |
| created_at | DateTime default utcnow | |

### api_cost_log

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| call_date | Date NOT NULL | |
| service | String(20) NOT NULL | x/claude/gemini/wechat |
| call_type | String(50) NOT NULL | fetch_tweets/global_analysis/single_process/thread_process/topic_process/summary/cover |
| endpoint | String(200) nullable | |
| model | String(100) nullable | |
| input_tokens | Integer default 0 | |
| output_tokens | Integer default 0 | |
| estimated_cost | Float default 0 | 美元（估算值）|
| success | Boolean default True | |
| duration_ms | Integer default 0 | |
| job_run_id | Integer FK→job_runs.id | |
| created_at | DateTime default utcnow | |

### fetch_log

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| fetch_date | Date NOT NULL | |
| job_run_id | Integer FK | |
| total_accounts | Integer default 0 | |
| success_count | Integer default 0 | |
| fail_count | Integer default 0 | |
| new_tweets | Integer default 0 | |
| error_details | Text nullable | JSON |
| started_at / finished_at | DateTime | |

---

## 状态机

### daily_digest.status

```
[不存在] ──pipeline──→ [draft v1, is_current=true]
                           │
             ┌─────────────┼──────────────┐
         编辑/排序     重新生成          确认发布
         (改快照,     (v1.is_current=     │
          不改源表)    false, 创建v2)     │
             │             │              │
             │             ▼              ▼
             │     [draft v2]      [published]──→可regenerate→[draft v3]
             │                           │
             │                      [failed]──→重试→[published]
             └─────→ 确认发布 ──→ [published]
```

**规则**: 非 current draft 编辑返回 409。已 published 不可修改但可 regenerate。

### job_runs.status

```
[running] → [completed]
          → [failed] + webhook通知
[skipped]  （不在push_days中）
```

**锁规则**: 同日有 pipeline running 时，manual/fetch、regenerate、publish 返回 409。编辑不受锁影响。

---

## Pydantic 类型定义

```python
# === app/schemas/fetcher_types.py ===
from enum import Enum
from pydantic import BaseModel
from datetime import datetime

class TweetType(str, Enum):
    ORIGINAL = "original"
    SELF_REPLY = "self_reply"
    QUOTE = "quote"
    RETWEET = "retweet"
    REPLY = "reply"

KEEP_TYPES = {TweetType.ORIGINAL, TweetType.SELF_REPLY, TweetType.QUOTE}

class ReferencedTweet(BaseModel):
    type: str          # "replied_to" | "quoted" | "retweeted"
    id: str
    author_id: str     # 从 includes.tweets 提取

class PublicMetrics(BaseModel):
    like_count: int = 0
    retweet_count: int = 0
    reply_count: int = 0

class RawTweet(BaseModel):
    tweet_id: str
    author_id: str
    text: str
    created_at: datetime
    public_metrics: PublicMetrics
    referenced_tweets: list[ReferencedTweet] = []
    media_urls: list[str] = []
    tweet_url: str = ""

class FetchResult(BaseModel):
    new_tweets_count: int
    fail_count: int
    total_accounts: int
    skipped_count: int = 0


# === app/schemas/client_types.py ===
class ClaudeResponse(BaseModel):
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    duration_ms: int


# === app/schemas/processor_types.py ===
class TopicResult(BaseModel):
    type: str                # "aggregated" | "single" | "thread"
    topic_label: str | None = None
    ai_importance_score: float
    tweet_ids: list[str]
    merged_text: str | None = None
    reason: str | None = None

class AnalysisResult(BaseModel):
    filtered_ids: list[str]
    filtered_count: int
    topics: list[TopicResult]

class ProcessResult(BaseModel):
    processed_count: int
    filtered_count: int
    topic_count: int
    failed_count: int = 0


# === app/schemas/digest_types.py ===
class ReorderInput(BaseModel):
    id: int                  # digest_items.id
    display_order: int
    is_pinned: bool = False


# === app/schemas/publisher_types.py ===
class PublishResult(BaseModel):
    success: bool
    status: str              # "published" | "failed"
    error_message: str | None = None
```
