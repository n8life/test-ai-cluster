"""Tool definitions for the Dependabot fix agent.

Each tool wraps a subprocess call (gh, git, npm) or file I/O operation.
"""

import json
import os
import subprocess
from pathlib import Path

from langchain_core.tools import tool


TIMEOUT = 300  # seconds


def _run(cmd: list[str], cwd: str | None = None) -> str:
    """Run a subprocess with timeout and return combined stdout/stderr."""
    env = os.environ.copy()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=cwd,
            env=env,
        )
        output = result.stdout
        if result.returncode != 0:
            output += f"\nSTDERR:\n{result.stderr}" if result.stderr else ""
            output += f"\n[exit code {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {TIMEOUT}s: {' '.join(cmd)}"
    except Exception as exc:
        return f"ERROR: {exc}"


@tool
def list_dependabot_alerts(repo: str) -> str:
    """List open Dependabot security alerts for a GitHub repository.

    Args:
        repo: Owner/repo string, e.g. 'n8life/nftkv'.
    """
    return _run([
        "gh", "api",
        f"/repos/{repo}/dependabot/alerts",
        "--jq",
        '.[] | select(.state=="open") | {number, severity: .security_advisory.severity, package: .security_vulnerability.package.name, title: .security_advisory.summary}',
    ])


@tool
def get_alert_details(repo: str, alert_number: int) -> str:
    """Get detailed information about a single Dependabot alert.

    Args:
        repo: Owner/repo string, e.g. 'n8life/nftkv'.
        alert_number: The alert number to fetch.
    """
    return _run([
        "gh", "api",
        f"/repos/{repo}/dependabot/alerts/{alert_number}",
        "--jq",
        '{number, state, severity: .security_advisory.severity, summary: .security_advisory.summary, package: .security_vulnerability.package.name, vulnerable_range: .security_vulnerability.vulnerable_version_range, first_patched: .security_vulnerability.first_patched_version.identifier}',
    ])


@tool
def clone_repo(repo: str, dest_dir: str) -> str:
    """Clone a GitHub repository to a local directory.

    Args:
        repo: Owner/repo string, e.g. 'n8life/nftkv'.
        dest_dir: Destination directory path.
    """
    Path(dest_dir).parent.mkdir(parents=True, exist_ok=True)
    return _run(["gh", "repo", "clone", repo, dest_dir])


@tool
def read_file(file_path: str) -> str:
    """Read and return the contents of a file.

    Args:
        file_path: Absolute path to the file.
    """
    try:
        return Path(file_path).read_text()
    except Exception as exc:
        return f"ERROR: {exc}"


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file, creating parent directories if needed.

    Args:
        file_path: Absolute path to the file.
        content: The content to write.
    """
    try:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Wrote {len(content)} bytes to {file_path}"
    except Exception as exc:
        return f"ERROR: {exc}"


@tool
def list_directory(dir_path: str) -> str:
    """List the contents of a directory.

    Args:
        dir_path: Absolute path to the directory.
    """
    try:
        entries = sorted(Path(dir_path).iterdir())
        return "\n".join(e.name + ("/" if e.is_dir() else "") for e in entries)
    except Exception as exc:
        return f"ERROR: {exc}"


@tool
def set_json_field(file_path: str, field: str, value: str) -> str:
    """Set or merge a top-level field in a JSON file (e.g. package.json).

    If the field already exists and both old and new values are objects,
    the new keys are merged into the existing object (existing keys are
    preserved unless overridden). Otherwise the field is replaced entirely.

    Use this instead of write_file for package.json edits to avoid JSON
    escaping issues.

    Args:
        file_path: Absolute path to the JSON file.
        field: Top-level field name to set (e.g. 'overrides').
        value: JSON-encoded value to set (e.g. '{"tar": "7.5.8", "ajv": "8.18.0"}').
    """
    try:
        p = Path(file_path)
        data = json.loads(p.read_text())
        parsed_value = json.loads(value)
        # Merge if both existing and new values are dicts
        if field in data and isinstance(data[field], dict) and isinstance(parsed_value, dict):
            data[field] = {**data[field], **parsed_value}
        else:
            data[field] = parsed_value
        p.write_text(json.dumps(data, indent=2) + "\n")
        return f"Set '{field}' in {file_path} to {json.dumps(data[field])}"
    except Exception as exc:
        return f"ERROR: {exc}"


@tool
def run_npm_install(project_dir: str, legacy_peer_deps: bool = True) -> str:
    """Run 'npm install' to regenerate package-lock.json.

    Uses --legacy-peer-deps by default to avoid peer dependency conflicts
    in projects like React Native / Expo.

    Args:
        project_dir: Absolute path to the project root (contains package.json).
        legacy_peer_deps: Pass --legacy-peer-deps flag (default: True).
    """
    cmd = ["npm", "install"]
    if legacy_peer_deps:
        cmd.append("--legacy-peer-deps")
    return _run(cmd, cwd=project_dir)


@tool
def run_npm_audit(project_dir: str) -> str:
    """Run 'npm audit --json' and return the results.

    Args:
        project_dir: Absolute path to the project root.
    """
    return _run(["npm", "audit", "--json"], cwd=project_dir)


@tool
def git_checkout_branch(project_dir: str, branch_name: str) -> str:
    """Create and switch to a new git branch.

    Args:
        project_dir: Absolute path to the repo.
        branch_name: Name for the new branch.
    """
    return _run(["git", "checkout", "-b", branch_name], cwd=project_dir)


@tool
def git_add_and_commit(project_dir: str, message: str) -> str:
    """Stage all changes and commit with the given message.

    Args:
        project_dir: Absolute path to the repo.
        message: Commit message.
    """
    add_result = _run(["git", "add", "-A"], cwd=project_dir)
    if "ERROR" in add_result or "exit code" in add_result:
        return add_result
    commit_result = _run(["git", "commit", "-m", message], cwd=project_dir)
    return f"$ git add -A\n{add_result}\n\n$ git commit -m \"{message}\"\n{commit_result}"


@tool
def git_push(project_dir: str) -> str:
    """Push the current branch to origin.

    Configures the repo remote to use GITHUB_TOKEN for HTTPS auth
    so that pushes work in non-interactive environments.

    Args:
        project_dir: Absolute path to the repo.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        # Rewrite the origin URL to embed the token for HTTPS auth
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=project_dir,
        )
        origin_url = result.stdout.strip()
        if origin_url.startswith("https://github.com/"):
            authed_url = origin_url.replace(
                "https://github.com/",
                f"https://x-access-token:{token}@github.com/",
            )
            _run(["git", "remote", "set-url", "origin", authed_url], cwd=project_dir)

    return _run(["git", "push", "-u", "origin", "HEAD"], cwd=project_dir)


@tool
def create_pull_request(
    project_dir: str, title: str, body: str, base: str = "main"
) -> str:
    """Create a GitHub pull request from the current branch.

    Args:
        project_dir: Absolute path to the repo.
        title: PR title.
        body: PR body/description.
        base: Base branch to merge into (default: main).
    """
    return _run(
        ["gh", "pr", "create", "--title", title, "--body", body, "--base", base],
        cwd=project_dir,
    )


ALL_TOOLS = [
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
]
