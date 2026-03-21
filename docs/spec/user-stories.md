# User Stories

> 所有功能需求的完整列表。按实现阶段分组，含验收标准和依赖关系。
> 数据模型详见 `docs/spec/data-model.md`，架构详见 `docs/spec/architecture.md`，Prompt 模板详见 `docs/spec/prompts.md`。

---

## 状态追踪表

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| US-001 | 项目骨架初始化 | P0 | ✅ 已完成 | 无 |
| US-002 | 数据库初始化与迁移 | P0 | ✅ 已完成 | US-001 |
| US-003 | SQLite 备份 | P0 | ✅ 已完成 | US-002 |
| US-004 | 日志系统 | P0 | ✅ 已完成 | 无 |
| US-006 | 定时任务调度 | P0 | ✅ 已完成 | US-001 |
| US-010 | 大V账号管理 | P0 | ✅ 已完成 | US-002, US-008 |
| US-011 | BaseFetcher 抽象基类 | P0 | ✅ 已完成 | US-001 |
| US-012 | 推文分类器 | P0 | ✅ 已完成 | US-001 |
| US-013 | 每日自动抓取推文 | P0 | ✅ 已完成 | US-011, US-012, US-010 |
| US-014 | 单账号抓取失败容错 | P0 | ✅ 已完成 | US-013 |
| US-015 | X API 限流处理 | P0 | ✅ 已完成 | US-013 |
| US-047 | 推文分类器测试 | P0 | ✅ 已完成 | US-012 |
| US-053 | 备份与清理测试 | P0 | ✅ 已完成 | US-003 |
| US-017 | Claude API 客户端封装 | P1 | ✅ 已完成 | US-001, US-004 |
| US-018 | JSON 输出校验与修复 | P1 | ✅ 已完成 | US-001 |
| US-019 | 全局分析（第一步 AI） | P1 | ✅ 已完成 | US-017, US-018 |
| US-020 | 分批处理策略 | P1 | ✅ 已完成 | US-019 |
| US-021 | 逐条/逐话题 AI 加工 | P1 | ✅ 已完成 | US-017, US-018 |
| US-022 | 热度分计算 | P1 | ✅ 已完成 | US-001 |
| US-048 | JSON 校验测试 | P1 | ✅ 已完成 | US-018 |
| US-049 | 热度计算测试 | P1 | ✅ 已完成 | US-022 |
| US-007 | 首次设置向导 | P2 | ✅ 已完成 | US-002 |
| US-008 | 管理员登录认证 | P2 | ✅ 已完成 | US-002 |
| US-023 | 导读摘要生成 | P2 | ✅ 已完成 | US-017 |
| US-024 | 草稿组装与 digest_items | P2 | ✅ 已完成 | US-019, US-021, US-022 |
| US-025 | Markdown 渲染 | P2 | ✅ 已完成 | US-024 |
| US-026 | 封面图生成（可选） | P2 | 🔲 待开发 | US-024 |
| US-030 | 查看今日内容列表 | P2 | ✅ 已完成 | US-024, US-008 |
| US-031 | 编辑单条内容 | P2 | ✅ 已完成 | US-030 |
| US-032 | 编辑导读摘要 | P2 | ✅ 已完成 | US-030, US-025 |
| US-033 | 调整排序与置顶 | P2 | ✅ 已完成 | US-030 |
| US-034 | 剔除与恢复条目 | P2 | ✅ 已完成 | US-030 |
| US-039 | Vue 项目初始化 | P2 | ✅ 已完成 | US-007, US-008 |
| US-040 | Dashboard 首页 | P2 | ✅ 已完成 | US-039 |
| US-041 | 系统设置页 | P2 | ✅ 已完成 | US-039 |
| US-052 | Markdown 渲染测试 | P2 | ✅ 已完成 | US-025 |
| US-005 | Docker Compose 部署 | P3 | ✅ 已完成 | US-001 |
| US-027 | Pipeline 主流程编排 | P3 | ✅ 已完成 | US-013, US-019, US-021, US-024, US-028, US-029 |
| US-027b | 手动触发抓取 | P3 | ✅ 已完成 | US-013, US-028 |
| US-028 | 任务幂等锁 | P3 | ✅ 已完成 | US-002 |
| US-029 | 通知服务（Webhook） | P3 | ✅ 已完成 | US-001 |
| US-035 | 重新生成草稿 | P3 | ✅ 已完成 | US-027, US-028 |
| US-036 | 手动发布模式 | P3 | ✅ 已完成 | US-025, US-030 |
| US-037 | API 自动发布（预留） | P3 | ✅ 已完成 | US-036 |
| US-038 | 预览功能（登录态） | P3 | ✅ 已完成 | US-025, US-030 |
| US-042 | 推送历史页 | P3 | ✅ 已完成 | US-039 |
| US-043 | API 成本监控 | P3 | ✅ 已完成 | US-002 |
| US-044 | Dashboard 日志展示 | P3 | ✅ 已完成 | US-039, US-004 |
| US-050 | API 接口测试 | P3 | ✅ 已完成 | US-008, US-030 |
| US-051 | 状态流转测试 | P3 | ✅ 已完成 | US-024, US-035 |
| US-009 | 预览签名链接 | P4 | ✅ 已完成 | US-025, US-008 |
| US-016 | 手动补录推文 | P4 | ✅ 已完成 | US-011, US-021, US-024, US-030 |
| US-045 | 冷门日处理 | P4 | ✅ 已完成 | US-024 |
| US-046 | 超时未审核处理 | P4 | ✅ 已完成 | US-027 |

---

## 阶段 P0: 项目骨架 + 数据采集

### US-001: 项目骨架初始化

**优先级**: 必须 | **依赖**: 无

