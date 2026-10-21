"""Build the self-contained Windows bundle: Vellric, its locked dependencies and install notes.

The bundle installs on 64-bit Windows without network resolution. Build it with Python 3.12+,
uv and Git. Registry wheels use published hashes; Conric is built from its exact locked commit.
Every local wheel's hash is recorded in the bundle:

    python packaging/windows_bundle.py --out dist

It refuses a version that is already tagged on different content (release_version.py).

It is a convenience for installing on one's own machines. Handing it to anyone else also hands
them third-party binaries, whose source and notice duties docs/LICENSING.md describes.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.parse
import zipfile
from pathlib import Path

import release_version

PROJECT = Path(__file__).resolve().parent.parent
EPOCH = 1609459200  # The build time the release procedure fixes, so equal inputs give equal bytes.
PIP_TOOL = "pip==26.2.2"

INSTALL = """\
Vellric {version} for Windows x64, Python {python}

Everything Vellric needs from Python is in the wheels folder; no package index is used.
In PowerShell, from the folder this file is in:

    python -m venv "{home}"
    & "{home}\\Scripts\\python.exe" -m pip install --no-index --require-hashes --no-deps -r requirements-wheels.txt
    & "{home}\\Scripts\\python.exe" -m pip check
    & "{home}\\Scripts\\vellric.exe" doctor

Then run it as:

    & "{home}\\Scripts\\vellric.exe" convert INPUT.pdf --out OUTPUT-FOLDER

Reading scanned pages without a vision model, and checking a model's transcription of them,
needs two programs that Python cannot install. They need an administrator:

    Tesseract {tesseract}     {tesseract_installer}
    Ghostscript {ghostscript}  {ghostscript_installer}

Run each installer in the ordinary way and keep its default folder under Program Files.
Until then, add --ocr never --vision-cross-check off to a convert that uses a vision model.

The bedrock, openai and command vision providers need nothing more. The anthropic provider
needs a package this bundle does not carry.

