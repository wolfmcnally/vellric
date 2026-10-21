---
slug: ancient-foxhound
title: Verify actual reviewer tool permissions rather than treating an allow list as a denial boundary
status: candidate
scope: methodology
proposed_surface: bin
filed: 2026-10-21
source: disposition
occurrences:
  - date: 2026-10-21
    ref: "0.2.3 release review execution-contract check"
---

As of 2026-10-21, a configured read-only critic was launched with the declared tools Read, Grep, Glob and WebFetch, and the caller explicitly prohibited shell execution. Its actual trace nevertheless recorded one Bash inventory command accepted by inherited configuration. The command counted and searched an already allowed source patch and listed filenames in its review directory; no protected transcript bytes, credentials or product execution were observed. The declared allow list therefore did not establish the promised execution exclusion in that launch.

Check the actual supported tool-denial or tool-availability surface, inherited permission semantics and observed tool trace before claiming a reviewer cannot execute commands. If the wrapper cannot express the intended restriction, report the gap rather than silently changing identities, settings or grants. A violated review remains nonqualifying; preserve it, reconstruct actual data flow, and rerun the affected review within its existing budget. Clean source that predates the violation does not need rewriting merely because the reviewer crossed a tool boundary.

The current correction preserved the first failed review, checked its exact command/results, and used the remaining permitted fresh review pass with a source-only Read/Grep/Glob contract. No engine, global permission or provider setting was changed. Any executable enforcement change and its real denial fixture require the operator's separate ratification; this candidate lesson is not a graduated rule or a claim that a stronger guard has already been installed.
