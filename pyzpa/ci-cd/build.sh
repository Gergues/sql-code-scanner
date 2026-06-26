#!/usr/bin/env bash
# Build clean sdist + wheel for the pyzpa package and validate metadata.
#
# Usage:
#   ci-cd/build.sh            # build and run `twine check`
#
# Honors PYTHON (defaults to `python`) so CI can pin an interpreter.
set -euo pipefail

PYTHON="${PYTHON:-python}"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

echo "==> Cleaning previous build artifacts"
rm -rf dist build ./*.egg-info

echo "==> Ensuring build tooling is present"
"$PYTHON" -m pip install --quiet --upgrade build twine

echo "==> Building sdist and wheel"
"$PYTHON" -m build

echo "==> Validating distribution metadata"
"$PYTHON" -m twine check dist/*

echo "==> Build complete:"
ls -1 dist
