"""Build the self-contained Windows bundle: Vellric, its locked dependencies and install notes.

The bundle installs on 64-bit Windows with no package index. It can be built on any system that
has uv, because every wheel is selected for the target and checked against its published hash:

    python packaging/windows_bundle.py --out dist

It is a convenience for installing on one's own machines. Handing it to anyone else also hands
them third-party binaries, whose source and notice duties docs/LICENSING.md describes.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
EPOCH = 1609459200  # The build time the release procedure fixes, so equal inputs give equal bytes.

INSTALL = """\
Vellric {version} for Windows x64, Python {python}

Everything Vellric needs from Python is in the wheels folder; no package index is used.
In PowerShell, from the folder this file is in:

    python -m venv "{home}"
    & "{home}\\Scripts\\python.exe" -m pip install --no-index --find-links wheels "{requirement}"
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--python", default="3.13", help="the Python release on the target")
    arguments = parser.parse_args()
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
        # Each wheel is checked against its published hash as it arrives.
        run(
            "uv",
            "tool",
            "run",
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
        for name in ("LICENSE", "NOTICE"):
            shutil.copyfile(PROJECT / name, root / name)
        shutil.copytree(PROJECT / "LICENSES", root / "LICENSES")
        (root / "docs").mkdir()
        for guide in sorted(path for path in (PROJECT / "docs").iterdir() if path.is_file()):
            shutil.copyfile(guide, root / "docs" / guide.name)
        (root / "INSTALL.txt").write_text(
            INSTALL.format(
                version=version,
                python=python,
                home="$env:LOCALAPPDATA\\vellric",
                requirement=f"vellric[ocr]=={version}",
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
