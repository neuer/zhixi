"""发布相关类型。"""

from pydantic import BaseModel, model_validator

from app.schemas.enums import DigestStatus


class PublishResult(BaseModel):
    """发布结果。"""

    success: bool
    status: DigestStatus
    error_message: str | None = None

    @model_validator(mode="after")
    def check_error_on_failure(self) -> "PublishResult":
        """失败时 error_message 不能为空。"""
        if not self.success and not self.error_message:
            msg = "发布失败时必须提供 error_message"
            raise ValueError(msg)
        return self
