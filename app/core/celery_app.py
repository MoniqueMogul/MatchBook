import os

from celery import Celery
from kombu import Queue
from dotenv import load_dotenv

import app.core.celery_observability  # Registers Celery signal handlers.
from app.core.observability import configure_logging


load_dotenv()
configure_logging()


CELERY_BROKER_URL = os.getenv(
    "MATCHBOOK_CELERY_BROKER_URL",
    "amqp://guest:guest@localhost:5672//",
)


celery_app = Celery(
    "matchbook",
    broker=CELERY_BROKER_URL,
    include=[
        "app.events.tasks",
        "app.events.monitoring",
        "app.notification.tasks",
        "app.chat.tasks",
        "app.matching.tasks",
    ],
)


# Periodic jobs run by Celery Beat.
celery_app.conf.beat_schedule = {
    "retry-pending-outbox-events": {
        "task": "app.events.tasks.retry_pending_outbox_events",
        "schedule": 60.0,
        "options": {"queue": "outbox"},
    },
    "check-outbox-backlog": {
        "task": "app.events.monitoring.check_outbox_backlog",
        "schedule": 60.0,
        "options": {"queue": "outbox"},
    },
}


celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Time
    timezone="UTC",
    enable_utc=True,

    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Queues
    task_queues=(
        Queue("outbox"),
        Queue("notifications"),
        Queue("chat"),
        Queue("matching"),
    ),

    # Task → queue routing
    task_routes={
        "app.events.tasks.send_outbox_event": {
            "queue": "outbox",
        },
        "app.events.tasks.retry_pending_outbox_events": {
            "queue": "outbox",
        },
        "app.events.monitoring.check_outbox_backlog": {
            "queue": "outbox",
        },
        "app.notification.tasks.process_notification_event": {
            "queue": "notifications",
        },
        "app.chat.tasks.process_chat_event": {
            "queue": "chat",
        },
        "app.matching.tasks.process_matching_event_task": {
            "queue": "matching",
        },
    },
)