**验收标准**:
- [ ] 目录结构与架构一致（见 `docs/spec/directory-structure.md`）
- [ ] `pyproject.toml` 包含核心依赖，使用 uv 管理（见 `docs/spec/constraints.md`）
- [ ] `.env.example` 包含所有环境变量（见 `docs/spec/constraints.md`）
- [ ] `app/config.py` 从 .env 读取密钥类配置，缺必填项启动报错
- [ ] `app/config.py` 从 DB system_config 读取业务配置
- [ ] `app/config.py` 包含 `get_today_digest_date()` 和 `get_fetch_window()` 时间工具函数（参考实现如下）
- [ ] 项目根目录有中文 README.md
- [ ] `ruff check .` 通过
- [ ] `pyright` 类型检查通过

**时间工具函数参考实现**:
```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
BEIJING_TZ = ZoneInfo("Asia/Shanghai")

def get_today_digest_date() -> date:
    """获取今日 digest_date（北京时间自然日）。禁止用 datetime.utcnow().date()"""
    return datetime.now(BEIJING_TZ).date()

def get_fetch_window(digest_date: date) -> tuple[datetime, datetime]:
    """前一日06:00~当日05:59（北京时间）→ 转UTC"""
    bj_since = datetime(digest_date.year, digest_date.month, digest_date.day,
                        6, 0, 0, tzinfo=BEIJING_TZ) - timedelta(days=1)
    bj_until = datetime(digest_date.year, digest_date.month, digest_date.day,
                        5, 59, 59, tzinfo=BEIJING_TZ)
    return bj_since.astimezone(ZoneInfo("UTC")), bj_until.astimezone(ZoneInfo("UTC"))
```
- [ ] 所有 Python 文件顶部有中文模块说明

### US-002: 数据库初始化与迁移

**优先级**: 必须 | **依赖**: US-001

**验收标准**:
- [ ] `alembic.ini` 放在**项目根目录**（非 alembic/ 子目录，与 Dockerfile COPY 一致）
- [ ] SQLAlchemy 模型使用通用类型（String/Boolean/Float/DateTime），不使用 SQLite 专属语法
- [ ] 数据库连接启用 WAL 模式 + busy_timeout=5000
- [ ] `alembic revision --autogenerate` 成功生成迁移脚本
- [ ] `alembic upgrade head` 从零创建全部表
- [ ] 初始迁移包含 system_config 全部默认数据（见 `docs/spec/data-model.md`）
- [ ] 所有外键、索引与数据模型一致
- [ ] digest_items 表必须包含 `snapshot_source_tweets` 字段（TEXT, nullable）
- [ ] digest_items 表必须添加联合唯一约束 `UNIQUE(digest_id, item_type, item_ref_id)`

### US-003: SQLite 备份

**优先级**: 必须 | **依赖**: US-002

**验收标准**:
- [ ] CLI `python -m app.cli backup` 使用 sqlite3 官方 backup API
- [ ] 备份到 `data/backups/zhixi_YYYYMMDD_HHMMSS.db`
- [ ] WAL 模式下不阻塞 Web 服务
- [ ] 超过 30 天自动清理
- [ ] CLI `python -m app.cli cleanup` 清理过期备份和日志
- [ ] 备份结果写入 job_runs

### US-004: 日志系统

**优先级**: 必须 | **依赖**: 无

**验收标准**:
- [ ] Python logging，按天轮转到 `data/logs/app_YYYYMMDD.log`
- [ ] **日志格式为结构化 JSON**（每行一个 JSON 对象，包含 timestamp、level、message、module 等字段）
- [ ] 所有请求必须带 `request_id`（通过 middleware 注入，贯穿日志上下文）
- [ ] 保留 30 天
- [ ] 后端日志英文
- [ ] LOG_LEVEL 通过 .env 控制
- [ ] 记录：抓取结果、AI 调用详情、发布操作、异常堆栈

### US-006: 定时任务调度

**优先级**: 必须 | **依赖**: US-001

**验收标准**:
- [ ] crontab: cleanup(北京04:00)、backup(北京05:00)、pipeline(北京06:00)
- [ ] 日志追加到 data/logs/cron.log
- [ ] CLI 支持 pipeline/backup/cleanup 子命令

### US-010: 大V账号管理

**优先级**: 必须 | **依赖**: US-002, US-008

**验收标准**:
- [ ] `GET /api/accounts` 返回列表
- [ ] `POST /api/accounts` 输入 handle，自动拉取信息；拉取失败允许手动填写
- [ ] `PUT /api/accounts/{id}` 可改 weight(0.1-5.0)、is_active
- [ ] `DELETE /api/accounts/{id}` **统一软删除**（设 is_active=false），不做硬删除，避免外键悬空
- [ ] 前端：Vant 列表 + 开关 + 滑动删除
- [ ] 接口契约详见 `docs/spec/architecture.md` > API 契约 > 大V管理

### US-011: BaseFetcher 抽象基类

**优先级**: 必须 | **依赖**: US-001

**验收标准**:
- [ ] `app/fetcher/base.py` 定义 BaseFetcher
- [ ] 抽象方法 `fetch_user_tweets(user_id, since, until) -> list[RawTweet]`
- [ ] RawTweet 包含：tweet_id, text, created_at, public_metrics, referenced_tweets, media_urls
- [ ] referenced_tweets 从 `includes.tweets` 提取 author_id
- [ ] XApiFetcher 使用 `httpx.AsyncClient`
- [ ] `third_party.py` 留空壳 + TODO
- [ ] 工厂函数 `get_fetcher() -> BaseFetcher`

### US-012: 推文分类器

**优先级**: 必须 | **依赖**: US-001

