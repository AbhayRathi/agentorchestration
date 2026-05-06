# Centralized Loop

A **minimal, production-minded agent orchestration system** designed as the
foundational infrastructure for autonomous applications.

Current use-cases supported:

* ✅ **Autonomous coding system** (Alpha) – generates, tests and reviews Python code
* 🔜 Autonomous hedge fund (future)
* 🔜 Hardware / FPGA design system (future)

---

## Architecture

```
centralized-loop/
├── core/                    # Domain-agnostic infrastructure
│   ├── task/                # Task, TaskStatus, Step, Action data-classes
│   ├── agent/               # BaseAgent ABC
│   ├── tools/               # BaseTool + built-in tools
│   ├── router/              # ModelRouter (model selection)
│   ├── engine/              # ExecutionEngine – the central loop
│   ├── memory/              # ShortTermMemory + LongTermMemory (JSON)
│   ├── evals/               # Evaluator, SuccessCriteria, EvalResult
│   ├── logging/             # StructuredLogger (JSON lines)
│   └── policy/              # ApprovalPolicy (human-in-the-loop gate)
├── examples/
│   └── coding_workflow/     # CodeAgent + TestAgent + ReviewAgent
└── tests/                   # Unit + integration tests (pytest)
```

### Core Design Principles

| Principle | Implementation |
|---|---|
| Smallest system that works | ~700 lines of core code |
| Clarity over abstraction | Concrete dataclasses, no metaclass magic |
| Everything testable | 86 tests; no global mutable state |
| Separate infra from domain | `core/` has zero domain knowledge |
| Logs are first-class | Every step emits structured JSON |
| Human approval for risky actions | `ApprovalPolicy` gates any tool |
| Support failure and retries | Engine retries agent exceptions; max-step guard |

---

## Components

### 1. Task System (`core/task/task.py`)

```python
from core.task.task import Task, TaskStatus, Action, Step

task = Task(
    goal="Implement a stack in Python",
    input_data={"language": "Python"},
    max_steps=20,
)
```

A `Task` is fully serialisable (`task.to_dict()` / `Task.from_dict(d)`).
Each execution step is recorded as a `Step` on `task.steps`.

### 2. Agent Interface (`core/agent/base_agent.py`)

```python
from core.agent.base_agent import BaseAgent
from core.task.task import Action

class MyAgent(BaseAgent):
    def act(self, task, state) -> Action:
        return Action(type="done", message="Nothing to do")
```

Agents **return** `Action` objects; they never execute tools directly.

### 3. Tool Interface (`core/tools/`)

| Tool | Name | Approval required |
|---|---|---|
| `FileWriteTool` | `write_file` | No |
| `FileReadTool` | `read_file` | No |
| `TestRunnerTool` | `run_tests` | No |
| `CodeExecutionTool` | `execute_code` | **Yes** |

All tools implement `BaseTool.execute(input_data) -> ToolResult`.

### 4. Model Router (`core/router/model_router.py`)

```python
from core.router.model_router import ModelRouter

router = ModelRouter(use_real_models=False)  # mock mode (default)
spec = router.route("code_generator")       # → ModelSpec("mock", ...)
```

Set `use_real_models=True` and plug in an LLM client to use real models.

### 5. Execution Engine (`core/engine/execution_engine.py`)

The heart of the system.  Loop:

1. Select eligible agent (`agent.can_act()`)
2. Agent returns `Action`
3. Validate action
4. Gate behind `ApprovalPolicy` if required
5. Execute tool (if `tool_call`)
6. Record `Step` on task history
7. Log everything
8. Check for `done` / `fail` / max-steps

```python
from core.engine.execution_engine import ExecutionEngine

engine = ExecutionEngine(agents=[...], tools=[...])
completed_task = engine.run(task, state={"phase": "code"})
```

### 6. Memory (`core/memory/memory.py`)

```python
from core.memory.memory import ShortTermMemory, LongTermMemory

# In-process (per execution)
mem = ShortTermMemory()
mem.set("last_result", result)

# Persistent (JSON lines file)
ltm = LongTermMemory(store_path="memory/long_term.jsonl")
ltm.store("task", task.to_dict(), tags=["coding"])
ltm.retrieve_latest("task")
```

### 7. Logging (`core/logging/logger.py`)

Every step emits a structured JSON log line:

```json
{"timestamp": "2026-04-30T07:35:29Z", "level": "INFO", "logger": "core.engine",
 "event": "engine.step", "task_id": "abc123", "step": 3, "agent": "TestAgent",
 "action_type": "tool_call", "tool": "run_tests", "success": true}
```

```python
from core.logging.logger import configure_logging, get_logger

configure_logging(level="INFO")
logger = get_logger(__name__)
logger.info("my.event", task_id="...", extra_key="extra_value")
```

