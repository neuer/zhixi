"""Alembic 迁移环境 — 从 app.config 读取 DB URL，同步模式运行。"""

from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from app.config import settings
from app.database import Base
from app.models import *  # noqa: F403 — 确保所有模型注册到 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Alembic 用同步引擎，直接使用原始 DATABASE_URL（sqlite:///...）
sync_url = settings.DATABASE_URL


def run_migrations_offline() -> None:
    """离线模式 — 仅生成 SQL。"""
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式 — 连接 DB 执行。"""
    connectable = create_engine(sync_url)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
