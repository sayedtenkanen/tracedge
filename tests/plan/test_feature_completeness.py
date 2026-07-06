"""Conformance tests: Feature completeness commitments from PLAN.md.

Verifies that Phase 1 modules exist and expose the expected types.
"""

from __future__ import annotations

import pathlib

SRC = pathlib.Path("src/autoharness")
PLAN_PHASE2_3_DIRS = ["skills", "memory", "compiler"]


class TestPhase1ModulesExist:
    """PLAN Phase 1: all required modules are present."""

    def test_ir_module_exists(self) -> None:
        assert (SRC / "ir").is_dir()

    def test_runtime_module_exists(self) -> None:
        assert (SRC / "runtime").is_dir()

    def test_environment_module_exists(self) -> None:
        assert (SRC / "environment").is_dir()

    def test_sandbox_module_exists(self) -> None:
        assert (SRC / "sandbox").is_dir()

    def test_trace_module_exists(self) -> None:
        assert (SRC / "trace").is_dir()

    def test_reward_module_exists(self) -> None:
        assert (SRC / "reward").is_dir()

    def test_search_module_exists(self) -> None:
        assert (SRC / "search").is_dir()

    def test_intelligence_module_exists(self) -> None:
        assert (SRC / "intelligence").is_dir()


class TestPhase23NotStarted:
    """PLAN: Phase 2/3 modules should not exist yet (Slices 7-16)."""

    def test_no_skills_dir(self) -> None:
        assert not (SRC / "skills").is_dir(), "skills/ should not exist before Slice 7"

    def test_no_memory_dir(self) -> None:
        assert not (SRC / "memory").is_dir(), "memory/ should not exist before Slice 10"

    def test_no_compiler_dir(self) -> None:
        assert not (SRC / "compiler").is_dir(), "compiler/ should not exist before Slice 12"


class TestUPIRSchema:
    """PLAN: UPIR substrate has specific fields."""

    def test_upir_has_entry(self) -> None:
        from autoharness.ir.upir import UPIR

        assert "entry" in UPIR.model_fields

    def test_upir_has_nodes(self) -> None:
        from autoharness.ir.upir import UPIR

        assert "nodes" in UPIR.model_fields

    def test_upir_has_edges(self) -> None:
        from autoharness.ir.upir import UPIR

        assert "edges" in UPIR.model_fields

    def test_upir_has_harness_table(self) -> None:
        from autoharness.ir.upir import UPIR

        assert "harness_table" in UPIR.model_fields

    def test_upir_has_skill_table(self) -> None:
        """PLAN: skill_table defined in Slice 1, stays empty until Phase 2."""
        from autoharness.ir.upir import UPIR

        assert "skill_table" in UPIR.model_fields

    def test_upir_schema_name(self) -> None:
        """PLAN: schema defaults to 'typed-executable-graph'."""
        from autoharness.ir.upir import UPIR

        upir = UPIR(
            entry="n1",
            nodes={"n1": {"kind": "observe", "node_id": "n1"}},
        )
        assert upir.schema_name == "typed-executable-graph"


class TestEdgeSchema:
    """PLAN: Edge has from, to, kind."""

    def test_edge_has_from(self) -> None:
        from autoharness.ir.upir import Edge

        assert "from_" in Edge.model_fields

    def test_edge_has_to(self) -> None:
        from autoharness.ir.upir import Edge

        assert "to" in Edge.model_fields

    def test_edge_has_kind(self) -> None:
        from autoharness.ir.upir import Edge

        assert "kind" in Edge.model_fields

    def test_edge_validate_from_dict(self) -> None:
        """PLAN: Edge accepts dict-style input via alias."""
        from autoharness.ir.upir import Edge

        e = Edge.model_validate({"from": "a", "to": "b", "kind": "sequential"})
        assert e.from_ == "a"

    def test_edge_dump_by_alias(self) -> None:
        """PLAN: Edge serializes with alias 'from'."""
        from autoharness.ir.upir import Edge

        e = Edge(from_="a", to="b", kind="sequential")
        assert e.model_dump(by_alias=True)["from"] == "a"


class TestNodeTypes:
    """PLAN: 7 node types — Observe, Act, Think, Branch, SkillCall, HarnessCall, Phi."""

    def test_observe_exists(self) -> None:
        from autoharness.ir.nodes import Observe

        assert Observe is not None

    def test_act_exists(self) -> None:
        from autoharness.ir.nodes import Act

        assert Act is not None

    def test_think_exists(self) -> None:
        from autoharness.ir.nodes import Think

        assert Think is not None

    def test_branch_exists(self) -> None:
        from autoharness.ir.nodes import Branch

        assert Branch is not None

    def test_skill_call_exists(self) -> None:
        from autoharness.ir.nodes import SkillCall

        assert SkillCall is not None

    def test_harness_call_exists(self) -> None:
        from autoharness.ir.nodes import HarnessCall

        assert HarnessCall is not None

    def test_phi_exists(self) -> None:
        from autoharness.ir.nodes import Phi

        assert Phi is not None