### 8. Evaluation System (`core/evals/evaluator.py`)

```python
from core.evals.evaluator import Evaluator, task_completed_criterion

evaluator = Evaluator(
    criteria=[task_completed_criterion()],
    results_dir="eval_results/",
)
result = evaluator.evaluate(task)
# result.overall_pass, result.score, result.criteria_results
```

Results are persisted to JSON files for trend analysis and
self-improvement loops.

### 9. Human Approval Layer (`core/policy/approval.py`)

```python
from core.policy.approval import ApprovalPolicy, ApprovalMode

# CI / automated environments:
policy = ApprovalPolicy(mode=ApprovalMode.AUTO_APPROVE)

# Interactive use:
policy = ApprovalPolicy(mode=ApprovalMode.CLI_PROMPT)

# Per-tool overrides:
policy = ApprovalPolicy(
    mode=ApprovalMode.AUTO_APPROVE,
    tool_overrides={"execute_code": ApprovalMode.CLI_PROMPT},
)
```

---

## Autonomous Coding Workflow

The first real workflow demonstrates the system end-to-end.

**Agents:**

| Agent | Role | Activates when |
|---|---|---|
| `CodeAgent` | Generates Python source code | `state["phase"] in {"code", "fix"}` |
| `TestAgent` | Writes and runs pytest tests | `state["phase"] == "test"` |
| `ReviewAgent` | Code-quality review | `state["phase"] == "review"` |

**Flow:**

```
CodeAgent ──write_file──▶ stack.py
TestAgent ──write_file──▶ test_stack.py
TestAgent ──run_tests───▶ pytest result
    ├── all pass ──▶ phase="review"
    └── failures ──▶ phase="fix" ──▶ CodeAgent regenerates
ReviewAgent ──read_file──▶ stack.py ──▶ done ✓
```

---

## How to Run

### Prerequisites

```bash
# Python 3.10+ required
pip install -r requirements.txt
```

### Run the coding workflow

```bash
cd centralized-loop/
python examples/coding_workflow/run.py
```

Expected output (truncated):

```json
{"event": "engine.start", "goal": "Implement a stack data structure in Python", ...}
{"event": "engine.step", "step": 1, "agent": "CodeAgent", "tool": "write_file", ...}
{"event": "engine.step", "step": 3, "agent": "TestAgent", "tool": "run_tests", ...}
{"event": "engine.done", ...}
...
{
  "status": "completed",
  "steps": 6,
  "output": {"final_message": "Code review passed. Notes: OK – defines a class, ..."}
}
```

### Run the tests

```bash
cd centralized-loop/
python -m pytest tests/ -v
# 86 passed in ~3s
```

---

## Future Extensions

| Area | What to do |
|---|---|
| Real LLM calls | Implement `_call_model()` in agents; set `use_real_models=True` in `ModelRouter` |
| Vector memory | Drop-in replace `LongTermMemory` with a ChromaDB / Pinecone adapter |
| Hedge fund agents | Add `ResearchAgent`, `SignalAgent`, `RiskAgent` in a new `examples/hedge_fund/` |
| Hardware design | Add `RTLAgent`, `SimAgent` in `examples/fpga_design/` |
| Distributed execution | Wrap `ExecutionEngine.run()` in Celery / Ray tasks |
| Streaming logs | Change `configure_logging()` to emit to a log aggregator |
| Web UI | Serve `task.to_dict()` via FastAPI; render in React |
| Self-improvement | Feed `EvalResult` data back into prompt construction |

---

## Directory Reference

```
centralized-loop/
├── core/
│   ├── task/task.py          Task, TaskStatus, Step, Action
│   ├── agent/base_agent.py   BaseAgent ABC
│   ├── tools/
│   │   ├── base_tool.py      BaseTool, ToolResult
│   │   ├── code_execution.py CodeExecutionTool
│   │   ├── file_tool.py      FileReadTool, FileWriteTool
│   │   └── test_runner.py    TestRunnerTool
│   ├── router/model_router.py ModelRouter, ModelSpec
│   ├── engine/execution_engine.py ExecutionEngine
│   ├── memory/memory.py      ShortTermMemory, LongTermMemory
│   ├── evals/evaluator.py    Evaluator, SuccessCriteria, EvalResult
│   ├── logging/logger.py     StructuredLogger, get_logger
│   └── policy/approval.py   ApprovalPolicy, ApprovalMode
├── examples/
│   └── coding_workflow/
│       ├── agents.py         CodeAgent, TestAgent, ReviewAgent
│       └── run.py            End-to-end entry point
├── tests/
│   ├── test_task.py
│   ├── test_tools.py
│   ├── test_engine.py
│   ├── test_memory.py
│   ├── test_evals.py
│   └── test_coding_workflow.py
├── pyproject.toml
├── requirements.txt
└── README.md
```
