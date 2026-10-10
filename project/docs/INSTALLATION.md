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

From extracted source, replace the wheel argument with `.`. For exact locked installation, export uv.lock and install its hash-pinned requirements as shown in [release preparation](RELEASE-PREPARATION.md), which was written for 0.1.0; use the current version number in its commands. The local proof uses fresh wheel and source installations with those exact pins.

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

Vellric runs natively on 64-bit Windows with Python 3.12.4 or later; earlier Python releases create the private workspace readable by other accounts, and jobs refuse. Native PDF work and a vision-model pass need no Linux subsystem or container, and nothing in them asks for an administrator.

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

Build the bundle on any system that has uv by running `python packaging/windows_bundle.py --out dist` from the project directory. It takes each dependency at the version in `uv.lock`, selects the Windows wheel for the target Python and checks it against its published hash. The bundle is for installing on one's own machines; [licensing](LICENSING.md) says what passing it to others involves. It does not carry the `anthropic` package, so the `anthropic` vision provider is refused from a bundle install.

Tesseract and Ghostscript are separate programs that need an administrator to install. Windows accepts Tesseract **5.5.3** from the project's official installer, `tesseract-ocr-w64-setup-5.5.3.20260724.exe`, because the project publishes no Windows build of 5.5.2; a scanned page may therefore read slightly differently on Windows than on macOS or Linux. Ghostscript is `gs10071w64.exe` (10.07.1). Run each installer in the ordinary way and keep its default folder under Program Files; the Ghostscript installer raises a window even when asked to run silently. Vellric looks for engines only in those folders, the Python environment it runs from and the Windows system folders, which it takes from the system and not from environment variables. It never looks in the current folder or on the user's PATH, and where two Ghostscript releases are installed it uses the newer. Without them a vision-model pass still works with `--ocr never --vision-cross-check off`; a scanned page then has no independent reading, so nothing checks the model's transcription of it.

As of 2026-10-10 the repository's Windows workflow proves this on a GitHub-hosted Windows Server 2025 machine, under an administrator account: the project tests on Python 3.12 and 3.13, a bundle installed with no package index into a stock Python 3.13, and both fixtures converted with the two engines present. Tesseract came from its installer; Ghostscript's files were unpacked from its installer to the default folder, because the installer waits for a person. Not tested: Windows 10 and 11 desktop editions, an account without administrator rights, other processor types, and inputs on volumes that report no file identity, such as some network shares.

What differs from macOS and Linux:

- The worker and every program it starts are held in a job object: each is started suspended and runs only once the job holds it. Ending the job, or the supervisor itself, ends them all.
- The result folder keeps the private workspace's restricted access and does not inherit the access rules of the folder it is published into.
- A parent process stops a job by sending a break event (`CTRL_BREAK_EVENT`) to a supervisor started in its own process group; Ctrl+C works at a console.
- `--vision-command` names a program Windows can start directly, such as an `.exe` or a `.cmd` file. Its output is read as UTF-8, and Windows line endings in it become plain ones.
- Refusing a linked input checks the name before and after opening it, since Windows cannot refuse a link in the open itself.
- Status and progress are written as UTF-8 whatever the console's code page.

For independently installed Drawbridge, set DRAWBRIDGE_VELLRIC to this environment's absolute executable. No sibling repository or editable Vellric import is needed. See [boundary integration](INTEGRATION.md).
