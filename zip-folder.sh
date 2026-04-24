#!/usr/bin/env sh
set -eu

OUTPUT="${1:-drone0-03.zip}"
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

cd "$ROOT_DIR"

zip -r "$OUTPUT" . \
  -x ".git/*" \
  -x ".vscode/*" \
  -x "$OUTPUT"

printf 'Created %s\n' "$OUTPUT"
