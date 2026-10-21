# Vellric

Vellric inspects PDFs, preserves exact native text, recovers scans at four rotations, and exports optional native Markdown, page images and layout artifacts. Each CLI invocation owns one complete document job and publishes an inspectable bundle atomically. It requires no Drawbridge, account credentials or model provider; an opt-in vision pass can add a model's reading of chosen pages.

The current candidate is **0.2.3**, licensed **AGPL-3.0-only**. Public source history retains its audited root and subsequent qualified commits. Original MIT grants and dependency notices are retained.

Candidate 0.2.3 is a local macOS native-RSS watchdog correction. Its installed-package and regression qualification is in progress; exact caller-sandbox acceptance and public publication are not claimed. The released 0.2.2 artifacts remain unchanged.

As of 2026-10-21, this version depends on an exact public MIT-licensed Conric 0.1.0 Git revision with a flat package root. The source integration is public. A tagged release requires exact-commit CI and Windows qualification; the matching GitHub release records the observed results. See [installation](docs/INSTALLATION.md) and [composed configuration](docs/CONFIGURATION.md). No-config CLI behavior is retained.

As of 2026-10-21, the operator approved v0.2.2’s `vellric-0.2.2-py3-none-any.whl` and `vellric-0.2.2.tar.gz` for qualified Conric, native and OCR use, conditional on every other mandatory release gate passing. **Cloud-vision human acceptance remains OPEN and UNQUALIFIED.** This one-release exception does not close the real-provider tests, authorize provider calls or credentials, qualify cloud-vision output, or permit Windows binary distribution.

## Quick start

With Python 3.12+ and uv and existing authorized Git access, from the directory containing the locally built candidate wheel:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ./vellric-0.2.3-py3-none-any.whl
.venv/bin/vellric --version
.venv/bin/vellric doctor --json
.venv/bin/vellric convert input.pdf --ocr never --structure native --out converted --status-json
```

`input.pdf` is your local PDF. `converted` must not exist. The result retains exact text in per-page artifacts; document.md is the reader view. Native-only conversion truthfully lists scan pages still requiring OCR. For scan recovery, install the OCR extra and qualified system engines as described in the installation guide, then omit `--ocr never`. For a higher-quality reading of scans and mathematics by a vision-capable model, and for re-reading selected pages of an earlier result, see the vision pass in the CLI guide.

## Guides

[Install](docs/INSTALLATION.md) · [Examples](docs/EXAMPLES.md) · [CLI/configuration/artifacts](docs/CLI.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Licensing](docs/LICENSING.md) · [Drawbridge boundary](docs/INTEGRATION.md) · [Build/release](docs/RELEASE-PREPARATION.md)

From extracted source, `uv tool install --python 3.12 --extra ocr .` installs the Python package. System OCR engines are separate; conversion never downloads tools, data or models. Build/test material, exact dependency lock, build constraints, full AGPL text and original MIT notices remain in the source archive.
