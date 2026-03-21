"""外部客户端响应类型。"""

from pydantic import BaseModel, Field


class ClaudeResponse(BaseModel):
    """Claude API 调用响应。"""

    content: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model: str
    duration_ms: int = Field(ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)


class GeminiImageResponse(BaseModel):
    """Gemini Imagen API 调用响应。"""

    image_bytes: bytes
    duration_ms: int = Field(ge=0)
    estimated_cost: float = Field(default=0.04, ge=0.0)
