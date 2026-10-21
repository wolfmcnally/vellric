---
slug: spotted-seagull
title: Check the vision pass against real providers and qualify its optional dependency
status: pending
category: credentials
urgency: medium
blocks:
  - Any release that advertises the vision pass
filed: 2026-10-07
needed_at: before the next release
source: primary
refs:
  - project/docs/CLI.md
  - project/docs/LICENSING.md
  - project/pyproject.toml
---

The vision pass has been proved against stand-in providers, through the external-program route, and on 2026-10-09 against Amazon Bedrock with a real bearer key. Two things need the owner.

First, run it once against each of the two other hosted routes with a real key, which no agent session holds. For Anthropic, set `ANTHROPIC_API_KEY`, install the `vision` extra, and convert `project/tests/fixtures/Fake_Math_Doc_watermarked.pdf` with `--vision-provider anthropic --vision-model` and a model of your choice. For an OpenAI-style endpoint, do the same with `--vision-provider openai`, `--vision-base-url` and `--vision-model`. Confirm the job completes, that `pages/000003/vision.md` holds the displayed formulas as LaTeX, and that the key appears nowhere in the output directory.

Second, the dependency inventory and notice portion was completed on 2026-10-21: a fresh locked macOS arm64 environment with both OCR and vision extras produced the current `project/docs/dependencies-qualified.json`, including `anthropic` 1.12.0, Conric's exact public Git source, actual installed notice-file hashes and locked registry source identities. Actual notice texts are retained in the local release companion. This does not close the first, human real-provider criterion, qualify other platforms or authorize binary bundle redistribution; this action remains pending.

As of 2026-10-21, the operator approved v0.2.2’s `vellric-0.2.2-py3-none-any.whl` and `vellric-0.2.2.tar.gz` for qualified Conric, native and OCR use, conditional on every other mandatory release gate passing. **Cloud-vision human acceptance remains OPEN and UNQUALIFIED.** This one-release exception does not close the real-provider tests, authorize provider calls or credentials, qualify cloud-vision output, or permit Windows binary distribution. The operator’s exact proposal and affirmative ruling are recorded in `policies/releases.md`. This action remains pending for the human real-provider checks and any claim of full cloud-vision qualification.
