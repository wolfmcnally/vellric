---
title: Root test fixtures and inherited proof records collide with a recipient's own
  suite and history
scope: methodology
proposed_surface: test
source: teach
slug: wondrous-panther
status: candidate
filed: '2026-11-20'
occurrences:
- date: '2026-11-20'
  ref: Starter 1.9.0 teach into a recipient with its own product conftest and a completed
    v3 reset
---

Three collisions surfaced in one transfer. First, the root `tests/conftest.py` arrives with an in-repository `tmp_path` fixture; collected together with the product suite it replaced the product tests' temporary directories (a test needing a directory outside any repository failed) and made `from conftest import ...` in product tests resolve to the root module. The recipient moved its shared constant to a uniquely named module and overrode `tmp_path` in its product conftest. Second, the recipient's reset had consolidated an older test of the same name as a new Starter test; the validator never lets a consolidated id return, so the new test had to be renamed locally. Third, many recorded defects in `tests/proof-plants.json` carry the placeholder expectation `failed`, which never matches a declared failure line, so a recipient must observe and supply every expectation itself. The transfer skill or the plants file should account for all three.