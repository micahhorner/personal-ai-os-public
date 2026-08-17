#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"
VENV_DEFAULT="$(dirname "$ROOT")/.$(basename "$ROOT").aios-venv/bin/python"
PYTHON="${AIOS_PYTHON:-$VENV_DEFAULT}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi
cd "$ROOT"

# A clean public distribution intentionally contains no private historical Git
# authority and no generated runtime state.  Public CI proves the distributed
# tree by activating its rebuildable indexes in the ephemeral checkout, while
# the separately pinned release-qualification gate proves every historical
# upgrade and recovery path.  The scopes are complementary and never conflated.
if [[ "${AIOS_PUBLIC_CI:-0}" == "1" ]]; then
  "$PYTHON" System/Scripts/aios.py generate
fi

"$PYTHON" System/Scripts/aios.py validate
"$PYTHON" System/Scripts/aios.py links
"$PYTHON" System/Scripts/aios.py dupes
"$PYTHON" System/Scripts/aios.py health
STRICT_ARGS=(
  --start-directory System/Tests/scripts
  --pattern 'test_*.py'
  --allow-skip test_docgen.TestRoundTrip.test_case_alias_targets_are_refused_before_mutation
)
if [[ "${AIOS_PUBLIC_CI:-0}" == "1" ]]; then
  STRICT_ARGS+=(
    --allow-skip-prefix test_historical_migrations.TestHistoricalMigrationEvidence
    --allow-skip-prefix test_release_fault_historical.TestHistoricalInterruptionAndRerun
    --allow-skip test_upgrade_launcher.TestHistoricalLauncherReview.test_official_143_163_164_reviews_are_read_only
  )
fi
"$PYTHON" System/Tests/scripts/run_strict_tests.py "${STRICT_ARGS[@]}"
