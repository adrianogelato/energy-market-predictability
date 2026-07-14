#!/usr/bin/env bash
# One-time setup: create the dedicated virtual environment and install deps.
# Run once from the project folder:  bash setup.sh
set -e

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Done. Environment ready in .venv/"
echo "Next:  source .venv/bin/activate && python fetch_prices.py"
