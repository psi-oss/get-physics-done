from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

DEFAULT_TEST_GIT_USER_NAME = "Human Author"
DEFAULT_TEST_GIT_USER_EMAIL = "human@example.com"


def run_git(
    repo_root: Path,
    *args: str,
    check: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        env=dict(env) if env is not None else None,
        check=check,
        capture_output=True,
        text=True,
    )


def init_test_git_repo(
    repo_root: Path,
    *,
    user_name: str = DEFAULT_TEST_GIT_USER_NAME,
    user_email: str = DEFAULT_TEST_GIT_USER_EMAIL,
) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    run_git(repo_root, "init")
    run_git(repo_root, "config", "user.email", user_email)
    run_git(repo_root, "config", "user.name", user_name)


def git_identity_env(
    *,
    author_name: str,
    author_email: str,
    committer_name: str | None = None,
    committer_email: str | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": committer_name or author_name,
            "GIT_COMMITTER_EMAIL": committer_email or author_email,
        }
    )
    return env


def git_add(repo_root: Path, *paths: str) -> None:
    run_git(repo_root, "add", *paths)


def git_commit(
    repo_root: Path,
    message: str,
    *,
    env: Mapping[str, str] | None = None,
    extra_message: str | None = None,
) -> None:
    args = ["commit", "-m", message]
    if extra_message is not None:
        args.extend(["-m", extra_message])
    run_git(repo_root, *args, env=env)


def seed_test_git_repo(
    repo_root: Path,
    *,
    relpath: str = "README.md",
    content: str = "seed\n",
    message: str = "seed",
) -> None:
    (repo_root / relpath).write_text(content, encoding="utf-8")
    git_add(repo_root, relpath)
    git_commit(repo_root, message)