**验收标准**:
- [ ] `classify_tweet(raw_tweet) -> TweetType`
- [ ] TweetType: ORIGINAL / SELF_REPLY / QUOTE / RETWEET / REPLY
- [ ] 判断基于 referenced_tweets 字段：无→ORIGINAL，replied_to且同作者→SELF_REPLY，replied_to且非同作者→REPLY，quoted→QUOTE，retweeted→RETWEET
- [ ] 保留: ORIGINAL + SELF_REPLY + QUOTE | 排除: RETWEET + REPLY
- [ ] 测试覆盖全部5种类型

### US-013: 每日自动抓取推文

**优先级**: 必须 | **依赖**: US-011, US-012, US-010

**验收标准**:
- [ ] fetch_service.run_daily_fetch() 读取 is_active=true 的账号
- [ ] 时间窗口：前一日06:00~当日05:59（北京时间）→ 转UTC
- [ ] X API 端点：`GET /2/users/{id}/tweets`
- [ ] X API 查询参数：`exclude=retweets`, `max_results=100`, `start_time={since_utc}`, `end_time={until_utc}`, `tweet.fields=created_at,public_metrics,attachments,referenced_tweets`, `expansions=attachments.media_keys,referenced_tweets.id`, `media.fields=url,type`
- [ ] 分页：如果响应含 `meta.next_token`，用 `pagination_token` 继续请求，直到无 `next_token` 或达到 **5 页上限**
- [ ] 分类后仅保存 ORIGINAL + SELF_REPLY + QUOTE
- [ ] 基于 tweet_id 去重
- [ ] digest_date 用 `get_today_digest_date()` 计算（北京时间自然日）
- [ ] API 成本记录到 api_cost_log（service='x', call_type='fetch_tweets'）
- [ ] 统计写入 fetch_log
- [ ] 边界条件：推文缺少必要字段→记录日志跳过；该账号无新推文→正常继续（new_tweets=0）

### US-014: 单账号抓取失败容错

**优先级**: 必须 | **依赖**: US-013

**验收标准**:
- [ ] 单账号异常：捕获、记录日志、跳过继续
- [ ] fetch_log.error_details 记录每个失败账号（JSON）
- [ ] 全部失败：pipeline 标记异常 + webhook

### US-015: X API 限流处理

**优先级**: 必须 | **依赖**: US-013

**验收标准**:
- [ ] HTTP 429 触发指数退避：2s→4s→8s，最多3次
- [ ] 超过3次标记该账号失败
- [ ] 正常请求间隔 ≥1s

### US-047: 推文分类器测试

**优先级**: 必须 | **依赖**: US-012

**验收标准**:
- [ ] tests/test_tweet_classifier.py 覆盖5种类型
- [ ] 每种 ≥2 个用例

### US-053: 备份与清理测试

**优先级**: 必须 | **依赖**: US-003

**验收标准**:
- [ ] `tests/test_backup.py` 验证 backup 命令生成正确文件名格式 `zhixi_YYYYMMDD_HHMMSS.db`
- [ ] 验证 cleanup 命令删除 31 天前的备份文件、保留 30 天内的文件
- [ ] 验证 cleanup 命令删除过期日志文件
- [ ] 验证 backup 结果写入 job_runs（status=completed 或 failed）

---

## 阶段 P1: AI 加工全流程

### US-017: Claude API 客户端封装

**优先级**: 必须 | **依赖**: US-001, US-004

**验收标准**:
- [ ] `app/clients/claude_client.py` 封装调用
- [ ] **必须使用 `anthropic.AsyncAnthropic` 异步客户端**（与项目异步架构一致）
- [ ] `complete()` 方法为 `async def`，内部调用 `await client.messages.create(...)`
- [ ] 模型名从 CLAUDE_MODEL 环境变量读取
- [ ] 返回 ClaudeResponse（含 input_tokens, output_tokens, duration_ms, estimated_cost），**Service 层负责写 api_cost_log**（ClaudeClient 本身不持有 db session）
- [ ] estimated_cost 按 Sonnet 定价估算：默认 input $3/MTok, output $15/MTok（可通过环境变量 `CLAUDE_INPUT_PRICE_PER_MTOK` / `CLAUDE_OUTPUT_PRICE_PER_MTOK` 覆盖）
- [ ] 所有 Prompt 自动注入安全声明（见 `docs/spec/prompts.md` R.1.1）
- [ ] 超时设置：单次调用 60 秒（`timeout=60.0`）
- [ ] 失败抛出 ClaudeAPIError

### US-018: JSON 输出校验与修复

**优先级**: 必须 | **依赖**: US-001

