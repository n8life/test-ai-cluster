"""Twelve-factor configuration loaded from environment variables."""

from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class Config:
    """Agent configuration — all values come from env vars."""

    langfuse_public_key: str = field(repr=False)
    langfuse_secret_key: str = field(repr=False)
    langfuse_host: str = field(repr=False)
    github_token: str = field(repr=False)
    target_repo: str = ""

    ollama_base_url: str = (
        "http://ollama.langchain-infra.svc.cluster.local:11434"
    )
    ollama_model: str = "gemma3:27b"
    work_dir: str = "/tmp/repos"

    @classmethod
    def from_env(cls) -> "Config":
        """Build Config from environment variables.

        Required: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST,
                  GITHUB_TOKEN, TARGET_REPO
        Optional: OLLAMA_BASE_URL, OLLAMA_MODEL, WORK_DIR
        """
        required = [
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_HOST",
            "GITHUB_TOKEN",
            "TARGET_REPO",
        ]
        missing = [v for v in required if not os.environ.get(v)]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        return cls(
            langfuse_public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            langfuse_secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            langfuse_host=os.environ["LANGFUSE_HOST"],
            github_token=os.environ["GITHUB_TOKEN"],
            target_repo=os.environ["TARGET_REPO"],
            ollama_base_url=os.environ.get(
                "OLLAMA_BASE_URL",
                "http://ollama.langchain-infra.svc.cluster.local:11434",
            ),
            ollama_model=os.environ.get("OLLAMA_MODEL", "gemma3:27b"),
            work_dir=os.environ.get("WORK_DIR", "/tmp/repos"),
        )
