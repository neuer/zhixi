"""M1 数据采集模块。"""

from app.fetcher.base import BaseFetcher
from app.fetcher.x_api import XApiFetcher


def get_fetcher(bearer_token: str) -> BaseFetcher:
    """工厂函数：返回数据抓取器实例。

    当前默认返回 XApiFetcher。如需切换实现可在此处添加分支。

    Args:
        bearer_token: X API Bearer Token

    Returns:
        BaseFetcher 实例
    """
    return XApiFetcher(bearer_token=bearer_token)
