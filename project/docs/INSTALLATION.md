# Install Vellric 0.1.0

Vellric needs Python 3.12+, PyMuPDF 1.28.2 and Pillow 12.3.0. macOS and Linux arm64 are qualified; atomic publication currently supports macOS/Linux and refuses unsupported platforms. English native/full-OCR samples are qualified. Other languages/architectures need their own fixture qualification.

## Native PDF work

Download the candidate wheel, or extract the matching source archive. In a new directory:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ./vellric-0.1.0-py3-none-any.whl
.venv/bin/vellric --version
.venv/bin/vellric doctor --json
```

From extracted source, replace the wheel argument with `.`. For exact locked installation, export uv.lock and install its hash-pinned requirements as shown in [release preparation](RELEASE-PREPARATION.md). The local proof uses fresh wheel and source installations with those exact pins.

## Scan OCR

```bash
uv pip install --python .venv/bin/python './vellric-0.1.0-py3-none-any.whl[ocr]'
.venv/bin/vellric doctor --json
```

The optional `vision` extra pins the `anthropic` package 1.12.0, needed only for `--vision-provider anthropic`; the `openai` and `command` providers need no extra package. The OCR extra pins OCRmyPDF 17.7.0. Install Tesseract **5.5.2**, the requested traineddata (`eng` and `osd` for qualified English preflight), and Ghostscript; qpdf is part of the qualified preflight platform. Python installation does not install those OS engines. Doctor reports what is present and refuses unqualified recognition versions; use its actual output before a conversion.

On macOS, Homebrew's tesseract/ghostscript/qpdf packages are a convenient prerequisite route; confirm the installed Tesseract version is 5.5.2 rather than assuming the formula matches. The qualified Mac Ghostscript is 10.07.1. On Linux, the qualification builds the official Tesseract 5.5.2 source with Leptonica and uses Ghostscript 10.00.0/qpdf from the platform. Build prerequisites are a C++ compiler, pkg-config, autoconf/automake/libtool and Leptonica development headers. Official source/data links and exact hashes are in [qualification evidence](QUALIFICATION.md). Distribution-specific package commands are outside the portable CLI install.

Specify an actual data directory when needed:

```bash
.venv/bin/vellric doctor --json --tessdata-dir /absolute/tessdata
.venv/bin/vellric convert scan.pdf --tessdata-dir /absolute/tessdata --out scan-result --status-json
```

The directory must contain the requested traineddata. Do not copy the illustrative absolute path literally. Executable search uses trusted standard directories and the Vellric environment; child credentials/loader/Python injection variables are scrubbed. No engine or language data downloads occur during jobs.

For independently installed Drawbridge, set DRAWBRIDGE_VELLRIC to this environment's absolute executable. No sibling repository or editable Vellric import is needed. See [boundary integration](INTEGRATION.md).
