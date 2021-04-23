#! /usr/bin/env bash

# Run migrations
if [ "$RUN_MIGRATIONS" = "True" ]; then
    alembic upgrade head
fi