**验收标准**:
- [ ] `validate_and_fix(raw_text, schema) -> dict`
- [ ] 第一级：直接 json.loads()
- [ ] 第二级：去除 ```json 包裹、去除前后多余文字、补全缺失括号
- [ ] 第三级：抛出 JsonValidationError 附带原始响应
- [ ] schema 校验：必需字段存在且类型正确
- [ ] 测试覆盖：正常JSON、markdown包裹、缺括号、多余前缀、字段缺失、完全无效
- [ ] JSON Schema 定义见 `docs/spec/prompts.md` 各 Prompt 对应的 Schema

### US-019: 全局分析（第一步 AI）

**优先级**: 必须 | **依赖**: US-017, US-018

**验收标准**:
- [ ] `run_global_analysis(tweets) -> AnalysisResult`
- [ ] Prompt 使用 `docs/spec/prompts.md` R.1.2 全局分析模板 + R.1.1 安全声明
- [ ] 输入：当日 is_processed=false 的推文（JSON 序列化，格式见 `docs/spec/prompts.md` R.1.1b）
- [ ] **输入排序**: 推文按 `tweet_time` 降序传入 AI（最新的在前），便于 AI 理解时间线
- [ ] 输出 JSON：filtered_ids, topics(type/ai_importance_score/tweet_ids/reason)
- [ ] filtered_ids 推文设 is_ai_relevant=false
- [ ] type=thread → topics 表(type=thread), 关联推文设 topic_id
- [ ] type=aggregated → topics 表(type=aggregated), 关联推文设 topic_id
- [ ] type=single → 不建 topic, topic_id=null
- [ ] **所有非 filtered 推文的 `ai_importance_score` 必须在此步写入 tweets 表**：single 推文直接取该条的 ai_importance_score；aggregated/thread 推文取所属话题的 ai_importance_score
- [ ] thread 类型的 `merged_text`（原始拼接文本）**仅在内存中保留**，传递给第二步 Thread Prompt，不写入 DB
- [ ] 输出经 json_validator 三级校验
- [ ] 失败重试1次，仍失败中止 pipeline + 通知
- [ ] 边界条件：0条推文通过过滤→正常继续（空草稿）；AI返回空topics→所有推文作为single处理

### US-020: 分批处理策略

**优先级**: 应该 | **依赖**: US-019

**验收标准**:
- [ ] 估算 token 数（中文1.5字/token, 英文4字符/token）
- [ ] 单批上限 100K input tokens
- [ ] 超限按 author_weight 降序分批
- [ ] 多批合并后做轻量 AI 去重（Prompt 见 `docs/spec/prompts.md` R.1.5b）
- [ ] 单批不触发去重

### US-021: 逐条/逐话题 AI 加工（第二步）

**优先级**: 必须 | **依赖**: US-017, US-018

**验收标准**:
- [ ] 单条推文（topic_id=null）：附录 R.1.3 单条推文加工 Prompt → `{title, translation, comment}`
- [ ] 聚合话题（type=aggregated）：附录 R.1.4 聚合话题加工 Prompt → `{title, summary, perspectives, comment}`
- [ ] Thread（type=thread）：**Thread 专用 Prompt**（见 `docs/spec/prompts.md` R.1.5）→ `{title, translation, comment}`
- [ ] Thread 的 translation 写入 `topics.summary`（对 Thread 来说该字段存中文翻译）
- [ ] 逐条调用，间隔1秒
- [ ] 单条失败重试2次，仍失败跳过（is_processed=false），继续其他
- [ ] 成功后更新 tweets/topics 表，is_processed=true
- [ ] 每次记录 api_cost_log

### US-022: 热度分计算

**优先级**: 必须 | **依赖**: US-001

**验收标准**:
- [ ] `heat_calculator.py` 纯函数
- [ ] `base_score = (likes*1 + retweets*3 + replies*2) * author_weight * exp(-0.05*hours)`
- [ ] hours 参考时间点：digest_date 当日北京时间 06:00（固定，确保可复现），详见 `docs/spec/architecture.md` > 热度公式
- [ ] **聚合/Thread话题**: `topic.raw_base_score = AVG(成员推文的 raw base_score)`
- [ ] **归一化**: 将所有单条推文的 raw base_score 和所有 topic 的 raw_base_score **放在一起**做 min-max 归一化到 0-100
- [ ] 全部相同或仅1条 → normalized=50
- [ ] `heat_score = normalized_base * 0.7 + ai_importance * 0.3`
- [ ] ai_importance: 单条取全局分析值，聚合/Thread取全局分析的话题评分
- [ ] 边界条件：likes=retweets=replies=0 → base_score=0；手动补录 → ai_importance固定50, base_score按互动算
- [ ] 测试：多条正常、单条、全同、极端值、time_decay、聚合(AVG→一起归一化)

### US-048: JSON 校验测试

**优先级**: 必须 | **依赖**: US-018

**验收标准**:
- [ ] tests/test_json_validator.py：正常、markdown包裹、缺括号、多余前缀、字段缺失、完全无效
- [ ] ≥8 个用例

### US-049: 热度计算测试

**优先级**: 必须 | **依赖**: US-022

**验收标准**:
- [ ] tests/test_heat_calculator.py：多条、单条(=50)、全同、time_decay、聚合(AVG)
- [ ] 精度到小数点后2位

---

## 阶段 P2: 草稿组装 + 管理后台

### US-007: 首次设置向导

**优先级**: 必须 | **依赖**: US-002

**验收标准**:
- [ ] `GET /api/setup/status` → `{need_setup: true/false}`
- [ ] `POST /api/setup/init` 接受 `{password, webhook_url?}`
- [ ] 用户名固定 admin
- [ ] 密码校验：≥8位含大小写+数字，不满足返回 422 中文错误
- [ ] bcrypt hash 存入 system_config
- [ ] 已完成后再调用返回 403
- [ ] 前端 App 初始化检查，need_setup=true 重定向 /setup
- [ ] 接口契约详见 `docs/spec/architecture.md`

### US-008: 管理员登录认证

**优先级**: 必须 | **依赖**: US-002

**验收标准**:
- [ ] `POST /api/auth/login` → JWT token
- [ ] JWT 有效期从 JWT_EXPIRE_HOURS 读取（默认72h）
- [ ] 所有 /api/* 需 Bearer JWT（除 setup/*、auth/login、digest/preview/{token}）
- [ ] 无效/过期返回 401 "登录已过期，请重新登录"
- [ ] `POST /api/auth/logout` 返回 200，后端无状态操作（前端清 token）
- [ ] 连续5次失败锁定15分钟。按用户名计数（只有 admin 等价于全局）；第6次及以后返回 423；15分钟从第5次失败时刻计算；任何一次成功登录重置计数器。MVP 用内存计数器（进程重启后归零，可接受）
- [ ] 接口契约详见 `docs/spec/architecture.md`

### US-023: 导读摘要生成

**优先级**: 必须 | **依赖**: US-017

**验收标准**:
- [ ] 使用 `docs/spec/prompts.md` R.1.6 导读摘要 Prompt 模板
- [ ] 输入 TOP 5 资讯
- [ ] 输出 2-3 句话，≤150字
- [ ] 失败用默认文案："今日 AI 热点已为您整理完毕，请查阅以下资讯。"
- [ ] 存入 daily_digest.summary

### US-024: 草稿组装与 digest_items 创建

**优先级**: 必须 | **依赖**: US-019, US-021, US-022

**验收标准**:
- [ ] 创建 daily_digest: status=draft, version=1, is_current=true
- [ ] 创建 digest_items 按 heat_score 降序，display_order 从1开始
- [ ] 每条写入完整快照（所有 snapshot_* 字段，映射表见 `docs/spec/data-model.md` > Snapshot 字段映射表）
- [ ] **topic 类型的 digest_item 必须写入 `snapshot_topic_type`**（取自 `topics.type`：`aggregated` 或 `thread`），渲染器据此选择模板
- [ ] 聚合话题额外写入 snapshot_summary, snapshot_perspectives, snapshot_source_tweets
- [ ] 仅含 is_ai_relevant=true 且 is_processed=true 的内容
- [ ] **已被聚合到 topic 的推文（topic_id 不为 null），不单独创建 tweet 类型的 digest_item**。它们只通过所属 topic 的 digest_item 间接展示
- [ ] digest_date 用 get_today_digest_date()

**Thread 数据流说明**:
1. 第一步全局分析输出 `merged_text`（原始英文拼接文本），**不持久化到 DB**，仅在内存中传递给第二步
2. 第二步 Thread Prompt 输入 `{merged_text}` = 第一步输出的 `merged_text`
3. 第二步输出 `{title, translation, comment}` 写入 topics 表：`title` → `topics.title`，`translation` → `topics.summary`，`comment` → `topics.ai_comment`
4. 创建 digest_item 时，`snapshot_translation` 读自 `topics.summary`（对 Thread 来说存的是中文翻译）

### US-025: Markdown 渲染

**优先级**: 必须 | **依赖**: US-024

**验收标准**:
- [ ] `render_markdown(digest, items) -> str`
- [ ] **从 digest_items 快照读取**（不从 tweets/topics 源表）
- [ ] 跳过 is_excluded=true
- [ ] 按 display_order 排序，置顶最前
- [ ] 聚合话题：摘要 + 各方观点 + 来源推文链接
- [ ] 单条推文：作者 + 翻译 + 点评 + 原文链接
- [ ] 底部 "智曦 - 每天一束AI之光" 固定文案
- [ ] **top_n 指最终渲染出的有效条目数**：先过滤掉 is_excluded=true，再取前 top_n 条渲染
- [ ] 存入 content_markdown
- [ ] 模板和渲染规则详见 `docs/spec/prompts.md` R.2

### US-026: 封面图生成（可选）

**优先级**: 可以 | **依赖**: US-024

**验收标准**:
- [ ] 默认关闭，enable_cover_generation=true 开启
- [ ] Prompt 见 `docs/spec/prompts.md` R.1.7
- [ ] 使用 `google-generativeai` 包，模型 `imagen-3.0-generate-002`，调用 `client.models.generate_images(model=..., prompt=..., config={"number_of_images": 1, "aspect_ratio": "16:9"})`
- [ ] 返回的 `response.generated_images[0].image.image_bytes` 用 Pillow 裁切/缩放至 900x383px 后保存为 PNG
- [ ] 超时30s用默认封面，**不重试不阻塞**
- [ ] 成功保存到 data/covers/cover_YYYYMMDD.png
- [ ] 记录 api_cost_log（service='gemini', call_type='cover'）
- [ ] `POST /api/manual/generate-cover` 手动触发封面图生成。功能未开启时返回 400 "封面图功能未开启"。成功则覆盖当前封面

### US-030: 查看今日内容列表

**优先级**: 必须 | **依赖**: US-024, US-008

**验收标准**:
- [ ] `GET /api/digest/today` → digest 信息 + items 列表。**"today" = `get_today_digest_date()` 北京时间自然日**，查询 `digest_date = today AND is_current = true`
- [ ] items 按 display_order 排序
- [ ] 含 snapshot 字段、is_pinned、is_excluded
- [ ] low_content_warning: item_count < min_articles 时 true
- [ ] Vant 卡片列表，聚合/单条不同样式
- [ ] 无数据时空状态提示（返回 `{"digest": null, "items": [], "low_content_warning": false}`）
- [ ] 接口契约详见 `docs/spec/architecture.md` > 日报操作

### US-031: 编辑单条内容

**优先级**: 必须 | **依赖**: US-030

**验收标准**:
- [ ] `PUT /api/digest/item/{item_type}/{item_ref_id}`
- [ ] item_type: tweet/topic, item_ref_id: tweets.id 或 topics.id
- [ ] **定位逻辑**: 找到当日 is_current=true 的 daily_digest → 在其 digest_items 中匹配 item_type + item_ref_id 的记录
- [ ] **仅更新 digest_items snapshot_* 字段，不修改源表**
- [ ] 权限检查: is_current=true 且 status=draft，否则 409 "当前版本不可编辑，请先重新生成新版本"
- [ ] 聚合话题 perspectives 支持修改/删除单条
- [ ] **编辑完成后必须调用 render_markdown 重新渲染 content_markdown**
- [ ] 前端：点击卡片→编辑页→Vant 表单→保存

### US-032: 编辑导读摘要

**优先级**: 应该 | **依赖**: US-030, US-025

**验收标准**:
- [ ] `PUT /api/digest/summary` → 更新 daily_digest.summary + 重渲染 Markdown
- [ ] 权限检查同 US-031（is_current=true 且 status=draft）

### US-033: 调整排序与置顶

**优先级**: 应该 | **依赖**: US-030

**验收标准**:
- [ ] `PUT /api/digest/reorder` 接受 `{items: [{id, display_order, is_pinned}]}`
- [ ] **多置顶规则**: 置顶条目按置顶先后顺序分配 display_order = 0, 1, 2...，非置顶条目从"置顶数量"开始编号。reorder 请求体中前端必须传入**所有条目**的最终 display_order 值，后端不自动计算
- [ ] 权限检查同 US-031
- [ ] **排序完成后必须调用 render_markdown 重新渲染 content_markdown**
- [ ] 前端：长按拖动排序，**拖动释放后自动调用 API 保存**。成功后 Toast 提示"排序已更新"，失败时恢复原位置并提示错误

### US-034: 剔除与恢复条目

**优先级**: 应该 | **依赖**: US-030

**验收标准**:
- [ ] `POST /api/digest/exclude/{type}/{id}` → is_excluded=true
- [ ] `POST /api/digest/restore/{type}/{id}` → is_excluded=false, display_order=max+1
- [ ] 渲染时跳过 excluded
- [ ] **剔除/恢复后必须调用 render_markdown 重新渲染 content_markdown**
- [ ] 前端：卡片左滑显示红色"剔除"按钮，点击后立即调用 API。被剔除条目灰显+删除线，移至列表底部独立"已剔除"分组，显示"恢复"按钮

### US-039: Vue 项目初始化

**优先级**: 必须 | **依赖**: US-007, US-008

**验收标准**:
- [ ] Vue 3 + TypeScript + Vant 4 + Vite，使用 bun 管理依赖
- [ ] 所有 `.vue` 文件使用 `<script setup lang="ts">`
- [ ] `tsconfig.json` 配置 strict 模式
- [ ] `env.d.ts` 包含 Vue 类型声明（`/// <reference types="vite/client" />`）
- [ ] `packages/openapi-client/` 配置 `@hey-api/openapi-ts`，从后端 OpenAPI 生成 TS 客户端和类型
- [ ] 前端通过 `packages/openapi-client` 导入 API 类型，禁止手写 API 响应类型
- [ ] `make gen` 可成功执行且生成物无 diff
- [ ] `biome.json` 配置 lint/格式化规则
- [ ] `biome check .` 通过
- [ ] `vue-tsc --noEmit` 类型检查通过
- [ ] Playwright 配置就绪（E2E 测试框架）
- [ ] **不使用 Pinia/Vuex 等全局状态管理**。组件级 `ref()`/`reactive()` + API 调用即可满足单管理员场景
- [ ] 路由：/setup, /login, /dashboard, /accounts, /digest, /digest/edit/:type/:id, /history, /history/:id, /settings, /preview
- [ ] 守卫：未登录→/login, need_setup→/setup。**白名单（不需要JWT）: /setup, /login, /preview**
- [ ] `/preview` 路由在 mounted 时从 URL 读取 token 参数，调用 `GET /api/digest/preview/{token}` 获取数据。token 无效时展示"链接已失效"提示页
- [ ] axios 拦截器：401→登录页
- [ ] 全中文界面
- [ ] 移动端优先

