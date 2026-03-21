"""微信公众号 API 客户端（MVP 空壳）。

公众号认证通过后实现实际 API 调用。当前所有方法均 raise NotImplementedError。
"""

_NOT_IMPLEMENTED_MSG = "微信API自动发布功能将在公众号认证后实现"


class WechatClient:
    """微信公众号 API 客户端。"""

    def __init__(self, app_id: str, app_secret: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret

    def get_access_token(self) -> str:
        """获取微信 access_token。"""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def upload_article(self, title: str, content: str, cover_url: str) -> str:
        """上传图文素材，返回 media_id。"""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def send_mass(self, media_id: str) -> str:
        """群发消息，返回 msg_id。"""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)


def get_wechat_client(app_id: str, app_secret: str) -> WechatClient:
    """创建微信客户端实例。APP_ID 或 APP_SECRET 为空时 raise ValueError。"""
    if not app_id or not app_secret:
        msg = "微信API未配置"
        raise ValueError(msg)
    return WechatClient(app_id=app_id, app_secret=app_secret)
