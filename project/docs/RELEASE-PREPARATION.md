# Prepared standalone release route

The local candidates are Vellric 0.1.0 (AGPL-3.0-only) and Drawbridge 0.1.0 (MIT). The owner selected Drawbridge 0.1.0 for its first public release; the public repository starts a fresh history; private development history remains separately retained. This preparation publishes nothing and changes no live consumer. The release route publishes each project wheel with its matching source archive, lock, build constraints and notices. Engines and Python dependencies install independently. The Vellric wheel contains Python source/docs/notices and no PDF-engine/OCR/codec/data binaries. There is no theoretical license-choice hold.

## Source and notices

Vellric source includes uv.lock, .python-version, exact six-package build-constraints.txt, all runtime source, tests, docs, NOTICE, full AGPL text and retained Drawbridge/Starter MIT grants. Hatchling is pinned to 1.32.4. The qualified dependency inventory is dependencies-qualified.json. The companion local evidence retains actual installed notices, exact source archives for all 34 distinct runtime dependency releases across both environments, six build-tool source archives, source URLs/hashes and qualified native/data identities. Upstream Python sdists are not asserted to contain every bundled native library's matching build source.

Those dependencies are not redistributed in the project wheel/source release route. A separately proposed wheelhouse/container would be a different artifact: its exact native build/source/license closure would need assembly before shipping it. This does not block the prepared standalone project artifacts. Drawbridge's source fixtures retain their explicit CC-BY-SA-4.0/IETF grants and full notices separately from its MIT runtime; fixtures are public and unmodified. Original attribution remains in tests/fixtures/MANIFEST.md.

## Reproducible build and locked installation

From extracted Vellric source, with Python 3.12 and uv available:

```bash
uv lock --check
SOURCE_DATE_EPOCH=1609459200 uv build . --python 3.12 --build-constraints build-constraints.txt --out-dir dist
uv export --locked --no-dev --extra ocr --no-emit-project --format requirements-txt --output-file requirements-ocr.txt
uv venv --python 3.12 /absolute/isolated/vellric-env
uv pip install --python /absolute/isolated/vellric-env/bin/python --require-hashes -r requirements-ocr.txt
uv pip install --python /absolute/isolated/vellric-env/bin/python --no-deps dist/vellric-0.1.0-py3-none-any.whl
/absolute/isolated/vellric-env/bin/vellric doctor --json
```

Use the same fixed SOURCE_DATE_EPOCH for both builds. Omitting `--extra ocr` exports the native closure. The source archive itself can be installed with the matching requirements already present and `--no-deps`; its build is constrained by build-constraints.txt through uv's `--build-constraints` option. Full OCR additionally requires the qualified Tesseract 5.5.2, Ghostscript/preflight prerequisites and explicit actual tessdata directory; doctor validates those identities. Never silently substitute an unqualified engine version.

Drawbridge uses its own uv.lock and build-constraints.txt with the same build/install commands and drawbridge-0.1.0 wheel. Its plain runtime environment contains no PyMuPDF, fitz or Vellric module. Point DRAWBRIDGE_VELLRIC at the trusted separately installed executable. Preserve the inherited behavior identifier drawbridge-0.4.3-pymupdf-1.28.2/v1: it names the qualified processing baseline, independently of package release versions.

The release evidence records repeated wheel/sdist hashes from independent source copies and fresh native/full-OCR/runtime installations against the final full commit IDs. Corresponding source archives, package and privacy inventories, exact-tree gate receipts, doctor results and sample assertions live in the ignored the separately retained local qualification evidence companion bundle. Its final machine receipt owns executed outcomes; these instructions do not predict a gate result.

## Output and privacy review

Preserved public-fixture native bytes, OCR selection and coverage match on 27 pages. Synthetic native typography/word goldens, mixed rotated/stale scan recovery and the 59-line five-band scroll are exact. The image comparison additionally produced identical text for the sideways hearing photograph and two-column page. Image confidence scores differ slightly; the upright columns' rotation metadata is corrected from baseline 90 degrees to 0. The pdf_processor header and package-version metadata are intentional additions. These are recorded metadata differences, not unexplained readability changes. No new text difference in the qualified corpus requires owner judgment; no human perceptual acceptance is claimed or required as a blanket release hold. The concise review viewer presents originals, output and these differences for optional inspection.

The public repositories start with fresh single-root histories. Private development logs, execution traces and operator records are excluded. Audit every file in the exact sanitized trees, including methodology and tooling, before publication; prior private-history screening does not authorize historical disclosure. Project package inventories exclude private evidence, virtual environments and local credentials. Rebuild the artifacts from the final fresh public commits and verify the complete gates and isolated installs. Retain local private histories and records separately; canonical hosting may be recreated only under the owner’s explicit current authorization. Private operation records are never pushed into the fresh repositories.

## Coordinated publication and consumer transition

1. Publish Vellric with the requested fresh public history. Use the exact final tested full Vellric commit from release-receipt.json; verify that commit is reachable from the intended public ref before publishing Drawbridge 0.1.0 or telling consumers to use it. Preserve notices and offer the matching source archive beside the wheel. If any source/version changes, regenerate the artifacts and gates.
2. Publish the corresponding tested Drawbridge commit only after the Vellric ref/artifacts are reachable. Optional audio uses the publicly reachable Quillric source commit c48b76e522f4e677df9184a2e82469ddcdb9cee9 documented in Drawbridge INSTALLATION.md; Quillric 0.1.0 is absent from PyPI at preparation. This does not block the standalone core route. The existing Drawbridge remote is not modified during preparation.
3. With separate live-consumer authorization, install Vellric independently in staging, verify doctor/schema/behavior/engine/data identities and configure DRAWBRIDGE_VELLRIC, CPU capacity and measured input/page/memory/deadline limits. Record both full commits and artifact hashes. Invalidate affected conversion caches explicitly and prove representative native/mixed/blocked/large inputs before changing stores.
4. Existing consumers that own PyMuPDF objects retain their own dependency obligations and the real PDF_LOCK/pdf_locked exports. Migrate their concrete native-object callers separately before removing those dependencies; audit each consumer distribution. The exact local consumer inventory/transition sequence is retained in the release companion evidence. No live installation/store/AWS change follows from these local candidates.
5. Production sizing, additional target architectures/languages and hard host/container containment remain deployment qualification. They do not block the qualified local standalone release route. The process watchdog is not a hostile-document sandbox; forced supervisor termination remains a documented containment limitation.
