#!/usr/bin/env sh
# check-no-ai-coauthors.sh — reject commits containing AI co-author lines.
#
# Use as a commit-msg hook:
#   cp scripts/check-no-ai-coauthors.sh .git/hooks/commit-msg
#   chmod +x .git/hooks/commit-msg
#
# Or run standalone against a range:
#   scripts/check-no-ai-coauthors.sh --range origin/main..HEAD

set -e

RED='\033[0;31m'
NC='\033[0m'

AI_PATTERN='Co-Authored-By:.*\(Claude\|Anthropic\|OpenAI\|GPT\|Gemini\|Copilot\|noreply@anthropic\.com\|noreply@openai\.com\|github-actions\)'

# --- Mode 1: commit-msg hook (single file argument) ---
if [ -f "${1:-}" ]; then
    if grep -qi "$AI_PATTERN" "$1"; then
        echo "${RED}ERROR: AI co-author detected in commit message.${NC}" >&2
        echo "" >&2
        echo "This project does not allow AI co-author attribution in commits." >&2
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
    offenders=$(git log "$range" --format="%H %s" --grep="Co-Authored-By" 2>/dev/null | while read hash msg; do
        body=$(git log -1 --format="%b" "$hash")
        if echo "$body" | grep -qi "$AI_PATTERN"; then
            echo "  $hash $msg"
        fi
    done)
    if [ -n "$offenders" ]; then
        echo "${RED}ERROR: AI co-author lines found in commit range ${range}:${NC}" >&2
        echo "$offenders" >&2
        exit 1
    fi
    echo "No AI co-authors found in $range."
    exit 0
fi

echo "Usage:" >&2
echo "  As commit-msg hook: $0 <commit-msg-file>" >&2
echo "  As range checker:   $0 --range <git-range>" >&2
exit 1
