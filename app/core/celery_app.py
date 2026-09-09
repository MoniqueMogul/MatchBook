import os

from celery import Celery
from kombu import Queue
from dotenv import load_dotenv


load_dotenv()


CELERY_BROKER_URL = os.getenv(
    "MATCHBOOK_CELERY_BROKER_URL",
    "amqp://guest:guest@localhost:5672//",
)

CELERY_RESULT_BACKEND = os.getenv(
    "MATCHBOOK_CELERY_RESULT_BACKEND",
    "redis://localhost:6379/1",
)


celery_app = Celery(
    "matchbook",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    timezone="UTC",
    enable_utc=True,

    task_acks_late=True,
    task_reject_on_worker_lost=True,

    worker_prefetch_multiplier=1,

    task_queues=(
        Queue("outbox"),
        Queue("notifications"),
        Queue("matching"),
    ),

    task_routes={
        "app.events.tasks.send_outbox_event": {
            "queue": "outbox",
        },

        "app.notifications.tasks.process_notification_event": {
            "queue": "notifications",
        },

        "app.matching.tasks.process_matching_event": {
            "queue": "matching",
        },
    },
)