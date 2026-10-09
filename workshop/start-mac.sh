#!/bin/sh
# Run from any directory. Explicit fixture mode overrides inherited VAST settings.
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
.venv/bin/python -m pip install -r requirements.txt
export WITNESS_WORKSHOP_MODE=fixture
export HOST=127.0.0.1
exec .venv/bin/python main.py
