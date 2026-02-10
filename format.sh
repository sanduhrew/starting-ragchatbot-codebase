#!/bin/bash
set -e

echo "Formatting code with Black..."
(cd backend && uv run black .)

echo "Sorting imports with Ruff..."
(cd backend && uv run ruff check --select I --fix .)

echo "✓ Code formatted successfully"
