# US-002: 数据库初始化与迁移 实施计划

> **执行结果**: ✅ 全部完成（2026-03-19）
> - Alembic 初始化 + 初始迁移（9 张表 + 种子数据）
> - 8 个迁移测试全部通过
> - 质量门禁全部绿灯（ruff, pyright, lint-imports）
> - 注意：env.py 使用独立同步引擎（`create_engine`），而非 async engine 的 sync_engine

**Goal:** 配置 Alembic，生成包含全部 9 张表和 system_config 种子数据的初始迁移脚本，确保 `alembic upgrade head` 从零创建完整数据库。

**Architecture:** 在项目根目录放置 `alembic.ini`，`alembic/env.py` 使用 sync engine 运行迁移（Alembic 不需要异步）。初始迁移通过 `--autogenerate` 生成建表语句，手动追加 `op.bulk_insert` 写入 system_config 默认数据。

**Tech Stack:** SQLAlchemy 2.x + Alembic + aiosqlite + SQLite WAL

---

## 上下文

US-001 已创建全部 9 个 ORM 模型文件和 `database.py` 引擎配置。当前缺少 Alembic 初始化和迁移脚本。本 US 补全数据库基础设施，使后续所有 US 可以正常使用 DB。

## 现有关键文件

- `app/database.py` — Base 基类、engine、async_session_factory、WAL pragma
- `app/models/__init__.py` — 集中注册 9 个模型
- `app/models/*.py` — 9 个模型定义（TwitterAccount, Tweet, Topic, DailyDigest, DigestItem, SystemConfig, JobRun, ApiCostLog, FetchLog）
- `app/config.py` — Settings + get_system_config()
- `tests/conftest.py` — 内存 DB fixture + seeded_db fixture
- `pyproject.toml` — 已包含 alembic 依赖

## 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| 创建 | `alembic.ini` | 项目根目录，Alembic 主配置 |
| 创建 | `alembic/env.py` | 迁移运行环境，连接 Base.metadata |
| 创建 | `alembic/script.py.mako` | 迁移脚本模板 |
| 创建 | `alembic/versions/<hash>_initial_schema.py` | 初始迁移：建表 + 种子数据 |
| 创建 | `tests/test_migration.py` | 迁移测试 |

---

## Task 1: 初始化 Alembic

**Files:**
- 创建: `alembic.ini`（项目根目录）
- 创建: `alembic/env.py`
- 创建: `alembic/script.py.mako`
- 创建: `alembic/versions/`（空目录）

- [ ] **Step 1: 运行 alembic init 生成骨架**

```bash
cd /Users/tongstark/ZhiXi && uv run alembic init alembic
```

这会在项目根目录生成 `alembic.ini` 和 `alembic/` 目录。

- [ ] **Step 2: 修改 alembic.ini**

关键修改：
- `sqlalchemy.url` 留空（由 env.py 从 app.config 获取）

```ini
# alembic.ini 中 sqlalchemy.url 行改为空：
sqlalchemy.url =
```

- [ ] **Step 3: 修改 alembic/env.py**

替换为同步方式运行迁移，从 app.database 获取 engine 和 metadata：

```python
"""Alembic 迁移环境 — 同步模式运行。"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.database import Base, engine
from app.models import *  # noqa: F403 — 确保所有模型注册到 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式 — 仅生成 SQL。"""
    url = engine.sync_engine.url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式 — 连接 DB 执行。"""
    connectable = engine.sync_engine

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 验证 alembic 能正常启动**

```bash
cd /Users/tongstark/ZhiXi && uv run alembic --help
```

预期：输出 alembic 帮助信息，无 import 错误。

- [ ] **Step 5: 提交 Alembic 骨架**

```bash
git add alembic.ini alembic/
git commit -m "chore(db): 初始化 Alembic 迁移框架"
```

---

## Task 2: 生成初始迁移并追加种子数据

**Files:**
- 创建: `alembic/versions/<hash>_initial_schema.py`（autogenerate 产出后手动追加种子数据）

- [ ] **Step 1: 确保 data/ 目录存在**

```bash
mkdir -p /Users/tongstark/ZhiXi/data
```

- [ ] **Step 2: 运行 autogenerate 生成初始迁移**

```bash
cd /Users/tongstark/ZhiXi && uv run alembic revision --autogenerate -m "initial schema"
```

预期：在 `alembic/versions/` 下生成一个迁移文件，包含 9 张表的 `op.create_table` 调用。

- [ ] **Step 3: 审查生成的迁移脚本**

检查要点：
1. 9 张表全部存在：twitter_accounts, tweets, topics, daily_digest, digest_items, system_config, job_runs, api_cost_log, fetch_log
2. 所有外键正确：tweets.account_id → twitter_accounts.id, tweets.topic_id → topics.id, daily_digest.job_run_id → job_runs.id, digest_items.digest_id → daily_digest.id, api_cost_log.job_run_id → job_runs.id, fetch_log.job_run_id → job_runs.id
3. 索引：tweets 的 heat_score DESC / digest_date / is_processed / topic_id
4. UniqueConstraint：digest_items(digest_id, item_type, item_ref_id)
5. Unique：twitter_accounts.twitter_handle, tweets.tweet_id, system_config.key

- [ ] **Step 4: 在 upgrade() 末尾追加 system_config 种子数据**

在迁移文件的 `upgrade()` 函数末尾追加：

```python
    # system_config 种子数据
    system_config = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
        sa.column("description", sa.String),
    )
    op.bulk_insert(
        system_config,
        [
            {"key": "push_time", "value": "08:00", "description": "推送参考时间"},
            {"key": "push_days", "value": "1,2,3,4,5,6,7", "description": "推送日（1=周一）"},
            {"key": "top_n", "value": "10", "description": "每日推送条数上限"},
            {"key": "min_articles", "value": "1", "description": "低于此值显示警告"},
            {"key": "display_mode", "value": "simple", "description": "展示模式（预留）"},
            {"key": "publish_mode", "value": "manual", "description": "发布模式"},
            {"key": "enable_cover_generation", "value": "false", "description": "封面图生成开关"},
            {"key": "cover_generation_timeout", "value": "30", "description": "封面图超时（秒）"},
            {"key": "notification_webhook_url", "value": "", "description": "通知 Webhook URL"},
            {"key": "admin_password_hash", "value": "", "description": "管理员密码哈希"},
        ],
    )
