#!/bin/bash

PYTHONPATH=. alembic revision --autogenerate -m "$@"
