#!/bin/sh
# Applies any pending Alembic migrations before starting the real command
# (gunicorn in production, or Flask's dev server via docker-compose.override.yml).
# Without this, a deploy that ships new model/migration code against an
# unmigrated database fails at the first query touching the new column/table
# -- exactly the class of error this exists to prevent. Assumes a single app
# instance; running several replicas of this image against the same database
# at once would race on the migration, which this app's docker-compose
# doesn't do.
set -e
python -m alembic upgrade head
exec "$@"
