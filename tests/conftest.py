"""Shared fixtures for dependabot_agent tests."""

import os

import pytest

from app.dependabot_agent.config import Config


@pytest.fixture
def env_vars(monkeypatch):
    """Set all required environment variables for Config."""
    vars = {
        "LANGFUSE_PUBLIC_KEY": "pk-test",
        "LANGFUSE_SECRET_KEY": "sk-test",
        "LANGFUSE_HOST": "http://localhost:3000",
        "GITHUB_TOKEN": "ghp_test123",
        "GH_TOKEN": "ghp_test123",
        "TARGET_REPO": "n8life/nftkv",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "gemma3:27b",
        "WORK_DIR": "/tmp/test-repos",
    }
    for k, v in vars.items():
        monkeypatch.setenv(k, v)
    return vars


@pytest.fixture
def config(env_vars) -> Config:
    """Build a Config from test environment variables."""
    return Config.from_env()
