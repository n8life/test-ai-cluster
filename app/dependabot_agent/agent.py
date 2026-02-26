"""Text-based ReAct agent for fixing Dependabot alerts.

Uses regex parsing of LLM output instead of native tool-calling,
since Gemma3:27b via Ollama does not support the tools API.
"""

import json
import re
import sys
import time

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

from app.dependabot_agent.config import Config
from app.dependabot_agent.llm import build_llm, get_langfuse_handler
from app.dependabot_agent.prompts import REACT_SYSTEM_PROMPT
from app.dependabot_agent.tools import ALL_TOOLS

MAX_ITERATIONS = 30

# Regex to extract Action and Action Input from LLM text
ACTION_RE = re.compile(
    r"Action\s*:\s*(.+?)\s*\n"
    r"Action\s+Input\s*:\s*(.+)",
    re.DOTALL,
)
FINAL_ANSWER_RE = re.compile(r"Final\s+Answer\s*:\s*(.+)", re.DOTALL)


def _build_system_message() -> str:
    """Render the system prompt with tool descriptions."""
    tool_descriptions = "\n\n".join(
        f"**{t.name}**: {t.description}" for t in ALL_TOOLS
    )
    tool_names = ", ".join(t.name for t in ALL_TOOLS)
    return REACT_SYSTEM_PROMPT.format(
        tool_descriptions=tool_descriptions,
        tool_names=tool_names,
    )


def _find_tool(name: str):
    """Look up a tool by name (case-insensitive)."""
    for t in ALL_TOOLS:
        if t.name.lower() == name.strip().lower():
            return t
    return None


def _parse_tool_input(raw: str) -> dict | str:
    """Try to parse Action Input as JSON; fall back to raw string.

    Uses json.JSONDecoder to extract the first valid JSON object, which
    handles cases where the LLM appends extra text after the JSON.
    """
    raw = raw.strip()
    # Try direct parse first
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    # Try to extract the first JSON object from the text
    try:
        decoder = json.JSONDecoder()
        idx = raw.index("{")
        obj, _ = decoder.raw_decode(raw, idx)
        return obj
    except (ValueError, json.JSONDecodeError):
        pass
    return raw


def run_react_loop(config: Config, handler: LangfuseCallbackHandler) -> str:
    """Run the text-based ReAct loop and return the final answer."""
    llm = build_llm(config)
    system_msg = _build_system_message()

    task = (
        f"Fix all open Dependabot security alerts for the repository "
        f"'{config.target_repo}'. Clone it to '{config.work_dir}/{config.target_repo}', "
        f"apply the fixes, and create a pull request."
    )

    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=task),
    ]

    for i in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- Iteration {i}/{MAX_ITERATIONS} ---")

        response = llm.invoke(messages, config={"callbacks": [handler]})
        text = response.content
        print(text)

        messages.append(AIMessage(content=text))

        # Check for Final Answer
        final_match = FINAL_ANSWER_RE.search(text)
        if final_match:
            return final_match.group(1).strip()

        # Parse Action / Action Input
        action_match = ACTION_RE.search(text)
        if not action_match:
            # Parsing error — ask the LLM to correct its format
            err = (
                "Could not parse your response. You MUST use exactly:\n"
                "Thought: ...\nAction: <tool_name>\nAction Input: <json>\n"
                "Or: Final Answer: <summary>"
            )
            print(f"[PARSE ERROR] {err}")
            messages.append(HumanMessage(content=f"Observation: {err}"))
            continue

        tool_name = action_match.group(1).strip()
        raw_input = action_match.group(2).strip()
        tool = _find_tool(tool_name)

        if tool is None:
            err = (
                f"Unknown tool '{tool_name}'. "
                f"Available tools: {', '.join(t.name for t in ALL_TOOLS)}"
            )
            print(f"[TOOL ERROR] {err}")
            messages.append(HumanMessage(content=f"Observation: {err}"))
            continue

        tool_input = _parse_tool_input(raw_input)
        print(f"[TOOL] {tool_name}({tool_input})")

        try:
            result = tool.invoke(tool_input)
        except Exception as exc:
            result = f"ERROR running {tool_name}: {exc}"

        # Truncate very long results — keep head + tail so exit codes are visible
        result_str = str(result)
        if len(result_str) > 6000:
            head = result_str[:3000]
            tail = result_str[-2000:]
            result_str = f"{head}\n\n... (truncated {len(result_str)} chars) ...\n\n{tail}"

        print(f"[OBSERVATION] {result_str[:500]}{'...' if len(result_str) > 500 else ''}")
        messages.append(HumanMessage(content=f"Observation: {result_str}"))

    return "Agent reached maximum iterations without completing."


def run_agent() -> int:
    """Entry point: load config, run ReAct loop, and return exit code."""
    try:
        config = Config.from_env()
    except EnvironmentError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("Dependabot Security Fix Agent")
    print("=" * 60)
    print(f"Target repo : {config.target_repo}")
    print(f"Ollama URL  : {config.ollama_base_url}")
    print(f"Model       : {config.ollama_model}")
    print(f"Work dir    : {config.work_dir}")
    print("=" * 60)

    handler = get_langfuse_handler()

    try:
        final_answer = run_react_loop(config, handler)
        print("\n" + "=" * 60)
        print("Agent finished.")
        print(f"Final Answer: {final_answer}")
        print("=" * 60)
    except Exception as exc:
        print(f"\nERROR: Agent failed — {exc}", file=sys.stderr)
        return 1
    finally:
        # Give Langfuse time to flush traces
        time.sleep(5)

    return 0
