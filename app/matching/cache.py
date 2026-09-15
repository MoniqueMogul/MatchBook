import json
import os
from typing import Any

import redis

from app.matching.config import MATCHING_VERSION


DEFAULT_CACHE_TTL_SECONDS = int(
    os.getenv(
        "MATCHBOOK_MATCH_CACHE_TTL_SECONDS",
        "300",
    )
)

REDIS_URL = os.getenv(
    "MATCHBOOK_REDIS_URL",
    "redis://localhost:6379/0",
)


class MatchCache:
    """
    Redis-backed cache for ranked MatchBook results.

    PostgreSQL remains the source of truth.
    Redis only stores temporary/cached matching results.
    """

    def __init__(
        self,
        redis_url: str = REDIS_URL,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError(
                "ttl_seconds must be greater than zero"
            )

        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        """
        Lazily create the Redis client.

        Importing the Matching module therefore does not require
        a live Redis server.
        """
        if self._client is None:
            self._client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
            )

        return self._client

    @staticmethod
    def ranked_matches_key(
        buyer_id: int,
    ) -> str:
        """
        Version is included so results from different matching
        algorithms never share the same cache entry.
        """
        return (
            f"matchbook:matching:"
            f"{MATCHING_VERSION}:"
            f"buyer:{buyer_id}:ranked"
        )

    def set_ranked_matches(
        self,
        buyer_id: int,
        results: list[dict[str, Any]],
    ) -> None:
        key = self.ranked_matches_key(
            buyer_id
        )

        payload = json.dumps(
            results,
            separators=(",", ":"),
        )

        self.client.setex(
            key,
            self.ttl_seconds,
            payload,
        )

    def get_ranked_matches(
        self,
        buyer_id: int,
    ) -> list[dict[str, Any]] | None:
        key = self.ranked_matches_key(
            buyer_id
        )

        payload = self.client.get(
            key
        )

        if payload is None:
            return None

        parsed = json.loads(
            payload
        )

        if not isinstance(parsed, list):
            return None

        return parsed

    def invalidate_buyer(
        self,
        buyer_id: int,
    ) -> None:
        """
        Invalidate cached rankings whenever data affecting a
        buyer's matches changes.
        """
        self.client.delete(
            self.ranked_matches_key(
                buyer_id
            )
        )


_match_cache: MatchCache | None = None


def get_match_cache() -> MatchCache:
    global _match_cache

    if _match_cache is None:
        _match_cache = MatchCache()

    return _match_cache