class TestHarnessSchema:
    """PLAN: Harness IR has kind, code, effects, guard_policy."""

    def test_harness_has_kind(self) -> None:
        from autoharness.ir.harness import Harness

        assert "kind" in Harness.model_fields

    def test_harness_has_code(self) -> None:
        from autoharness.ir.harness import Harness

        assert "code" in Harness.model_fields

    def test_harness_has_effects(self) -> None:
        from autoharness.ir.harness import Harness

        assert "effects" in Harness.model_fields

    def test_harness_has_guard_policy(self) -> None:
        from autoharness.ir.harness import Harness

        assert "guard_policy" in Harness.model_fields

    def test_harness_valid_kinds(self) -> None:
        """PLAN: kind must be action_filter, action_verifier, or policy."""
        from autoharness.ir.harness import VALID_HARNESS_KINDS

        assert VALID_HARNESS_KINDS == ("action_filter", "action_verifier", "policy")


class TestEnvironmentProtocol:
    """PLAN: Environment Protocol with reset/step/legal_actions/tools."""

    def test_protocol_exists(self) -> None:
        from autoharness.environment.protocol import Environment

        assert Environment is not None

    def test_tool_env_exists(self) -> None:
        from autoharness.environment.tool_env import ToolEnvironment

        assert ToolEnvironment is not None

    def test_game_env_exists(self) -> None:
        from autoharness.environment.game_env import GameEnvironment

        assert GameEnvironment is not None


class TestSandboxGuardrails:
    """PLAN: Guardrails — no_try_except, path validation, timeouts."""

    def test_guardrails_module_exists(self) -> None:
        from autoharness.sandbox import guardrails

        assert hasattr(guardrails, "check_harness_code")

    def test_workspace_module_exists(self) -> None:
        from autoharness.sandbox import workspace

        assert hasattr(workspace, "Workspace")

    def test_harness_runner_exists(self) -> None:
        from autoharness.sandbox import harness_runner

        assert hasattr(harness_runner, "run_harness")


class TestRewardSchema:
    """PLAN: Reward has task_success, efficiency, safety, skill_gain, legality."""

    def test_reward_has_task_success(self) -> None:
        from autoharness.reward.scorer import Reward

        assert "task_success" in Reward.model_fields

    def test_reward_has_efficiency(self) -> None:
        from autoharness.reward.scorer import Reward

        assert "efficiency" in Reward.model_fields

    def test_reward_has_safety(self) -> None:
        from autoharness.reward.scorer import Reward

        assert "safety" in Reward.model_fields

    def test_reward_has_skill_gain(self) -> None:
        from autoharness.reward.scorer import Reward

        assert "skill_gain" in Reward.model_fields

    def test_reward_has_legality(self) -> None:
        from autoharness.reward.scorer import Reward

        assert "legality" in Reward.model_fields

    def test_scorer_has_score_trace(self) -> None:
        from autoharness.reward.scorer import score_trace

        assert callable(score_trace)

    def test_scorer_has_value(self) -> None:
        from autoharness.reward.scorer import value

        assert callable(value)


class TestCriticOutput:
    """PLAN: CriticOutput has failure_clusters, legality_violations, inefficiency_patterns."""

    def test_has_failure_clusters(self) -> None:
        from autoharness.intelligence.critic import CriticOutput

        assert "failure_clusters" in CriticOutput.model_fields

    def test_has_legality_violations(self) -> None:
        from autoharness.intelligence.critic import CriticOutput

        assert "legality_violations" in CriticOutput.model_fields

    def test_has_inefficiency_patterns(self) -> None:
        from autoharness.intelligence.critic import CriticOutput

        assert "inefficiency_patterns" in CriticOutput.model_fields


class TestSearchModule:
    """PLAN: Thompson tree search exists."""

    def test_thompson_module_exists(self) -> None:
        from autoharness.search import thompson

        assert hasattr(thompson, "ThompsonTreeSearch")

    def test_thompson_has_branch(self) -> None:
        from autoharness.search.thompson import Branch

        assert Branch is not None

    def test_thompson_has_thompson_sample(self) -> None:
        from autoharness.search.thompson import thompson_sample

        assert callable(thompson_sample)

    def test_thompson_has_update_posterior(self) -> None:
        from autoharness.search.thompson import update_posterior

        assert callable(update_posterior)
