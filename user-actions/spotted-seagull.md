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

The vision pass has been proved against stand-in providers and through the external-program route. Two things need the owner.

First, run it once against each hosted route with a real key, which no agent session holds. For Anthropic, set `ANTHROPIC_API_KEY`, install the `vision` extra, and convert `project/tests/fixtures/Fake_Math_Doc_watermarked.pdf` with `--vision-provider anthropic --vision-model` and a model of your choice. For an OpenAI-style endpoint, do the same with `--vision-provider openai`, `--vision-base-url` and `--vision-model`. Confirm the job completes, that `pages/000003/vision.md` holds the displayed formulas as LaTeX, and that the key appears nowhere in the output directory.

Second, before a release, add the `vision` extra's locked dependency closure (the `anthropic` package 1.12.0 and what it pulls in) to the qualified dependency inventory and its licence notices. That closure is locked in `project/uv.lock` but has not been through the release qualification the OCR closure received.
