---
title: Optional PDF page citation markers in Markdown
date: 2026-10-29
status: historical
scope: Current capability and a minimal opt-in citation-marker proposal preserving Vellric's default Markdown output.
---

Historical as of 2026-11-16: Vellric 0.2.4 made physical PDF page citation anchors standard output instead of the opt-in markers proposed here; see `project/docs/PAGE-CITATIONS.md`. This brief is kept as the research record.

Vellric already emits physical PDF page headings. The useful addition to investigate is an explicit, optional citation-marker contract, rather than a new page-counting subsystem. Recommend keeping default Markdown byte-for-byte unchanged and adding deterministic citation anchors only when requested. This is research and a proposal, not implementation approval or a qualified capability. The separate [image-description research](vision-image-descriptions.md) remains unchanged; cloud-vision human acceptance remains OPEN and UNQUALIFIED, and page markers require no vision model.

## 1. Evidence and scope

As of 2026-10-29, source observation began at 02:57:00 UTC on Vellric commit `1ff8803f14121499ca4c83d466f53abaed9076d2`, version 0.2.3. Research occurred on that UTC date, still 2026-10-28 locally. The current working tree additionally contains attributed, uncommitted research documentation; product source is unchanged. No conversions, model calls, installations, configuration changes or other repository inspection were performed for this proposal.

The operator requested investigation of optional page numbers for citable Markdown, including a proposed downstream Word-ingestion mode retaining both its rendered PDF and Markdown. The present finding changes the premise: visible physical page headings already exist. Treat the requested option as control over additional citation metadata, with existing defaults preserved. Whether the operator instead wants the existing headings suppressible is an unresolved product interpretation, not a reason to silently remove them.

## 2. Current capability

| Concern | Source observation |
|---|---|
| Default reader Markdown | [`worker.py`](../project/vellric/worker.py), lines 37–46, always emits `## Page N` with one-based physical ordinals, even for empty pages. Lines 765–778 apply it to `document.md` and optional `structured.md`, including accepted vision reader sections. |
| Option surface | [`cli.py`](../project/vellric/cli.py), lines 107–164, has no Markdown page-marker switch. `--structure` defaults to `none` (line 113); it is not a page-number switch. `--pages` is a render-only selection option (lines 164–166). |
| Ordinal versus index | [`pdf_tools.py`](../project/vellric/pdf_tools.py), lines 286–291, maps physical ordinal N to engine index N−1. Neither is a printed page label. |
| Boundaries and identifiers | [`worker.py`](../project/vellric/worker.py), lines 643–671, creates `pages/000001/` and an ordered `number` field. [`runtime.py`](../project/vellric/runtime.py), lines 362–374, validates the full one-through-count sequence. Paths identify positions within a particular PDF, not persistent semantic pages across revised PDFs. |
| Provenance | [`document.schema.json`](../project/docs/document.schema.json), lines 37–73, declares source SHA-256/size, page count and page numbers. Worker lines 818–862 record artifact digests, source identity and page records. There is no explicit Markdown anchor, page ID or logical-label field. |
| Exact text | [`CLI.md`](../project/docs/CLI.md), section on output artifacts, identifies per-page files as authoritative boundaries. `document.txt` joins page text with form feeds; literal form feeds inside a page make splitting that text an unsafe boundary parser. Reader Markdown trims text and adds presentation; it is not the fidelity artifact. |
| Downstream contract | [`INTEGRATION.md`](../project/docs/INTEGRATION.md), line 9, directs consumers to validate complete jobs/source/files/page sequence and assemble their mirror from per-page final text. This contract does not prove current Drawbridge preserves Vellric's root Markdown headings. Its implementation and proposed Word/PDF retention have not been checked here. |

No typed mapping of PDF logical page labels or visually printed page numbers was found in current product source. A footer number may be recovered as ordinary text without becoming a recognized page label. A viewer's automatically generated heading slug is not an explicit Vellric anchor guarantee; arbitrary source headings can also resemble `Page N`.

