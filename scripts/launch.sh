#!/bin/sh
# Prepare the local environment and open Quota Orb.
set -eu
cd "$(dirname "$0")/.."
python_command=${PYTHON:-python3}
if [ ! -x .venv/bin/python ]; then
    "$python_command" -c 'import sys, tkinter; assert sys.version_info >= (3, 10)' || {
        echo 'Python 3.10+ with Tcl/Tk is required.' >&2
        exit 1
    }
    "$python_command" -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-bridge.txt
exec .venv/bin/python -m bridge.launch
