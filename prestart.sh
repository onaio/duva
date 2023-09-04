#! /usr/bin/env bash

# Run migrations
alembic upgrade head

# Create initial data
python /app/app/initial_data.py 
