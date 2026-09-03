import json
from unittest.mock import Mock

from app.matching.cache import (
    MatchCache,
)


def make_cache() -> tuple[MatchCache, Mock]:
    cache = MatchCache(
        redis_url="redis://test",
        ttl_seconds=300,
    )

    fake_client = Mock()

    cache._client = fake_client

    return cache, fake_client


def test_cache_key_contains_matching_version():
    key = MatchCache.ranked_matches_key(
        42
    )

    assert (
        key
        == "matchbook:matching:v1:buyer:42:ranked"
    )


def test_set_ranked_matches():
    cache, client = make_cache()

    results = [
        {
            "rank": 1,
            "score": 0.90,
        }
    ]

    cache.set_ranked_matches(
        42,
        results,
    )

    client.setex.assert_called_once()

    args = (
        client.setex
        .call_args
        .args
    )

    assert args[0] == (
        "matchbook:matching:"
        "v1:buyer:42:ranked"
    )

    assert args[1] == 300

    assert json.loads(
        args[2]
    ) == results


def test_get_ranked_matches():
    cache, client = make_cache()

    client.get.return_value = json.dumps(
        [
            {
                "rank": 1,
                "score": 0.90,
            }
        ]
    )

    result = cache.get_ranked_matches(
        42
    )

    assert result == [
        {
            "rank": 1,
            "score": 0.90,
        }
    ]


def test_cache_miss_returns_none():
    cache, client = make_cache()

    client.get.return_value = None

    assert (
        cache.get_ranked_matches(
            42
        )
        is None
    )


def test_invalidate_buyer():
    cache, client = make_cache()

    cache.invalidate_buyer(
        42
    )

    client.delete.assert_called_once_with(
        "matchbook:matching:"
        "v1:buyer:42:ranked"
    )