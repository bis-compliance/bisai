#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
fi
exec python3 -m streamlit run app.py --server.address 127.0.0.1
