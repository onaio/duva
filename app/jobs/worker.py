#!/usr/bin/env python
import os

import sentry_sdk
from app.settings import settings
from redis import Redis
from rq import Connection, Worker, Queue
from sentry_sdk.integrations.rq import RqIntegration

# Preload libraries

QUEUE_NAME = os.environ.get("QUEUE_NAME", "default")


redis_conn = Redis.from_url(settings.redis_url)

# Provide queue names to listen to as arguments to this script,
# similar to rq worker
with Connection():
    if settings.sentry_dsn:
        sentry_sdk.init(settings.sentry_dsn, integrations=[RqIntegration()])
    queue = Queue(QUEUE_NAME, connection=redis_conn)

    w = Worker(queue, connection=redis_conn)
    w.work()
