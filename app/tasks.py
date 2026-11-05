import os

from celery import Celery

from .services.submissions import run_grading

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("campusclaw", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(bind=True, max_retries=2, name="campusclaw.grade_submission")
def grade_submission_task(self, submission_id):
    from . import create_app

    app = create_app()
    with app.app_context():
        try:
            run_grading(submission_id)
        except Exception as exc:  # noqa: BLE001
            if self.request.retries < 2:
                countdown = 5 if self.request.retries == 0 else 20
                raise self.retry(exc=exc, countdown=countdown)
            from .extensions import db
            from .models import Submission

            submission = db.session.get(Submission, submission_id)
            if submission is not None and submission.status in {"pending", "grading"}:
                submission.status = "failed"
                submission.error_message = str(exc)[:500]
                db.session.commit()
            raise