## 3. Minimal proposed option

Recommendation: investigate a convert option tentatively spelled `--page-markers citation`, defaulting to `none`. Here `none` means no *additional citation markers*, not removal of today's `## Page N` headings. The spelling and this potentially confusing distinction need product/API review before implementation; it may be clearer to name the option `--page-citations`.

In the proposed citation mode, retain the current page heading once and precede it with a generated anchor such as `<a id="vellric-pdf-SHA256-page-000001"></a>`, where `SHA256` is replaced by the complete validated lowercase PDF digest, not a prefix. Use the original physical ordinal, never a renumbered selection index. The anchor's format is a proposed contract, not existing syntax. Digest plus ordinal identifies a page position in immutable PDF bytes; it deliberately changes when those bytes change. It is not a semantic identifier surviving editing, reflow or re-rendering.

Apply the option consistently to reader `document.md` and, when produced, root `structured.md`. Preserve exact per-page native/recovered text, searchable PDF, layout coordinates, transcription prompts and source document bytes. Keep model-generated text from inventing or controlling the outer marker. Do not infer boundaries by parsing headings, arbitrary Markdown fences or form feeds. Reuse the worker's ordered page records as the boundary authority.

An explicit anchor is a small candidate design, not a universal Markdown interoperability promise. HTML-disabled renderers may discard it; sanitizers may rename or remove IDs; source HTML could collide with generated IDs. Before selecting it, qualify the actual downstream renderer and handling of untrusted Markdown. Do not mutate recovered source text merely to enforce uniqueness. If safe rendered-anchor behavior cannot be established, retain visible physical-page headings and expose citation mapping as structured metadata, rather than claiming clickable anchors work everywhere. A marker comment alone would be invisible in many rendered views and is insufficient as the only human citation cue.

Record the selected mode and exact marker mapping with the ordinary complete-job metadata. Review schema strictness, behavior/version identifiers and installed consumers before choosing additive fields versus a new schema/behavior version; there is no approved schema change here. Prefer one owner for formatting, shared by root Markdown and consumer assembly, over a second numbering system. A downstream consumer using per-page text must explicitly preserve/reconstruct the same mapping; a root-output-only option cannot automatically change that consumer.

## 4. Physical ordinals, logical labels and links

Physical ordinal is the minimum useful and deterministic citation target: PDF page 1 includes any cover, and page 2 means the second physical page. A zero-based index is an internal programming coordinate, not the displayed citation. A PDF logical label such as `iv` or `A-3` is separate document metadata, and a number visibly printed on a page is a third fact. They can disagree, repeat or be absent.

Recommend physical ordinals only for the minimal option. A future label feature should preserve the physical target and expose a nullable, explicitly attributed label alongside it, never silently replace the ordinal or guess labels with a model. PyMuPDF's documented label API is a potential existing dependency capability to investigate, not evidence of an implemented Vellric label feature or a tested mapping to printed text. OCR footer inference is broader work and is not recommended for this minimal addition.

[RFC 8118 section 3](../docs/rfc8118-page-fragment-excerpt.txt) describes `page=` as a one-based physical PDF target. Thus a consumer-owned PDF link ending `#page=2` can accompany a citation when that consumer has an accessible retained PDF URI. Actual viewer support still requires testing. Vellric should not invent public URLs, emit local absolute paths or assume a private filesystem path is accessible to readers. Plain Markdown can retain a visible `PDF page 2` cue even where clickable links are unavailable.

## 5. Proposed Word/PDF consumer handoff

The downstream owner would render Word once, preserve those exact PDF bytes, pass that same snapshot to Vellric, verify the returned source digest and ordered page count, and retain a relationship between the Word input, rendered PDF and Markdown. Cite the PDF snapshot's physical pagination, not Word's mutable editor pagination. Re-rendering after changes creates a new PDF identity and requires a fresh mapping. Font, layout and renderer changes may repaginate Word even when its visible prose seems unchanged.