### US-040: Dashboard 首页

**优先级**: 必须 | **依赖**: US-039

**验收标准**:
- [ ] `GET /api/dashboard/overview` → pipeline状态、digest状态、近7天记录、告警
- [ ] 状态卡片 + API成本卡片 + 「审核今日内容」大按钮
- [ ] 失败时红色告警
- [ ] 近7天推送记录
- [ ] 接口契约详见 `docs/spec/architecture.md` > Dashboard

### US-041: 系统设置页

**优先级**: 必须 | **依赖**: US-039

**验收标准**:
- [ ] `GET /api/settings` → 全部业务配置（不含密钥）
- [ ] `PUT /api/settings` → 部分更新
- [ ] 可配置：push_time, push_days(多选), top_n, min_articles, publish_mode, enable_cover_generation, cover_generation_timeout, webhook_url
- [ ] **push_days 至少选择1天**，空数组返回 422 "至少选择一个推送日"
- [ ] API 状态检测：`GET /api/settings/api-status` 并发 ping 各 API，**每个超时 5 秒，总耗时不超过 10 秒**（asyncio.gather）。超时视为 status='error'
- [ ] API Key 只显示"已配置/未配置"
- [ ] DB 大小、最近备份时间
- [ ] 接口契约详见 `docs/spec/architecture.md` > 设置

