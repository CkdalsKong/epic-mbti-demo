#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping EPIC runtime server on port 8765 if it is running..."
epic_pids="$(lsof -ti tcp:8765 || true)"
if [[ -n "$epic_pids" ]]; then
    echo "$epic_pids" | xargs kill
fi

echo "Done."
