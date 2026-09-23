def test_document_task_is_registered_on_shared_celery_app():
    from app.core.celery_app import celery_app
    import app.verification.tasks  # noqa: F401

    assert "app.verification.tasks.process_document" in celery_app.tasks
    assert (
        celery_app.conf.task_routes["app.verification.tasks.process_document"]
        == {"queue": "verification"}
    )
