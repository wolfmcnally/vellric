# `docs/` — Third-Party Documentation

This directory holds externally authored reference material the project depends on — vendor documentation, specifications, RFCs, API references, standards text, license texts — pinned locally so that briefs and policies can cite exact wording and every role can read the cited authority without leaving the repository.

Nothing here is written by the project about the project. A file under `docs/` is verbatim third-party text (or a verbatim excerpt) and never links to anything else in this repository; commentary on a pinned document is a brief, and a rule derived from one is a policy. The full contract — what belongs here, naming, licensing, the citation direction, and what `bin/check-catalogs` enforces — is [`policies/docs.md`](../policies/docs.md).

## Catalog

Every top-level entry in this directory has one row here. `As of` is the date or version the source itself carries; `Retrieved` is when the project fetched it. `Basis` names the license or terms under which the material is redistributed here. `Pinned for` names the brief, policy, or plan concern that depends on it and says whether the pin is an excerpt.

| Document | Source | As of | Retrieved | Basis | Pinned for |
|---|---|---|---|---|---|
| [RFC 8118 page fragment excerpt](rfc8118-page-fragment-excerpt.txt) | https://www.rfc-editor.org/rfc/rfc8118.html#section-3 | March 2017 | 2026-10-29 UTC | Bounded quotation of a public IETF standard for research commentary; RFC copyright IETF Trust and identified authors, 2017; not a whole-document redistribution license | Verbatim page parameter clause, whitespace normalized from HTML; physical PDF citation research. |
| [WAI complex images excerpt](w3c-complex-images-excerpt.txt) | https://www.w3.org/WAI/tutorials/images/complex/ | 2026-04-08 (tutorial update; copyright 2026) | 2026-10-29 UTC | W3C Document License 2023, linked in the excerpt; original copyright retained | Verbatim clause from the first paragraph of Example 1, with source/license URLs and copyright attribution; figure-description research. Tutorial guidance, not a conformance claim. |
