#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${1:?Use pace or bp}"
CHECKPOINT="${2:-extracted-course-package}"
case "$PROFILE" in pace|bp) ;; *) echo 'Unknown frozen runtime' >&2; exit 2;; esac
READY="/tmp/lab1-final-ready-${PROFILE}.json"
python3 -B "$HERE/build.py" --profile "$PROFILE" --out "$READY"
python3 -B "$HERE/run.py" --profile "$PROFILE" --ready "$READY" --checkpoint "$CHECKPOINT" --timeout 600
python3 -B "$HERE/analyze.py" --profile "$PROFILE" --out "/work/output/lab1-final-replay/${PROFILE}"
