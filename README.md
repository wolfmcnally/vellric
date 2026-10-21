# Vellric

Vellric inspects PDFs, preserves exact native text, recovers scans at four rotations, and exports optional native Markdown, page images and layout artifacts. Each CLI invocation owns one complete document job and publishes an inspectable bundle atomically. It requires no Drawbridge, account credentials or model provider.

The current candidate is **0.2.3**, licensed **AGPL-3.0-only**. Public source history retains its audited root and subsequent qualified commits. Original MIT grants and dependency notices are retained.

Version 0.2.3 replaces the macOS process-listing watchdog with native process-group resident-memory queries. Memory, disk and deadline limits remain sampled controls, and network containment belongs to the caller. The matching release notes must record measured platform and caller-profile qualification; cloud-vision human acceptance remains OPEN and UNQUALIFIED. The released 0.2.2 artifacts remain unchanged.

As of 2026-10-21, this version pins public MIT-licensed Conric 0.1.0 for [composed configuration](project/docs/CONFIGURATION.md). The source integration is public. A tagged release requires exact-commit public CI, Windows bundle qualification and the other [release checks](policies/releases.md); the matching GitHub release records the observed results.

Historical v0.2.2 ruling: as of 2026-10-21, the operator approved v0.2.2’s `vellric-0.2.2-py3-none-any.whl` and `vellric-0.2.2.tar.gz` for qualified Conric, native and OCR use, conditional on every other mandatory release gate passing. **Cloud-vision human acceptance remains OPEN and UNQUALIFIED.** This one-release exception does not close the real-provider tests, authorize provider calls or credentials, qualify cloud-vision output, or permit Windows binary distribution.

## Quick start

With Python 3.12+, uv and Git access to the public dependency, from the directory containing the locally built candidate wheel:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python ./vellric-0.2.3-py3-none-any.whl
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
