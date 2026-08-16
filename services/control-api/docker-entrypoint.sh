#!/bin/sh
# Applies database migrations when RUN_MIGRATIONS_ON_START=true, then execs the
# container command. `alembic upgrade head` is idempotent (a no-op at head), so
# it is safe to run on every start of a single-instance deployment.
set -e
if [ "${RUN_MIGRATIONS_ON_START:-false}" = "true" ]; then
  echo "conductor: applying database migrations (alembic upgrade head)"
  alembic upgrade head
fi
exec "$@"
