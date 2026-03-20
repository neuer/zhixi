"""数据库引擎 — 异步 SQLAlchemy + aiosqlite，WAL 模式。"""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """ORM 模型基类。"""


def _utcnow() -> datetime:
    """返回当前 UTC 时间（供 ORM default/onupdate 使用）。"""
    return datetime.now(UTC)


def get_async_url(url: str) -> str:
    """sqlite:/// → sqlite+aiosqlite:///。"""
    return url.replace("sqlite:///", "sqlite+aiosqlite:///")


engine = create_async_engine(get_async_url(settings.DATABASE_URL), echo=False)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection: object, connection_record: object) -> None:
    """SQLite WAL 模式 + busy_timeout=5000ms。"""
    cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


_logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """依赖注入 — 自动 commit/rollback。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                _logger.error("事务回滚也失败", exc_info=True)
            raise
