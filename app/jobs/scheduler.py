import os

from redis import Redis
from rq import Queue
from rq_scheduler import Scheduler

from app.models import HyperFile
from app.database import SessionLocal
from app.jobs.jobs import csv_import_job

QUEUE_NAME = os.environ.get("QUEUE_NAME", "default")
CRON_SCHEDULE = os.environ.get("CRON_SCHEDULE", "*/15 * * * *")
TASK_TIMEOUT = os.environ.get("TASK_TIMEOUT", "3600")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/1")


def schedule_form(file_id):
    schedule_jobs(csv_import_job, [file_id])


def schedule_all_forms():
    db = SessionLocal()
    for file_obj in HyperFile.get_all(db):
        schedule_form(file_obj.id)


def schedule_jobs(job_func, args_list):

    redis_conn = Redis.from_url(REDIS_URL)
    queue = Queue(QUEUE_NAME, connection=redis_conn)

    scheduler = Scheduler(queue=queue, connection=redis_conn)

    scheduler.cron(
        CRON_SCHEDULE,  # A cron string (e.g. "0 0 * * 0")
        func=job_func,  # Function to be queued
        args=args_list,  # Arguments passed into function when executed
        kwargs={},  # Keyword arguments passed into function when executed
        repeat=None,  # Repeat this number of times (None means repeat forever)
        queue_name=QUEUE_NAME,  # In which queue the job should be put in
        meta={},  # Arbitrary pickleable data on the job itself
        use_local_timezone=False,  # Interpret hours in the local timezone
        timeout=int(TASK_TIMEOUT),  # How long jobs can run for
    )

    print("Jobs scheduled ....")

    return scheduler


if __name__ == "__main__":
    if os.environ.get("SCHEDULE_ALL", False):
        schedule_all_forms()
