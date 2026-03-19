"""数据库迁移测试 — 表结构、外键、索引、种子数据。"""

from sqlalchemy import Connection, inspect, select
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
        table_names = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    assert EXPECTED_TABLES.issubset(set(table_names))


async def test_system_config_seed_data(seeded_db: AsyncSession) -> None:
    """system_config 包含全部默认配置。"""
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


def _get_foreign_keys(sync_conn: Connection) -> dict[str, list[dict[str, object]]]:
    """收集各表的外键信息。"""
    insp = inspect(sync_conn)
    result: dict[str, list[dict[str, object]]] = {}
    for table in insp.get_table_names():
        fks: list[dict[str, object]] = list(insp.get_foreign_keys(table))  # type: ignore[assignment]
        if fks:
            result[table] = fks
    return result


async def test_foreign_keys(db_engine) -> None:
    """关键外键约束存在。"""
    async with db_engine.connect() as conn:
        fk_map = await conn.run_sync(_get_foreign_keys)

    # tweets.account_id → twitter_accounts.id
    tweets_fks = [(fk["referred_table"], fk["referred_columns"]) for fk in fk_map.get("tweets", [])]
    assert ("twitter_accounts", ["id"]) in tweets_fks
    # tweets.topic_id → topics.id
    assert ("topics", ["id"]) in tweets_fks

    # digest_items.digest_id → daily_digest.id
    di_fks = [
        (fk["referred_table"], fk["referred_columns"]) for fk in fk_map.get("digest_items", [])
    ]
    assert ("daily_digest", ["id"]) in di_fks

    # api_cost_log.job_run_id → job_runs.id
    acl_fks = [
        (fk["referred_table"], fk["referred_columns"]) for fk in fk_map.get("api_cost_log", [])
    ]
    assert ("job_runs", ["id"]) in acl_fks

    # fetch_log.job_run_id → job_runs.id
    fl_fks = [(fk["referred_table"], fk["referred_columns"]) for fk in fk_map.get("fetch_log", [])]
    assert ("job_runs", ["id"]) in fl_fks

    # daily_digest.job_run_id → job_runs.id
    dd_fks = [
        (fk["referred_table"], fk["referred_columns"]) for fk in fk_map.get("daily_digest", [])
    ]
    assert ("job_runs", ["id"]) in dd_fks


async def test_digest_items_unique_constraint(db_engine) -> None:
    """digest_items(digest_id, item_type, item_ref_id) 联合唯一约束存在。"""
    async with db_engine.connect() as conn:
        uniques = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("digest_items")
        )
    column_sets = [set(u["column_names"]) for u in uniques]
    assert {"digest_id", "item_type", "item_ref_id"} in column_sets


async def test_tweet_indexes(db_engine) -> None:
    """tweets 表关键索引存在。"""
    async with db_engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes("tweets"))
    indexed_columns = [set(idx["column_names"]) for idx in indexes]
    for col in ["heat_score", "digest_date", "is_processed", "topic_id"]:
        assert any(col in cols for cols in indexed_columns), f"缺少 {col} 索引"


async def test_system_config_key_unique(db_engine) -> None:
    """system_config.key 有唯一约束。"""
    async with db_engine.connect() as conn:
        uniques = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("system_config")
        )
    has_key_unique = any("key" in u["column_names"] for u in uniques)
    assert has_key_unique, "system_config.key 缺少唯一约束"


async def test_twitter_accounts_handle_unique(db_engine) -> None:
    """twitter_accounts.twitter_handle 有唯一约束。"""
    async with db_engine.connect() as conn:
        uniques = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("twitter_accounts")
        )
    has_handle_unique = any("twitter_handle" in u["column_names"] for u in uniques)
    assert has_handle_unique, "twitter_accounts.twitter_handle 缺少唯一约束"


async def test_tweets_tweet_id_unique(db_engine) -> None:
    """tweets.tweet_id 有唯一约束。"""
    async with db_engine.connect() as conn:
        uniques = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("tweets")
        )
    has_tweet_id_unique = any("tweet_id" in u["column_names"] for u in uniques)
    assert has_tweet_id_unique, "tweets.tweet_id 缺少唯一约束"
