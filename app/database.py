"""数据库引擎 — 异步 SQLAlchemy + aiosqlite，WAL 模式。"""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """ORM 模型基类。"""


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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """依赖注入 — 自动 commit/rollback。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
