from app.worker.arq_settings import WorkerSettings


def test_worker_settings_use_request_conscious_defaults() -> None:
    assert WorkerSettings.max_jobs == 1
    assert WorkerSettings.poll_delay >= 10
