---
slug: amber-bison
title: Separate text declaration identity from platform newline bytes
status: candidate
scope: local
proposed_surface: bin
filed: 2026-11-02
source: disposition
occurrences:
  - date: 2026-11-02
    ref: "Windows pipeline first exact-source CI qualification"
  - date: 2026-11-03
    ref: "Final installed-ZIP assembly refused checkout-dependent lock hash"
---

When validating a text declaration produced by an existing cross-platform writer, retain the raw artifact hash and compare the declared identity with only the writer's documented newline variation normalized. Do not strip whitespace, ignore extra lines or weaken exact URL/revision checks. Include actual Windows CRLF bytes in the fixture before claiming portability from a macOS pass.

As of 2026-11-02, the first Windows pipeline source commit built and installed its bundle but the new inventory compared SOURCE.txt against literal LF bytes. The immutable builder uses a normal text writer, which emits CRLF on Windows. Local LF fixtures missed this transport difference. The correction accepts CRLF as LF solely for that single exact declaration while preserving original archive bytes and hashes; an extra blank line still refuses. Original CI failures and production-mutation red/restored-green evidence are retained.

The workflow's later forced diagnostic conversion reported missing language data because the earlier provenance refusal caused engine installation to be skipped. Preserve both failures and their ordering; do not diagnose an engine regression from a conversion that ran before its prerequisites. Actual installed-engine and final-ZIP qualification remain required, separate from this correction.

As of 2026-11-03, final assembly exposed the same distinction in a second surface: Git converted the committed LF dependency lock to CRLF on Windows, making a checkout-byte hash differ despite identical clean source and pins. Bind source identity to the exact committed Git blob, retain the observed checkout hash separately, and continue refusing actual dirty lock changes. The existing portable proof now covers clean CRLF lock checkout through real assembly and a modified-lock refusal; this extends the same proof family rather than introducing a duplicate.
