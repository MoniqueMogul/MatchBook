import json
import os
import time

from openai import OpenAI

from app.chat.ai_chat_assistant.config import (
    ACTIVE_INTRODUCTION_PROMPT,
    PromptConfig,
)
from app.chat.ai_chat_assistant.schema import (
    AIGenerationMetadata,
    AIIntroductionContext,
    AIIntroductionGenerationResult,
    GeneratedIntroduction,
)


class AIIntroductionGenerationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        error_code: str,
    ) -> None:
        super().__init__(message)

        self.error_code = error_code


class AIIntroductionLLM:
    """
    Generates introduction suggestions from trusted
    MatchBook context.

    This layer owns communication with the LLM provider.

    It does not:
    - query the database
    - calculate match compatibility
    - persist generated messages
    - send chat messages
    """

    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        model: str | None = None,
        prompt: PromptConfig = ACTIVE_INTRODUCTION_PROMPT,
    ) -> None:
        self.client = client or OpenAI()

        self.model = (
            model
            or os.getenv("MATCHBOOK_CHAT_AI_MODEL")
            or "gpt-5.4-mini"
        )

        self.prompt = prompt

    # ========================================================
    # GENERATE
    # ========================================================

    def generate_introduction(
        self,
        *,
        context: AIIntroductionContext,
        instruction: str | None = None,
    ) -> AIIntroductionGenerationResult:
        """
        Generate an introduction and return both the generated
        message and operational metadata.
        """

        started_at = time.perf_counter()

        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": self.prompt.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": self._build_user_prompt(
                            context=context,
                            instruction=instruction,
                        ),
                    },
                ],
                text_format=GeneratedIntroduction,
            )

        except Exception as exc:
            raise AIIntroductionGenerationError(
                "Failed to generate AI introduction."
            ) from exc

        latency_ms = int(
            (time.perf_counter() - started_at) * 1000
        )

        introduction = response.output_parsed

        if introduction is None:
            raise AIIntroductionGenerationError(
                "The AI returned no introduction."
            )

        metadata = AIGenerationMetadata(
            model=self.model,
            prompt_version=self.prompt.version,
            latency_ms=latency_ms,
            input_tokens=self._get_input_tokens(response),
            output_tokens=self._get_output_tokens(response),
        )

        return AIIntroductionGenerationResult(
            introduction=introduction,
            metadata=metadata,
        )

    # ========================================================
    # USER PROMPT
    # ========================================================

    @staticmethod
    def _build_user_prompt(
        *,
        context: AIIntroductionContext,
        instruction: str | None,
    ) -> str:
        """
        Serialize only the controlled AI context.
        """

        context_data = context.model_dump(
            mode="json",
            exclude_none=True,
        )

        context_json = json.dumps(
            context_data,
            indent=2,
        )

        user_instruction = (
            instruction.strip()
            if instruction and instruction.strip()
            else "No additional writing instruction was provided."
        )

        return f"""
MATCHBOOK_CONTEXT:

{context_json}

USER_INSTRUCTION:

{user_instruction}

Write one useful first-message introduction using the trusted
MatchBook context above.
""".strip()

    # ========================================================
    # TOKEN USAGE
    # ========================================================

    @staticmethod
    def _get_input_tokens(
        response,
    ) -> int | None:
        """
        Safely retrieve input-token usage.

        Returning None is better than inventing 0 when the
        provider does not return usage information.
        """

        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage is None:
            return None

        return getattr(
            usage,
            "input_tokens",
            None,
        )

    @staticmethod
    def _get_output_tokens(
        response,
    ) -> int | None:
        """
        Safely retrieve output-token usage.
        """

        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage is None:
            return None

        return getattr(
            usage,
            "output_tokens",
            None,
        )