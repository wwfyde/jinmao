#! /bin/sh

set -e

# Run migrations
#alembic upgrade head

# Create initial data in DB
#PYTHONPATH=$(pwd) python  app/init_data.py

exec "$@"
