# Vellric

Vellric inspects PDFs, preserves exact native text, recovers scans at four rotations, and exports optional native Markdown, page images and layout artifacts. Each CLI invocation owns one complete document job and publishes an inspectable bundle atomically. It requires no Drawbridge, account credentials or model provider.

The current candidate is **0.2.0**, licensed **AGPL-3.0-only**. Public releases use fresh audited histories. Original MIT grants and dependency notices are retained.

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

- [Installation and platform prerequisites](project/docs/INSTALLATION.md)
- [Worked self-contained examples](project/docs/EXAMPLES.md)
- [CLI, artifacts, limits and configuration](project/docs/CLI.md)
- [Troubleshooting and typed failures](project/docs/TROUBLESHOOTING.md)
- [Licensing, source and notices](project/docs/LICENSING.md)
- [Drawbridge boundary](project/docs/INTEGRATION.md)
- [Release build and coordinated publication](project/docs/RELEASE-PREPARATION.md)

## Repository development

The package lives in project/. The repository retains the Starter methodology, proof estate, skills, policies and tooling; they are not removed from the public source tree. [CLAUDE.md](CLAUDE.md), [plan](plan/INDEX.md), [policies](policies/README.md), [provenance](THIRD_PARTY.md) and the [seed brief](briefs/BRIEF.md) explain that workspace.

```bash
./bin/setup
./bin/python -m vellric doctor --json
./bin/test project/tests
./bin/check all
```

Linux arm64 and macOS are qualified on public/synthetic English fixtures. Read the [qualification scope](project/docs/QUALIFICATION.md) and [integration results](project/docs/INTEGRATION-QUALIFICATION.md). Full gates, license/source notices and independent review evidence remain part of delivery. No model/layout stack or provider service is required for PDF work.
