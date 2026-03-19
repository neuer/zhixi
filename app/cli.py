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
    # TODO: US-027 实现
    typer.echo("Pipeline not implemented yet")


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
    # TODO: US-028 实现
    typer.echo("Unlock not implemented yet")


if __name__ == "__main__":
    cli()
