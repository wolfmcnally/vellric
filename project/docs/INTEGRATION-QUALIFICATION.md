# Extraction integration qualification

Vellric is AGPL-3.0-only and Drawbridge is MIT. Drawbridge uses an independently installed complete-job CLI; its plain runtime contains no PyMuPDF, fitz or Vellric module. Existing mirror, native-formatting and word assertions remain unchanged.

The preserved public PDF fixtures exercise 27 pages of native text, OCR selection and image coverage. Synthetic native-report, mixed rotated/stale OCR and five-band scroll cases exercise exact expected visible text and source custody. Installed macOS/Linux arm64 jobs match these goldens. All 59 scroll lines are retained. Image samples preserve text while confidence values and upright-column rotation metadata change as documented.

An independent source review produced nineteen findings; all high/medium findings were corrected and every disposition recorded privately. No independent re-review is claimed. Private review payloads, development logs and original Git histories are excluded from public source. Public test proofs and license provenance are retained. These previous implementation results do not substitute for the sanitized public candidate's own full gate.

Run `./bin/check all` at the Vellric repository root. In Drawbridge, configure a separately installed Vellric executable and run `uv run --locked pytest -q`. Release artifacts must be rebuilt from the final fresh public commit and qualified through isolated installs. Unchanged proven text has no blanket human readability hold. Additional architectures/languages, production sizing, hard containment and live consumer migrations remain separate qualification.
