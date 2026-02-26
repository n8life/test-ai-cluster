"""
LangChain + Langfuse integration test.

Sends a few prompts to Gemma3 (via Ollama) and traces everything
through Langfuse so you can verify both the AI workload and the
observability pipeline are working end-to-end.
"""

import os
import sys
import time

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler


def get_langfuse_handler() -> LangfuseCallbackHandler:
    """Build a Langfuse callback handler from environment variables.

    langfuse v3+ reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and
    LANGFUSE_HOST automatically from the environment.
    """
    return LangfuseCallbackHandler()


def build_llm() -> ChatOllama:
    """Create a ChatOllama instance pointed at the in-cluster Ollama service."""
    return ChatOllama(
        base_url=os.environ.get(
            "OLLAMA_BASE_URL",
            "http://ollama.langchain-infra.svc.cluster.local:11434",
        ),
        model=os.environ.get("OLLAMA_MODEL", "gemma3:27b"),
        temperature=0.7,
    )


def test_simple_question(llm: ChatOllama, handler: LangfuseCallbackHandler) -> bool:
    """Test 1 — ask a simple factual question."""
    print("\n--- Test 1: Simple question ---")
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content="You are a helpful assistant. Keep answers concise."),
            ("human", "{question}"),
        ]
    )
    chain = prompt | llm | StrOutputParser()

    response = chain.invoke(
        {"question": "What is the capital of France?"},
        config={"callbacks": [handler]},
    )
    print(f"Q: What is the capital of France?\nA: {response}")
    passed = "paris" in response.lower()
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return passed


def test_creative_prompt(llm: ChatOllama, handler: LangfuseCallbackHandler) -> bool:
    """Test 2 — ask a creative/generative question."""
    print("\n--- Test 2: Creative prompt ---")
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content="You are a helpful assistant. Keep answers to one paragraph."
            ),
            ("human", "{question}"),
        ]
    )
    chain = prompt | llm | StrOutputParser()

    response = chain.invoke(
        {"question": "Explain why the sky is blue in simple terms."},
        config={"callbacks": [handler]},
    )
    print(f"Q: Explain why the sky is blue in simple terms.\nA: {response}")
    passed = len(response.strip()) > 20
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return passed


def test_multi_turn(llm: ChatOllama, handler: LangfuseCallbackHandler) -> bool:
    """Test 3 — multi-message conversation to verify message handling."""
    print("\n--- Test 3: Multi-turn conversation ---")
    messages = [
        SystemMessage(content="You are a helpful math tutor. Be concise."),
        HumanMessage(content="What is 7 * 8?"),
    ]
    response = llm.invoke(messages, config={"callbacks": [handler]})
    print(f"Q: What is 7 * 8?\nA: {response.content}")
    passed = "56" in response.content
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return passed


def main() -> int:
    required_vars = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        return 1

    print("=" * 60)
    print("LangChain + Langfuse Cluster Validation Test")
    print("=" * 60)
    print(f"Ollama URL : {os.environ.get('OLLAMA_BASE_URL', 'http://ollama.langchain-infra.svc.cluster.local:11434')}")
    print(f"Model      : {os.environ.get('OLLAMA_MODEL', 'gemma3:27b')}")
    print(f"Langfuse   : {os.environ['LANGFUSE_HOST']}")

    handler = get_langfuse_handler()
    llm = build_llm()

    results = []
    for test_fn in [test_simple_question, test_creative_prompt, test_multi_turn]:
        try:
            results.append(test_fn(llm, handler))
        except Exception as exc:
            print(f"\nERROR in {test_fn.__name__}: {exc}")
            results.append(False)

    # Give Langfuse time to export traces
    time.sleep(5)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("ALL TESTS PASSED — cluster validation successful!")
        return 0
    else:
        print("SOME TESTS FAILED — check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
