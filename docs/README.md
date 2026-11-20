# `docs/` — Third-Party Documentation

This directory holds externally authored reference material the project depends on — vendor documentation, specifications, RFCs, API references, standards text, license texts — pinned locally so that briefs and policies can cite exact wording and every role can read the cited authority without leaving the repository.

Nothing here is written by the project about the project. A file under `docs/` is verbatim third-party text (or a verbatim excerpt) and never links to anything else in this repository; commentary on a pinned document is a brief, and a rule derived from one is a policy. The full contract — what belongs here, naming, licensing, the citation direction, and what `bin/check-catalogs` enforces — is [`policies/docs.md`](../policies/docs.md).

## Catalog

Every top-level entry in this directory has one row here. `As of` is the date or version the source itself carries; `Retrieved` is when the project fetched it. `Basis` names the license or terms under which the material is redistributed here. `Pinned for` names the brief, policy, or plan concern that depends on it and says whether the pin is an excerpt.

| Document | Source | As of | Retrieved | Basis | Pinned for |
|---|---|---|---|---|---|
| [RFC 8118 page fragment excerpt](rfc8118-page-fragment-excerpt.txt) | https://www.rfc-editor.org/rfc/rfc8118.html#section-3 | March 2017 | 2026-10-29 UTC | Bounded quotation of a public IETF standard for research commentary; RFC copyright IETF Trust and identified authors, 2017; not a whole-document redistribution license | Verbatim page parameter clause, whitespace normalized from HTML; physical PDF citation research. |
| [WAI complex images excerpt](w3c-complex-images-excerpt.txt) | https://www.w3.org/WAI/tutorials/images/complex/ | 2026-04-08 (tutorial update; copyright 2026) | 2026-10-29 UTC | W3C Document License 2023, linked in the excerpt; original copyright retained | Verbatim clause from the first paragraph of Example 1, with source/license URLs and copyright attribution; figure-description research. Tutorial guidance, not a conformance claim. |
| [Diátaxis reader needs](diataxis-reader-needs.txt) | https://diataxis.fr/start-here/ | 2026-10-16 (living-page observation; no publication date) | 2026-10-16 | Minimal attributed quotation for reference; Daniele Procida; upstream CC BY-SA 4.0 | Software-documentation brief; excerpt of the four-kind enumeration. |
| [Docs as Code tools](writethedocs-docs-as-code.txt) | https://www.writethedocs.org/guide/docs-as-code/ | 2026-10-16 (living-page observation; no publication date) | 2026-10-16 | Minimal attributed quotation for reference, Eric Holscher and Write the Docs; broader CC BY-NC-SA material is not mirrored | Software-documentation brief; excerpt of four tool-category names only. |
| [Accessible-writing headings](w3c-accessible-writing.txt) | https://www.w3.org/WAI/tips/writing/ | 2024-07-16 (page's minor-update date) | 2026-10-16 | Minimal attributed quotation of three headings, W3C WAI | Software-documentation brief; headings on structure, links and alternatives. |
| [mdBook 0.4.50 configuration and operation](mdbook-0.4.50/) | https://github.com/rust-lang/mdBook/tree/v0.4.50/guide/src | 0.4.50 | 2026-10-16 | MPL-2.0; upstream license included | Software-documentation brief; full general configuration plus verbatim serve server/open section, locked-dependency/Rust-test sentences and playground runnable option. |
| [admonish 1.19.0 reproducible builds](mdbook-admonish-1.19.0/) | https://github.com/tommilligan/mdbook-admonish/tree/v1.19.0 | 1.19.0 | 2026-10-16 | MIT; upstream copyright/license included | Software-documentation brief; reproducible-build subsection excerpt. |
