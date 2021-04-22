"""
Settings file for RQ Workers
"""
import os
import sentry_sdk
from sentry_sdk.integrations.rq import RqIntegration

from app.settings import settings

# Init sentry
if settings.sentry_dsn:
    sentry_sdk.init(settings.sentry_dsn, integrations=[RqIntegration()])

REDIS_URL = settings.redis_url
QUEUES = [os.environ.get("QUEUE_NAME", "default")]
