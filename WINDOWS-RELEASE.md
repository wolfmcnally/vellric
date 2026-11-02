# Windows x64 Python 3.13 release procedure

The standard Windows asset is `vellric-X.Y.Z-windows-x64-py313.zip`. It contains the exact project/dependency wheels, hash-bound offline requirements, original and assembled notices, matching source materials and `WINDOWS-RELEASE.json` provenance. Python, Tesseract and Ghostscript installers are not bundled. Owner authorization and applicable third-party redistribution terms remain separate from a passing test or a manifest field.

## Prepare exact materials

Start from the existing release tag and preserve its project tree. Review the exact Windows registry wheel hashes against the lock and the actual bundled native libraries, not a macOS dependency inventory or an old license summary. `bin/windows-release inventory` records every wheel/native member and notice hash. The installed Windows probe records actual native versions; it refuses to pretend a non-Windows host is Windows.

Complete `lib/windows-release-sources.json` with verified exact materials and native-wheel obligations. All locked registry source archives and required native source/build/notice materials must be present with hashes. Correct misleading component-version notices by adding an attributed correction while retaining original notices. A qualified technical disposition is not proof of owner identity, a redistribution sublicense, or human product acceptance. If a term or provenance fact remains unknown, keep status pending and do not publish or retain the binary ZIP publicly.

## Build and qualify in existing Windows CI

Dispatch the existing Windows workflow on the current qualified release-tooling revision, selecting an immutable source tag. Example for the explicitly authorized backfill:

```sh
gh workflow run windows.yml --ref main -f release_ref=v0.2.4
```

Retain the actual returned/run-query identity and verify its repository, source, event, tooling revision and successful jobs. Do not select a reassuring default on a query error. Wait for that run, then download its `windows-release-zip` and `windows-measured` artifacts through the existing authenticated route. A pending closure declaration intentionally cannot yield a releasable ZIP. No binary upload is inferred from the earlier measured-only workflow run.

The qualified source ZIP is newly assembled, expanded and installed into a fresh Windows venv with `--no-index --require-hashes --no-deps`. Dependency checks, doctor, inspect and native/OCR fixture conversions must succeed on the installed copy. Match the final ZIP digest/size with `windows-release-asset.json`. Preserve real engine/version results, warnings and failures. Existing Parallels Windows may provide additional local qualification without resetting or discarding saved work; report ARM emulation separately from GitHub's real x64 runner. No human desktop acceptance is claimed by either automated route.

## Add only the qualified asset

Read the existing release/tag target and complete asset inventory first. Match the exact tagged project source, raw wheel inventory, source closure and final installed-ZIP result. Keep current version authorization and any redistribution-rights evidence in the private release receipt. No new repository token scope or workflow write permission is needed: use the existing owner-authorized CLI release route.

Upload only the exact qualified ZIP under its standard name, without clobbering or replacing any existing asset. Read it back and independently download the public bytes, verifying SHA-256 and size. Update release notes truthfully with the matching binary-source/notice location inside the ZIP and measured coverage/limits. Preserve the old notes/asset metadata privately before any authorized append. Never claim that a locally rebuilt ZIP is the old discarded CI artifact, or that private source/check receipts were published. Cloud vision and target-desktop human acceptance remain explicitly unqualified/open where applicable.

For v0.2.4, the two existing project assets and tag must remain byte-identical. Source/archive timestamps are fixed; reproduce the assembled ZIP with the same inputs. Actual source and release results belong in the private release receipt and final handoff, not predicted outcomes in this procedure.

The immutable v0.2.4 guides inside the project wheel and raw bundle predate the Windows asset and describe its former undistributed status. The added asset's release notes and `WINDOWS-RELEASE.json`, `third-party-notices/` and `sources/` describe the separately qualified binary distribution; preserve the historical guides rather than silently rewriting tagged project bytes.
