# Command Line

`vellric --help` and each command's `--help` list every option. This page summarizes what each command is for and what a result contains.

## Commands

| Command | Purpose |
|---|---|
| `inspect` | Traverse every page and report exact native text, page dimensions, raster coverage and which pages would be recognized. `--layout` adds character, font, link, image and table geometry. |
| `convert` | Publish a complete document result: exact per-page text, recognized text for scanned pages, the reader view and, on request, native Markdown structure or a searchable PDF. |
| `render` | Render selected pages to PNG, PNM or JPEG at a chosen resolution, rotation and clip, or produce a page-range PDF subset. |
| `image` | Publish a normalized PNG and fingerprint for one image file. |
| `doctor` | Report installed engines, their hashes and what this machine can enforce. |

`inspect`, `convert` and `render` read one local regular file or bounded standard input. The input is copied and hashed into private storage, and the original is never rewritten. A PDF password comes from `--password-file` or `--password-stdin` and never appears in the result.

## The result

`--out` names a directory that must not exist. Vellric fills a private staging directory beside it, validates it, and renames it into place with an operation that never replaces an existing name. A failed or cancelled job removes its staging directory and publishes nothing.

| Path | Contents |
|---|---|
| `manifest.json` | The `vellric.document/1.1` record: input hash and size, pages, methods, engines, settings and every artifact with its size and SHA-256. |
| `pages/NNNNNN/` | One directory per page with its exact native text and the text used for that page. |
| `document.md` | The reader view, with a standard page anchor before each page heading. |
| `document.txt` | All page texts joined by form feeds. |

Artifact text is the document's own content, kept faithful rather than made safe. A consumer that renders Markdown as HTML must sanitize it.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | A validated, complete result was published. |
| 2 | Usage error. |
| 3 | Blocked by a password or a document with zero pages. |
| 4 | Malformed, unreadable or non-PDF input. |
| 5 | Dependency, OCR, resource, deadline, artifact or internal failure. |

`--status-json` reserves standard output for one terminal status record; progress goes to standard error. A run that is killed may print no record, so treat a missing status as a failure.

## Limits

Defaults bound the input at 512 MiB, the output at 2 GiB, the document at 10000 pages and the job at 3600 seconds, with a 2048 MiB memory watchdog over the whole job process group. The process boundary is not a network or filesystem sandbox: run genuinely hostile PDFs inside a separately reviewed offline container with hard host limits.
