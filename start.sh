#!/usr/bin/env bash
# Start the poster bot. Loads a .env file if present.
set -e
cd "$(dirname "$0")"

if [ -f .env ]; then
  echo "Loading .env file..."
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

exec python bot.py
