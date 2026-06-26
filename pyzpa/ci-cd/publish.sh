#!/usr/bin/env bash
# Publish the already-built distribution in ./dist to PyPI or TestPyPI.
#
# Usage:
#   ci-cd/publish.sh [pypi|testpypi]      # default: pypi
#
# Authentication (token-based) is taken from the environment:
#   TWINE_USERNAME   (defaults to "__token__")
#   TWINE_PASSWORD   the API token, e.g. "pypi-AgEI..." (REQUIRED)
#
# Notes:
#   * Run ci-cd/build.sh first so ./dist contains the artifacts.
#   * --skip-existing makes the upload idempotent: re-running with an already
#     published version is a no-op instead of an error (important for the
#     periodic pipeline).
set -euo pipefail

PYTHON="${PYTHON:-python}"
REPO="${1:-pypi}"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

case "$REPO" in
    pypi|testpypi) ;;
    *) echo "error: repository must be 'pypi' or 'testpypi' (got '$REPO')" >&2; exit 2 ;;
esac

if [[ -z "${TWINE_PASSWORD:-}" ]]; then
    echo "error: TWINE_PASSWORD is not set (provide a PyPI API token)" >&2
    exit 2
fi
export TWINE_USERNAME="${TWINE_USERNAME:-__token__}"

if [[ -z "$(ls -A dist 2>/dev/null || true)" ]]; then
    echo "error: ./dist is empty — run ci-cd/build.sh first" >&2
    exit 1
fi

echo "==> Validating distribution metadata"
"$PYTHON" -m twine check dist/*

echo "==> Uploading to '$REPO'"
"$PYTHON" -m twine upload --non-interactive --skip-existing \
    --repository "$REPO" dist/*

echo "==> Publish to '$REPO' complete"
