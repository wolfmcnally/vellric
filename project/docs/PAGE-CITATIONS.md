# Physical PDF page citations — contract 1.0

Vellric 0.2.4 makes PDF page anchors standard for `inspect`, `convert` and `render`. No option or vision model is needed. Root `document.md` and optional root `structured.md` retain `## Page N` headings, with an empty HTML anchor before each heading. Blank, rotated and repeated pages retain their original one-based physical position. Exact native/recovered per-page text is unchanged. Printed footer numbers and PDF logical labels are not extracted or substituted for physical ordinals.

## Machine contract

The complete bundle schema is `vellric.document/1.1`; status/progress schemas and the PDF processing behavior identity are unchanged. Every PDF manifest requires root `page_citations` equal to `{"schema": "vellric.pdf-page-citations/1.0"}`. Each ordered `pages` record retains `number` and `files.text` and adds `anchor`.

The exact anchor is `vellric-pdf-` + `source.sha256` + `-page-` + original physical `number` formatted as decimal with a minimum width of six and zero padding. The digest is the full 64-character lowercase SHA-256 of admitted original PDF bytes, not extracted text. Ordinals above six digits are not truncated. Example suffixes are `-page-000001` and `-page-1000000`.

There is one source identity (`source.sha256`), one order (`pages[].number`, exactly 1 through `page_count`) and one materialized anchor per page. Do not infer boundaries from headings, form feeds or text resembling markers. Verify source identity, complete status, schema, page sequence and artifact sizes/digests as well as citation mapping. The [JSON schema](document.schema.json) validates structure/patterns; cross-field equality requires independently recomputing anchors. `runtime.validate_bundle` does so without importing a PDF engine.

The schema's anchor pattern is a structural superset of generated forms; exact recomputation also rejects alternate zero padding. A schema-only check does not establish canonical citation identity.

The 1.1 validator rejects old 1.0 bundles and 1.0 `--amend` bases; rerun a complete job from the retained original PDF. There is no legacy-reader branch. Image jobs use the new 1.1 envelope but forbid `page_citations` and per-page `anchor`, because a raster image is not a physical PDF page. Consumers must qualify the new envelope rather than assuming every job is PDF. `doctor --json` reports the envelope.

## Independent consumer reconstruction

After validating the manifest, a consumer reading `pages[].files.text` can preserve identity without importing Vellric. Emit literal `<a id="ANCHOR"></a>` on its own line, replacing `ANCHOR` with that page's validated `anchor`, then a blank line and the physical page heading. Root Markdown uses exactly that markup and separation. Its page-body presentation retains existing trimming, NUL removal and empty-page notice semantics. Do not derive anchors from text or interpolate arbitrary source/model strings into HTML attributes.

Only anchor markup and separation are identical across these assembly routes. Root page bodies may use an accepted transcription's heading-demoted reader Markdown instead of `files.text`; copying per-page final text does not promise byte-identical root bodies. The root `page_citations` object is closed: extending it requires a new citation-contract identifier.

Consumers assembling mirrors from per-page text must explicitly preserve the mapping: verifying root `document.md` as an artifact does not consume its anchors. Normalization, formatting or heading demotion must retain physical-page association. Generate markers at the final page-assembly boundary. Identical input bytes retain their identities across processing changes; PDF revisions/rerenders change them even when extracted text stays equal.

## Renderer and untrusted-content limits

Raw Markdown contains the anchor bytes. Tests exercise markdown-it-py 4.2.0 CommonMark mode with HTML enabled/disabled and Bleach 6.3.0 with default attributes and an explicit `a.id` allowlist. HTML-enabled rendering retains ordinary anchors; HTML-disabled rendering escapes them. Default Bleach removes IDs; explicitly allowing the attribute retains them. These bounded configurations do not qualify GitHub, every viewer or any consumer's production sanitizer.

In that CommonMark configuration the empty anchor is inline HTML inside its own paragraph, rendered as `<p><a id="ANCHOR"></a></p>`. Consumer Markdown grooming or heading-based section splitting can attach an anchor line to the wrong page; preserve page identity from the manifest throughout assembly rather than inferring it from a heading regex. Separate-page rendering/trusted destinations are consumer guidance, not an implemented viewer in Vellric or its downstream Markdown emitter.

Combined reader Markdown is untrusted document presentation, not a sanitizer or authentication channel. Unterminated code fences/raw HTML can hide later anchors; source text can duplicate IDs and preempt generated destinations. Vellric does not rewrite fidelity text or repair arbitrary Markdown to prevent this. Tests retain these limitations. Consumers needing reliable clickable navigation should render/sanitize page bodies separately, then insert trusted destinations from the validated mapping outside each body, with their own duplicate-ID policy. Do not search raw document HTML for authoritative identity.

## Retained PDF and derivatives

Publishing page anchors discloses the original PDF digest and permits matching against candidate PDFs; see the [source-derived artifact privacy note](CLI.md#canonical-native-identities-and-pdf-ranges).

The target is the original input PDF bytes. Preserve them and verify their digest before attaching a consumer-owned URL. A link ending `#page=N` targets the original one-based physical page as described by RFC 8118 section 3; viewer support and URL access need separate qualification. Vellric invents no public URL or absolute file link.

`searchable.pdf`, `subset.pdf` and resaved copies have their own byte identities. Subset page k corresponds to original physical page `pdf_subset.pages[k-1]`; do not confuse the subset ordinal with the source ordinal or claim its bytes match the original digest. For Word ingestion, render once, retain that exact PDF snapshot, pass it unchanged to Vellric, and bind Markdown to its digest/ordinals. Fonts, renderer and input changes can repaginate Word. Rendering/retention are consumer work, not a feature implemented here.
