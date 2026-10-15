"""Refuse a project tree whose version is already tagged on different content.

A version names one commit: the tag ``v<version>``. Once that tag exists, any change under the
project folder needs a new version before it is committed, qualified or built. The pre-commit
hook checks the staged tree; the repository gate and the Windows bundle builder check the
working tree:

    python packaging/release_version.py [--staged]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def _git(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    # A hook exports the repository's location, possibly relative to the folder it runs in, and
    # without a work tree; under ``-C`` git would take the project folder as the whole tree. Git
    # finds the same repository from the project folder, so those variables are dropped. The
    # index a commit is about to record is kept, made absolute.
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
    }
    if environment.get("GIT_INDEX_FILE"):
        environment["GIT_INDEX_FILE"] = os.path.abspath(environment["GIT_INDEX_FILE"])
    return subprocess.run(
        ["git", "-C", str(project), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )


def problem(project: Path = PROJECT, *, staged: bool = False) -> str | None:
    """Why this tree may not carry its version, or None when it may."""
    try:
        shallow = _git(project, "rev-parse", "--is-shallow-repository")
    except FileNotFoundError:
        return "cannot tell whether the version is tagged: git is not installed"
    if shallow.returncode:
        return f"cannot tell whether the version is tagged: {shallow.stderr.strip()}"
    if shallow.stdout.strip() != "false":
        return "cannot tell whether the version is tagged: a shallow clone may lack its tags"
    if staged:
        recorded = _git(project, "show", ":./pyproject.toml")
        if recorded.returncode:
            return f"cannot read the staged version: {recorded.stderr.strip()}"
        pyproject = recorded.stdout
    else:
        pyproject = (project / "pyproject.toml").read_text(encoding="utf-8")
    tag = "v" + tomllib.loads(pyproject)["project"]["version"]
    listed = _git(project, "tag", "--list")
    if listed.returncode:
        return f"cannot list tags: {listed.stderr.strip()}"
    tags = listed.stdout.splitlines()
    if not any(name.startswith("v") for name in tags):
        # Released versions are tagged, so an empty list means the tags were not fetched.
        return f"cannot tell whether {tag} is tagged: this clone has no release tags"
    if tag not in tags:
        return None
    ref = f"refs/tags/{tag}"
    if staged:
        results = [_git(project, "diff", "--cached", "--name-only", ref, "--", ".")]
    else:
        # The tag's tree against the working tree, then files the tag never had.
        results = [
            _git(project, "diff", "--name-only", ref, "--", "."),
            _git(project, "ls-files", "--others", "--exclude-standard", "--full-name", "--", "."),
        ]
    paths = []
    for result in results:
        if result.returncode:
            return f"cannot compare with {tag}: {result.stderr.strip()}"
        paths += result.stdout.splitlines()
    if paths:
        return (
            f"{tag} is already tagged and {len(paths)} project path(s) differ from it, "
            f"first {paths[0]}; change the version first"
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staged", action="store_true", help="check the staged tree")
    reason = problem(staged=parser.parse_args().staged)
    if reason:
        print(f"RELEASE VERSION REFUSED: {reason}", file=sys.stderr)
        return 1
    print("RELEASE VERSION OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
