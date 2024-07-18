#!/usr/bin/env python
import os

import sentry_sdk
from redis import Redis
from rq import Connection, Queue, Worker
from sentry_sdk.integrations.rq import RqIntegration

from app.core.config import settings

# Preload libraries

QUEUE_NAME = os.environ.get("QUEUE_NAME", "default")


redis_conn = Redis.from_url(
    settings.REDIS_URL, socket_timeout=30, socket_connect_timeout=30
)

# Provide queue names to listen to as arguments to this script,
# similar to rq worker
with Connection():
    if settings.SENTRY_DSN:
        sentry_sdk.init(settings.sentry_dsn, integrations=[RqIntegration()])
    queue = Queue(QUEUE_NAME, connection=redis_conn)

    w = Worker(queue, connection=redis_conn)
    w.work()
