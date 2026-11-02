# Policy: Releases

This policy governs how a Vellric version is prepared, tagged and published on GitHub, and how the Windows bundle is built and handed out. It codifies what was done for 0.1.0, published on 2026-10-01, and for 0.2.0, tagged on 2026-10-10 but not yet published, whose Windows bundle has been used inside the owner's organisation. The commands live in [`project/docs/RELEASE-PREPARATION.md`](../project/docs/RELEASE-PREPARATION.md) and [`project/docs/INSTALLATION.md`](../project/docs/INSTALLATION.md#windows). This policy says which steps are required, in what order, and who takes them.

## Authority

- A release needs the owner's current authorization naming the version. Agents prepare it: they bump the version, update the guides, run the gates, build the artifacts locally and draft the release notes.
- Tags belong to the owner (hard rule 1). An agent creates a tag only on the owner's explicit, current instruction naming the version, and never moves or deletes one.
- The owner publishes the GitHub release. An agent runs `gh release create`, uploads an asset or publishes a draft only under an explicit, current instruction naming the version and the artifacts.
- No release goes to a package index. Windows binary distribution requires the current owner authorization and exact source/notice/redistribution closure below.

## One-release ruling: v0.2.2 (2026-10-21)

The operator replied “Y” to this exact proposal:

> Before you sleep, one release decision is still pending: approve Vellric v0.2.2’s wheel/source archive for qualified Conric, native and OCR use, with cloud-vision acceptance explicitly left open? All other release checks, including the Windows CI fixes, would still be required.

As of 2026-10-21, the operator approved v0.2.2’s `vellric-0.2.2-py3-none-any.whl` and `vellric-0.2.2.tar.gz` for qualified Conric, native and OCR use, conditional on every other mandatory release gate passing. **Cloud-vision human acceptance remains OPEN and UNQUALIFIED.** This one-release exception does not close the real-provider tests, authorize provider calls or credentials, qualify cloud-vision output, or permit Windows binary distribution. The explicit instruction covers the qualified source push, lightweight `v0.2.2` tag and GitHub release with exactly those two assets. Qualification item 5 is excepted only for the still-pending cloud-vision human checks in `spotted-seagull`; all other qualification, review, CI, license, installation, reproducibility and publication checks remain mandatory. No later release inherits this exception. The retained `misty-hyena` action concerns acceptance of Windows support in 0.2.0 and external distribution of a Windows binary bundle. Neither is claimed or performed by this v0.2.2 project wheel/source release; the action stays pending, and the historical State entries below keep their original version scope. Automated Windows checks still must pass. The separately relayed current instruction explicitly says “Finish bounded repair, exact review/gates, source push/tag/GitHub release as explicitly approved”; this is the delivery scope, not a new inference from the one-word answer.

## One-release ruling: v0.2.3 (2026-10-21)

The operator replied “Y” to the exact question “approve the Vellric 0.2.3 release exception for only the unfinished cloud-vision human checks?” The proposal explicitly kept cloud vision unqualified and made actual publication conditional on resuming the paused delivery session. The session was explicitly resumed before this ruling was applied.

As of 2026-10-21, this current-release exception covers only qualification item 5's unfinished human cloud-vision checks in `spotted-seagull`, for `vellric-0.2.3-py3-none-any.whl` and `vellric-0.2.3.tar.gz`. The bounded native macOS watchdog correction and qualified Conric, native and OCR use remain the release scope. **Cloud-vision human acceptance remains OPEN and UNQUALIFIED.** The pending action stays pending; neither this ruling nor unchanged optional vision descriptions claim real-provider acceptance. No provider calls, credentials, Windows binary distribution or future inheritance are authorized. Every other mandatory review, local gate, exact-commit CI, installed-package, reproducibility, license, independent target qualification and publication verification remains required.

The existing release instruction, explicitly resumed for this version, covers the qualified source push, lightweight `v0.2.3` tag and GitHub publication with exactly those two frozen artifacts after the remaining mandatory gates pass. The temporary sanitized transport sidecar is preserved privately and removed from the draft before publication. The wheel and source archive remain unchanged by this policy-only ruling. No later release inherits this exception; the historical v0.2.2 ruling retains its original scope.

## Version

