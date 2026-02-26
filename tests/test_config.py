"""Tests for app.dependabot_agent.config."""

import pytest

from app.dependabot_agent.config import Config


class TestConfigFromEnv:
    def test_loads_all_values(self, env_vars):
        cfg = Config.from_env()
        assert cfg.target_repo == "n8life/nftkv"
        assert cfg.ollama_base_url == "http://localhost:11434"
        assert cfg.ollama_model == "gemma3:27b"
        assert cfg.work_dir == "/tmp/test-repos"
        assert cfg.github_token == "ghp_test123"

    def test_missing_required_var_raises(self, monkeypatch):
        # Set only some required vars
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
        monkeypatch.delenv("LANGFUSE_HOST", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("TARGET_REPO", raising=False)

        with pytest.raises(EnvironmentError, match="LANGFUSE_HOST"):
            Config.from_env()

    def test_defaults_applied(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
        monkeypatch.setenv("LANGFUSE_HOST", "http://lf:3000")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_x")
        monkeypatch.setenv("TARGET_REPO", "owner/repo")
        # Clear optional vars to verify defaults
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.delenv("WORK_DIR", raising=False)

        cfg = Config.from_env()
        assert "ollama.langchain-infra" in cfg.ollama_base_url
        assert cfg.ollama_model == "gemma3:27b"
        assert cfg.work_dir == "/tmp/repos"
