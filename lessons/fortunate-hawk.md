---
title: A v3 proof estate needs a supported route to v5, and admission must refuse
  an empty expectation before it witnesses anything
scope: methodology
proposed_surface: bin
source: teach
slug: fortunate-hawk
status: candidate
filed: '2026-11-20'
occurrences:
- date: '2026-11-20'
  ref: Starter 1.9.0 teach into a recipient whose proof estate was on schema v3
---

The v5 manager refuses every admitted or repaired proof without an observed witness receipt. A recipient whose estate predates receipts (schema v3, prose red-witness fields) has no supported conversion: its post-baseline admissions all become unwitnessed, and its admission of arriving proofs is refused until every one is witnessed. In this transfer 183 historical proofs had to be witnessed by hand-authored defects (128 jobs, shared defects only under the policy's three conditions), two of them only in a networkless qualification container that carries the system OCR engines, and two only under the product's locked optional extra.

Separately, `test-governance admit` checked that its result could be recorded before planting, but not that each supplied expectation was nonempty. An input with empty expectations witnessed two proofs, appended their receipts, then stopped at the third; the receipts stayed in the append-only ledger naming proofs the audit ledger did not yet know, and validation refused until a corrected admission recorded them. The precheck should reject malformed witness fields before the first plant, and the transfer skill should describe the v3-to-v5 route (receipts for prior admissions, gate and hook proofs witnessed through the pytest that asserts their command lists, environment-bound proofs witnessed in the environment that runs them).