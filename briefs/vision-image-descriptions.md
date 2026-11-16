---
title: Inline descriptions of PDF images and technical figures
date: 2026-10-29
status: draft
scope: Research evidence and design options for opt-in vision descriptions of PDF figures in Vellric Markdown.
---

This brief recommends a distinct, grounded image-description enrichment path alongside Vellric's existing transcription path. Use rendered figure regions plus bounded page context, and place visibly labeled generated descriptions beside the corresponding figure or caption in the reader Markdown. This is research, not an approved implementation, schema, model selection or capability qualification. Cloud-vision human acceptance remains **OPEN and UNQUALIFIED**.

## 1. Research basis and dates

Research and retrieval occurred on 2026-10-29 UTC, which was still 2026-10-28 in the operator's local timezone. Local architecture observations are as of that UTC research date, on clean Vellric 0.2.3 source `1ff8803f14121499ca4c83d466f53abaed9076d2`. Public primary sources are distinguished below from recommendations and unresolved choices. Live vendor pages are observations of published guidance at retrieval time, not evidence that the installed adapters implement every newly documented feature. Historical papers are not current model rankings.

No model calls, document uploads, dependency installations or product experiments were performed. Ten generic discovery queries were used within the twelve-query primary research budget; subsequent source retrieval used public GET-equivalent browsing. No repository text or private document content was sent to research services.

## 2. What the present implementation actually does

These are source observations, not proposed behavior:

- [`vision.py`](../project/vellric/vision.py) defines page transcription, not figure explanation. Its prompt requires verbatim visible text, includes captions, excludes commentary, and requests empty output for text-free pages. A description of a text-free photograph would conflict with that contract.
- [`worker.py`](../project/vellric/worker.py) renders selected pages to PNG at a bounded effective resolution, calls the named provider/model, and stores accepted page Markdown with provider, model, prompt hash, resolution and cross-check facts. The root `document.md` chooses accepted vision Markdown where nonempty, otherwise independent text. Native and recovered text artifacts remain separately represented. The existing scanner/native distinction affects which final page text may come from vision; descriptions should not silently alter that meaning.
- Optional layout records already retain page coordinate transforms and image-placement metadata through `get_image_info()`. Raw nontext blocks are excluded from the serialized text geometry. There is no implemented figure-region description, semantic figure/caption association, or inline description merge contract.
- [`cli.py`](../project/vellric/cli.py) requires explicit provider/model selection for hosted vision, and `--local-only` rejects **every** vision provider, including the external-command route. A future description option cannot reinterpret that flag as permission for a local vision model. The existing explicit fallback setting is not permission to choose an implicit replacement model.
- [`pdf_tools.py`](../project/vellric/pdf_tools.py) serializes PyMuPDF calls through `PDF_LOCK`. Page rendering, coordinate transforms, resource supervision and publication checks are existing integration boundaries to preserve.

The pinned PyMuPDF dependency is 1.28.2. Static inspection of its installed source confirmed `get_image_info`, clipped `get_pixmap`, and `cluster_drawings` are present. That establishes available API definitions, not accuracy on a corpus. No new parser, OCR engine or provider wrapper is justified by this research alone.

## 3. Evidence that changes the design

WAI distinguishes a concise image identifier from a longer explanation for complex visual information. Its examples include textual detail and structured data rather than hiding an entire explanation in one alternative-text string. The [local excerpt](../docs/w3c-complex-images-excerpt.txt) preserves one relevant statement; the full tutorial is [S1]. This supports a short figure label followed by readable inline prose, lists or a table where warranted. It does not establish that generated text is accessible or correct.

PyMuPDF distinguishes referenced image resources from displayed image occurrences; an occurrence need not have a usable PDF xref. Its rendering and vector APIs provide additional evidence about visible appearance [S2]. The installed 1.28.2 definitions corroborate availability of the particular APIs considered here. Resource extraction alone therefore cannot define the feature's coverage.

W3C's tagged-PDF technique explains that logical order is principally structural and illustrates multi-column failures; it also warns that complex layouts can acquire incorrect order [S3]. Neither coordinate sorting nor the mere presence of tags is a sufficient correctness witness for inline placement.

Current provider guidance describes resizing and limitations around small text, spatial localization, counting and chart interpretation [S4, S5]. The specific model, endpoint and adapter determine usable detail and limits; accepting an image payload does not qualify detailed technical descriptions. No model is selected here.

