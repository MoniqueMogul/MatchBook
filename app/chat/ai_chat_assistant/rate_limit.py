from datetime import datetime, timezone
from uuid import UUID, uuid4

from redis import Redis

from app.chat.ai_chat_assistant.config import (
    AI_CHAT_GENERATION_LOCK_SECONDS,
    AI_CHAT_MINUTE_WINDOW_SECONDS,
    AI_CHAT_RATE_LIMIT_PER_MINUTE,
    AI_CHAT_DAILY_GENERATION_LIMIT,
    AI_CHAT_DAILY_WINDOW_SECONDS
)


# ============================================================
# EXCEPTIONS
# ============================================================

class AIChatRateLimitError(Exception):
    """Base exception for AI chat rate limiting."""


class AIChatTooManyRequestsError(AIChatRateLimitError):

    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many AI generation requests.")
        self.retry_after = retry_after


class AIChatDailyLimitError(AIChatRateLimitError):
    """Raised when the user's daily generation limit is reached."""


class AIChatGenerationInProgressError(AIChatRateLimitError):
    """Raised when another generation is already running."""


# ============================================================
# RATE LIMITER
# ============================================================

class AIChatRateLimiter:

    def __init__(self, redis_client: Redis) -> None:
        self.redis = redis_client

    # --------------------------------------------------------
    # GENERATION LOCK
    # --------------------------------------------------------

    def acquire_generation_lock(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
    ) -> str:
        key = self._generation_lock_key(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        lock_token = str(uuid4())

        acquired = self.redis.set(
            key,
            lock_token,
            nx=True,
            ex=AI_CHAT_GENERATION_LOCK_SECONDS,
        )

        if not acquired:
            raise AIChatGenerationInProgressError(
                "An AI generation is already in progress."
            )

        return lock_token

    def release_generation_lock(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
        lock_token: str,
    ) -> None:
        key = self._generation_lock_key(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        # Atomic:
        # Only delete the lock if it still belongs to this request.
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        self.redis.eval(
            release_script,
            1,
            key,
            lock_token,
        )

    # --------------------------------------------------------
    # SHORT-TERM RATE LIMIT
    # --------------------------------------------------------

    def reserve_daily_generation(
            self,
            *,
            user_id: UUID,
    ) -> None:
        key = self._daily_key(
            user_id=user_id,
        )

        script = """
        local current = tonumber(redis.call("GET", KEYS[1]) or "0")
        local limit = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])

        if current >= limit then
            return 0
        end

        local new_count = redis.call("INCR", KEYS[1])

        if new_count == 1 then
            redis.call("EXPIRE", KEYS[1], window)
        end

        return 1
        """

        allowed = self.redis.eval(
            script,
            1,
            key,
            AI_CHAT_DAILY_GENERATION_LIMIT,
            AI_CHAT_DAILY_WINDOW_SECONDS,
        )

        if not allowed:
            raise AIChatDailyLimitError(
                "Daily AI generation limit reached."
            )

    def release_daily_generation(
            self,
            *,
            user_id: UUID,
    ) -> None:
        key = self._daily_key(
            user_id=user_id,
        )

        script = """
        local current = tonumber(redis.call("GET", KEYS[1]) or "0")

        if current <= 0 then
            return 0
        end

        return redis.call("DECR", KEYS[1])
        """

        self.redis.eval(
            script,
            1,
            key,
        )

    # --------------------------------------------------------
    # REDIS KEYS
    # --------------------------------------------------------

    @staticmethod
    def _generation_lock_key(
        *,
        user_id: UUID,
        conversation_id: UUID,
    ) -> str:
        return (
            f"ai_chat:generation_lock:"
            f"{user_id}:{conversation_id}"
        )

    @staticmethod
    def _minute_key(
        *,
        user_id: UUID,
    ) -> str:
        return f"ai_chat:minute:{user_id}"

    @staticmethod
    def _daily_key(
        *,
        user_id: UUID,
    ) -> str:
        today = datetime.now(timezone.utc).date().isoformat()

        return f"ai_chat:daily:{user_id}:{today}"