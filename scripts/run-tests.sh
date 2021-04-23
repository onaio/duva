#!/bin/bash

PYTHONPATH=. pytest --cov-config=.coveragerc --cov=app -s app/tests
