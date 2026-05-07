# Centralized Loop

Centralized Loop is a conservative, single-kernel agent orchestration system for deterministic coding, research, and C++ execution workflows.

## What it is
- A centralized execution engine that selects agents, validates actions, gates risky tools, executes tools, records steps, logs JSONL traces, and persists eval results.
- A small infrastructure repo for reliable mock-first workflow development.
- A place to add narrowly scoped tools and workflows without changing the core loop shape.

## What it is not
- Browser automation
- Email automation
- Trading execution or hedge fund logic
- FPGA/Verilog automation
- Local Hugging Face or vLLM serving
- Multi-agent swarm expansion
- Distributed deployment or self-improvement loops

## Architecture
```text
Task + state
  -> ExecutionEngine
     -> select eligible agent
     -> agent returns Action
     -> validate Action
     -> ApprovalPolicy gates risky tool calls
     -> Tool executes and returns ToolResult
     -> Step is recorded on the Task
     -> RunTrace writes JSONL logs
     -> Evaluator persists JSON results
```

## Repository layout
- `centralized-loop/core/` - engine, tasks, tools, approvals, logging, evals, model clients
- `centralized-loop/examples/coding_workflow/` - deterministic Python coding workflow
- `centralized-loop/examples/research_workflow/` - deterministic research workflow
- `centralized-loop/examples/cpp_workflow/` - deterministic C++ workflow
- `centralized-loop/tests/` - unit and integration tests

## Local setup
```bash
cd centralized-loop
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

## Run tests
```bash
cd centralized-loop
python -m pytest tests/ -v --no-cov
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy .
```

## Run mock examples
```bash
cd centralized-loop
MODEL_PROVIDER=mock CENTRALIZED_LOOP_SAFE_MODE=true python -m examples.coding_workflow.run
MODEL_PROVIDER=mock CENTRALIZED_LOOP_SAFE_MODE=true python -m examples.research_workflow.run
MODEL_PROVIDER=mock CENTRALIZED_LOOP_SAFE_MODE=true python -m examples.cpp_workflow.run
```

The C++ workflow skips gracefully if `g++` is unavailable.

## Run with DeepSeek
```bash
cd centralized-loop
export MODEL_PROVIDER=deepseek
export DEEPSEEK_API_KEY=your_key
export DEEPSEEK_BASE_URL=https://api.deepseek.com
export DEEPSEEK_MODEL=deepseek-chat
python -m examples.research_workflow.run
```

## Run with Anthropic
```bash
cd centralized-loop
export MODEL_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your_key
export ANTHROPIC_MODEL=claude-3-5-sonnet-latest
python -m examples.research_workflow.run
```

## Add a new tool
1. Add a `BaseTool` implementation in `centralized-loop/core/tools/`.
2. Define a stable `name`, `input_schema`, and structured `ToolResult`.
3. Mark risky execution tools so the approval policy can gate them.
4. Register the tool in the workflow engine and add focused tests.

## Add a new workflow
1. Create agents under `centralized-loop/examples/<workflow_name>/`.
2. Keep orchestration in `ExecutionEngine`; agents should return `Action` objects only.
3. Reuse `ModelClient` instead of calling provider SDKs directly.
4. Persist eval results and assert deterministic behavior in tests.

## CI
GitHub Actions runs on push and pull requests across Python 3.11 and 3.12. It installs dev dependencies, checks formatting and linting with Ruff, runs mypy, runs pytest with coverage, and executes the deterministic coding, research, and C++ workflows in mock mode.
