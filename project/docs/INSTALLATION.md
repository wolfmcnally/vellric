# Install Vellric 0.2.0

Vellric needs Python 3.12+, PyMuPDF 1.28.2 and Pillow 12.3.0. macOS and Linux arm64 are qualified, and Windows x64 is supported as described under [Windows](#windows); atomic publication refuses any other platform. English native/full-OCR samples are qualified. Other languages/architectures need their own fixture qualification.

## Native PDF work

Download the candidate wheel, or extract the matching source archive. In a new directory:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ./vellric-0.2.0-py3-none-any.whl
.venv/bin/vellric --version
.venv/bin/vellric doctor --json
```

From extracted source, replace the wheel argument with `.`. For exact locked installation, export uv.lock and install its hash-pinned requirements as shown in [release preparation](RELEASE-PREPARATION.md). The local proof uses fresh wheel and source installations with those exact pins.

## Scan OCR

```bash
uv pip install --python .venv/bin/python './vellric-0.2.0-py3-none-any.whl[ocr]'
.venv/bin/vellric doctor --json
```

The optional `vision` extra pins the `anthropic` package 1.12.0, needed only for `--vision-provider anthropic`; the `openai`, `bedrock` and `command` providers need no extra package. The OCR extra pins OCRmyPDF 17.7.0. Install Tesseract **5.5.2**, the requested traineddata (`eng` and `osd` for qualified English preflight), and Ghostscript; qpdf is part of the qualified preflight platform. Python installation does not install those OS engines. Doctor reports what is present and refuses unqualified recognition versions; use its actual output before a conversion.

On macOS, Homebrew's tesseract/ghostscript/qpdf packages are a convenient prerequisite route; confirm the installed Tesseract version is 5.5.2 rather than assuming the formula matches. The qualified Mac Ghostscript is 10.07.1. On Linux, the qualification builds the official Tesseract 5.5.2 source with Leptonica and uses Ghostscript 10.00.0/qpdf from the platform. Build prerequisites are a C++ compiler, pkg-config, autoconf/automake/libtool and Leptonica development headers. Official source/data links and exact hashes are in [qualification evidence](QUALIFICATION.md). Distribution-specific package commands are outside the portable CLI install.

Specify an actual data directory when needed:

```bash
.venv/bin/vellric doctor --json --tessdata-dir /absolute/tessdata
.venv/bin/vellric convert scan.pdf --tessdata-dir /absolute/tessdata --out scan-result --status-json
```

The directory must contain the requested traineddata. Do not copy the illustrative absolute path literally. Executable search uses trusted standard directories and the Vellric environment; child credentials/loader/Python injection variables are scrubbed. No engine or language data downloads occur during jobs.

## Windows

Vellric runs natively on 64-bit Windows 10 or 11 with Python 3.12.4 or later; earlier Python releases create the private workspace readable by other accounts, and jobs refuse. No Linux subsystem, container or administrator right is needed for native PDF work or for a vision-model pass.

The Windows bundle, `vellric-0.2.0-windows-x64-py313.zip`, holds Vellric, every locked Python dependency of the OCR extra as Windows wheels for Python 3.13, the guides and an `INSTALL.txt`. It installs with no package index. In PowerShell, from the extracted folder:

```powershell
python -m venv "$env:LOCALAPPDATA\vellric"
```

```powershell
& "$env:LOCALAPPDATA\vellric\Scripts\python.exe" -m pip install --no-index --find-links wheels "vellric[ocr]==0.2.0"
```

```powershell
& "$env:LOCALAPPDATA\vellric\Scripts\vellric.exe" doctor
```

Build the bundle on Windows, with the Python release it is for, by running `python packaging/windows_bundle.py --out dist` from the project directory; it checks each wheel against the hashes in `uv.lock`.

Tesseract and Ghostscript are separate programs that need an administrator to install. Windows accepts Tesseract **5.5.3** from the project's official installer, `tesseract-ocr-w64-setup-5.5.3.20260724.exe`, because the project publishes no Windows build of 5.5.2; a scanned page may therefore read slightly differently on Windows than on macOS or Linux. Ghostscript is `gs10071w64.exe` (10.07.1). Install both to their default folders under Program Files, where Vellric looks for them. Without them a vision-model pass still works with `--ocr never --vision-cross-check off`; a scanned page then has no independent reading, so nothing checks the model's transcription of it.

What differs from macOS and Linux:

- The worker and every program it starts are held in a job object. Ending the job, or the supervisor itself, ends them all.
- A parent process stops a job by sending a break event (`CTRL_BREAK_EVENT`) to a supervisor started in its own process group; Ctrl+C works at a console.
- `--vision-command` names a program Windows can start directly, such as an `.exe` or a `.cmd` file. Its output is read as UTF-8, and Windows line endings in it become plain ones.
- Refusing a linked input checks the name before and after opening it, since Windows cannot refuse a link in the open itself.
- Status and progress are written as UTF-8 whatever the console's code page.

For independently installed Drawbridge, set DRAWBRIDGE_VELLRIC to this environment's absolute executable. No sibling repository or editable Vellric import is needed. See [boundary integration](INTEGRATION.md).
