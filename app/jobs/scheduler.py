import os
from typing import Callable

from redis import Redis
from rq import Queue
from rq.job import Job
from rq_scheduler import Scheduler

QUEUE_NAME = os.environ.get("QUEUE_NAME", "default")
CRON_SCHEDULE = os.environ.get("CRON_SCHEDULE", "*/15 * * * *")
TASK_TIMEOUT = os.environ.get("TASK_TIMEOUT", "3600")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
REDIS_CONN = Redis.from_url(REDIS_URL, socket_timeout=30, socket_connect_timeout=30)
QUEUE = Queue(QUEUE_NAME, connection=REDIS_CONN)


class UniqueJobScheduler(Scheduler):
    """
    Custom Redis Queue scheduler that only allows unique cron jobs
    to be scheduled
    """

    def cron(
        self,
        cron_string,
        func,
        args=None,
        kwargs=None,
        repeat=None,
        queue_name=None,
        id=None,
        timeout=None,
        description=None,
        meta=None,
        use_local_timezone=False,
        depends_on=None,
    ):
        for job in self.get_jobs():
            if job.func == func and job.args == args:
                return job
        return super(UniqueJobScheduler, self).cron(
            cron_string,
            func,
            args=args,
            kwargs=kwargs,
            repeat=repeat,
            queue_name=queue_name,
            id=id,
            timeout=timeout,
            description=description,
            meta=meta,
            use_local_timezone=use_local_timezone,
            depends_on=depends_on,
        )


SCHEDULER = UniqueJobScheduler(queue=QUEUE, connection=REDIS_CONN)


def cancel_job(job_id, job_args: list = None, func_name: str = None):
    SCHEDULER.cancel(job_id)

    if job_args and func_name:
        for job in SCHEDULER.get_jobs():
            if job.func_name == func_name and job.args == job_args:
                SCHEDULER.cancel(job)

    print(f"Job {job_id} cancelled ....")


def clear_scheduler_queue():
    for job in SCHEDULER.get_jobs():
        cancel_job(job)


def schedule_cron_job(job_func: Callable, args_list) -> Job:
    job = SCHEDULER.cron(
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
    print(f"Job {job.id} scheduled ....")
    return job
