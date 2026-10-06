"""Shared provider configuration for MatchBook's on-demand writing tools."""
import os


AI_MODEL = "gpt-5.4-mini"


def ai_model() -> str:
    return AI_MODEL


def ai_client():
    from openai import OpenAI

    api_key = os.getenv("MATCHBOOK_CHAT_AI_MODEL")

    if not api_key:
        raise RuntimeError(
            "MATCHBOOK_CHAT_AI_MODEL environment variable is not set"
        )

    return OpenAI(api_key=api_key)