```

- [ ] **Step 5: 在 downgrade() 中追加删除种子数据**

在 downgrade() 的 `op.drop_table("system_config")` 之前追加（如果 drop_table 已包含则无需额外操作，因为删表会自动删数据）。实际上 downgrade 已有 `op.drop_table("system_config")`，删表即删数据，无需额外操作。

- [ ] **Step 6: 从零执行 upgrade head 验证**

```bash
# 删除已有 DB（如有）
rm -f /Users/tongstark/ZhiXi/data/zhixi.db
cd /Users/tongstark/ZhiXi && uv run alembic upgrade head
```

预期：无错误，`data/zhixi.db` 被创建。

- [ ] **Step 7: 验证表结构和种子数据**

```bash
cd /Users/tongstark/ZhiXi && uv run python -c "
import sqlite3
conn = sqlite3.connect('data/zhixi.db')
cursor = conn.cursor()

# 检查所有表
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\")
tables = [r[0] for r in cursor.fetchall()]
print('Tables:', tables)

# 检查 system_config 种子数据
cursor.execute('SELECT key, value FROM system_config ORDER BY key')
for row in cursor.fetchall():
    print(f'  {row[0]} = {row[1]}')

# 检查 WAL 模式
cursor.execute('PRAGMA journal_mode')
print('Journal mode:', cursor.fetchone()[0])

