#!/bin/bash
set -e

echo "Running Ruff linter..."
(cd backend && uv run ruff check .)

echo "Checking Black formatting..."
(cd backend && uv run black --check --diff .)

echo "✓ All quality checks passed"
