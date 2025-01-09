"""
Settings file for RQ Workers
"""

import os

import sentry_sdk
from sentry_sdk.integrations.rq import RqIntegration

from app.core.config import settings

# Init sentry
sentry_dsn = str(settings.SENTRY_DSN) if settings.SENTRY_DSN else None
if sentry_dsn:
    sentry_sdk.init(sentry_dsn, integrations=[RqIntegration()])

if not os.path.isdir(settings.MEDIA_ROOT):
    os.mkdir(settings.MEDIA_ROOT)

REDIS_URL = settings.REDIS_URL
QUEUES = [os.environ.get("QUEUE_NAME", "default")]