conn.close()
"
```

预期：9 张表 + alembic_version 表、10 条 system_config 记录、WAL 模式。

- [ ] **Step 8: 提交迁移脚本**

```bash
git add alembic/versions/
git commit -m "feat(db): US-002 初始迁移 — 9 张表 + system_config 种子数据"
```

---

## Task 3: 编写迁移测试

**Files:**
- 创建: `tests/test_migration.py`

- [ ] **Step 1: 编写测试 — 验证全部表创建成功**

```python
"""数据库迁移测试。"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import SystemConfig

EXPECTED_TABLES = {
    "twitter_accounts",
    "tweets",
    "topics",
    "daily_digest",
    "digest_items",
    "system_config",
    "job_runs",
    "api_cost_log",
    "fetch_log",
}


async def test_all_tables_created(db_engine) -> None:
    """upgrade head 后 9 张表全部存在。"""
    async with db_engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    assert EXPECTED_TABLES.issubset(set(table_names))
```

- [ ] **Step 2: 编写测试 — 验证 system_config 种子数据（seeded_db fixture）**

```python
async def test_system_config_seed_data(seeded_db: AsyncSession) -> None:
    """system_config 包含全部默认配置。"""
    from sqlalchemy import select

    result = await seeded_db.execute(select(SystemConfig))
    configs = {row.key: row.value for row in result.scalars().all()}

    assert configs["push_time"] == "08:00"
    assert configs["push_days"] == "1,2,3,4,5,6,7"
    assert configs["top_n"] == "10"
    assert configs["min_articles"] == "1"
    assert configs["display_mode"] == "simple"
    assert configs["publish_mode"] == "manual"
    assert configs["enable_cover_generation"] == "false"
    assert configs["cover_generation_timeout"] == "30"
    assert configs["notification_webhook_url"] == ""
    assert configs["admin_password_hash"] == ""
```

- [ ] **Step 3: 编写测试 — 验证外键约束存在**

```python
async def test_foreign_keys(db_engine) -> None:
    """关键外键约束存在。"""
    async with db_engine.connect() as conn:
        fk_map = await conn.run_sync(_get_foreign_keys)

    # tweets.account_id → twitter_accounts.id
    assert ("twitter_accounts", ["id"]) in [
        (fk["referred_table"], fk["referred_columns"]) for fk in fk_map.get("tweets", [])
    ]
    # tweets.topic_id → topics.id
    assert ("topics", ["id"]) in [
        (fk["referred_table"], fk["referred_columns"]) for fk in fk_map.get("tweets", [])
    ]
    # digest_items.digest_id → daily_digest.id
    assert ("daily_digest", ["id"]) in [
        (fk["referred_table"], fk["referred_columns"]) for fk in fk_map.get("digest_items", [])
    ]


def _get_foreign_keys(sync_conn) -> dict:
    """收集各表的外键信息。"""
    inspector = inspect(sync_conn)
    result = {}
    for table in inspector.get_table_names():
        fks = inspector.get_foreign_keys(table)
        if fks:
            result[table] = fks
    return result
```

- [ ] **Step 4: 编写测试 — 验证 digest_items 联合唯一约束**

```python
async def test_digest_items_unique_constraint(db_engine) -> None:
    """digest_items(digest_id, item_type, item_ref_id) 联合唯一约束存在。"""
    async with db_engine.connect() as conn:
        uniques = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("digest_items")
        )
    column_sets = [set(u["column_names"]) for u in uniques]
    assert {"digest_id", "item_type", "item_ref_id"} in column_sets
```

- [ ] **Step 5: 编写测试 — 验证关键索引存在**

```python
async def test_tweet_indexes(db_engine) -> None:
    """tweets 表关键索引存在。"""
    async with db_engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_indexes("tweets")
        )
    indexed_columns = [set(idx["column_names"]) for idx in indexes]
    # heat_score, digest_date, is_processed, topic_id 各有索引
    for col in ["heat_score", "digest_date", "is_processed", "topic_id"]:
        assert any(col in cols for cols in indexed_columns), f"缺少 {col} 索引"
```

- [ ] **Step 6: 编写测试 — 验证 system_config.key 唯一约束**

```python
async def test_system_config_key_unique(db_engine) -> None:
    """system_config.key 有唯一约束。"""
    async with db_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_columns("system_config")
        )
        uniques = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("system_config")
        )
    # key 列本身 unique=True 或存在 UniqueConstraint
    key_col = next(c for c in columns if c["name"] == "key")
    has_unique = key_col.get("unique", False) or any(
        "key" in u["column_names"] for u in uniques
    )
    assert has_unique, "system_config.key 缺少唯一约束"
```

- [ ] **Step 7: 运行全部测试**

```bash
cd /Users/tongstark/ZhiXi && uv run pytest tests/test_migration.py -v
```

预期：全部 PASS。

- [ ] **Step 8: 运行既有测试确保无回归**

```bash
cd /Users/tongstark/ZhiXi && uv run pytest -v
```

预期：全部 PASS（包括 test_config.py 和 test_logging.py）。

- [ ] **Step 9: 提交测试**

```bash
git add tests/test_migration.py
git commit -m "test(db): US-002 迁移测试 — 表结构、外键、索引、种子数据"
```

---

## Task 4: 质量门禁验证

- [ ] **Step 1: ruff 检查**

```bash
cd /Users/tongstark/ZhiXi && uv run ruff check .
```

- [ ] **Step 2: ruff 格式化检查**

```bash
cd /Users/tongstark/ZhiXi && uv run ruff format --check .
```

- [ ] **Step 3: pyright 类型检查**

```bash
cd /Users/tongstark/ZhiXi && uv run pyright
```

- [ ] **Step 4: import-linter 模块边界检查**

```bash
cd /Users/tongstark/ZhiXi && uv run lint-imports
```

- [ ] **Step 5: 修复门禁发现的问题（如有）并重新提交**

---

## Task 5: 收尾

- [ ] **Step 1: 更新 user-stories.md 状态**

将 US-002 状态从 `🔲 待开发` 改为 `✅ 已完成`。

- [ ] **Step 2: 清理临时 DB 文件**

```bash
rm -f /Users/tongstark/ZhiXi/data/zhixi.db
```

- [ ] **Step 3: 最终提交并推送**

```bash
git push origin HEAD
```

---

## 验证清单

| 验收标准 | 验证方式 |
|---------|---------|
| alembic.ini 在项目根目录 | `ls alembic.ini` |
| 模型使用通用类型 | 已在 US-001 完成，无 SQLite 专属语法 |
| WAL + busy_timeout=5000 | `database.py` set_sqlite_pragma（已有） |
| autogenerate 成功 | Task 2 Step 2 |
| upgrade head 从零建表 | Task 2 Step 6 |
| system_config 默认数据 | Task 2 Step 7 + Task 3 test |
| 外键、索引与模型一致 | Task 3 tests |
| digest_items.snapshot_source_tweets | 模型已有（TEXT, nullable） |
| digest_items UNIQUE(digest_id, item_type, item_ref_id) | 模型已有 + Task 3 test |
