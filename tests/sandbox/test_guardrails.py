"""Tests for harness guardrails — static checks and effect boundary enforcement."""

import pytest


class TestNoTryExcept:
    """Generated harness code must not contain try/except."""

    def test_harness_no_try_except_rejected(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = """
x = 1
try:
    x = x + 1
except:
    pass
"""
        with pytest.raises(ValueError, match="try"):
            check_harness_code(code)

    def test_harness_no_except_rejected(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = """
x = 1
try:
    x = x + 1
except Exception:
    pass
"""
        with pytest.raises(ValueError, match="try"):
            check_harness_code(code)


class TestEffectBoundary:
    """Harness code must respect the declared effect boundary."""

    def test_harness_effect_boundary_no_step(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = """
result = environment.step(state, action)
"""
        with pytest.raises(ValueError, match="environment"):
            check_harness_code(code, effects={"filesystem": False, "network": False})

    def test_harness_effect_boundary_no_state_mutation(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = """
state["key"] = "new_value"
"""
        with pytest.raises(ValueError, match="state"):
            check_harness_code(code, effects={"filesystem": False, "network": False})

    def test_harness_effect_boundary_no_filesystem(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = """
with open("file.txt", "w") as f:
    f.write("data")
"""
        with pytest.raises(ValueError, match="filesystem"):
            check_harness_code(code, effects={"filesystem": False, "network": False})

    def test_harness_effect_boundary_no_network(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = """
import urllib.request
urllib.request.urlopen("http://example.com")
"""
        with pytest.raises(ValueError, match="network"):
            check_harness_code(code, effects={"filesystem": False, "network": False})

    def test_state_delete_rejected(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = "del state['key']"
        with pytest.raises(ValueError, match="state"):
            check_harness_code(code, effects={"filesystem": False, "network": False})

    def test_filesystem_import_rejected(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = "import os"
        with pytest.raises(ValueError, match="filesystem"):
            check_harness_code(code, effects={"filesystem": False, "network": False})

    def test_filesystem_importfrom_rejected(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = "from os.path import join"
        with pytest.raises(ValueError, match="filesystem"):
            check_harness_code(code, effects={"filesystem": False, "network": False})

    def test_network_import_rejected(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = "import urllib.request"
        with pytest.raises(ValueError, match="network"):
            check_harness_code(code, effects={"filesystem": False, "network": False})

    def test_network_importfrom_rejected(self) -> None:
        from tracedge.sandbox.guardrails import check_harness_code

        code = "from urllib.request import urlopen"
        with pytest.raises(ValueError, match="network"):
            check_harness_code(code, effects={"filesystem": False, "network": False})
