#!/bin/bash
# next-id.sh — Generate next sequential feature or story ID
#
# Usage:
#   next-id.sh feature                → F05 (next available feature number)
#   next-id.sh story F01              → F01-S05 (next story in feature F01)
#
# Scans tasks/ and tasks/completed/ for existing IDs.
# Zero-padded two digits (F01-F99, S01-S99).
#
# Path resolution: walks up from the script's location to find
# the atlas project root, then scans tasks/ (including completed/).

set -euo pipefail

# Resolve the script's own directory, then walk up to atlas root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# scripts/ → prd-creator/ → skills/ → .claude/ → atlas/
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
TASKS_DIR="${ATLAS_TASKS_PATH:-$PROJECT_ROOT/tasks}"

if [[ ! -d "$TASKS_DIR" ]]; then
    echo "Error: Tasks directory not found at $TASKS_DIR"
    echo "Set ATLAS_TASKS_PATH to override."
    exit 1
fi

usage() {
    echo "Usage: next-id.sh feature | story <feature-id>"
    echo ""
    echo "Examples:"
    echo "  next-id.sh feature        → F05"
    echo "  next-id.sh story F01      → F01-S03"
    echo ""
    echo "Tasks dir: $TASKS_DIR"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

TYPE="$1"

case "$TYPE" in
    feature)
        # Find highest F## number in tasks/ and tasks/completed/ (recursive)
        MAX=0
        while IFS= read -r file; do
            fname=$(basename "$file")
            if [[ "$fname" =~ ^F([0-9]+)- ]]; then
                num=$((10#${BASH_REMATCH[1]}))
                if (( num > MAX )); then
                    MAX=$num
                fi
            fi
        done < <(find "$TASKS_DIR" -name 'F[0-9]*' -type f 2>/dev/null)

        NEXT=$((MAX + 1))
        printf "F%02d\n" "$NEXT"
        ;;

    story)
        if [[ $# -lt 2 ]]; then
            echo "Error: story requires a feature ID (e.g., F01)"
            usage
        fi

        FEATURE_ID="$2"

        if [[ ! "$FEATURE_ID" =~ ^F[0-9]+$ ]]; then
            echo "Error: Invalid feature ID format. Expected F## (e.g., F01, F12)"
            exit 1
        fi

        # Find highest S## number for this feature in tasks/ and tasks/completed/ (recursive)
        MAX=0
        while IFS= read -r file; do
            fname=$(basename "$file")
            if [[ "$fname" =~ ^${FEATURE_ID}-S([0-9]+)- ]]; then
                num=$((10#${BASH_REMATCH[1]}))
                if (( num > MAX )); then
                    MAX=$num
                fi
            fi
        done < <(find "$TASKS_DIR" -name "${FEATURE_ID}-S[0-9]*" -type f 2>/dev/null)

        NEXT=$((MAX + 1))
        printf "%s-S%02d\n" "$FEATURE_ID" "$NEXT"
        ;;

    *)
        echo "Error: Unknown type '$TYPE'"
        usage
        ;;
esac
