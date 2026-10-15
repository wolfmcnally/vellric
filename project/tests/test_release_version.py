from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

PACKAGING = Path(__file__).resolve().parent.parent / "packaging"


@pytest.fixture(autouse=True)
def own_repositories(monkeypatch):
    # A hook that runs these tests passes its own repository's location; the synthetic
    # repositories here must never be confused with it.
    for name in list(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)


def load(name: str, monkeypatch):
    # The folder is not a package, and its name would collide with the `packaging` library.
    monkeypatch.syspath_prepend(str(PACKAGING))
    spec = importlib.util.spec_from_file_location(name, PACKAGING / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root: Path, *arguments: str) -> None:
    quiet = ["-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]
    identity = ["-c", "user.name=Release Check", "-c", "user.email=release@example.invalid"]
    subprocess.run(["git", "-C", str(root), *quiet, *identity, *arguments], check=True)


def version(project: Path, number: str) -> None:
    (project / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{number}"\n')


def checkout(root: Path, number: str) -> Path:
    """A repository whose first commit is already released as v0.9.0."""
    project = root / "project"
    project.mkdir(parents=True)
    version(project, number)
    (project / "code.py").write_text("ANSWER = 1\n")
    (project / ".gitignore").write_text("*.log\n")
    (root / "outside.md").write_text("Not part of the project.\n")
    git(root, "init", "--quiet")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "start")
    git(root, "tag", "v0.9.0")
    return project


def refusal(release_version, project: Path, **options) -> str:
    return str(release_version.problem(project, **options))


def test_a_tagged_version_is_bound_to_its_project_tree(tmp_path, monkeypatch):
    release_version = load("release_version", monkeypatch)
    project = checkout(tmp_path, "1.0.0")
    assert release_version.problem(project) is None  # 1.0.0 is not tagged yet.
    git(tmp_path, "tag", "v1.0.0")
    assert release_version.problem(project) is None  # The tree is the tagged one.
    (tmp_path / "outside.md").write_text("Changed outside the project.\n")
    (tmp_path / "scratch.txt").write_text("Untracked outside the project.\n")
    (project / "build.log").write_text("Ignored inside the project.\n")
    assert release_version.problem(project) is None
    (project / "code.py").write_text("ANSWER = 2\n")
    assert "v1.0.0 is already tagged" in refusal(release_version, project)
    git(tmp_path, "commit", "--quiet", "-am", "change")
    assert "v1.0.0 is already tagged" in refusal(release_version, project)
    git(tmp_path, "checkout", "--quiet", "v1.0.0", "--", "project/code.py")
    git(tmp_path, "commit", "--quiet", "-am", "undo")
    (project / "new.py").write_text("")
    assert "first project/new.py" in refusal(release_version, project)
    version(project, "1.0.1")
    assert release_version.problem(project) is None  # A new version for the new content.


def test_the_staged_tree_is_checked_at_commit_time(tmp_path, monkeypatch):
    release_version = load("release_version", monkeypatch)
    project = checkout(tmp_path, "1.0.0")
    git(tmp_path, "tag", "v1.0.0")
    (project / "code.py").write_text("ANSWER = 2\n")
    assert release_version.problem(project, staged=True) is None  # Nothing staged yet.
    git(tmp_path, "add", "project/code.py")
    version(project, "1.0.1")  # Changed on disk, but not in what would be committed.
    assert "v1.0.0 is already tagged" in refusal(release_version, project, staged=True)
    git(tmp_path, "add", "project/pyproject.toml")
    assert release_version.problem(project, staged=True) is None


def test_a_hooks_repository_location_is_honoured(tmp_path, monkeypatch):
    release_version = load("release_version", monkeypatch)
    project = checkout(tmp_path, "1.0.0")
    git(tmp_path, "tag", "v1.0.0")
    # What a hook may see: the location relative to the top of the work tree, and no work tree.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_DIR", ".git")
    monkeypatch.setenv("GIT_INDEX_FILE", ".git/index")
    assert release_version.problem(project) is None
    assert release_version.problem(project, staged=True) is None
    (project / "code.py").write_text("ANSWER = 2\n")
    git(tmp_path, "add", "project/code.py")
    assert "first project/code.py" in refusal(release_version, project, staged=True)


def test_an_unknowable_tag_state_refuses(tmp_path, monkeypatch):
    release_version = load("release_version", monkeypatch)
    loose = tmp_path / "loose"
    loose.mkdir()
    version(loose, "1.0.0")
    assert "not a git repository" in refusal(release_version, loose).lower()
    origin = tmp_path / "origin"
    checkout(origin, "1.0.0")
    git(origin, "tag", "v1.0.0")
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "--quiet", "--depth", "1", origin.as_uri(), str(shallow))
    assert "shallow clone" in refusal(release_version, shallow / "project")
    untagged = tmp_path / "untagged"
    git(tmp_path, "clone", "--quiet", "--no-tags", origin.as_uri(), str(untagged))
    assert "no release tags" in refusal(release_version, untagged / "project")


def test_the_bundle_builder_refuses_before_building(tmp_path, monkeypatch):
    windows_bundle = load("windows_bundle", monkeypatch)
    built = []

    def run(*command, **kwargs):
        built.append(command)
        raise SystemExit("Injected: the build started")

    monkeypatch.setattr(windows_bundle, "run", run)
    monkeypatch.setattr(
        windows_bundle.release_version, "problem", lambda project: "v9.9.9 is already tagged"
    )
    monkeypatch.setattr("sys.argv", ["windows_bundle.py", "--out", str(tmp_path / "dist")])
    with pytest.raises(SystemExit, match="v9.9.9 is already tagged"):
        windows_bundle.main()
    assert built == [] and not (tmp_path / "dist").exists()


def test_the_bundle_carries_only_tracked_guides(tmp_path, monkeypatch):
    windows_bundle = load("windows_bundle", monkeypatch)
    project = checkout(tmp_path, "1.0.0")
    (project / "docs").mkdir()
    (project / "docs" / "GUIDE.md").write_text("Tracked.\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "guide")
    (project / "docs" / "notes.log").write_text("Ignored.\n")
    (project / "docs" / "DRAFT.md").write_text("Untracked.\n")
    monkeypatch.setattr(windows_bundle, "PROJECT", project)
    assert windows_bundle.tracked("docs") == ["docs/GUIDE.md"]
