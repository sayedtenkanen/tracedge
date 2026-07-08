"""Shared test fixtures for the Tracedge test suite."""

from __future__ import annotations

import pytest

from tracedge.ir.upir import UPIR, Edge


class FakeLLM:
    """Canned LLM for testing Think/Branch nodes."""

    def __init__(self, response: str = "true") -> None:
        self.call_count = 0
        self._response = response

    def chat(self, prompt: str) -> str:
        self.call_count += 1
        return self._response


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def sample_upir() -> UPIR:
    return UPIR(
        entry="n1",
        nodes={
            "n1": {"kind": "observe", "node_id": "n1", "query": "test"},
            "n2": {"kind": "act", "node_id": "n2", "tool": "read_file"},
        },
        edges=[Edge(from_="n1", to="n2", kind="sequential")],
        harness_table={},
        skill_table={},
    )
