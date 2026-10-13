#!/usr/bin/env bash
# Download app updates without Git or a GitHub login.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -x .venv/Scripts/python.exe ]]; then
  .venv/Scripts/python.exe korail_update.py
elif [[ -x .venv/bin/python ]]; then
  .venv/bin/python korail_update.py
elif command -v python3 >/dev/null; then
  python3 korail_update.py
elif command -v python >/dev/null; then
  python korail_update.py
else
  printf 'Run 1_설치.bat first to install Python.\n' >&2
  exit 1
fi
