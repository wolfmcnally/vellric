# Get Started

Vellric needs Python 3.12 or later and [uv](https://docs.astral.sh/uv/). PDF work needs nothing else; scan recognition needs the OCR engines described below.

## Install a wheel

From the directory holding the Vellric wheel, create an environment and install it:

```bash
uv venv --python 3.12 .venv
```

```bash
uv pip install --python .venv/bin/python ./vellric-0.2.6-py3-none-any.whl
```

Confirm the installation and see what the machine supports:

```bash
.venv/bin/vellric doctor --json
```

`doctor` reports the software and schema versions, the engines it finds with their executable hashes, and whether atomic publication and process supervision are available here. It installs nothing and processes no document.

## Convert a first document

Convert a PDF without OCR. The output directory must not exist yet:

```bash
.venv/bin/vellric convert input.pdf --ocr never --structure native --out converted --status-json
```

`converted/` now holds the published result. Each page's exact text is in its own directory under `pages/`, `document.md` is the reader view, and `manifest.json` records every artifact. A native-only conversion lists the scanned pages that still need recognition, so a caller that requires OCR can refuse the result.

## Recognize scanned pages

Install the `ocr` extra, then the system engines it drives: Tesseract 5.5.2 with the `eng` and `osd` language data, Ghostscript and qpdf. Python installation does not install these engines. Run `doctor` again; it refuses unqualified Tesseract versions rather than guessing.

```bash
uv pip install --python .venv/bin/python './vellric-0.2.6-py3-none-any.whl[ocr]'
```

Then convert with the default `--ocr auto`, which recognizes the pages that have no native text or are mostly covered by images:

```bash
.venv/bin/vellric convert scan.pdf --out scan-result --status-json
```

```admonish tip title="Where the full guides live"
Installation details for each platform, including the offline Windows bundle and the Linux arm64 offline route, are in `project/docs/INSTALLATION.md` and `project/docs/LINUX-ARM64-OFFLINE.md` in the repository.
```

## Develop Vellric

In a clone of the repository, set up the locked environment and run the checks:

```bash
./bin/setup
```

```bash
./bin/test project/tests
```

```bash
./bin/check all
```

`./bin/check all` is the full gate that qualifies a change for delivery.