- One version string, changed in one commit whose subject ends `; version X.Y.Z`. It appears in:
  - `project/pyproject.toml` and `project/vellric/__init__.py`;
  - the `vellric` entry of `project/uv.lock` (regenerate it with `uv lock`, never by hand);
  - the "current candidate" line of `README.md` and `project/README.md`;
  - `project/docs/INSTALLATION.md` (title and bundle name);
  - `project/docs/LICENSING.md` (first line);
  - `project/NOTICE`.
- Before tagging, search the tree for the previous version string and update every current-state mention. Dated historical records keep the version they describe.
- Tags are `vX.Y.Z`: lightweight, on `main`, at the exact commit that was qualified.
- A version names one commit (owner ruling, 2026-10-15). Once `vX.Y.Z` is tagged, the next change under `project/` bumps the version first, in that change or an earlier one.
- `project/packaging/release_version.py` enforces this in three places:
  - the pre-commit hook checks the staged tree, so the offending commit is never made;
  - `./bin/check all` and the Windows bundle builder check the working tree.

  Each refuses a version that is already tagged on different project content. Each also refuses when tags cannot be read: no Git checkout, a shallow clone, or a clone with no release tags. The CI checkouts that run the check fetch full history for this reason.
- A full-gate result saved before the owner tagged can still let a push through locally. CI re-runs the check on every push.

## Qualification before tagging

Everything below runs on the exact commit that will be tagged:

1. `./bin/check all` passes locally, with every warning explained.
2. Both GitHub workflows, Qualification and Windows, pass for that commit.
3. Wheel and source archive are built reproducibly with the fixed `SOURCE_DATE_EPOCH` and `project/build-constraints.txt`. Rebuilding from the source archive gives byte-identical files.
4. Fresh, isolated, locked installs of the built wheel complete native and OCR jobs on macOS and Linux, and `vellric doctor` reports the qualified engine identities.
5. Every file in `user-actions/` whose `blocks` names this release, or a capability it advertises, is closed.
6. Hashes, receipts and install results go into the local release evidence (`release-receipt.json` and its companion files). That evidence is never committed to the public tree, and the public history never carries private development records.

## GitHub release

- Titled `Vellric X.Y.Z` and attached to tag `vX.Y.Z`, with the full commit ID as its target. It is not a prerelease.
- Created as a draft, checked, then published. (0.1.0 was created at 09:34 UTC and published at 10:04.)
- The project assets are `vellric-X.Y.Z-py3-none-any.whl` and `vellric-X.Y.Z.tar.gz`, byte-identical to the recorded hashes. The separately qualified Windows asset is `vellric-X.Y.Z-windows-x64-py313.zip`; it may be added only under current authorization after the Windows binary closure and real installed-ZIP qualification below. Existing assets are never replaced or deleted.
- The notes follow 0.1.0's order:
  1. What the version provides.
  2. Licensing: AGPL-3.0-only with the retained MIT grants; dependencies install separately under their own licenses; the packages contain no dependency binaries, OCR programs or language data; read NOTICE before redistributing a bundled runtime.
  3. `Qualified source:` the full commit ID, then the gate, CI, install and reproducibility results actually observed.
  4. Known limits, such as the watchdog not being a sandbox.

  State only what was observed.
- After publishing, `gh release view vX.Y.Z` must show the expected tag, target and asset names. The downloaded assets must match the recorded hashes.
- A coordinated consumer release follows the publication order in `RELEASE-PREPARATION.md`. Live consumer changes need their own authorization.

## Windows bundle

