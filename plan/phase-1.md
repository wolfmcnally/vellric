---
id: phase-1
title: PDF extraction and conversion checklist
depends_on: []
informs: []
---

# PDF extraction and conversion checklist

## Goal

Implement the locally authorized standalone document-job contract. This is one lightweight checklist for tooling navigation, not a scheduled multi-phase program. The operator approved local Vellric implementation on 2026-09-30; no formal phase is opened. Production migration and distribution remain separate.

## Deliverables

The [seed brief](../briefs/BRIEF.md) owns the CLI, artifact schema, PDF/OCR behavior, packaging and migration design. Implement complete inspection/conversion/render jobs; retain original provenance and engine terms; produce isolated install and unchanged parity evidence. Drawbridge migration is separately authorized work.

## Acceptance

Use the five-item [acceptance checklist](../briefs/BRIEF.md#empirical-basis-and-acceptance-strategy), preserving word gates/goldens. Run `./bin/check all` for the complete repository and qualified PDF/OCR gates once they exist. Scaffold checks do not prove PDF functionality. Record any implementation approval and objective evidence before declaring work complete.

## Open questions

The owner-selected license is AGPL-3.0-only. The standalone complete-job process boundary is reaffirmed and local Drawbridge integration authorized; it is not an open owner architecture decision. Measured resource defaults and whether the first public deliverable must include full OCR remain decisions described in the brief. Linux arm64 English full OCR is qualified in project/docs/QUALIFICATION.md; this does not claim other architectures/languages or release authorization.
