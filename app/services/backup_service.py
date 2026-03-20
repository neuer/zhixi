"""backup_service — SQLite 备份与清理编排层。"""

import logging
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun

logger = logging.getLogger(__name__)

# 保留天数
RETENTION_DAYS = 30


class BackupResult(BaseModel):
    """备份操作结果。"""

    success: bool
    file_path: str = ""
    error: str = ""


class BackupService:
    """SQLite 数据库备份与清理服务。"""

    def __init__(self, db: AsyncSession) -> None:
        """注入异步数据库 Session。"""
        self._db = db

    async def run_backup(
        self,
        db_path: str = "data/zhixi.db",
        backup_dir: str = "data/backups",
    ) -> BackupResult:
        """执行 SQLite 在线备份。

        步骤：
        1. 创建 JobRun 记录（status=running）
        2. 使用 sqlite3 在线备份 API（阻塞，MVP CLI 场景可接受）
        3. 成功时更新 job.status=completed，失败时更新 status=failed
        返回 BackupResult。
        """
        now = datetime.now(UTC)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"zhixi_{timestamp}.db"

        # 1. 写入 job_run 记录
        job = JobRun(
            job_type="backup",
            trigger_source="manual",
            status="running",
            started_at=now,
        )
        self._db.add(job)
        await self._db.flush()  # 获取自增 id，但不提交

        # 确保备份目录存在
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        backup_path = str(Path(backup_dir) / backup_filename)

        source_conn: sqlite3.Connection | None = None
        target_conn: sqlite3.Connection | None = None
        try:
            # 2. 执行在线备份（sqlite3 阻塞调用，MVP CLI 场景可接受）
            source_conn = sqlite3.connect(db_path)
            target_conn = sqlite3.connect(backup_path)
            with source_conn, target_conn:
                source_conn.backup(target_conn)

            # 3. 成功
            job.status = "completed"
            job.finished_at = datetime.now(UTC)
            return BackupResult(success=True, file_path=backup_path)

        except Exception as exc:
            # 3. 失败
            logger.error("数据库备份失败: %s", exc, exc_info=True)
            error_msg = str(exc)
            job.status = "failed"
            job.error_message = error_msg
            job.finished_at = datetime.now(UTC)
            # 若备份文件已创建但内容不完整，尝试清理
            try:
                if Path(backup_path).exists():
                    Path(backup_path).unlink()
            except OSError as cleanup_err:
                logger.warning(
                    "备份失败后清理残留文件也失败: path=%s, error=%s",
                    backup_path,
                    cleanup_err,
                )
            return BackupResult(success=False, error=error_msg)
        finally:
            if target_conn:
                target_conn.close()
            if source_conn:
                source_conn.close()

    async def run_cleanup(
        self,
        backup_dir: str = "data/backups",
        logs_dir: str = "data/logs",
    ) -> int:
        """删除 mtime 超过 RETENTION_DAYS 天的备份和日志文件。

        返回删除的文件数量。
        """
        cutoff = time.time() - RETENTION_DAYS * 86400
        removed = 0

        for directory in (backup_dir, logs_dir):
            dir_path = Path(directory)
            if not dir_path.exists():
                continue
            for file_path in dir_path.iterdir():
                if not file_path.is_file():
                    continue
                try:
                    mtime = file_path.stat().st_mtime
                    if mtime < cutoff:
                        file_path.unlink()
                        removed += 1
                except OSError as e:
                    logger.warning("清理过期文件失败: path=%s, error=%s", file_path, e)
                    continue

        return removed
