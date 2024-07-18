"""
Settings file for RQ Workers
"""

import os

import sentry_sdk
from sentry_sdk.integrations.rq import RqIntegration

from app.core.config import settings

# Init sentry
if settings.SENTRY_DSN:
    sentry_sdk.init(settings.SENTRY_DSN, integrations=[RqIntegration()])

REDIS_URL = settings.REDIS_URL
QUEUES = [os.environ.get("QUEUE_NAME", "default")]
