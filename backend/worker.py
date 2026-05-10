from celery import Celery

celery_app = Celery('club50', broker='redis://localhost:6379/0')

@celery_app.task
def run_hidden_tests(submission_id):
    # TODO: Run hidden tests in Docker
    return {"status": "done"}