CharXiv separates chart-element description from reasoning on realistic scientific charts [S8]. SciCap studies scientific figure captions, a narrower/different output objective than complete technical description [S9]. OmniDocBench provides document-level and task-level evaluation with layout and reading-order concerns [S10]. These are useful evaluation precedents, not demonstrations of this proposed capability or of current models' quality.

## 4. Vision-capability gating

Recommendation: require an explicit description opt-in as well as the existing authorized vision provider/model route. Determine image-input support from the exact provider/model's documented capability contract and a later permitted qualification, not a model-name substring or the provider's brand. An OpenAI-compatible URL or command transport is not itself proof of vision capability. Describe unsupported, unqualified and operationally failed outcomes separately.

Capability checking should precede sending document pixels; preserve destination validation, credential handling and the existing local-only refusal before worker execution. Do not probe a hosted endpoint with document content merely to discover capability. An eventual synthetic capability probe would itself need authorized model use and budget. Keep description policy in the leaf-owned configuration rather than introducing another wrapper configuration system.

## 5. Embedded resources versus displayed figures

Recommended conceptual unit: a **figure occurrence**, identified by source identity, page and displayed region, with its coordinate transform. It is not simply an embedded image stream or xref.

| Input case | Useful evidence | Recommended treatment and limitation |
| --- | --- | --- |
| Standalone raster image | Displayed bounds, transform, resource identity | Use appearance-preserving crop; retain the resource only when export is requested and safe. |
| Vector chart or schematic | Drawing clusters, surrounding labels and caption | Render the grouped region. A drawing cluster is a proposal, not a semantic figure detector; tables and borders can also cluster. |
| Composite or multi-panel figure | Multiple objects, panel labels, shared legend | Group the full figure before describing panel-specific details; avoid separating an arrow from its destination or a plot from its legend. |
| Scanned page | Whole-page raster and local OCR/layout | Detect candidate regions in the visible page; treating the entire scan as one embedded figure misses its internal structure. |
| Reused logo, masked image or clipped placement | Resource identity plus each placement's visible appearance | Reuse asset storage where appropriate, but retain occurrence-specific context. Hash equality alone does not establish identical visible content or meaning. |

A bounded two-view approach is worth evaluating: one overview to associate regions and captions, plus higher-detail rendered crops for figure content. The overview may be reused within a page budget. Send only the context needed to disambiguate the region. Crops alone lose context; whole pages alone shrink dense labels and expose unrelated text. Rendering the actual visible appearance is preferable to exposing hidden or masked resource pixels. This is a recommendation, not a claim that crops always improve quality.

Existing render-size, raster-memory, disk, deadline and cancellation controls should cover additional images and attempts. Preserve rotation/crop-box transforms so model observations refer back to the original page. Native PDF operations remain within existing locking/process boundaries. Do not add unbounded whole-document image enumeration or autonomous zoom loops.

## 6. Technical fidelity and hallucination controls

Recommended content rubric, tailored to the visible figure:

- Start with figure type, subject and a concise overview. Add technical detail that contributes information rather than adjectives.
- For charts, preserve readable axes, units, scale type, legend mapping, series distinctions, error indicators and salient relationships. Distinguish a printed value from a visually estimated trend. Do not invent exact measurements from a plot or a data table from unreadable marks.
- For diagrams, identify visible components and labels, connections, arrow direction, grouping, sequence and relevant notation. Do not infer hidden mechanisms, specifications or causal conclusions merely because the picture resembles a familiar system.
- For multi-panel figures, retain panel labels and distinguish panel-specific observations from the overall explanation. Preserve meaningful color and line-style distinctions in words.
- Mark unreadable labels and uncertain associations specifically. Attribute claims supplied only by a caption as caption statements. Separate direct observation from interpretation; do not present a numeric self-confidence score as calibrated evidence.

Native/OCR labels and existing captions can support checking, but cannot verify all visual meaning. A second model is not independent ground truth. Structured model output could make missing fields and evidence references detectable, but valid JSON would not establish truth. Figure text and surrounding document instructions remain untrusted data; description generation should not execute tools, fetch depicted URLs or obey instructions printed in a figure. Generated Markdown also needs a later rendering/link-safety design.

The current word-agreement check is a proxy for transcription fidelity. A correct description introduces words that are absent from OCR, so combining it with transcription can create false rejection. Worse, copying the caption can score well while describing no visual relationships: the proxy can prefer the less useful result. Recommendation: keep transcription comparison intact and assess descriptions through a separate evidence/fidelity rubric, rather than lowering the transcription threshold to accommodate added prose.

## 7. Inline placement, captions and Markdown

