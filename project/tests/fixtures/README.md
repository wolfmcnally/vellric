# Vellric test fixtures

Standard input documents for Vellric's tests. Each row records what the file is, where it came from and why it is kept.

| File | SHA-256 | What it is | Source and terms | Why it is here |
|---|---|---|---|---|
| `Fake_Doc_watermarked.pdf` | `d594e0faa8e3d8ba6f206a082bd93dc6032244779263c24afd6af4672da24736` | Four letter-size pages from the Google Docs PDF renderer. Each page is one flattened page image with no usable text layer, under a translucent diagonal vector watermark. Page 1 is tilted about one degree and carries vertical margin text; page 4 is scaled down. | Pages 1 to 4 of the 53-page arXiv:2209.03310v1 (Kifer et al., 7 September 2022); the identifier is printed in the page-1 margin, so the excerpt names its own source. arXiv distributes the paper under its non-exclusive distribution license. The owner ruled on 2026-10-07 that this partial excerpt is used here under fair use. Added 2026-10-07. | The standard example of a flattened, watermarked PDF. The goal is high-quality ingest of documents like it. |

Verify with `shasum -a 256 tests/fixtures/*.pdf` from `project/`.

## Measured baseline

As of 2026-10-07, Vellric 0.1.0 with `convert --ocr auto` (PyMuPDF 1.28.2, Tesseract 5.5.2, OCRmyPDF 17.7.0) on `Fake_Doc_watermarked.pdf`:

- Recovers 95.8% of the original paper's words on these four pages (2702 of 2821), measured against the native text of the arXiv original. The same page images without the watermark score 96.5%, so the watermark costs under one point.
- Emits no watermark text, and reports all four pages as recognized.
- Most remaining differences are mathematical symbols, superscript affiliation marks and bullets, which Tesseract's English model does not read.
- Reports pages 1 and 4 as rotated 90 degrees although every page is upright: the four-rotation scores for 0 and 90 degrees differ by under 1.5%. The recovered text is unaffected.
- Output is unstructured recognized lines: no headings, joined paragraphs, links or emphasis, and the page numbers are dropped.
