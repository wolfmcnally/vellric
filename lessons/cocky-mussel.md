---
title: An execution archive with no phases is parsed but never regenerated or compared
scope: methodology
proposed_surface: bin
source: teach
slug: cocky-mussel
status: candidate
filed: '2026-11-20'
occurrences:
- date: '2026-11-20'
  ref: Starter 1.9.0 teach; stale-dashboard proof failed in a recipient with an empty
    archive
---

`bin/check-execution-dashboards` returned early for an archive with no phase payloads: it parsed the tracked index and checked its phase lists, but never compared it with a regeneration and could not regenerate it. A recipient adopting the renderer (every fresh stamp and every migration without reports) therefore failed the inherited stale-dashboard proof with `not a data-only frozen assignment` instead of `stale dashboard artifact`, and `--regenerate` could not repair the file. The recipient now renders the empty index through the same regenerate-and-compare path as a populated archive (`_write_index(regenerated, [])`). The template should carry the same correction and a proof on an empty archive.