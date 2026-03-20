"""SPA 路径遍历安全防护测试。"""

from pathlib import Path

import pytest


@pytest.fixture
def admin_dist(tmp_path: Path):
    """创建临时 admin/dist 目录结构。"""
    dist = tmp_path / "admin" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>SPA</html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('app')")
    # 模拟敏感文件（在 dist 外部）
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET")
    return dist


def test_path_traversal_resolve_blocks_escape(admin_dist: Path):
    """resolve + is_relative_to 能阻止路径遍历攻击。"""
    # 模拟 spa_fallback 中的路径校验逻辑
    malicious_path = "../../secret.txt"
    file_path = admin_dist / malicious_path
    resolved = file_path.resolve()
    # 解析后的路径不应在 admin_dist 内
    assert not resolved.is_relative_to(admin_dist.resolve())


def test_normal_file_passes_check(admin_dist: Path):
    """admin_dist 内的正常文件应通过校验。"""
    file_path = admin_dist / "index.html"
    resolved = file_path.resolve()
    assert resolved.is_relative_to(admin_dist.resolve())
    assert resolved.is_file()


def test_assets_subdir_passes_check(admin_dist: Path):
    """admin_dist 子目录中的文件也应通过校验。"""
    file_path = admin_dist / "assets" / "app.js"
    resolved = file_path.resolve()
    assert resolved.is_relative_to(admin_dist.resolve())
    assert resolved.is_file()


def test_nonexistent_file_not_served(admin_dist: Path):
    """不存在的文件不通过 is_file() 检查。"""
    file_path = admin_dist / "nonexistent.js"
    resolved = file_path.resolve()
    assert resolved.is_relative_to(admin_dist.resolve())
    assert not resolved.is_file()
