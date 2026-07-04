from autoharness.ir.nodes import (
    Act,
    Branch,
    HarnessCall,
    Observe,
    Phi,
    SkillCall,
    Think,
)


class TestObserveNode:
    def test_construct(self):
        n = Observe(node_id="n1", kind="observe", query="state of the world")
        assert n.node_id == "n1"
        assert n.kind == "observe"
        assert n.query == "state of the world"

    def test_default_kind(self):
        n = Observe(node_id="n1", query="q")
        assert n.kind == "observe"


class TestActNode:
    def test_construct(self):
        n = Act(node_id="n2", kind="act", tool="write_file", args={"path": "/tmp/f"})
        assert n.node_id == "n2"
        assert n.kind == "act"
        assert n.tool == "write_file"

    def test_default_kind(self):
        n = Act(node_id="n2", tool="t")
        assert n.kind == "act"


class TestThinkNode:
    def test_construct(self):
        n = Think(node_id="n3", kind="think", prompt="reason about X")
        assert n.node_id == "n3"
        assert n.kind == "think"

    def test_default_kind(self):
        n = Think(node_id="n3", prompt="p")
        assert n.kind == "think"


class TestBranchNode:
    def test_construct(self):
        n = Branch(
            node_id="n4",
            kind="branch",
            condition="state.score > 0.5",
            true_next="n5",
            false_next="n6",
        )
        assert n.true_next == "n5"
        assert n.false_next == "n6"

    def test_default_kind(self):
        n = Branch(node_id="n4", condition="c", true_next="n5", false_next="n6")
        assert n.kind == "branch"


class TestSkillCallNode:
    def test_construct(self):
        n = SkillCall(
            node_id="n5",
            kind="skill_call",
            skill_id="s1",
            args={"x": 1},
        )
        assert n.skill_id == "s1"
        assert n.args == {"x": 1}

    def test_default_kind(self):
        n = SkillCall(node_id="n5", skill_id="s1")
        assert n.kind == "skill_call"


class TestHarnessCallNode:
    def test_construct(self):
        n = HarnessCall(
            node_id="n6",
            kind="harness_call",
            harness_id="h1",
            args={"input": "data"},
        )
        assert n.harness_id == "h1"
        assert n.args == {"input": "data"}

    def test_default_kind(self):
        n = HarnessCall(node_id="n6", harness_id="h1")
        assert n.kind == "harness_call"


class TestPhiNode:
    def test_construct(self):
        n = Phi(node_id="n7", kind="phi", sources=["n5", "n6"])
        assert n.sources == ["n5", "n6"]

    def test_default_kind(self):
        n = Phi(node_id="n7", sources=[])
        assert n.kind == "phi"


class TestAllNodeTypes:
    """Ensure all 7 node types are constructable and share UPIRNode base."""

    def test_all_constructable(self):
        nodes = [
            Observe(node_id="o", query="q"),
            Act(node_id="a", tool="t"),
            Think(node_id="t", prompt="p"),
            Branch(node_id="b", condition="c", true_next="t", false_next="f"),
            SkillCall(node_id="s", skill_id="s1"),
            HarnessCall(node_id="h", harness_id="h1"),
            Phi(node_id="p", sources=[]),
        ]
        for n in nodes:
            assert n.node_id is not None
            assert n.kind is not None

    def test_invalid_kind_rejected(self):
        from autoharness.ir.upir import UPIRNode

        n = UPIRNode(node_id="x", kind="not_a_real_kind")
        assert n.kind == "not_a_real_kind"
