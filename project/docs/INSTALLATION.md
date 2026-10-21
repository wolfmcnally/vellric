# Install Vellric 0.2.3 (local candidate)

As of 2026-10-21 this version uses an exact public MIT-licensed Conric 0.1.0 Git dependency, pinned to commit ed9286297e92b8c049f70eb15a3b5556ed107ff0 at https://github.com/wolfmcnally/conric.git. The package lives at the repository root; no subdirectory selector is used. The wheel's metadata carries that source reference. The source integration is public; tagged release artifacts require repository release qualification. No package-index publication is authorized. A release requires passing exact-commit public CI and the Windows bundle pipeline, as recorded in the matching GitHub release. The Windows instructions describe the internal bundle contract; this project wheel/source release distributes no Windows bundle. No credentials or artifact feed are provisioned. See [configuration](CONFIGURATION.md).

Vellric needs Python 3.12+, PyMuPDF 1.28.2 and Pillow 12.3.0. Earlier fixture evidence qualifies macOS and Linux arm64; current release CI/install results are recorded with their observed architectures in the matching GitHub release. Windows x64 automation and still-pending desktop acceptance are distinct, as described under [Windows](#windows); atomic publication refuses any other platform. English native/full-OCR samples are qualified. Other languages/architectures need their own fixture qualification.

## Native PDF work

Build the candidate wheel locally, or use the matching locally prepared source. In a new directory:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ./vellric-0.2.3-py3-none-any.whl
.venv/bin/vellric --version
.venv/bin/vellric doctor --json
```

From extracted source, replace the wheel argument with `.`. For exact locked installation, export uv.lock and install its pinned requirements as shown in [release preparation](RELEASE-PREPARATION.md), using its current Git-aware registry-hash and exact-source procedure. The local proof uses fresh wheel and source installations with those exact pins.

## Scan OCR

```bash
uv pip install --python .venv/bin/python './vellric-0.2.3-py3-none-any.whl[ocr]'
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

An internally built Windows bundle, `vellric-0.2.3-windows-x64-py313.zip`, holds Vellric, every locked Python dependency of the OCR extra as Windows wheels for Python 3.13, the guides and an `INSTALL.txt`. That bundle contract installs with no package index. Its exact-commit automated proof is a release gate; desktop owner acceptance remains open and no Windows bundle is included in this public release. In PowerShell, run these commands from inside the qualified extracted bundle directory:

```powershell
python -m venv "$env:LOCALAPPDATA\vellric"
```

```powershell
& "$env:LOCALAPPDATA\vellric\Scripts\python.exe" -m pip install --no-index --require-hashes --no-deps -r requirements-wheels.txt
```

```powershell
& "$env:LOCALAPPDATA\vellric\Scripts\python.exe" -m pip check
```

```powershell
& "$env:LOCALAPPDATA\vellric\Scripts\vellric.exe" doctor
```

Build the bundle with Python 3.12+, uv and Git by running `python packaging/windows_bundle.py --out dist` from the project directory. Build it in a full Git checkout: the builder refuses a version that is already tagged on different content, and refuses when it cannot read the tags. Registry wheels are selected for the target Python at the locked versions and checked against their published hashes. The Conric wheel is built from the exact locked Git commit; SOURCE.txt records that source. Every bundled wheel is hashed in requirements-wheels.txt and in the printed build list. The bundle is for installing on one's own machines; [licensing](LICENSING.md) says what passing it to others involves. It does not carry the `anthropic` package, so the `anthropic` vision provider is refused from a bundle install.

Tesseract and Ghostscript are separate programs that need an administrator to install. Windows accepts Tesseract **5.5.3** from the project's official installer, `tesseract-ocr-w64-setup-5.5.3.20260724.exe`, because the project publishes no Windows build of 5.5.2; a scanned page may therefore read slightly differently on Windows than on macOS or Linux. Ghostscript is `gs10071w64.exe` (10.07.1). Run each installer in the ordinary way and keep its default folder under Program Files; the Ghostscript installer raises a window even when asked to run silently. Vellric looks for engines only in those folders, the Python environment it runs from and the Windows system folders, which it takes from the system and not from environment variables. It never looks in the current folder or on the user's PATH, and where two Ghostscript releases are installed it uses the newer. Without them a vision-model pass still works with `--ocr never --vision-cross-check off`; a scanned page then has no independent reading, so nothing checks the model's transcription of it.

As of 2026-10-10 the repository's Windows workflow proves this on a GitHub-hosted Windows Server 2025 machine, under an administrator account: the project tests on Python 3.12 and 3.13, a bundle installed with no package index into a stock Python 3.13, and both fixtures converted with the two engines present. Tesseract came from its installer; Ghostscript's files were unpacked from its installer to the default folder, because the installer waits for a person. On the same date the owner ran the 0.2.0 bundle on a Windows 11 Enterprise machine, from an account without administrator rights and with neither engine installed: it installed with no package index into Python 3.13, and `doctor`, `inspect` and a `convert` whose scanned page was read through the Bedrock vision provider all completed on a generated two-page PDF. Not tested: Windows 10, the two engines on a desktop edition or under an account without administrator rights, other processor types, and inputs on volumes that report no file identity, such as some network shares.

What differs from macOS and Linux:

- The worker and every program it starts are held in a job object: each is started suspended and runs only once the job holds it. Ending the job, or the supervisor itself, ends them all.
- The result folder keeps the private workspace's restricted access and does not inherit the access rules of the folder it is published into.
- A parent process stops a job by sending a break event (`CTRL_BREAK_EVENT`) to a supervisor started in its own process group; Ctrl+C works at a console.
- `--vision-command` names a program Windows can start directly, such as an `.exe` or a `.cmd` file. Its output is read as UTF-8, and Windows line endings in it become plain ones.
- Refusing a linked input checks the name before and after opening it, since Windows cannot refuse a link in the open itself.
- Status and progress are written as UTF-8 whatever the console's code page.

For independently installed Drawbridge, set DRAWBRIDGE_VELLRIC to this environment's absolute executable. No sibling repository or editable Vellric import is needed. See [boundary integration](INTEGRATION.md).

The installed-package configuration proof builds a real wheel and installs the exact locked public runtime sources into a fresh environment, using the executing Python version. It may access public package/Git sources; an unavailable source fails closed rather than substituting another dependency. The separate Windows bundle carries a locally built wheel of the exact locked Conric commit, records that source in SOURCE.txt, and installs every bundled wheel by its recorded hash with dependency resolution disabled. Run pip check afterward; the installed package metadata remains unchanged and no Git access is needed for that bundle installation.

On macOS, candidate 0.2.3 samples the supervised process group through native libproc resident-byte queries, without executing ps. Doctor tests the complete observer on a fresh private process group. Missing, denied, short or persistently truncated observations refuse supervision instead of silently disabling memory enforcement. The existing sampled memory/disk/deadline controls remain; they can overshoot and are not a hard sandbox. Exact caller-sandbox acceptance of this candidate remains open; no sandbox profile or network policy is changed.
