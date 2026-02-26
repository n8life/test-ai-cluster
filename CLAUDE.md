# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kubernetes cluster validation suite with two workloads that run as K8s Jobs, both using Ollama (Gemma3 27B) for LLM inference and Langfuse for observability:

1. **Cluster validation test** (`app/main.py`) — sends prompts to Gemma3 via LangChain and verifies responses, proving the AI + observability stack works end-to-end.
2. **Dependabot fix agent** (`app/dependabot_agent/`) — a text-based ReAct agent that autonomously fixes Dependabot security alerts by cloning a repo, updating npm dependencies/overrides, and opening a PR.

## Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync --dev

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_tools.py

# Run a single test class or method
uv run pytest tests/test_tools.py::TestSetJsonField
uv run pytest tests/test_tools.py::TestSetJsonField::test_sets_overrides

# Build container images
./build-and-push.sh                        # main test image
./build-and-push.sh Dockerfile.dependabot   # dependabot agent image

# Deploy to Kubernetes
# First, load secrets from .env and apply secret manifests via envsubst
set -a && source .env && set +a
kubectl apply -f k8s/namespace.yaml
envsubst < k8s/secret.yaml | kubectl apply -f -
envsubst < k8s/github-token-secret.yaml | kubectl apply -f -
kubectl apply -f k8s/job.yaml               # cluster validation test
kubectl apply -f k8s/dependabot-fix-job.yaml # dependabot agent
```

## Architecture

### Cluster Validation Test (`app/main.py`)
Standalone script that runs three LangChain prompt tests (factual Q&A, creative generation, multi-turn conversation) against Ollama. Each call uses `LangfuseCallbackHandler` to trace to Langfuse. Exits 0 on all-pass, 1 on any failure.

### Dependabot Fix Agent (`app/dependabot_agent/`)
A ReAct (Thought→Action→Observation) loop that uses **regex parsing** of LLM output rather than native tool-calling, because Gemma3 via Ollama doesn't support the tools API.

- `config.py` — frozen dataclass loaded from env vars via `Config.from_env()`
- `llm.py` — constructs `ChatOllama` and `LangfuseCallbackHandler`
- `prompts.py` — ReAct system prompt template with `{tool_descriptions}` and `{tool_names}` placeholders
- `tools.py` — LangChain `@tool`-decorated functions wrapping `gh`, `git`, `npm`, and file I/O. All subprocess calls go through `_run()` helper with 300s timeout
- `agent.py` — the ReAct loop (`run_react_loop`): parses `ACTION_RE` / `FINAL_ANSWER_RE` regexes from LLM output, dispatches to tools, feeds observations back. Max 30 iterations. Truncates tool output >6000 chars.

### Kubernetes Manifests (`k8s/`)
Both workloads deploy as K8s Jobs in the `langchain-test` namespace. They pull Langfuse credentials from a `langfuse-credentials` secret and the dependabot agent also uses a `github-token` secret. Node affinity excludes `k8s002`. Images are pushed to Docker Hub under `nsmith2100/`.

## Key Environment Variables

All configuration is via environment variables (12-factor):

| Variable | Used by | Required |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | Both | Yes |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Both | No (defaults to in-cluster Ollama, gemma3:27b) |
| `GITHUB_TOKEN` / `GH_TOKEN` | Dependabot agent | Yes (for agent) |
| `TARGET_REPO` | Dependabot agent | Yes (for agent) |
| `WORK_DIR` | Dependabot agent | No (defaults to /tmp/repos) |

## Testing Notes

- Tests use `pytest` with `pytest-mock`. Shared fixtures in `tests/conftest.py` provide `env_vars` and `config` fixtures.
- Subprocess calls in tools are mocked via `mock_subprocess` fixture (patches `app.dependabot_agent.tools.subprocess.run`).
- Tests are pure unit tests — no network or cluster required.
