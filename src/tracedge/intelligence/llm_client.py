"""LLM Client — protocol and OpenAI adapter for LLM integration."""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Protocol formalizing the chat interface expected by the VM.

    Any object with a ``chat(prompt: str) -> str`` method satisfies this protocol.
    """

    def chat(self, prompt: str) -> str: ...


class OpenAIChatClient:
    """Adapter that wraps the ``openai`` package for LLM calls.

    Reads ``OPENAI_API_KEY`` from the environment at construction time.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.0,
    ) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAIChatClient")
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self._system_prompt = system_prompt
        self._temperature = temperature

    @property
    def model(self) -> str:
        return self._model

    def chat(self, prompt: str) -> str:
        """Send a prompt to the OpenAI API and return the response text."""
        messages: list[Any] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
        )
        content = response.choices[0].message.content
        return content if content is not None else ""


class OllamaChatClient:
    """Adapter for local Ollama models via the OpenAI-compatible /v1 endpoint.

    Reads ``OLLAMA_MODEL`` from the environment if not specified.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.0,
    ) -> None:
        import openai

        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model or os.environ.get("OLLAMA_MODEL", "gemma4:12b-mlx")
        self._system_prompt = system_prompt
        self._temperature = temperature

    @property
    def model(self) -> str:
        return self._model

    def chat(self, prompt: str) -> str:
        """Send a prompt to Ollama and return the response text."""
        messages: list[Any] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
        )
        content = response.choices[0].message.content
        return content if content is not None else ""
