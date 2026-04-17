#!/bin/sh
set -e

echo "Starting Celery worker..."
celery -A config worker -l INFO