The proposed downstream option would determine whether to retain/present the rendered PDF and citation-enabled Markdown together. It must specify whether it consumes Vellric's root Markdown or assembles a mirror from per-page text, and how it preserves generated anchors across normalization. These are handoff questions for Drawbridge's owner; no claim is made about current implementation. The PDF's availability, access controls, relative-link base and retention lifetime remain the consumer's responsibility. Do not add a second PDF rendering pass solely for citations.

## 6. Future falsifying tests

- Verify omitted option and explicit default produce the exact existing default Markdown bytes and filenames for representative jobs. Keep today's headings and empty-page notice. Native/OCR/accepted-vision paths should retain identical text/fidelity artifacts and require no new provider calls for markers.
- Test one-page, blank, scanned, rotated, cropped and multi-page PDFs; covers, Roman labels, duplicated labels, missing labels and visible numbers disagreeing with logical labels. Confirm original physical order, exact source digest and stable anchors for repeated runs on identical bytes.
- Test document text containing `## Page 1`, form feeds, fenced code, raw HTML, marker-looking text and duplicate IDs. Verify source content cannot create false page boundaries or silently redirect a citation; qualify actual renderer/sanitizer behavior rather than assuming HTML syntax is enough.
- Test repagination and two PDFs with identical page text but different bytes. Their citation identities must differ; concatenated documents must not cross-link pages. Verify no source digest is shortened into an undocumented collision risk.
- Test the installed CLI option/default/error contract, metadata/schema validation, root structured output consistency and any consumer that reconstructs Markdown. Test failed/cancelled jobs preserve existing no-success/no-partial-publication semantics.
- In an authorized downstream synthetic Word integration, preserve the exact rendered PDF, verify its digest, match Markdown pages to that PDF, and open representative PDF-page and Markdown-anchor links in the supported viewer. Verify absent/inaccessible PDF handling is explicit. No such test was run during this research.

## 7. Remaining choices and limits

The principal choice is whether the requested optional behavior means additional citation anchors, links to a retained PDF, or control over the existing visible headings. Recommendation: additional citations with default bytes unchanged, physical numbering first, no inferred printed labels. Exact option name, renderer-safe marker syntax, metadata/version contract and downstream link ownership need one bounded design decision before coding. No broad pagination engine, provider change or model evaluation is necessary.

Research does not qualify clickable interoperability or confirm downstream consumption. Source inspection and documentation checks establish the current behavior and proposal only. Existing image-description research is complementary: future figure descriptions should remain inside the correct physical-page section and should not generate or redefine its citation identity.

## Sources and freshness

- Local source links above: as of Vellric 0.2.3 commit `1ff8803f14121499ca4c83d466f53abaed9076d2`; inspected 2026-10-29 UTC. Line numbers refer to that source snapshot.
- [RFC 8118, section 3](https://www.rfc-editor.org/rfc/rfc8118.html#section-3): as of March 2017; retrieved 2026-10-29 UTC. The bounded verbatim [local excerpt](../docs/rfc8118-page-fragment-excerpt.txt) supports the physical-page link recommendation. RFC 8118 is informational and defers disagreements to ISO 32000-2; this research does not claim complete PDF conformance.
- [PyMuPDF Page API](https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_label): retrieved 2026-10-29 UTC, undated moving documentation; exploratory reference for a separately deferred logical-label investigation, not a version-qualified implementation dependency.
- [GFM specification](https://github.github.com/gfm/#raw-html): edition 0.29-gfm, 2019-04-06; retrieved 2026-10-29 UTC. Exploratory renderer reference only; no universal anchor/sanitizer contract is inferred from Markdown syntax. An implementation must pin and qualify its actual receiving renderer.

Only public known-source GET retrieval was used; no new discovery searches, repository uploads or external document/model evaluations were performed.
