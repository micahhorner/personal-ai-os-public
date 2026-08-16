#!/usr/bin/env bash
# backup-clone.sh — copy this vault to an off-machine destination and record
# the evidence marker (SPEC-backup-onboarding; see System/Documentation/
# Backup and Recovery Options.md).
#
# Usage:  System/Scripts/backup-clone.sh /path/to/destination-folder
#         (typically a folder on an encrypted external drive)
#
# What it does:
#   1. Refuses obviously wrong destinations (inside the vault; a non-empty
#      folder that is not a previous clone of this vault).
#   2. Copies the whole vault — including .git history when present — with
#      rsync as an exact mirror: files deleted here are removed there too.
#      If rsync is unavailable the script refuses; an additive copy must never
#      be labeled a current, exact backup.
#   3. Only after the copy succeeds, writes `80 User/LAST-BACKUP.txt` — the
#      marker `aios health` reads to report your last recorded backup. The
#      marker is evidence of THIS run only; the script that made the copy is
#      the one thing entitled to write it. Copying by hand instead? Update
#      the marker yourself with the one-line command in the options doc.
#
# macOS / Linux. On Windows, use one of the other options in the menu
# (GitHub remote, cloud folder, whole-disk backup).
set -euo pipefail

VAULT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${1:?usage: backup-clone.sh /path/to/destination-folder}"

mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"

case "$DEST/" in
  "$VAULT"/*)
    rmdir "$DEST" 2>/dev/null || true   # undo the mkdir if we just created it
    echo "refusing: destination is inside the vault itself" >&2; exit 1 ;;
esac
if [ -n "$(ls -A "$DEST" 2>/dev/null)" ] && [ ! -f "$DEST/SYSTEM-MANIFEST.yaml" ]; then
  echo "refusing: destination is non-empty and not a previous clone of a vault" >&2
  echo "(point at an empty folder, or at the folder a previous run created)" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "refusing: rsync is required for an exact backup clone" >&2
  echo "no backup marker was written" >&2
  exit 1
fi
rsync -a --delete "$VAULT"/ "$DEST"/

MARKER_DIR="$VAULT/80 User"
mkdir -p "$MARKER_DIR"
{
  echo "last_backup: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "destination: $DEST"
  echo "method: backup-clone.sh"
} > "$MARKER_DIR/LAST-BACKUP.txt"
mkdir -p "$DEST/80 User"
cp "$MARKER_DIR/LAST-BACKUP.txt" "$DEST/80 User/LAST-BACKUP.txt"

echo "backup complete: $VAULT -> $DEST"
echo "marker written: 80 User/LAST-BACKUP.txt (aios health now reports this run)"
