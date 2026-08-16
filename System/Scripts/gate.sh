#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"
VENV_DEFAULT="$(dirname "$ROOT")/.$(basename "$ROOT").aios-venv/bin/python"
PYTHON="${AIOS_PYTHON:-$VENV_DEFAULT}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi
cd "$ROOT"

"$PYTHON" System/Scripts/aios.py validate
"$PYTHON" System/Scripts/aios.py links
"$PYTHON" System/Scripts/aios.py dupes
"$PYTHON" System/Scripts/aios.py health
"$PYTHON" System/Tests/scripts/run_strict_tests.py \
  --start-directory System/Tests/scripts \
  --pattern 'test_*.py' \
  --allow-skip test_docgen.TestRoundTrip.test_case_alias_targets_are_refused_before_mutation
