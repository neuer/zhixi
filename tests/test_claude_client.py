"""Claude API 客户端测试（US-017）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import TextBlock

from app.clients.claude_client import SAFETY_PREFIX, ClaudeAPIError, ClaudeClient
from app.schemas.client_types import ClaudeResponse


def _make_mock_response(
    text: str = "test response",
    input_tokens: int = 100,
    output_tokens: int = 50,
    model: str = "claude-sonnet-4-20250514",
) -> MagicMock:
    """构造模拟的 anthropic API 响应。"""
    response = MagicMock()
    content_block = TextBlock(type="text", text=text)
    response.content = [content_block]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    response.model = model
    return response


class TestClaudeClient:
    """Claude API 客户端核心功能。"""

    @pytest.fixture
    def client(self) -> ClaudeClient:
        # I-35 局限性说明：通过构造函数 _async_client 参数注入 mock 客户端，
        # 测试中直接访问 client._client 内部属性来设置 mock 返回值。
        # 这与实现细节耦合较深，若 ClaudeClient 内部重命名 _client 属性，
        # 所有测试都会失败。更好的做法是通过公开接口或依赖注入模式解耦。
        return ClaudeClient(
            api_key="test-key",
            model="claude-sonnet-4-20250514",
            input_price=3.0,
            output_price=15.0,
            _async_client=AsyncMock(),
        )

    async def test_complete_returns_claude_response(self, client: ClaudeClient):
        mock_response = _make_mock_response()
        client._client.messages.create = AsyncMock(return_value=mock_response)

        result = await client.complete("测试 prompt")

        assert isinstance(result, ClaudeResponse)
        assert result.content == "test response"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.model == "claude-sonnet-4-20250514"
        assert result.duration_ms >= 0

    async def test_complete_estimated_cost(self, client: ClaudeClient):
        """成本计算：input $3/MTok, output $15/MTok。"""
        mock_response = _make_mock_response(input_tokens=1000, output_tokens=500)
        client._client.messages.create = AsyncMock(return_value=mock_response)

        result = await client.complete("测试 prompt")

        # 1000 * 3 / 1_000_000 + 500 * 15 / 1_000_000 = 0.003 + 0.0075 = 0.0105
        assert result.estimated_cost == 0.0105

    async def test_estimated_cost_precision(self, client: ClaudeClient):
        """成本保留 6 位小数。"""
        mock_response = _make_mock_response(input_tokens=7, output_tokens=3)
        client._client.messages.create = AsyncMock(return_value=mock_response)

        result = await client.complete("测试")

        # 7 * 3 / 1_000_000 + 3 * 15 / 1_000_000 = 0.000021 + 0.000045 = 0.000066
        assert result.estimated_cost == 0.000066

    async def test_safety_prefix_injected_with_system(self, client: ClaudeClient):
        """有 system 参数时，安全声明注入到开头。"""
        mock_response = _make_mock_response()
        client._client.messages.create = AsyncMock(return_value=mock_response)

        await client.complete("测试", system="你是内容编辑")

        # 有意通过 call_args 验证安全前缀注入：这是核心安全机制，
        # 必须确保每次 API 调用都携带 SAFETY_PREFIX，属于白盒测试的合理场景
        call_kwargs = client._client.messages.create.call_args
        system_arg = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")
        assert system_arg.startswith(SAFETY_PREFIX)
        assert "你是内容编辑" in system_arg

    async def test_safety_prefix_injected_without_system(self, client: ClaudeClient):
        """无 system 参数时，安全声明仍然注入。"""
        mock_response = _make_mock_response()
        client._client.messages.create = AsyncMock(return_value=mock_response)

        await client.complete("测试")

        # 同上：验证无 system 参数时安全前缀仍被注入，防止遗漏
        call_kwargs = client._client.messages.create.call_args
        system_arg = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")
        assert system_arg == SAFETY_PREFIX

    async def test_user_message_format(self, client: ClaudeClient):
        """prompt 作为 user message 传入。"""
        mock_response = _make_mock_response()
        client._client.messages.create = AsyncMock(return_value=mock_response)

        await client.complete("我的测试 prompt")

        # 验证 prompt 正确封装为 messages 格式传递给 API
        call_kwargs = client._client.messages.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "我的测试 prompt"

    async def test_max_tokens_default(self, client: ClaudeClient):
        mock_response = _make_mock_response()
        client._client.messages.create = AsyncMock(return_value=mock_response)

        await client.complete("测试")

        # 验证默认 max_tokens 参数正确传递给 API
        call_kwargs = client._client.messages.create.call_args
        max_tokens = call_kwargs.kwargs.get("max_tokens") or call_kwargs[1].get("max_tokens")
        assert max_tokens == 4096

    async def test_max_tokens_custom(self, client: ClaudeClient):
        mock_response = _make_mock_response()
        client._client.messages.create = AsyncMock(return_value=mock_response)

        await client.complete("测试", max_tokens=1024)

        # 验证自定义 max_tokens 正确透传
        call_kwargs = client._client.messages.create.call_args
        max_tokens = call_kwargs.kwargs.get("max_tokens") or call_kwargs[1].get("max_tokens")
        assert max_tokens == 1024

    async def test_api_error_wrapped(self, client: ClaudeClient):
        """anthropic API 异常包装为 ClaudeAPIError。"""
        import anthropic

        client._client.messages.create = AsyncMock(
            side_effect=anthropic.APIError(
                message="Rate limit exceeded",
                request=MagicMock(),
                body=None,
            )
        )

        with pytest.raises(ClaudeAPIError, match="Rate limit exceeded"):
            await client.complete("测试")

    async def test_timeout_configuration(self):
        """验证 timeout 设置传入 AsyncAnthropic。"""
        with patch("app.clients.claude_client.anthropic.AsyncAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            ClaudeClient(
                api_key="test-key",
                model="test-model",
                input_price=3.0,
                output_price=15.0,
            )
            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args
            assert call_kwargs.kwargs.get("timeout") == 60.0


class TestGetClaudeClient:
    """get_claude_client() 异步工厂函数。"""

    async def test_returns_client_when_key_configured(self):
        from unittest.mock import AsyncMock, patch

        from app.clients.claude_client import ClaudeClient, get_claude_client

        mock_db = AsyncMock()
        with (
            patch(
                "app.clients.claude_client.get_secret_config",
                new_callable=AsyncMock,
                return_value="sk-test-key",
            ),
            patch(
                "app.clients.claude_client.get_system_config",
                new_callable=AsyncMock,
                return_value="claude-sonnet",
            ),
            patch(
                "app.clients.claude_client.safe_float_config",
                new_callable=AsyncMock,
                return_value=3.0,
            ),
        ):
            client = await get_claude_client(mock_db)
            assert isinstance(client, ClaudeClient)

    async def test_raises_when_key_missing(self):
        from unittest.mock import AsyncMock, patch

        import pytest

        from app.clients.claude_client import ClaudeAPIError, get_claude_client

        mock_db = AsyncMock()
        with (
            patch(
                "app.clients.claude_client.get_secret_config",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(ClaudeAPIError, match="API Key 未配置"),
        ):
            await get_claude_client(mock_db)