### US-052: Markdown 渲染测试

**优先级**: 必须 | **依赖**: US-025

**验收标准**:
- [ ] 输出含标题、导读、热度榜、详细资讯
- [ ] excluded 不在输出中
- [ ] 聚合含各方观点和来源链接

---

## 阶段 P3: 发布流程 + 部署

### US-005: Docker Compose 部署

**优先级**: 必须 | **依赖**: US-001

**验收标准**:
- [ ] docker-compose.yml 包含 web、scheduler、caddy 三容器
- [ ] web 启动前自动 `alembic upgrade head`
- [ ] scheduler 使用 supercronic 执行 crontab
- [ ] 三容器共享 ./data 目录
- [ ] Caddyfile 通过 ${DOMAIN} 读取域名
- [ ] Dockerfile 多阶段构建：Node 构建前端 → Python 运行

### US-027: Pipeline 主流程编排

**优先级**: 必须 | **依赖**: US-013, US-019, US-021, US-024, US-028, US-029

**验收标准**:
- [ ] `python -m app.cli pipeline`: fetch → process → digest
- [ ] 上一步失败不执行下一步
- [ ] 不在 push_days → job_runs status=skipped，不抓取不加工
- [ ] 执行前写 job_runs: running, trigger=cron
- [ ] 成功: completed | 失败: failed + error_message + webhook通知

