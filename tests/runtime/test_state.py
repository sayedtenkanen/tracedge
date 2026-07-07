from tracedge.runtime.state import State


class TestStateNamespacing:
    """State scoped per node_id, no key collisions."""

    def test_set_and_get(self) -> None:
        s = State()
        s.set("n1", "x", 42)
        assert s.get("n1", "x") == 42

    def test_namespace_isolation(self) -> None:
        s = State()
        s.set("n1", "key", "value1")
        s.set("n2", "key", "value2")
        assert s.get("n1", "key") == "value1"
        assert s.get("n2", "key") == "value2"

    def test_get_missing_returns_default(self) -> None:
        s = State()
        assert s.get("n1", "missing", default="fallback") == "fallback"

    def test_get_missing_returns_none(self) -> None:
        s = State()
        assert s.get("n1", "missing") is None

    def test_apply_delta(self) -> None:
        s = State()
        s.apply_delta({"n1": {"a": 1, "b": 2}})
        assert s.get("n1", "a") == 1
        assert s.get("n1", "b") == 2

    def test_apply_delta_merges(self) -> None:
        s = State()
        s.set("n1", "existing", "keep")
        s.apply_delta({"n1": {"new_key": "new_val"}})
        assert s.get("n1", "existing") == "keep"
        assert s.get("n1", "new_key") == "new_val"

    def test_flatten(self) -> None:
        s = State()
        s.set("n1", "a", 1)
        s.set("n2", "b", 2)
        flat = s.flatten()
        assert flat == {"n1": {"a": 1}, "n2": {"b": 2}}

    def test_flatten_does_not_leak_mutable_references(self) -> None:
        s = State()
        s.set("n1", "data", {"nested": "value"})
        flat = s.flatten()
        flat["n1"]["data"]["nested"] = "mutated"
        assert s.get("n1", "data") == {"nested": "value"}
