# Vellric

Vellric inspects PDFs, preserves exact native text, recovers scans at four rotations, and exports optional native Markdown, page images and layout artifacts. Each CLI invocation owns one complete document job and publishes an inspectable bundle atomically. It requires no Drawbridge, account credentials or model provider.

The first local public candidate is **0.1.0**, licensed **AGPL-3.0-only**. Public releases use fresh audited histories. Original MIT grants and dependency notices are retained.

## Quick start

With Python 3.12+ and uv, from the directory containing the downloaded candidate wheel:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ./vellric-0.1.0-py3-none-any.whl
.venv/bin/vellric --version
.venv/bin/vellric doctor --json
.venv/bin/vellric convert input.pdf --ocr never --structure native --out converted --status-json
```

`input.pdf` is your local PDF. `converted` must not exist. The result retains exact text in per-page artifacts; document.md is the reader view. Native-only conversion truthfully lists scan pages still requiring OCR. For scan recovery, install the OCR extra and qualified system engines as described in the installation guide, then omit `--ocr never`.

## Guides

[Install](docs/INSTALLATION.md) · [Examples](docs/EXAMPLES.md) · [CLI/configuration/artifacts](docs/CLI.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Licensing](docs/LICENSING.md) · [Drawbridge boundary](docs/INTEGRATION.md) · [Build/release](docs/RELEASE-PREPARATION.md)

From extracted source, `uv tool install --python 3.12 --extra ocr .` installs the Python package. System OCR engines are separate; conversion never downloads tools, data or models. Build/test material, exact dependency lock, build constraints, full AGPL text and original MIT notices remain in the source archive.