### US-027b: 手动触发抓取

**优先级**: 应该 | **依赖**: US-013, US-028

**验收标准**:
- [ ] `POST /api/manual/fetch` 创建 job_runs（job_type='fetch', trigger_source='manual'）
- [ ] 仅执行 `fetch_service.run_daily_fetch()`，**不触发后续 process/digest**
- [ ] 抓取完成后管理员可通过 `POST /api/digest/regenerate` 触发 process + digest 全链路
- [ ] 检查增强锁（同日有 pipeline running → 409）
- [ ] 成功返回 200 `{"message": "抓取完成", "job_run_id": ..., "new_tweets": ...}`
- [ ] 失败返回 500 + error_message，job_runs 标记 failed

### US-028: 任务幂等锁

**优先级**: 必须 | **依赖**: US-002

**验收标准**:
- [ ] 基本锁：同日+同job_type有running → 跳过
- [ ] 增强锁：同日有pipeline running时，以下返回 409:
  - POST /api/manual/fetch
  - POST /api/digest/regenerate
  - POST /api/digest/publish
- [ ] 409 中文提示："当前有任务在运行中，请稍后再试"
- [ ] 编辑操作不受锁影响
- [ ] running残留修复：CLI `python -m app.cli unlock` 将当日所有 status='running' 的 job_runs 标记为 failed + error_message='manually unlocked'
- [ ] 自动清理：running 超过 2 小时自动标记 failed（在 pipeline 启动时检查）
- [ ] **unlock 命令必须有测试覆盖**

### US-029: 通知服务（Webhook）

**优先级**: 必须 | **依赖**: US-001

**验收标准**:
- [ ] 从 system_config 读取 webhook URL
- [ ] 企业微信格式: `{"msgtype":"text","text":{"content":"【智曦告警】{title}\n{message}"}}`
- [ ] 包含：失败时间、环节、错误摘要
- [ ] URL 为空时跳过
- [ ] 发送失败记录日志，不影响主流程

### US-035: 重新生成草稿

**优先级**: 必须 | **依赖**: US-027, US-028

**验收标准**:
- [ ] `POST /api/digest/regenerate` 需前端二次确认弹窗
- [ ] 检查增强锁（同日running → 409）
- [ ] **重置步骤（M2 重跑前必须执行）**: 将当日所有推文的 `is_processed` 重置为 false、`is_ai_relevant` 重置为 true、`topic_id` 重置为 null，以便全局分析从零开始
- [ ] 流程: 旧版本 is_current=false → M2 全量重跑 → M3 新版本(version+1)
- [ ] **当日尚无草稿时**: regenerate 等价于首次生成（创建 v1 而非 v+1），跳过 is_current=false 步骤。这使得管理员在 manual/fetch 后可以通过 regenerate 触发 process+digest
- [ ] **topics 表处理**: regenerate 时不删除旧 topics 记录；新一轮全局分析创建新 topics（新 id），推文的 topic_id 更新指向新 topics。旧版本 digest_items 通过 snapshot 自包含，不依赖 topics 当前值
- [ ] **tweets 表处理**: run_daily_process 会覆盖所有推文的 AI 字段（含手动补录推文的 title/translation/comment），这是预期行为。原始数据（original_text/互动量等）不变
- [ ] 旧版本 digest_items 快照保留不动
- [ ] 旧预览 token 失效
- [ ] 已 published 版本不可修改但可 regenerate 创建新 draft
- [ ] **status=failed 的版本也可以 regenerate** 创建新 draft
- [ ] job_runs trigger_source=regenerate
- [ ] **执行方式**: 在请求处理线程内同步执行（可能耗时数分钟）。前端发起请求后显示全屏 loading 遮罩，请求返回后刷新页面。不使用异步任务队列
- [ ] **失败回滚**: 如果 M2 成功但 M3 失败，在 finally 块中将旧版本 is_current 恢复为 true（如有旧版本）。tweets/topics 的 AI 字段被覆盖不可逆，但旧版本快照不受影响。job_runs 标记 failed + 发送通知

### US-036: 手动发布模式

**优先级**: 必须 | **依赖**: US-025, US-030

**验收标准**:
- [ ] `GET /api/digest/markdown` → 直接读取 `daily_digest.content_markdown` 字段返回（该字段在每次编辑/排序/剔除/恢复/导读编辑后同步更新）
- [ ] 前端"一键复制"按钮（Clipboard API）
- [ ] `POST /api/digest/mark-published` → status=published, published_at=now
- [ ] 同日最多1个 published 版本
- [ ] 前端流程：确认发布 → 判断 publish_mode → manual 弹出 Markdown + 复制 + "已发布"按钮

### US-037: API 自动发布（预留）

**优先级**: 可以 | **依赖**: US-036

**验收标准**:
- [ ] wechat_client.py 封装微信API（access_token → 上传 → 群发）
- [ ] WECHAT_APP_ID/SECRET 为空时返回"微信API未配置"
- [ ] `POST /api/digest/publish` 根据 publish_mode 分支
- [ ] 失败: status=failed + error_message，支持重试
- [ ] **MVP 实现范围**: wechat_client.py 为**空壳**，仅定义接口签名并在调用时 raise `NotImplementedError("微信API自动发布功能将在公众号认证后实现")`。`publish_mode='api'` 时直接返回 501

### US-038: 预览功能（登录态）

**优先级**: 应该 | **依赖**: US-025, US-030

