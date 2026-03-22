"""测试基础设施 — 内存 DB、HTTP 客户端、预置数据。"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import create_jwt
from app.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def db_engine():
    """内存 SQLite 引擎。"""
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """测试用异步 Session。"""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """测试用 HTTP 客户端。"""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # I-37: 精确清理自己设置的覆盖，避免影响其他 fixture 或中间件设置的覆盖
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """JWT 认证 header — 用于需要登录的 API 测试。"""
    token, _ = create_jwt("admin")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def authed_client(
    db: AsyncSession, auth_headers: dict[str, str]
) -> AsyncGenerator[AsyncClient, None]:
    """带 JWT 认证的 HTTP 客户端。"""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as c:
        yield c
    # I-37: 精确清理自己设置的覆盖，避免影响其他 fixture 或中间件设置的覆盖
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def seeded_db(db: AsyncSession) -> AsyncSession:
    """预置 system_config 默认数据的 session。"""
    from app.models.config import SystemConfig

    defaults = [
        SystemConfig(key="push_time", value="08:00"),
        SystemConfig(key="push_days", value="1,2,3,4,5,6,7"),
        SystemConfig(key="top_n", value="10"),
        SystemConfig(key="min_articles", value="1"),
        SystemConfig(key="display_mode", value="simple"),
        SystemConfig(key="publish_mode", value="manual"),
        SystemConfig(key="enable_cover_generation", value="false"),
        SystemConfig(key="cover_generation_timeout", value="30"),
        SystemConfig(key="notification_webhook_url", value=""),
        SystemConfig(key="admin_password_hash", value=""),
    ]
    db.add_all(defaults)
    await db.commit()
    return db
