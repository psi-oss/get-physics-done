#!/usr/bin/env bash
# Pre-commit hook script: prevent GPD/ files from entering the repo.
#
# GPD/ is intentionally NOT in .gitignore so that local GPD workflow
# commit commands (gpd commit) succeed.  This hook silently unstages
# any GPD/ paths before the commit is recorded, keeping the repo clean.

staged_gpd=$(git diff --cached --name-only -- 'GPD/*' 'GPD/**')

if [ -n "$staged_gpd" ]; then
    echo "$staged_gpd" | xargs git reset -q HEAD --

    if git diff --cached --quiet; then
        echo "pre-commit: all staged files were under GPD/ — nothing left to commit."
        exit 1
    fi

    echo "pre-commit: unstaged GPD/ files (repo-local only):"
    echo "$staged_gpd" | sed 's/^/  /'
fi