**验收标准**:
- [ ] `GET /api/digest/preview` → JSON（digest + items + Markdown）
- [ ] 前端 ArticlePreview.vue 全屏预览
- [ ] 清新简约风：白底、淡色分割线、圆角卡片

### US-042: 推送历史页

**优先级**: 应该 | **依赖**: US-039

**验收标准**:
- [ ] `GET /api/history` 分页，每日期只返回一条。**版本选择优先级**: (1) status='published' → (2) is_current=true → (3) version 最大的记录。如果某天所有版本都不满足前两个条件（如 regenerate 失败后），取最新版本
- [ ] `GET /api/history/{id}` 完整信息 + items快照
- [ ] 前端列表页：日期列表 + Badge + 点击详情
- [ ] **前端详情页** (`/history/:id` → `HistoryDetail.vue`)：展示该版本完整 digest_items 快照内容，布局与今日内容页一致但**只读、不显示操作按钮**（无编辑/排序/剔除/发布）

### US-043: API 成本监控

**优先级**: 应该 | **依赖**: US-002

**验收标准**:
- [ ] `GET /api/dashboard/api-costs` → 今日/本月各service汇总
- [ ] `GET /api/dashboard/api-costs/daily` → 30天按日趋势
- [ ] estimated_cost 标注为"估算值"

### US-044: Dashboard 日志展示

**优先级**: 可以 | **依赖**: US-039, US-004

**验收标准**:
- [ ] `GET /api/dashboard/logs` → 最近100条，支持按级别过滤
- [ ] 前端：代码风格、可滚动、ERROR红色高亮

### US-050: API 接口测试

**优先级**: 必须 | **依赖**: US-008, US-030

**验收标准**:
- [ ] tests/test_api.py：认证流程、setup、digest CRUD、权限409、锁409
- [ ] 外部 API 全 Mock

### US-051: 状态流转测试

**优先级**: 必须 | **依赖**: US-024, US-035

**验收标准**:
- [ ] draft→published、draft→regenerate→v2、published后regenerate→new draft
- [ ] **failed→regenerate→new draft**（发布失败后也可 regenerate）
- [ ] **failed→重试发布→published**
- [ ] 已published不可修改（编辑返回409）
- [ ] is_current 切换正确（旧版本false，新版本true）
- [ ] regenerate 失败时旧版本 is_current 恢复为 true

---

## 阶段 P4: 联调 + 试运行

### US-009: 预览签名链接

**优先级**: 应该 | **依赖**: US-025, US-008

**验收标准**:
- [ ] `POST /api/digest/preview-link` 生成 token（`secrets.token_urlsafe(32)`），有效期24h
- [ ] 同一 daily_digest 只允许一个有效 token，生成新token旧token覆盖失效
- [ ] `GET /api/digest/preview/{token}` 验证签名+过期+is_current
- [ ] 返回 JSON 数据，前端 SPA `/preview?token=xxx` 路由渲染
- [ ] token 对应版本 is_current=false 时自动失效
- [ ] 无效 token 返回 403 `{"detail": "链接已失效或过期"}`

### US-016: 手动补录推文

**优先级**: 应该 | **依赖**: US-011, US-021, US-024, US-030

**验收标准**:
- [ ] `POST /api/digest/add-tweet` 接受 `{tweet_url}`
- [ ] 提取 tweet_id，调用 X API 抓取
- [ ] 入库 source='manual', is_ai_relevant=true
- [ ] 执行单条 AI 加工（第二步 Prompt），生成 title/translation/comment
- [ ] ai_importance_score **固定 50**
- [ ] base_score 按公式计算。**normalize 使用当日已有推文的 min/max 范围**（不重算已有推文的 normalized_base 和 heat_score）。若补录推文 base_score 超出现有范围，其 normalized_base 截断到 0 或 100。其他推文的 heat_score 和快照不变
- [ ] 创建 digest_item，display_order=max+1，写入快照
- [ ] **不触发全局重算**
- [ ] 权限检查：仅 current draft 可操作
- [ ] **当日无草稿时**: 返回 409 + "今日草稿尚未生成，请等待 pipeline 完成或手动触发后再补录"
- [ ] **AI 加工失败时**: 推文仍保留在 tweets 表（is_processed=false），但不创建 digest_item。返回 502 "推文已入库但AI加工失败，将在下次重新生成时处理"
- [ ] 错误响应: 400 "无效的推文URL" | 409 "该推文已存在" / "当前版本不可编辑" / "今日草稿尚未生成..." | 502 "推文抓取失败" / "推文已入库但AI加工失败..."

### US-045: 冷门日处理

**优先级**: 必须 | **依赖**: US-024

**验收标准**:
- [ ] 低于 min_articles 时仍生成草稿
- [ ] Dashboard + 今日内容页黄色提示："今日资讯较少（N条）"
- [ ] 0条推文 → 空草稿 + 默认导读"今日 AI 领域较为平静"

### US-046: 超时未审核处理

**优先级**: 必须 | **依赖**: US-027

**验收标准**:
- [ ] pipeline 生成草稿后不设自动发布定时器
- [ ] 草稿保持 draft 直到管理员操作
- [ ] Dashboard 显示"待审核"
- [ ] push_time **纯展示参考**，不触发任何自动操作

---

## 补充规则（R.11）

1. **Reorder 排除项**: reorder 只需传 non-excluded 条目。恢复时 display_order = max(non-excluded) + 1
2. **Regenerate 手动补录**: regenerate 重置所有推文（含 manual），ai_importance_score 由 AI 重新评分（不保持50）
3. **tweet_url 构建**: `f"https://x.com/{twitter_handle}/status/{tweet_id}"`
4. **display_mode**: MVP 预留字段，固定 `simple`，不影响渲染
