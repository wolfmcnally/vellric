---
title: A transfer that adds a gate lane must also provision its prerequisites in the
  recipient's hosted qualification
scope: methodology
proposed_surface: skill
source: teach
slug: wonderful-goldfish
status: candidate
filed: '2026-11-20'
occurrences:
- date: '2026-11-20'
  ref: Starter 1.9.0 teach; hosted Qualification run 44815226044 failed policy-docs
    with mdbook missing
---

The 1.9.0 gate runs `./bin/docs check`, which needs the pinned mdBook and admonish tools. The transfer built them locally under the ignored `.kickoff/docs-tools/` and passed the full gate, but the recipient's hosted Qualification job never provisions them, so the first hosted run that reached the policy lanes failed with `DOCS REFUSED: required mdbook 0.4.50 missing`. The teach skill's gate-prerequisite step lists prerequisites outside the tree but only checks the local machine. It should also inspect every hosted job that runs the full gate and carry each new prerequisite into it (here: the Rust pin from `documentation.toml` and `./bin/docs setup`) in the same transfer.