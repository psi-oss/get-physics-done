#!/usr/bin/env bash
# Pre-commit hook script: prevent GPD/ files from entering the repo.
#
# GPD/ is intentionally NOT in .gitignore so that local GPD workflow
# commit commands (gpd commit) succeed.  This hook silently unstages
# any GPD/ paths before the commit is recorded, keeping the repo clean.

staged_gpd_paths=()
while IFS= read -r -d '' path; do
    staged_gpd_paths+=("$path")
done < <(git diff --cached --name-only -z -- 'GPD/*' 'GPD/**')

if [ "${#staged_gpd_paths[@]}" -gt 0 ]; then
    git reset -q HEAD -- "${staged_gpd_paths[@]}"

    if git diff --cached --quiet; then
        echo "pre-commit: all staged files were under GPD/ — nothing left to commit."
        exit 1
    fi

    echo "pre-commit: unstaged GPD/ files (repo-local only):"
    printf '  %s\n' "${staged_gpd_paths[@]}"
fi
