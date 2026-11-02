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
---

When validating a text declaration produced by an existing cross-platform writer, retain the raw artifact hash and compare the declared identity with only the writer's documented newline variation normalized. Do not strip whitespace, ignore extra lines or weaken exact URL/revision checks. Include actual Windows CRLF bytes in the fixture before claiming portability from a macOS pass.

As of 2026-11-02, the first Windows pipeline source commit built and installed its bundle but the new inventory compared SOURCE.txt against literal LF bytes. The immutable builder uses a normal text writer, which emits CRLF on Windows. Local LF fixtures missed this transport difference. The correction accepts CRLF as LF solely for that single exact declaration while preserving original archive bytes and hashes; an extra blank line still refuses. Original CI failures and production-mutation red/restored-green evidence are retained.

The workflow's later forced diagnostic conversion reported missing language data because the earlier provenance refusal caused engine installation to be skipped. Preserve both failures and their ordering; do not diagnose an engine regression from a conversion that ran before its prerequisites. Actual installed-engine and final-ZIP qualification remain required, separate from this correction.
