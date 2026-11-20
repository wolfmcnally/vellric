---
title: The public handoff path guard knows only macOS and Windows forms
scope: methodology
proposed_surface: bin
source: teach
slug: broad-kelpie
status: candidate
filed: '2026-11-20'
occurrences:
- date: '2026-11-20'
  ref: Hosted Linux Qualification of a recipient after the Starter 1.9.0 teach (run
    44801328916)
---

`HANDOFF_FORBIDDEN` in `lib/agentic_starter/execution_dashboard.py` refuses `/Users/` and drive-letter paths only. On a Linux runner the inherited proof `test_payload_reports_each_operator_park_and_nonexact_total` wrote a handoff whose project was the checkout path `/home/runner/...`; it was accepted, so the proof that a refusal leaves the evidence unchanged failed. The suite passes on macOS only because the temporary path happens to sit under `/Users`. The recipient added a generic absolute-POSIX pattern (a slash that begins the text or follows a space, quote or bracket) with a proof that four Linux paths are refused and relative labels such as `reports/execution`, `and/or` and `1/2` are kept. The template should carry the same guard and run its handoff proofs on a Linux path.