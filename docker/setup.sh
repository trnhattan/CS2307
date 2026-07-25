#!/usr/bin/env sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

mkdir -p \
  "$SCRIPT_DIR/.mnt/postgresql/data" \
  "$SCRIPT_DIR/.mnt/cloudbeaver"

printf '%s\n' \
  "Docker mount directories are ready:" \
  "  $SCRIPT_DIR/.mnt/postgresql/data" \
  "  $SCRIPT_DIR/.mnt/cloudbeaver"
