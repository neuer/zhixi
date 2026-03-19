"""日报相关类型。"""

from pydantic import BaseModel


class ReorderInput(BaseModel):
    """排序请求条目。"""

    id: int
    display_order: int
    is_pinned: bool = False
