# Policy: Releases

This policy governs how a Vellric version is prepared, tagged and published on GitHub, and how the Windows bundle is built and handed out. It codifies what was done for 0.1.0, published on 2026-10-01, and for 0.2.0, tagged on 2026-10-10 but not yet published, whose Windows bundle has been used inside the owner's organisation. The commands live in [`project/docs/RELEASE-PREPARATION.md`](../project/docs/RELEASE-PREPARATION.md) and [`project/docs/INSTALLATION.md`](../project/docs/INSTALLATION.md#windows). This policy says which steps are required, in what order, and who takes them.

## Authority

- A release needs the owner's current authorization naming the version. Agents prepare it: they bump the version, update the guides, run the gates, build the artifacts locally and draft the release notes.
- Tags belong to the owner (hard rule 1). An agent never creates, moves or deletes a tag.
- The owner publishes the GitHub release. An agent runs `gh release create`, uploads an asset or publishes a draft only under an explicit, current instruction naming the version and the artifacts.
- No release goes to a package index. Nothing in this policy authorizes publishing the Windows bundle anywhere.

## Version

- One version string, changed in one commit whose subject ends `; version X.Y.Z`. It appears in:
  - `project/pyproject.toml` and `project/vellric/__init__.py`;
  - the `vellric` entry of `project/uv.lock` (regenerate it with `uv lock`, never by hand);
  - the "current candidate" line of `README.md` and `project/README.md`;
  - `project/docs/INSTALLATION.md` (title, bundle name and `pip install` pin);
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
- Its assets are exactly `vellric-X.Y.Z-py3-none-any.whl` and `vellric-X.Y.Z.tar.gz`, byte-identical to the recorded hashes. It never carries the Windows bundle or any third-party binary.
- The notes follow 0.1.0's order:
  1. What the version provides.
  2. Licensing: AGPL-3.0-only with the retained MIT grants; dependencies install separately under their own licenses; the packages contain no dependency binaries, OCR programs or language data; read NOTICE before redistributing a bundled runtime.
  3. `Qualified source:` the full commit ID, then the gate, CI, install and reproducibility results actually observed.
  4. Known limits, such as the watchdog not being a sandbox.

  State only what was observed.
- After publishing, `gh release view vX.Y.Z` must show the expected tag, target and asset names. The downloaded assets must match the recorded hashes.
- A coordinated consumer release follows the publication order in `RELEASE-PREPARATION.md`. Live consumer changes need their own authorization.

## Windows bundle

- **Build.** Start from the tagged commit, in a full Git checkout with a clean tree. From `project/`, run `python packaging/windows_bundle.py --out dist`. The bundle targets Python 3.13 unless `--python` says otherwise, and the target goes into its name: `vellric-X.Y.Z-windows-x64-py313.zip`. Every dependency comes from `uv.lock` and is checked against its published hash, and the archive's timestamps are fixed, so equal inputs give equal bytes. Only tracked guides and license files go into it. `dist/` is never committed.
- **Record.** The builder prints a SHA-256 for each wheel and for the ZIP. Keep that list, with the version and the commit, in the local release evidence. It is how a bundle in hand is matched to the one the Windows workflow proved.
- **Proof.** On every push, the Windows workflow builds the bundle and installs it with no package index. It then runs `doctor`, `inspect` and `render`, installs the qualified engines, runs the tests with no skips allowed, and converts the fixtures. A trial on the target machine is the owner's acceptance, recorded in `user-actions/`. An agent never claims it.
- **Distribution.** The bundle holds third-party binary wheels without their assembled source and notice closure (`project/docs/LICENSING.md`).
  - The owner's own machines may receive it, and so may colleagues' workspaces inside the owner's organisation (owner ruling, 2026-10-10).
  - It may not be attached to a GitHub release, uploaded as a workflow artifact, placed anywhere public, or given to anyone outside the organisation. That holds until the owner decides otherwise and the closure is assembled.
  - The workflow keeps only measured results. Do not add an upload of the bundle back.

## State as of 2026-10-15

- **0.1.0:** tag `v0.1.0` at `a2b140a4eda87b4e6cb5925ba5e605031890fb31`. GitHub release published on 2026-10-01 with the wheel and source archive. No Windows bundle existed.
- **0.2.0:** tag `v0.2.0` at `1fc89991063d29c91f9c96e83d73307b5989d3c2`; no GitHub release.
  - `project/docs/RELEASE.md` records that 0.2.0 has not been through release preparation.
  - User actions `misty-hyena` and `spotted-seagull` block it.
  - Commits after the tag changed the project while still calling it 0.2.0. On 2026-10-15 those changes became 0.2.1, untagged and unpublished, so 0.2.0 again names only the tagged code.

## Open decisions (owner)

1. Whether 0.2.0 is published from its existing tag, and when 0.2.1 is tagged.
2. Whether a release is recorded in `LOG.md`. No release has been so far.
3. Whether the Windows bundle may be shared outside the owner's organisation (`misty-hyena`).
