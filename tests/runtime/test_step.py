from tracedge.runtime.step import StepResult


class TestStepResultContract:
    """StepResult has required fields per PLAN.md."""

    def test_has_next(self) -> None:
        r = StepResult(
            next="n2",
            state_delta={},
            outputs={},
            reward_signal={},
            trace_event={},
        )
        assert r.next == "n2"

    def test_has_state_delta(self) -> None:
        r = StepResult(
            next=None,
            state_delta={"key": "value"},
            outputs={},
            reward_signal={},
            trace_event={},
        )
        assert r.state_delta == {"key": "value"}

    def test_has_outputs(self) -> None:
        r = StepResult(
            next=None,
            state_delta={},
            outputs={"result": 42},
            reward_signal={},
            trace_event={},
        )
        assert r.outputs == {"result": 42}

    def test_has_reward_signal(self) -> None:
        r = StepResult(
            next=None,
            state_delta={},
            outputs={},
            reward_signal={"task_success": 1.0},
            trace_event={},
        )
        assert r.reward_signal == {"task_success": 1.0}

    def test_has_trace_event(self) -> None:
        r = StepResult(
            next=None,
            state_delta={},
            outputs={},
            reward_signal={},
            trace_event={"node_id": "n1", "cost": 0.1},
        )
        assert r.trace_event["node_id"] == "n1"

    def test_next_can_be_none(self) -> None:
        r = StepResult(
            next=None,
            state_delta={},
            outputs={},
            reward_signal={},
            trace_event={},
        )
        assert r.next is None

    def test_all_fields_optional_except_next(self) -> None:
        r = StepResult(next="n1")
        assert r.state_delta == {}
        assert r.outputs == {}
        assert r.reward_signal == {}
        assert r.trace_event == {}
