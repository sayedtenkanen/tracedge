"""Code task demo — ToolEnvironment with UPIR VM."""


from autoharness.environment.tool_env import ToolEnvironment
from autoharness.ir.upir import UPIR, Edge
from autoharness.runtime.vm import VM


class SimpleLLM:
    """LLM that returns fixed responses."""

    def __init__(self) -> None:
        self.call_count = 0

    def chat(self, prompt: str) -> str:
        self.call_count += 1
        if "read" in prompt.lower():
            return "read_file"
        return "write_file"


def main() -> None:
    env = ToolEnvironment(workspace="/tmp/autoharness_demo")

    # Build a UPIR: observe → think → act
    upir = UPIR(
        entry="observe",
        nodes={
            "observe": {
                "kind": "observe",
                "node_id": "observe",
                "query": "What tool should I use?",
            },
            "decide": {
                "kind": "think",
                "node_id": "decide",
                "prompt": "Choose a tool: read_file or write_file",
            },
            "execute": {
                "kind": "act",
                "node_id": "execute",
                "tool": "write_file",
                "args": {"path": "/tmp/autoharness_demo/output.txt", "content": "Hello from AutoHarness!"},
            },
        },
        edges=[
            Edge(from_="observe", to="decide", kind="sequential"),
            Edge(from_="decide", to="execute", kind="sequential"),
        ],
    )

    llm = SimpleLLM()
    vm = VM(upir=upir, llm=llm, environment=env)

    print("=== Code Task Demo ===\n")

    trace = vm.run()
    for event in trace:
        print(f"  {event.get('kind', '?')}: {event}")

    print(f"\nTrace length: {len(trace)} steps")
    print(f"LLM calls: {llm.call_count}")


if __name__ == "__main__":
    main()