The guides are in the docs folder, starting with INSTALLATION.md and CLI.md. This bundle is
for installing on your own machines; LICENSING.md says what passing it to others involves.
"""

ENGINES = {
    "tesseract": "5.5.3",
    "tesseract_installer": "tesseract-ocr-w64-setup-5.5.3.20260724.exe",
    "ghostscript": "10.07.1",
    "ghostscript_installer": "gs10071w64.exe",
}


def run(*command: str, cwd: Path = PROJECT) -> str:
    environment = os.environ | {"SOURCE_DATE_EPOCH": str(EPOCH)}
    done = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"{' '.join(command[:3])} failed:\n{done.stdout}{done.stderr}")
    return done.stdout


def tracked(folder: str) -> list[str]:
    """Files Git tracks under a project folder, so nothing ignored rides into the bundle."""
    listed = subprocess.run(
        ["git", "-C", str(PROJECT), "ls-files", "-z", "--", folder], capture_output=True, check=True
    )
    return [name for name in listed.stdout.decode("utf-8").split("\0") if name]


def materialize_conric(selected: Path, wheels: Path) -> str:
    """Build the exact locked public source; leave registry requirements hash-checked."""
    lock = tomllib.loads((PROJECT / "uv.lock").read_text(encoding="utf-8"))
    package = next(item for item in lock["package"] if item["name"] == "conric")
    source = urllib.parse.urlsplit(package["source"]["git"])
    commit = source.fragment
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or urllib.parse.parse_qs(source.query) != {
        "rev": [commit]
    }:
        raise SystemExit("Conric bundle source must be an exact flat-root Git commit")
    url = urllib.parse.urlunsplit(source._replace(query="", fragment=""))
    requirement = f"conric @ git+{url}@{commit}"
    lines = selected.read_text(encoding="utf-8").splitlines(keepends=True)
    references = [line for line in lines if line.startswith("conric @")]
    if [line.strip() for line in references] != [requirement]:
        raise SystemExit("Selected Conric source does not match the exact lock")
    run(
        "uv",
        "tool",
        "run",
        "--from",
        PIP_TOOL,
        "--python",
        sys.executable,
        "pip",
        "wheel",
        "--no-deps",
        "--build-constraint",
        "build-constraints.txt",
        "--wheel-dir",
        str(wheels),
        requirement,
    )
    expected = wheels / f"conric-{package['version']}-py3-none-any.whl"
    if not expected.is_file() or list(wheels.glob("conric-*.whl")) != [expected]:
        raise SystemExit("Conric source did not produce one portable pure-Python wheel")
    selected.write_text("".join(line for line in lines if line not in references), encoding="utf-8")
    return requirement


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--python", default="3.13", help="the Python release on the target")
    arguments = parser.parse_args()
    reason = release_version.problem(PROJECT)
    if reason:
        raise SystemExit(f"Refusing to build the bundle: {reason}")
    out = arguments.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    python = arguments.python
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch) / "bundle"
        wheels = root / "wheels"
        wheels.mkdir(parents=True)
        run(
            "uv",
            "build",
            ".",
            "--wheel",
            "--build-constraints",
            "build-constraints.txt",
            "--out-dir",
            str(wheels),
        )
        (wheels / ".gitignore").unlink(missing_ok=True)
        (wheel,) = wheels.glob("vellric-*.whl")
        version = wheel.name.split("-")[1]
        # The versions come from the lock; the target decides which of them it needs.
        locked = Path(scratch) / "locked.txt"
        locked.write_text(
            run(
                "uv",
                "export",
                "--locked",
                "--extra",
                "ocr",
                "--no-dev",
                "--no-emit-project",
                "--no-hashes",
                "--format",
                "requirements-txt",
            ),
            encoding="utf-8",
        )
        selected = Path(scratch) / "selected.txt"
        run(
            "uv",
            "pip",
            "compile",
            "pyproject.toml",
            "--extra",
            "ocr",
            "--constraint",
            str(locked),
            "--python-platform",
            "x86_64-pc-windows-msvc",
            "--python-version",
            python,
            "--generate-hashes",
            "--no-header",
            "--output-file",
            str(selected),
        )
        conric_source = materialize_conric(selected, wheels)
        # Each registry wheel is checked against its published hash as it arrives.
        run(
            "uv",
            "tool",
            "run",
            "--from",
            PIP_TOOL,
            "--python",
            sys.executable,
            "pip",
            "download",
            "--require-hashes",
            "--only-binary=:all:",
            "--no-deps",
            "--platform",
            "win_amd64",
            "--python-version",
            python,
            "--implementation",
            "cp",
            "--dest",
            str(wheels),
            "--requirement",
            str(selected),
        )
        # Install every recorded wheel without resolving direct Git metadata on the target.
        wheel_requirements = [
            f"./wheels/{item.name} --hash=sha256:{hashlib.sha256(item.read_bytes()).hexdigest()}\n"
            for item in sorted(wheels.glob("*.whl"))
        ]
        (root / "requirements-wheels.txt").write_text("".join(wheel_requirements), encoding="utf-8")
        (root / "SOURCE.txt").write_text(conric_source + "\n", encoding="utf-8")
        for name in ("LICENSE", "NOTICE"):
            shutil.copyfile(PROJECT / name, root / name)
        for name in tracked("LICENSES"):
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT / name, root / name)
        (root / "docs").mkdir()
        for name in tracked("docs"):
            if Path(name).parent == Path("docs"):  # The guides, not their sample folders.
                shutil.copyfile(PROJECT / name, root / name)
        (root / "INSTALL.txt").write_text(
            INSTALL.format(
                version=version,
                python=python,
                home="$env:LOCALAPPDATA\\vellric",
                **ENGINES,
            ),
            encoding="utf-8",
            newline="\r\n",
        )
        target = out / f"vellric-{version}-windows-x64-py{python.replace('.', '')}.zip"
        stamp = time.gmtime(EPOCH)[:6]
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    entry = zipfile.ZipInfo(path.relative_to(root).as_posix(), stamp)
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    entry.external_attr = 0o644 << 16
                    archive.writestr(entry, path.read_bytes())
        for path in sorted(wheels.iterdir()):
            print(hashlib.sha256(path.read_bytes()).hexdigest(), path.name)
    print(hashlib.sha256(target.read_bytes()).hexdigest(), target.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
