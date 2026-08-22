#!/bin/sh
set -eu

python scripts/migrate_database.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