Recommendation: keep generated descriptions visibly distinct from source text and attach them to a stable figure/caption anchor in the reader view. Consider validated source structure when available, then spatial layout, column membership and caption proximity as evidence. The existing layout output does not implement a tagged-PDF structure reader; adding one would be a separate design choice. Never claim that sorting boxes top-to-bottom alone solves reading order.

Prefer placement after the associated caption or figure location within the correct page and column flow. If association is ambiguous, preserve the region as explicitly unplaced within that page with a warning instead of silently inserting it into an unrelated paragraph. A page-end fallback is less inline, but more truthful than a fabricated anchor. Retain source page boundaries and exact-text artifacts.

Keep an original caption once. If it already explains the visual content adequately, suppress redundant generated prose or add only missing visual information. Use a caption reference instead of repeating it wholesale. Deduplication should compare the association and contribution, not merely word overlap. Reused figures with different captions remain separate occurrences.

A portable illustrative presentation is a labeled block such as “Generated image description — Figure 2, page 4”, followed by ordinary paragraphs or lists. If image assets are exported, a short image alternative can accompany that block. Avoid relying only on raw HTML, collapsed details or an extremely long image-alt attribute; actual Markdown renderer and assistive-technology behavior would need testing. This is not a settled output syntax or an accessibility-conformance claim.

## 8. Provenance and uncertainty

Recommendation: retain region identity and bounds, source/crop digests, coordinate transforms, actual input dimensions, context selection, provider and exact model identity, prompt version/hash, attempts/fallbacks, truncation/refusal status and available usage facts. Link the description to the original caption/text spans and rendered region where practical. Do not put secrets or absolute local paths into output provenance.

Distinguish at least: generated, omitted as redundant/decorative, unreadable, unplaced, refused, truncated and operationally failed. An empty reply must not mean that every image on a page was successfully described. Preserve failed attempts and their reason without disguising them as source text. Selection/grouping and placement are uncertain too; uncertainty is not confined to the prose generator.

## 9. Privacy and cost

Provider privacy terms are model-, endpoint- and account-specific. Current Anthropic guidance includes model-specific retention requirements that can preclude ordinary ZDR eligibility; partner-hosted routes have their own arrangements [S6]. OpenAI documents default abuse-monitoring retention and endpoint/image exceptions, including qualifications on stricter retention modes [S7]. No account eligibility, retention configuration or contractual assurance was checked here. Consumer subscription behavior is not an API privacy guarantee.

Recommendation: explicit egress authorization for the actual pixels and context, minimum necessary regions/context, controlled rasterization and metadata handling, private bounded caches, and sanitized operational logs. Full-page context can expose text unrelated to the target image. A crop can still contain private information. Hashing a crop or cache key is not anonymization. Do not change the current all-vision local-only refusal as part of this feature by implication.

Estimate future cost as the sum of each request's image/context input tokens and output tokens at the exact selected model's current rates, including retries and explicit fallbacks. Input resizing/detail costs differ by model [S4, S5]; a lower named detail setting is not universally cheaper. Bound figures per page, request count, total image pixels, output length, concurrency and job spend. A page overview plus many crops may cost more than one page pass. Measure detailed-description usefulness per cost, not output length alone. No paid evaluation was run and no dollar quote or default model is proposed.

## 10. Practical future evaluation approach

This is a proposed study design, not an execution queue or an authorization to call models. Begin with offline layout/placement witnesses and a later separately authorized, budgeted vision study. Use owned synthetic fixtures with known diagram graphs, labels and chart values, then a consented/licensed held-out corpus. Benchmark or article availability does not by itself grant redistribution or model-upload rights to every underlying figure.

Compare page-only, crop-only and crop-plus-bounded-context conditions using the same explicitly selected models/prompts and the same source figures. Include raster/vector/scanned and multi-panel cases; multi-column and rotated pages; repeated resources with different placements; full-page scans; plots with log scales and dashed lines; low-resolution labels; caption-only/decorative pages; text-free figures; mixed languages; and adversarial instructions drawn in images. Keep selection, grouping, caption matching and description quality as separate measured failure stages.

Human reference annotations should name visible facts and critical relationships, not only provide one preferred paragraph. Measure figure coverage/false positives, caption-association precision, ordering errors, unsupported-claim rate, label/unit/numeric fidelity, relationship/arrow accuracy, omission of important facts, appropriate uncertainty, caption redundancy and reading utility. Preserve errors by figure type and severity rather than hiding them in a single average. A reversed arrow or invented value may be disqualifying even when prose overlap is high. Add latency, actual token/cost and failure/truncation rates after authorized calls.

