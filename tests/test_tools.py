"""Tests for app.dependabot_agent.tools."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.dependabot_agent.tools import (
    list_dependabot_alerts,
    get_alert_details,
    clone_repo,
    read_file,
    write_file,
    list_directory,
    set_json_field,
    run_npm_install,
    run_npm_audit,
    git_checkout_branch,
    git_add_and_commit,
    git_push,
    create_pull_request,
    _run,
)


@pytest.fixture
def mock_subprocess():
    with patch("app.dependabot_agent.tools.subprocess.run") as mock:
        mock.return_value = MagicMock(
            stdout="ok", stderr="", returncode=0
        )
        yield mock


class TestRunHelper:
    def test_captures_stdout(self, mock_subprocess):
        result = _run(["echo", "hello"])
        assert result == "ok"

    def test_includes_stderr_on_failure(self, mock_subprocess):
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "bad thing"
        result = _run(["false"])
        assert "STDERR" in result
        assert "bad thing" in result
        assert "exit code 1" in result

    def test_handles_timeout(self, mock_subprocess):
        mock_subprocess.side_effect = subprocess.TimeoutExpired(
            cmd="slow", timeout=300
        )
        result = _run(["slow"])
        assert "timed out" in result


class TestListDependabotAlerts:
    def test_calls_gh_api(self, mock_subprocess):
        list_dependabot_alerts.invoke({"repo": "n8life/nftkv"})
        args = mock_subprocess.call_args[0][0]
        assert args[:2] == ["gh", "api"]
        assert "/repos/n8life/nftkv/dependabot/alerts" in args[2]


class TestGetAlertDetails:
    def test_calls_gh_api_with_number(self, mock_subprocess):
        get_alert_details.invoke({"repo": "n8life/nftkv", "alert_number": 31})
        args = mock_subprocess.call_args[0][0]
        assert "/repos/n8life/nftkv/dependabot/alerts/31" in args[2]


class TestCloneRepo:
    def test_calls_gh_repo_clone(self, mock_subprocess, tmp_path):
        dest = str(tmp_path / "repo")
        clone_repo.invoke({"repo": "n8life/nftkv", "dest_dir": dest})
        args = mock_subprocess.call_args[0][0]
        assert args[:3] == ["gh", "repo", "clone"]
        assert "n8life/nftkv" in args


class TestReadFile:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        result = read_file.invoke({"file_path": str(f)})
        assert result == "hello world"

    def test_returns_error_for_missing(self):
        result = read_file.invoke({"file_path": "/nonexistent/file.txt"})
        assert "ERROR" in result


class TestWriteFile:
    def test_writes_content(self, tmp_path):
        f = tmp_path / "out.txt"
        result = write_file.invoke({"file_path": str(f), "content": "data"})
        assert "4 bytes" in result
        assert f.read_text() == "data"

    def test_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "a" / "b" / "c.txt"
        write_file.invoke({"file_path": str(f), "content": "nested"})
        assert f.read_text() == "nested"


class TestListDirectory:
    def test_lists_contents(self, tmp_path):
        (tmp_path / "file.txt").touch()
        (tmp_path / "subdir").mkdir()
        result = list_directory.invoke({"dir_path": str(tmp_path)})
        assert "file.txt" in result
        assert "subdir/" in result


class TestSetJsonField:
    def test_sets_overrides(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text('{"name": "test", "version": "1.0.0"}')
        result = set_json_field.invoke({
            "file_path": str(f),
            "field": "overrides",
            "value": '{"tar": "7.5.8", "ajv": "8.18.0"}',
        })
        import json
        data = json.loads(f.read_text())
        assert data["overrides"] == {"tar": "7.5.8", "ajv": "8.18.0"}
        assert data["name"] == "test"
        assert "Set 'overrides'" in result

    def test_error_on_invalid_json_value(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text('{"name": "test"}')
        result = set_json_field.invoke({
            "file_path": str(f),
            "field": "overrides",
            "value": "not json",
        })
        assert "ERROR" in result


class TestRunNpmInstall:
    def test_runs_in_project_dir(self, mock_subprocess, tmp_path):
        run_npm_install.invoke({"project_dir": str(tmp_path)})
        args = mock_subprocess.call_args[0][0]
        assert args == ["npm", "install", "--legacy-peer-deps"]
        assert mock_subprocess.call_args[1]["cwd"] == str(tmp_path)


class TestRunNpmAudit:
    def test_runs_audit_json(self, mock_subprocess, tmp_path):
        run_npm_audit.invoke({"project_dir": str(tmp_path)})
        args = mock_subprocess.call_args[0][0]
        assert args == ["npm", "audit", "--json"]


class TestGitCheckoutBranch:
    def test_runs_checkout(self, mock_subprocess, tmp_path):
        git_checkout_branch.invoke({
            "project_dir": str(tmp_path),
            "branch_name": "fix/deps",
        })
        args = mock_subprocess.call_args[0][0]
        assert args == ["git", "checkout", "-b", "fix/deps"]
        assert mock_subprocess.call_args[1]["cwd"] == str(tmp_path)


class TestGitAddAndCommit:
    def test_runs_add_then_commit(self, mock_subprocess, tmp_path):
        git_add_and_commit.invoke({
            "project_dir": str(tmp_path),
            "message": "fix deps",
        })
        calls = [c[0][0] for c in mock_subprocess.call_args_list]
        assert calls[0] == ["git", "add", "-A"]
        assert calls[1][:2] == ["git", "commit"]
        assert "fix deps" in calls[1]

    def test_stops_on_add_failure(self, mock_subprocess, tmp_path):
        mock_subprocess.return_value = MagicMock(
            stdout="", stderr="fatal: not a git repo", returncode=128
        )
        result = git_add_and_commit.invoke({
            "project_dir": str(tmp_path),
            "message": "fix deps",
        })
        assert "exit code" in result
        # Should only have called git add, not git commit
        assert mock_subprocess.call_count == 1


class TestGitPush:
    def test_pushes_head(self, mock_subprocess, tmp_path):
        git_push.invoke({"project_dir": str(tmp_path)})
        args = mock_subprocess.call_args[0][0]
        assert args == ["git", "push", "-u", "origin", "HEAD"]
        assert mock_subprocess.call_args[1]["cwd"] == str(tmp_path)


class TestCreatePullRequest:
    def test_calls_gh_pr_create(self, mock_subprocess, tmp_path):
        create_pull_request.invoke({
            "project_dir": str(tmp_path),
            "title": "fix: deps",
            "body": "Fixes alerts",
        })
        args = mock_subprocess.call_args[0][0]
        assert args[:3] == ["gh", "pr", "create"]
        assert "--title" in args
