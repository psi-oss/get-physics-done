#!/usr/bin/env sh
# check-human-authors.sh - enforce human commit attribution, with explicit
# repository automation exceptions.
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

COAUTHOR_TRAILER_PATTERN='^[[:space:]]*co-authored-by:[[:space:]]*'
NON_HUMAN_IDENTITY_PATTERN='(Claude|Anthropic|OpenAI|GPT|C[o]dex|Gemini|Copilot|AI Runtime|\[bot\]|bot@|dependabot|github-actions|noreply@anthropic\.com|noreply@openai\.com)'

is_allowed_automation_identity() {
    case "$1" in
        "GitHub <noreply@github.com>" | "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>")
            return 0
            ;;
    esac
    return 1
}

is_non_human_identity() {
    identity="$1"
    if is_allowed_automation_identity "$identity"; then
        return 1
    fi
    printf '%s\n' "$identity" | grep -Eiq "$NON_HUMAN_IDENTITY_PATTERN"
}

identity_from_git_var() {
    git var "$1" 2>/dev/null | sed -E 's/[[:space:]][0-9]+[[:space:]][+-][0-9]{4}$//' || true
}

identity_offender_line() {
    role="$1"
    identity="$2"
    if [ -n "$identity" ] && is_non_human_identity "$identity"; then
        printf '%s: %s\n' "$role" "$identity"
    fi
}

coauthor_offenders_from_text() {
    printf '%s\n' "$1" | while IFS= read -r line; do
        if printf '%s\n' "$line" | grep -Eiq "$COAUTHOR_TRAILER_PATTERN"; then
            identity=$(printf '%s\n' "$line" | sed -E 's/^[[:space:]]*[Cc][Oo]-[Aa][Uu][Tt][Hh][Oo][Rr][Ee][Dd]-[Bb][Yy]:[[:space:]]*//')
            if is_non_human_identity "$identity"; then
                printf '%s\n' "$line"
            fi
        fi
    done
}

print_offender_details() {
    identity_offenders="$1"
    coauthor_offenders="$2"
    if [ -n "$identity_offenders" ]; then
        printf '%s\n' "$identity_offenders" | sed 's/^/    /' >&2
    fi
    if [ -n "$coauthor_offenders" ]; then
        printf '%s\n' "$coauthor_offenders" | sed 's/^/    co-author trailer: /' >&2
    fi
}

# --- Mode 1: commit-msg hook (single file argument) ---
if [ -f "${1:-}" ]; then
    message=$(cat "$1")
    author=$(identity_from_git_var GIT_AUTHOR_IDENT)
    committer=$(identity_from_git_var GIT_COMMITTER_IDENT)
    identity_offenders=$(
        identity_offender_line "author" "$author"
        identity_offender_line "committer" "$committer"
    )
    coauthor_offenders=$(coauthor_offenders_from_text "$message")

    if [ -n "$identity_offenders" ] || [ -n "$coauthor_offenders" ]; then
        echo "${RED}ERROR: non-human commit attribution detected.${NC}" >&2
        echo "" >&2
        echo "This project requires commit attribution to list human authors only." >&2
        echo "Use a human author/committer identity and remove non-human Co-Authored-By lines." >&2
        echo "" >&2
        print_offender_details "$identity_offenders" "$coauthor_offenders"
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
        author=$(git log -1 --format="%an <%ae>" "$hash")
        committer=$(git log -1 --format="%cn <%ce>" "$hash")
        body=$(git log -1 --format="%B" "$hash")
        identity_offenders=$(
            identity_offender_line "author" "$author"
            identity_offender_line "committer" "$committer"
        )
        coauthor_offenders=$(coauthor_offenders_from_text "$body")
        if [ -n "$identity_offenders" ] || [ -n "$coauthor_offenders" ]; then
            echo "  $hash $subject"
            if [ -n "$identity_offenders" ]; then
                printf '%s\n' "$identity_offenders" | sed 's/^/    /'
            fi
            if [ -n "$coauthor_offenders" ]; then
                printf '%s\n' "$coauthor_offenders" | sed 's/^/    co-author trailer: /'
            fi
        fi
    done)
    if [ -n "$offenders" ]; then
        echo "${RED}ERROR: non-human commit attribution found in commit range ${range}:${NC}" >&2
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
