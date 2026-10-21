---
slug: easygoing-skylark
title: Check installed notice completeness independently of filename extension filters
status: candidate
scope: local
proposed_surface: bin
filed: 2026-10-21
source: disposition
occurrences:
  - date: 2026-10-21
    ref: "v0.2.2 final release-repair advice ADV-F01"
---

When collecting dependency notices, recognize operative license basenames without assuming a text-file extension, then compare the inventory with a separate filesystem census. The v0.2.2 collector accepted only empty, txt, md and rst suffixes: it retained sniffio's short LICENSE pointer but omitted LICENSE.APACHE2 and LICENSE.MIT. A nonempty per-package notice list therefore did not prove that the operative terms were retained.

The original collection and inventory were preserved. The corrected collection retains and hashes both operative files, excludes Python code captured merely by a licenses directory name, and an independent recursive filesystem census verifies every named notice and its actual byte hash. No license grant changed. This is a provisional lesson for release evidence tooling, not a graduated rule or a claim that all possible notice names can be inferred mechanically.