- **Build.** Start from the tagged commit, in a full Git checkout with a clean tree. From `project/`, run `python packaging/windows_bundle.py --out dist`. The bundle targets Python 3.13 unless `--python` says otherwise, and the target goes into its name: `vellric-X.Y.Z-windows-x64-py313.zip`. Registry dependency wheels come from `uv.lock` and are checked against their published hashes. Conric is built from its exact locked Git commit, recorded in `SOURCE.txt`; both locally built project wheels and every registry wheel have their byte hashes recorded in `requirements-wheels.txt` and the printed list. The archive's timestamps are fixed; identical source bytes and build inputs give identical output bytes. Only tracked guides and license files go into it. `dist/` is never committed.
- **Record.** The builder prints a SHA-256 for each wheel and for the ZIP. Keep that list, with the version and the commit, in the local release evidence. It matches a bundle in hand against the Windows workflow's list wheel by wheel. The project's own wheel matches only if both were built on the same kind of system (see State).
- **Proof.** On every push, the Windows workflow builds the bundle and installs it with no package index. It then runs `doctor`, `inspect` and `render`, installs the qualified engines, runs the tests with no skips allowed, and converts the fixtures. A trial on the target machine is the owner's acceptance, recorded in `user-actions/`. An agent never claims it.
- **Distribution.** The operator explicitly requested the Windows ZIP as part of the standard release pipeline and its addition to current v0.2.4 on 2026-11-02. This supplies the publication decision, not proof of third-party rights, native source or notices. Existing organisation-only use remains historical; public workflow retention and release attachment require the exact closure below.
- **Source closure.** `lib/windows-release-sources.json` records the reviewed native wheel identities, exact source/notice materials and observed native versions. A pending declaration refuses release assembly/retention. The declaration is a technical disposition, not authentication or a grant of a Microsoft license. Corresponding source includes native libraries and build material where their licenses require it; Python sdists alone are not assumed sufficient. Preserve original wheel notices and add any evidenced correction, retaining both provenance and exact material hashes. Establish applicable non-open-source redistribution terms as well as open-source obligations before declaring closure qualified.
- **Pipeline.** The existing Windows workflow retains measured reports on ordinary pushes. A published-release event or `workflow_dispatch` with an existing `release_ref` additionally assembles the source-closed ZIP, freshly installs that actual ZIP offline with hashes, checks dependencies/doctor, and completes native/OCR conversions before retaining `windows-release-zip`. It uses the existing read-only repository token; it does not add a publication grant. The standard owner-authorized CLI publication route is documented in [Windows release procedure](../WINDOWS-RELEASE.md).
- **Current backfill.** v0.2.4's source/tag and existing project wheel/source archive remain immutable. Release tooling outside `project/` may produce the additional ZIP from the exact tagged project content, with the tooling revision/content identity recorded separately. No project edit or retag is implied. The original discarded CI bundle is not claimed recovered; a new exact-source build receives its own hash and real Windows qualification. Target-desktop human acceptance remains separate from hosted x64 CI and any ARM64 Parallels emulation coverage.

## State as of 2026-10-16

- **0.1.0:** tag `v0.1.0` at `a2b140a4eda87b4e6cb5925ba5e605031890fb31`. GitHub release published on 2026-10-01 with the wheel and source archive. No Windows bundle existed.
- **0.2.0:** tag `v0.2.0` at `1fc89991063d29c91f9c96e83d73307b5989d3c2`; no GitHub release.
  - `project/docs/RELEASE.md` records that 0.2.0 has not been through release preparation.
  - User actions `misty-hyena` and `spotted-seagull` block it.
  - Commits after the tag changed the project while still calling it 0.2.0. On 2026-10-15 those changes became 0.2.1, so 0.2.0 again names only the tagged code.
- **0.2.1:** tag `v0.2.1` at `963396fbe51255dd0ed761b6f4c16e2ce8181942`, created on 2026-10-16 on the owner's instruction after qualification on that commit; no GitHub release.
  - Gates: full gate and both workflows passed.
  - Builds: wheel and source archive rebuilt byte-identically from the source archive.
  - macOS (arm64): a fresh locked install ran native and OCR jobs with page text identical to the source tree.
  - Linux: a fresh locked install in a disposable Ubuntu 24.04 arm64 container, with Tesseract 5.5.2 built from source, ran the same jobs. Native and `Fake_Doc_watermarked.pdf` pages are identical to macOS. `Fake_Math_Doc_watermarked.pdf` pages 1 and 3 differ, the same pages that differ on Windows.
  - Windows bundle: built from the tagged tree, rebuilt byte-identically, and handed to the owner. Its 29 dependency wheels match the Windows workflow's list for that commit. Its Vellric wheel does not: the copy built on Windows differs from the macOS build.
  - The same user actions block its release.

## Open decisions (owner)

1. Whether 0.2.0 is published from its existing tag, and when 0.2.1 gets a GitHub release.
2. Whether a release is recorded in `LOG.md`. No release has been so far.
3. Historical sharing decision resolved by the 2026-11-02 instruction above; exact binary source/notice/redistribution closure remains an executable preparation obligation, not an inferred waiver of third-party terms.
4. Whether the locally built Vellric and Conric wheels must build byte-identically on every system. The likely cause of the Windows difference is unconfirmed: license and notice files have no fixed line ending in `.gitattributes`, so a Windows checkout may give them CRLF.
