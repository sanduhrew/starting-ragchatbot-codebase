#!/bin/bash
set -e

echo "Auto-fixing with Ruff..."
(cd backend && uv run ruff check --fix .)

echo "Formatting with Black..."
(cd backend && uv run black .)

echo "✓ Auto-fixes applied"
