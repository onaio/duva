from fastapi_cache import caches
from fastapi_cache.backends.redis import CACHE_KEY, RedisCacheBackend
from tableauhyperapi import HyperProcess, Telemetry

from app.common_tags import HYPER_PROCESS_CACHE_KEY
from app.core.config import settings
from app.utils.onadata_utils import start_csv_import_to_hyper


def csv_import_job(instance_id):
    # Connect to redis cache
    rc = RedisCacheBackend(settings.REDIS_URL)
    caches.set(CACHE_KEY, rc)

    # Check if Hyper Process has started
    # Note: Doing this in order to ensure only one
    # Hyper process is started.
    if not caches.get(HYPER_PROCESS_CACHE_KEY):
        caches.set(
            HYPER_PROCESS_CACHE_KEY,
            HyperProcess(telemetry=Telemetry.SEND_USAGE_DATA_TO_TABLEAU),
        )
    process: HyperProcess = caches.get(HYPER_PROCESS_CACHE_KEY)

    start_csv_import_to_hyper(instance_id, process)
