#!/bin/sh
# Read-only entry point. No installation, restart or printer commands.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3 is required to run this read-only check.' >&2
    exit 2
fi
exec python3 -B "$script_dir/preflight.py" "$@"
