"""FastAPI 应用入口 — 路由注册、中间件、SPA 静态文件。"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.accounts import router as accounts_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.digest import router as digest_router
from app.api.history import router as history_router
from app.api.manual import router as manual_router
from app.api.settings import router as settings_router
from app.api.setup import router as setup_router
from app.clients.x_client import XApiError
from app.config import settings
from app.database import engine
from app.logging_config import setup_logging
from app.middleware import RequestIdMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期 — 启动/关闭钩子。"""
    setup_logging(settings.LOG_LEVEL)
    yield
    await engine.dispose()


app = FastAPI(title="智曦 API", version="1.0.0", lifespan=lifespan)

# request_id 中间件
app.add_middleware(RequestIdMiddleware)

# CORS 仅 DEBUG 模式
if settings.DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 路由注册
app.include_router(setup_router, prefix="/api/setup", tags=["初始化"])
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(accounts_router, prefix="/api/accounts", tags=["大V管理"])
app.include_router(digest_router, prefix="/api/digest", tags=["日报"])
app.include_router(manual_router, prefix="/api/manual", tags=["手动操作"])
app.include_router(settings_router, prefix="/api/settings", tags=["设置"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["仪表盘"])
app.include_router(history_router, prefix="/api/history", tags=["历史记录"])


# 全局异常处理器
logger = logging.getLogger(__name__)


@app.exception_handler(XApiError)
async def handle_x_api_error(_request: Request, exc: XApiError) -> JSONResponse:
    """X API 调用失败 → 502 + allow_manual 标记。"""
    logger.error("X API 调用失败: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=502,
        content={"detail": f"X API拉取失败: {exc}", "allow_manual": True},
    )


# Vue SPA 静态文件（生产环境）
ADMIN_DIST = Path("admin/dist")
if ADMIN_DIST.exists():
    app.mount("/assets", StaticFiles(directory=ADMIN_DIST / "assets"), name="static")

    @app.get("/{path:path}")
    async def spa_fallback(path: str) -> FileResponse:
        """SPA 回退 — 所有非 API 请求返回 index.html，含路径遍历防护。"""
        file_path = ADMIN_DIST / path
        resolved = file_path.resolve()
        if resolved.is_relative_to(ADMIN_DIST.resolve()) and resolved.is_file():
            return FileResponse(resolved)
        return FileResponse(ADMIN_DIST / "index.html")
