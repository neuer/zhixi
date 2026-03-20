"""M2 AI 内容加工模块。"""

from app.processor.analyzer import run_global_analysis
from app.processor.heat_calculator import (
    calculate_base_score,
    calculate_heat_score,
    calculate_hours_since_post,
    get_reference_time,
    normalize_scores,
)
from app.processor.json_validator import JsonValidationError, validate_and_fix
from app.processor.translator import (
    process_aggregated_topic,
    process_single_tweet,
    process_thread,
)

__all__ = [
    "run_global_analysis",
    "calculate_base_score",
    "calculate_heat_score",
    "calculate_hours_since_post",
    "get_reference_time",
    "normalize_scores",
    "JsonValidationError",
    "validate_and_fix",
    "process_aggregated_topic",
    "process_single_tweet",
    "process_thread",
]
