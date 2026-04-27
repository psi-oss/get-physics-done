#!/usr/bin/env sh
# check-human-authors.sh — enforce human-only commit author attribution.
#
# Use as a commit-msg hook:
#   cp scripts/check-human-authors.sh .git/hooks/commit-msg
#   chmod +x .git/hooks/commit-msg
#
# Or run standalone against a range:
#   scripts/check-human-authors.sh --range origin/main..HEAD

set -e

RED='\033[0;31m'
NC='\033[0m'

NON_HUMAN_COAUTHOR_PATTERN='^[[:space:]]*co-authored-by:[[:space:]]*.*(Claude|Anthropic|OpenAI|GPT|C[o]dex|Gemini|Copilot|noreply@anthropic\.com|noreply@openai\.com|github-actions)'

# --- Mode 1: commit-msg hook (single file argument) ---
if [ -f "${1:-}" ]; then
    if grep -Eqi "$NON_HUMAN_COAUTHOR_PATTERN" "$1"; then
        echo "${RED}ERROR: non-human co-author detected in commit message.${NC}" >&2
        echo "" >&2
        echo "This project requires commit attribution to list human authors only." >&2
        echo "Remove the Co-Authored-By line and try again." >&2
        echo "" >&2
        grep -ni "Co-Authored-By" "$1" >&2
        exit 1
    fi
    exit 0
fi

# --- Mode 2: range check (--range <range>) ---
if [ "${1:-}" = "--range" ] && [ -n "${2:-}" ]; then
    range="$2"
    if ! git rev-list "$range" >/dev/null 2>&1; then
        echo "${RED}ERROR: invalid git range ${range}.${NC}" >&2
        exit 1
    fi

    offenders=$(git log "$range" --format="%H" | while read -r hash; do
        subject=$(git log -1 --format="%s" "$hash")
        body=$(git log -1 --format="%B" "$hash")
        if printf '%s\n' "$body" | grep -Eqi "$NON_HUMAN_COAUTHOR_PATTERN"; then
            echo "  $hash $subject"
        fi
    done)
    if [ -n "$offenders" ]; then
        echo "${RED}ERROR: non-human co-author lines found in commit range ${range}:${NC}" >&2
        echo "$offenders" >&2
        exit 1
    fi
    echo "Human author attribution check passed for $range."
    exit 0
fi

echo "Usage:" >&2
echo "  As commit-msg hook: $0 <commit-msg-file>" >&2
echo "  As range checker:   $0 --range <git-range>" >&2
exit 1
