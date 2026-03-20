"""accounts 路由 — 大V账号 CRUD。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_account_service
from app.schemas.account_types import (
    AccountCreate,
    AccountListResponse,
    AccountResponse,
    AccountUpdate,
)
from app.schemas.digest_types import MessageResponse
from app.services.account_service import AccountDuplicateError, AccountNotFoundError, AccountService

# TODO: US-008 添加 Depends(get_current_admin)
router = APIRouter()


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: AccountService = Depends(get_account_service),
) -> AccountListResponse:
    """获取大V账号分页列表。"""
    return await svc.list_accounts(page=page, page_size=page_size)


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    data: AccountCreate,
    svc: AccountService = Depends(get_account_service),
) -> AccountResponse:
    """创建大V账号。

    自动调用 X API 拉取用户信息。请求体含 display_name 时跳过 X API，走手动模式。
    X API 失败时由全局异常处理器返回 502 + allow_manual。
    """
    try:
        account = await svc.create_account(data)
    except AccountDuplicateError:
        raise HTTPException(status_code=409, detail="该账号已存在") from None
    # XApiError 不在此捕获，由 main.py 全局处理器处理
    return AccountResponse.model_validate(account)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    data: AccountUpdate,
    svc: AccountService = Depends(get_account_service),
) -> AccountResponse:
    """更新账号配置（weight、is_active）。"""
    try:
        account = await svc.update_account(account_id, data)
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="账号不存在") from None
    return AccountResponse.model_validate(account)


@router.delete("/{account_id}", response_model=MessageResponse)
async def delete_account(
    account_id: int,
    svc: AccountService = Depends(get_account_service),
) -> MessageResponse:
    """软删除账号（设 is_active=false）。"""
    try:
        await svc.delete_account(account_id)
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="账号不存在") from None
    return MessageResponse(message="账号已删除")
