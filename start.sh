#!/usr/bin/env bash
set -e
flask --app app init-db
gunicorn --bind 0.0.0.0:${PORT:-3000} app:app
