#!/usr/bin/env bash

python3 app/jobs/scheduler.py && rqscheduler --host cache --port 6379 --db 1