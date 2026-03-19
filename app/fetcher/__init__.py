"""M1 数据采集模块。"""

from app.fetcher.base import BaseFetcher
from app.fetcher.x_api import XApiFetcher


def get_fetcher(bearer_token: str) -> BaseFetcher:
    """工厂函数：根据配置返回合适的数据抓取器。

    当前默认返回 XApiFetcher。Phase 2 可根据环境变量切换为 ThirdPartyFetcher。

    Args:
        bearer_token: X API Bearer Token

    Returns:
        BaseFetcher 实例
    """
    return XApiFetcher(bearer_token=bearer_token)
