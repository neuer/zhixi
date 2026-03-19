"""US-003 + US-053 — SQLite 备份与清理服务测试。"""

import os
import sqlite3
import time
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun
from app.services.backup_service import BackupService

# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    """临时备份目录。"""
    d = tmp_path / "backups"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def logs_dir(tmp_path: Path) -> Path:
    """临时日志目录。"""
    d = tmp_path / "logs"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def source_db(tmp_path: Path) -> Path:
    """创建一个包含真实数据的 SQLite 源数据库。"""
    db_path = tmp_path / "zhixi.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test_table VALUES (1, 'hello')")
    conn.commit()
    conn.close()
    return db_path


# ─── 备份测试 ────────────────────────────────────────────────────────────────


async def test_backup_creates_file(db: AsyncSession, source_db: Path, backup_dir: Path) -> None:
    """备份后在 backup_dir 中生成 zhixi_YYYYMMDD_HHMMSS.db 格式文件。"""
    svc = BackupService(db)
    result = await svc.run_backup(db_path=str(source_db), backup_dir=str(backup_dir))

    assert result.success is True
    assert result.file_path != ""

    backup_file = Path(result.file_path)
    assert backup_file.exists()
    assert backup_file.suffix == ".db"
    # 检验文件名格式：zhixi_YYYYMMDD_HHMMSS.db
    assert backup_file.name.startswith("zhixi_")
    name_no_ext = backup_file.stem  # zhixi_YYYYMMDD_HHMMSS
    parts = name_no_ext.split("_")
    assert len(parts) == 3
    assert len(parts[1]) == 8  # YYYYMMDD
    assert len(parts[2]) == 6  # HHMMSS
    assert parts[1].isdigit()
    assert parts[2].isdigit()


async def test_backup_file_is_valid_sqlite(
    db: AsyncSession, source_db: Path, backup_dir: Path
) -> None:
    """备份文件可用 sqlite3 打开，且原始数据可读取。"""
    svc = BackupService(db)
    result = await svc.run_backup(db_path=str(source_db), backup_dir=str(backup_dir))

    assert result.success is True

    conn = sqlite3.connect(result.file_path)
    rows = conn.execute("SELECT id, name FROM test_table").fetchall()
    conn.close()

    assert rows == [(1, "hello")]


async def test_backup_writes_job_run_completed(
    db: AsyncSession, source_db: Path, backup_dir: Path
) -> None:
    """成功备份写入 job_runs 表，status=completed。"""
    svc = BackupService(db)
    result = await svc.run_backup(db_path=str(source_db), backup_dir=str(backup_dir))

    assert result.success is True

    rows = (await db.execute(select(JobRun).where(JobRun.job_type == "backup"))).scalars().all()
    assert len(rows) == 1
    job = rows[0]
    assert job.status == "completed"
    assert job.trigger_source == "manual"
    assert job.finished_at is not None
    assert job.error_message is None


async def test_backup_writes_job_run_failed(db: AsyncSession, backup_dir: Path) -> None:
    """备份失败时写入 job_runs 表，status=failed 且含 error_message。"""
    svc = BackupService(db)
    # 使用不存在的数据库路径触发失败
    result = await svc.run_backup(
        db_path="/nonexistent/path/does_not_exist.db",
        backup_dir=str(backup_dir),
    )

    assert result.success is False
    assert result.error != ""

    rows = (await db.execute(select(JobRun).where(JobRun.job_type == "backup"))).scalars().all()
    assert len(rows) == 1
    job = rows[0]
    assert job.status == "failed"
    assert job.error_message is not None
    assert job.error_message != ""
    assert job.finished_at is not None


# ─── 清理测试 ────────────────────────────────────────────────────────────────


def _set_old_mtime(path: Path, days: int = 31) -> None:
    """将文件 mtime 设置为 N 天前。"""
    old_time = time.time() - days * 86400
    os.utime(str(path), (old_time, old_time))


async def test_cleanup_removes_old_backups(
    db: AsyncSession, backup_dir: Path, logs_dir: Path
) -> None:
    """删除 mtime 超过 30 天的备份文件。"""
    old_file = backup_dir / "zhixi_20240101_000000.db"
    old_file.write_bytes(b"old backup")
    _set_old_mtime(old_file, days=31)

    recent_file = backup_dir / "zhixi_20260301_120000.db"
    recent_file.write_bytes(b"recent backup")

    svc = BackupService(db)
    removed = await svc.run_cleanup(backup_dir=str(backup_dir), logs_dir=str(logs_dir))

    assert removed >= 1
    assert not old_file.exists()
    assert recent_file.exists()


async def test_cleanup_keeps_recent_backups(
    db: AsyncSession, backup_dir: Path, logs_dir: Path
) -> None:
    """30 天内的备份文件不被删除。"""
    recent_file = backup_dir / "zhixi_20260318_080000.db"
    recent_file.write_bytes(b"recent backup")
    # mtime 保持默认（当前时间）

    svc = BackupService(db)
    removed = await svc.run_cleanup(backup_dir=str(backup_dir), logs_dir=str(logs_dir))

    assert removed == 0
    assert recent_file.exists()


async def test_cleanup_removes_old_logs(db: AsyncSession, backup_dir: Path, logs_dir: Path) -> None:
    """删除 mtime 超过 30 天的日志文件。"""
    old_log = logs_dir / "app_20240101.log"
    old_log.write_text("old log content")
    _set_old_mtime(old_log, days=35)

    recent_log = logs_dir / "app_20260318.log"
    recent_log.write_text("recent log content")

    svc = BackupService(db)
    removed = await svc.run_cleanup(backup_dir=str(backup_dir), logs_dir=str(logs_dir))

    assert removed >= 1
    assert not old_log.exists()
    assert recent_log.exists()
