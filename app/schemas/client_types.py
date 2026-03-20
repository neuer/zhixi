"""外部客户端响应类型。"""

from pydantic import BaseModel


class ClaudeResponse(BaseModel):
    """Claude API 调用响应。"""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    duration_ms: int
    estimated_cost: float = 0.0
