"""LLM and Langfuse callback construction."""

from langchain_ollama import ChatOllama
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

from app.dependabot_agent.config import Config


def build_llm(config: Config) -> ChatOllama:
    """Create a ChatOllama instance pointed at the in-cluster Ollama service."""
    return ChatOllama(
        base_url=config.ollama_base_url,
        model=config.ollama_model,
        temperature=0.2,
    )


def get_langfuse_handler() -> LangfuseCallbackHandler:
    """Build a Langfuse callback handler from environment variables.

    langfuse v3+ reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and
    LANGFUSE_HOST automatically from the environment.
    """
    return LangfuseCallbackHandler()
