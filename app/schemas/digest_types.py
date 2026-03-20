"""日报相关类型。"""

from pydantic import BaseModel, Field


class ReorderInput(BaseModel):
    """排序请求条目。"""

    id: int = Field(gt=0)
    display_order: int = Field(ge=0)
    is_pinned: bool = False


class MessageResponse(BaseModel):
    """通用消息响应。"""

    message: str
