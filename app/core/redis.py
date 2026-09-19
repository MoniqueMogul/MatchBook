import os

from dotenv import load_dotenv
from redis import Redis


load_dotenv()


REDIS_URL = os.getenv("MATCHBOOK_REDIS_URL")

if not REDIS_URL:
    raise RuntimeError(
        "MATCHBOOK_REDIS_URL environment variable is not configured."
    )


redis_client = Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)