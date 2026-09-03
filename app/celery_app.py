import os

from celery import Celery


BROKER_URL = os.getenv(
    "MATCHBOOK_CELERY_BROKER_URL",
    "amqp://guest:guest@localhost:5672//",
)

RESULT_BACKEND = os.getenv(
    "MATCHBOOK_CELERY_RESULT_BACKEND",
    "redis://localhost:6379/1",
)


celery_app = Celery(
    "matchbook",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        "app.matching.tasks",
    ],
)


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    timezone="UTC",
    enable_utc=True,

    task_track_started=True,

    # Acknowledge a job after execution rather than immediately.
    task_acks_late=True,

    # If a worker crashes during a job, allow the job to be
    # returned to the queue.
    task_reject_on_worker_lost=True,

    # Prevent a worker from reserving too many expensive jobs
    # at once.
    worker_prefetch_multiplier=1,

    # Retry broker connection when workers start.
    broker_connection_retry_on_startup=True,

    task_routes={
        "app.matching.tasks.rank_matches_task": {
            "queue": "matching"
        },
    },
)