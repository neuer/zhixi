"""热度分计算 — 兼容层，实际实现已移至 app.lib.heat_calculator。

保留此文件以兼容现有 import 路径（app.processor.heat_calculator）。
新代码请直接 import app.lib.heat_calculator。
"""

from app.lib.heat_calculator import (
    calculate_base_score,
    calculate_heat_score,
    calculate_hours_since_post,
    get_reference_time,
    normalize_scores,
)

__all__ = [
    "calculate_base_score",
    "calculate_heat_score",
    "calculate_hours_since_post",
    "get_reference_time",
    "normalize_scores",
]
