"""Pipeline 主流程编排相关类型定义。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.schemas.fetcher_types import FetchResult
from app.schemas.processor_types import ProcessResult


class PipelineResult(BaseModel):
    """Pipeline 执行结果。"""

    status: Literal["completed", "failed", "skipped"]
    """执行状态。"""

    digest_date: date
    """执行日期（北京时间自然日）。"""

    job_run_id: int | None = None
    """关联的 job_run 记录 ID。"""

    error_message: str | None = None
    """失败时的错误描述。"""

    failed_step: Literal["fetch", "process", "digest"] | None = None
    """失败的步骤。"""

    fetch_result: FetchResult | None = None
    """fetch 步骤执行结果。"""

    process_result: ProcessResult | None = None
    """process 步骤执行结果。"""
