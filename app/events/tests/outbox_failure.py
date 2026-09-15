from app.events.failure import OutboxFailure


def test_outbox_failure_does_not_store_exception_message():
    secret = "FAKE_BANK_ACCOUNT_12345"
    failure = OutboxFailure.from_exception(
        TimeoutError(secret)
    )

    assert failure.to_storage_value() == "TIMEOUT:TimeoutError"
    assert secret not in failure.to_storage_value()