"""Tests for LLM Client — protocol and OpenAI adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tracedge.intelligence.llm_client import LLMClient, OpenAIChatClient


class TestLLMClientProtocol:
    """LLMClient formalizes the chat interface expected by the VM."""

    def test_fake_llm_satisfies_protocol(self) -> None:
        """A simple class with chat(prompt) -> str satisfies LLMClient."""

        class FakeLLM:
            def chat(self, prompt: str) -> str:
                return "response"

        llm: LLMClient = FakeLLM()
        assert llm.chat("hello") == "response"

    def test_protocol_is_runtime_checkable(self) -> None:
        """LLMClient can be used with isinstance at runtime."""

        class ConformingLLM:
            def chat(self, prompt: str) -> str:
                return "response"

        class NonConformingLLM:
            pass

        assert isinstance(ConformingLLM(), LLMClient)
        assert not isinstance(NonConformingLLM(), LLMClient)


class TestOpenAIChatClient:
    """OpenAIChatClient wraps the openai package for LLM calls."""

    def test_requires_api_key(self) -> None:
        """Raises ValueError if OPENAI_API_KEY is not set."""
        with patch.dict("os.environ", {}, clear=True):
            import os

            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIChatClient()

    def test_chat_returns_string(self) -> None:
        """chat() returns a string from the OpenAI API."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello!"))]

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            client = OpenAIChatClient()
            result = client.chat("Say hello")
            assert result == "Hello!"
            mock_openai.return_value.chat.completions.create.assert_called_once()

    def test_custom_model(self) -> None:
        """Model can be configured via constructor."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            client = OpenAIChatClient(model="gpt-4")
            client.chat("test")
            call_kwargs = mock_openai.return_value.chat.completions.create.call_args
            assert call_kwargs.kwargs["model"] == "gpt-4"

    def test_custom_system_prompt(self) -> None:
        """System prompt is included in messages."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            client = OpenAIChatClient(system_prompt="You are helpful.")
            client.chat("test")
            call_kwargs = mock_openai.return_value.chat.completions.create.call_args
            messages = call_kwargs.kwargs["messages"]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are helpful."

    def test_passes_through_to_vm(self) -> None:
        """OpenAIChatClient can be passed directly to VM."""
        from tracedge.ir.upir import UPIR, UPIRNode
        from tracedge.runtime.vm import VM

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="4"))]

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            client = OpenAIChatClient()

            upir = UPIR(
                entry="n1",
                nodes={"n1": UPIRNode(kind="think", node_id="n1", prompt="What is 2+2?")},
                edges=[],
            )
            vm = VM(upir=upir, llm=client, seed=42)
            trace = vm.run()
            assert len(trace) == 1
            assert trace[0]["kind"] == "think"
            assert trace[0]["response"] == "4"

    def test_chat_returns_empty_string_on_none_content(self) -> None:
        """chat() returns '' when the API returns content=None."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            client = OpenAIChatClient()
            result = client.chat("test")
            assert result == ""

    def test_chat_raises_on_empty_choices(self) -> None:
        """chat() raises IndexError when API returns an empty choices list."""
        mock_response = MagicMock()
        mock_response.choices = []

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            client = OpenAIChatClient()
            with pytest.raises(IndexError):
                client.chat("test")
