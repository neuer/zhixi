"""SQLAlchemy 模型集中注册 — Alembic autogenerate 依赖此文件发现所有表。"""

from app.database import _utcnow
from app.models.account import TwitterAccount
from app.models.api_cost_log import ApiCostLog
from app.models.config import SystemConfig
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.fetch_log import FetchLog
from app.models.job_run import JobRun
from app.models.topic import Topic
from app.models.tweet import Tweet

__all__ = [
    "_utcnow",
    "ApiCostLog",
    "DailyDigest",
    "DigestItem",
    "FetchLog",
    "JobRun",
    "SystemConfig",
    "Topic",
    "Tweet",
    "TwitterAccount",
]
