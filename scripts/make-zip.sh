#!/usr/bin/env bash
# Create the source-code zip for Moodle (excludes .venv, __pycache__, .git, report screenshots).
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="$(basename "$PWD")"
OUT="../${NAME}.zip"
rm -f "$OUT"
cd ..
zip -r "${NAME}.zip" "$NAME" \
  -x "*/.venv/*" "*/venv/*" "*/__pycache__/*" "*.pyc" "*/.git/*" "*/.DS_Store" "*/.env" \
     "*/report/Report.pdf" "*/report/report.html" \
     "*/report/screenshots/*.png" "*/report/screenshots/*.jpg" "*/report/screenshots/*.jpeg"
echo "Created: $(cd "$(dirname "$OUT")" && pwd)/${NAME}.zip"
