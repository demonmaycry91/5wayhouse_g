#!/bin/sh
set -e

echo "[Boot Sequence] Applying database schemas / migrations..."
flask db upgrade

echo "[Boot Sequence] Synchronizing internal permissions tree to DB records..."
flask auth init-roles

echo "[Boot Sequence] Seeding generic module accounts..."
flask auth seed-users || echo "Accounts already seeded."

echo "[Boot Sequence] Engaging Gunicorn multithreaded server block..."
exec gunicorn --bind 0.0.0.0:5000 -w 4 run:app
