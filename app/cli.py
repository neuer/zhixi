"""Typer CLI — pipeline/backup/cleanup/unlock 子命令。"""

import asyncio

import typer

cli = typer.Typer(help="智曦 CLI 工具")


@cli.command()
def pipeline() -> None:
    """每日主流程：抓取 → AI 加工 → 草稿生成。"""
    asyncio.run(_run_pipeline())


@cli.command()
def backup() -> None:
    """SQLite 数据库备份。"""
    asyncio.run(_run_backup())


@cli.command()
def cleanup() -> None:
    """清理过期备份和日志文件。"""
    asyncio.run(_run_cleanup())


@cli.command()
def unlock() -> None:
    """解锁卡住的任务（将 running 标记为 failed）。"""
    asyncio.run(_run_unlock())


async def _run_pipeline() -> None:
    """执行每日主流程并根据结果输出状态。"""
    from app.database import async_session_factory
    from app.services.pipeline_service import run_pipeline

    async with async_session_factory() as db:
        try:
            result = await run_pipeline(db, trigger_source="cron")
            await db.commit()

            if result.status == "skipped":
                typer.echo(f"Pipeline skipped: {result.error_message or 'not a push day'}")
            elif result.status == "completed":
                typer.echo("Pipeline completed successfully")
            elif result.status == "failed":
                typer.echo(
                    f"Pipeline failed at [{result.failed_step}]: {result.error_message}",
                    err=True,
                )
                raise typer.Exit(code=1)
        except typer.Exit:
            raise
        except Exception:
            await db.rollback()
            raise


async def _run_backup() -> None:
    """执行 SQLite 备份并输出结果。"""
    from app.database import async_session_factory
    from app.services.backup_service import BackupService

    async with async_session_factory() as db:
        try:
            svc = BackupService(db)
            result = await svc.run_backup()
            await db.commit()
            if result.success:
                typer.echo(f"Backup completed: {result.file_path}")
            else:
                typer.echo(f"Backup failed: {result.error}", err=True)
                raise typer.Exit(code=1)
        except typer.Exit:
            raise
        except Exception:
            await db.rollback()
            raise


async def _run_cleanup() -> None:
    """清理过期备份和日志文件。"""
    from app.database import async_session_factory
    from app.services.backup_service import BackupService

    async with async_session_factory() as db:
        try:
            svc = BackupService(db)
            removed = await svc.run_cleanup()
            await db.commit()
            typer.echo(f"Cleanup completed: removed {removed} files")
        except Exception:
            await db.rollback()
            raise


async def _run_unlock() -> None:
    """解锁当日所有 running 状态的 job_runs。"""
    from app.config import get_today_digest_date
    from app.database import async_session_factory
    from app.services.lock_service import unlock_all_running

    digest_date = get_today_digest_date()

    async with async_session_factory() as db:
        try:
            count = await unlock_all_running(db, digest_date)
            await db.commit()
            if count > 0:
                typer.echo(f"已解锁 {count} 个卡住的任务（{digest_date}）")
            else:
                typer.echo(f"当日无 running 状态的任务（{digest_date}）")
        except Exception:
            await db.rollback()
            raise


if __name__ == "__main__":
    cli()
