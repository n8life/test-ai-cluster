"""Tests for app.dependabot_agent.agent."""

from unittest.mock import patch, MagicMock

import pytest

from app.dependabot_agent.agent import (
    _build_system_message,
    _find_tool,
    _parse_tool_input,
    ACTION_RE,
    FINAL_ANSWER_RE,
)
from app.dependabot_agent.tools import ALL_TOOLS


class TestSystemMessage:
    def test_contains_all_tool_names(self):
        msg = _build_system_message()
        for tool in ALL_TOOLS:
            assert tool.name in msg

    def test_contains_key_instructions(self):
        msg = _build_system_message()
        assert "Dependabot" in msg
        assert "overrides" in msg
        assert "npm install" in msg
        assert "pull request" in msg


class TestFindTool:
    def test_finds_by_exact_name(self):
        tool = _find_tool("clone_repo")
        assert tool is not None
        assert tool.name == "clone_repo"

    def test_case_insensitive(self):
        tool = _find_tool("Clone_Repo")
        assert tool is not None

    def test_returns_none_for_unknown(self):
        assert _find_tool("nonexistent_tool") is None


class TestParseToolInput:
    def test_parses_json_object(self):
        result = _parse_tool_input('{"repo": "n8life/nftkv"}')
        assert result == {"repo": "n8life/nftkv"}

    def test_falls_back_to_string(self):
        result = _parse_tool_input("just a string")
        assert result == "just a string"


class TestRegexParsing:
    def test_action_regex_matches(self):
        text = (
            "Thought: I need to list alerts\n"
            "Action: list_dependabot_alerts\n"
            'Action Input: {"repo": "n8life/nftkv"}'
        )
        match = ACTION_RE.search(text)
        assert match is not None
        assert match.group(1).strip() == "list_dependabot_alerts"
        assert "n8life/nftkv" in match.group(2)

    def test_final_answer_regex_matches(self):
        text = "Thought: All done\nFinal Answer: Created PR #42 with fixes."
        match = FINAL_ANSWER_RE.search(text)
        assert match is not None
        assert "PR #42" in match.group(1)
