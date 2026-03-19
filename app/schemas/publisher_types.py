"""发布相关类型。"""

from pydantic import BaseModel


class PublishResult(BaseModel):
    """发布结果。"""

    success: bool
    status: str
    error_message: str | None = None
