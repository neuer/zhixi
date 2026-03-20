"""X API 用户查询客户端测试。"""

import pytest
import respx
from httpx import ConnectTimeout, Response

from app.clients.x_client import XApiError, XUserProfile, lookup_user

X_USER_URL = "https://api.x.com/2/users/by/username/testuser"


def _mock_success_response() -> Response:
    """正常的 X API 成功响应。"""
    return Response(
        200,
        json={
            "data": {
                "id": "12345",
                "name": "Test User",
                "description": "A test bio",
                "profile_image_url": "https://pbs.twimg.com/test.jpg",
                "public_metrics": {
                    "followers_count": 1000,
                    "following_count": 500,
                    "tweet_count": 200,
                },
            }
        },
    )


class TestLookupUserSuccess:
    """正常返回场景。"""

    @respx.mock
    async def test_fields_mapped_correctly(self):
        """成功响应时所有字段正确映射。"""
        respx.get(X_USER_URL).mock(return_value=_mock_success_response())

        result = await lookup_user("fake_token", "testuser")

        assert isinstance(result, XUserProfile)
        assert result.twitter_user_id == "12345"
        assert result.display_name == "Test User"
        assert result.bio == "A test bio"
        assert result.avatar_url == "https://pbs.twimg.com/test.jpg"
        assert result.followers_count == 1000

    @respx.mock
    async def test_missing_public_metrics_defaults_to_zero(self):
        """public_metrics 缺失时 followers_count 默认为 0。"""
        respx.get(X_USER_URL).mock(
            return_value=Response(
                200,
                json={"data": {"id": "12345", "name": "Minimal"}},
            )
        )

        result = await lookup_user("fake_token", "testuser")
        assert result.followers_count == 0

    @respx.mock
    async def test_optional_fields_none_when_absent(self):
        """bio 和 avatar_url 缺失时为 None。"""
        respx.get(X_USER_URL).mock(
            return_value=Response(
                200,
                json={"data": {"id": "99", "name": "NoBio"}},
            )
        )

        result = await lookup_user("fake_token", "testuser")
        assert result.bio is None
        assert result.avatar_url is None


class TestLookupUserErrors:
    """错误场景。"""

    @respx.mock
    async def test_http_403_raises_x_api_error(self):
        """HTTP 403 → XApiError。"""
        respx.get(X_USER_URL).mock(return_value=Response(403, json={"error": "Forbidden"}))

        with pytest.raises(XApiError, match="查询失败"):
            await lookup_user("fake_token", "testuser")

    @respx.mock
    async def test_http_500_raises_x_api_error(self):
        """HTTP 500 → XApiError。"""
        respx.get(X_USER_URL).mock(return_value=Response(500, text="Internal Server Error"))

        with pytest.raises(XApiError, match="查询失败"):
            await lookup_user("fake_token", "testuser")

    @respx.mock
    async def test_empty_data_raises_x_api_error(self):
        """200 但 data 为空 → XApiError。"""
        respx.get(X_USER_URL).mock(return_value=Response(200, json={"data": None}))

        with pytest.raises(XApiError, match="未找到用户"):
            await lookup_user("fake_token", "testuser")

    @respx.mock
    async def test_no_data_key_raises_x_api_error(self):
        """200 但无 data 键 → XApiError。"""
        respx.get(X_USER_URL).mock(
            return_value=Response(200, json={"errors": [{"message": "Not found"}]})
        )

        with pytest.raises(XApiError, match="未找到用户"):
            await lookup_user("fake_token", "testuser")

    @respx.mock
    async def test_timeout_raises_x_api_error(self):
        """网络超时 → XApiError。"""
        respx.get(X_USER_URL).mock(side_effect=ConnectTimeout("连接超时"))

        with pytest.raises(XApiError, match="查询失败"):
            await lookup_user("fake_token", "testuser")

    @respx.mock
    async def test_non_json_response_raises_x_api_error(self):
        """200 但非 JSON 响应 → XApiError。"""
        respx.get(X_USER_URL).mock(return_value=Response(200, text="<html>Error</html>"))

        with pytest.raises(XApiError, match="查询失败"):
            await lookup_user("fake_token", "testuser")

    @respx.mock
    async def test_missing_id_field_raises_x_api_error(self):
        """data 缺少 id 字段 → XApiError。"""
        respx.get(X_USER_URL).mock(return_value=Response(200, json={"data": {"name": "NoId"}}))

        with pytest.raises(XApiError, match="字段缺失"):
            await lookup_user("fake_token", "testuser")

    @respx.mock
    async def test_missing_name_field_raises_x_api_error(self):
        """data 缺少 name 字段 → XApiError。"""
        respx.get(X_USER_URL).mock(return_value=Response(200, json={"data": {"id": "123"}}))

        with pytest.raises(XApiError, match="字段缺失"):
            await lookup_user("fake_token", "testuser")