Use CharXiv-style descriptive/reasoning separation [S8], caption-task distinctions from SciCap [S9], and document/layout evaluation ideas from OmniDocBench [S10]. Do not treat BLEU/word overlap, a self-rated confidence field or an LLM judge as the acceptance oracle. Blinded expert review and reader/accessibility testing should assess technical usefulness and placement; separate them from executable fidelity, resource, egress and failure-handling checks. No acceptance thresholds, model winner or capability qualification is established by this research.

## 11. Unresolved choices and limitations

| Choice | Recommendation for consideration | What remains unproved |
| --- | --- | --- |
| Feature scope | Describe meaningful figures, including vector/scanned appearances, rather than only raster streams | Region detection/grouping recall and acceptable decorative-image policy |
| Output surface | Labeled enrichment in reader Markdown, exact text preserved | Final syntax, asset export, schema/version changes and renderer accessibility |
| Model route | Explicit qualified image-capable model on an already authorized route | Actual model capabilities, route/account retention and task-specific accuracy |
| Ambiguous placement | Warning and page-local unplaced fallback | Acceptable tradeoff between inline coverage and false association |
| Detail and cost | Overview plus selective detail, with hard budgets | Measured quality/cost tradeoff and numeric-accuracy tolerances |

The strongest architectural fit is a separate figure-enrichment representation feeding a controlled reader-view merge, not a prompt-only modification of verbatim transcription. Exact configuration/schema choices and any implementation remain unapproved. The current cloud-vision human acceptance is still OPEN/UNQUALIFIED; this document does not extend a historical release exception.

## Sources

All sources below were retrieved 2026-10-29 UTC. External vendor pages were read without sending repository or document content. Apart from the small permissively licensed WAI excerpt, vendor/paper material is URL-cited rather than mirrored: redistribution rights for those page editions were not established in this assignment. A future binding implementation contract would need appropriately licensed, version-matched pins. No paper's arXiv hosting license is assumed to license its underlying figures for arbitrary use.

| ID | Primary source | Evidence date/edition and contribution |
| --- | --- | --- |
| S1 | [W3C WAI: Complex Images](https://www.w3.org/WAI/tutorials/images/complex/), [local excerpt](../docs/w3c-complex-images-excerpt.txt) | As of 2026-04-08, the page's explicit update date; short/long text alternatives. W3C WAI/EOWG; copyright 2026 W3C; [Document License 2023](https://www.w3.org/copyright/document-license-2023/). |
| S2 | [PyMuPDF Page API](https://pymupdf.readthedocs.io/en/latest/page.html) | Undated moving latest documentation, observed at retrieval; image resources/occurrences, rendering and drawing APIs. Specific candidate methods independently found by static inspection of installed 1.28.2 source; no future/latest-version equivalence assumed. |
| S3 | [W3C WCAG 2.2 Technique PDF3](https://www.w3.org/WAI/WCAG22/Techniques/pdf/PDF3) | WCAG 2.2 technique, page revision date not established; tagged-PDF order and complex-layout caveats. Technique guidance, not a claim of conformance. |
| S4 | [Anthropic: Vision](https://platform.claude.com/docs/en/build-with-claude/vision) | Undated live documentation observed at retrieval; model-dependent image handling, resizing, costs and interpretation limitations. |
| S5 | [OpenAI: Images and vision](https://developers.openai.com/api/docs/guides/images-vision) | Undated live documentation observed at retrieval; supported image input and detail/cost/accuracy caveats. No new wire options presumed supported by Vellric's existing Chat Completions adapter. |
| S6 | [Anthropic: API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention) | Undated live documentation observed at retrieval; model-specific retention and feature/route eligibility. No account configuration verified. |
| S7 | [OpenAI: Data controls](https://developers.openai.com/api/docs/guides/your-data) | Undated live documentation observed at retrieval; endpoint retention and image exceptions. No account eligibility verified. |
| S8 | [Wang et al., CharXiv](https://arxiv.org/abs/2406.18521) | As of 2024-06-26 submission; realistic chart diversity and descriptive versus reasoning evaluation. Historical benchmark evidence, not current-model ranking. |
| S9 | [Hsu, Giles and Huang, SciCap](https://aclanthology.org/2021.findings-emnlp.277/) | As of 2021-11 publication; scientific figure-caption task and dataset distinctions. No image-rights or current-quality guarantee inferred. |
| S10 | [Ouyang et al., OmniDocBench v2](https://arxiv.org/html/2412.07626v2) | As of 2025-03-25 revision; diverse document parsing, layout and reading-order evaluation. Source content held by authors; no local redistribution pin. |
