"""Build the self-contained Windows bundle: Vellric, its locked dependencies and install notes.

Run on Windows with the Python release the bundle is for; the wheels fetched are the ones that
interpreter would install. The bundle installs with no package index:

    python packaging/windows_bundle.py --out dist
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

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

    Tesseract {tesseract}   {tesseract_installer}
    Ghostscript {ghostscript}  {ghostscript_installer}

Install both to their default folders under Program Files. Until then, add
--vision-cross-check off --ocr never to a convert that uses a vision model.

The guides are in the docs folder, starting with INSTALLATION.md and CLI.md.
"""

ENGINES = {
    "tesseract": "5.5.3",
    "tesseract_installer": "tesseract-ocr-w64-setup-5.5.3.20260724.exe",
    "ghostscript": "10.07.1",
    "ghostscript_installer": "gs10071w64.exe",
}


def run(*command: str, cwd: Path = PROJECT) -> str:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    if sys.platform != "win32":
        parser.error("the bundle is built on Windows, by the Python release it is for")
    out = arguments.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    python = f"{sys.version_info.major}.{sys.version_info.minor}"
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
        (wheel,) = wheels.glob("vellric-*.whl")
        version = wheel.name.split("-")[1]
        locked = Path(scratch) / "requirements.txt"
        locked.write_text(
            run(
                "uv",
                "export",
                "--locked",
                "--extra",
                "ocr",
                "--no-dev",
                "--no-emit-project",
                "--format",
                "requirements-txt",
            ),
            encoding="utf-8",
        )
        # The hashes in the lock are checked as each wheel arrives.
        run(
            sys.executable,
            "-m",
            "pip",
            "download",
            "--require-hashes",
            "--only-binary=:all:",
            "--no-deps",
            "--dest",
            str(wheels),
            "--requirement",
            str(locked),
        )
        for name in ("LICENSE", "NOTICE"):
            shutil.copyfile(PROJECT / name, root / name)
        shutil.copytree(PROJECT / "LICENSES", root / "LICENSES")
        (root / "docs").mkdir()
        for guide in sorted((PROJECT / "docs").glob("*.md")):
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
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
    print(target.name, hashlib.sha256(target.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
