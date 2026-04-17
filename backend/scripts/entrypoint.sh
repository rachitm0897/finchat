#!/bin/sh
set -e

echo "Starting finchat container..."

if [ "${DB_ENGINE}" = "postgres" ]; then
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
  while ! nc -z "${POSTGRES_HOST}" "${POSTGRES_PORT}"; do
    sleep 1
  done
  echo "PostgreSQL is available."
fi

exec "$@"