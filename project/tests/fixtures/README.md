# Vellric test fixtures

Standard input documents for Vellric's tests. Each row records what the file is, where it came from and why it is kept.

| File | SHA-256 | What it is | Source and terms | Why it is here |
|---|---|---|---|---|
| `Fake_Doc_watermarked.pdf` | `d594e0faa8e3d8ba6f206a082bd93dc6032244779263c24afd6af4672da24736` | Four letter-size pages from the Google Docs PDF renderer. Each page is one flattened page image with no usable text layer, under a translucent diagonal vector watermark. Page 1 is tilted about one degree and carries vertical margin text; page 4 is scaled down. | Pages 1 to 4 of the 53-page arXiv:2209.03310v1 (Kifer et al., 7 September 2022); the identifier is printed in the page-1 margin, so the excerpt names its own source. arXiv distributes the paper under its non-exclusive distribution license. The owner ruled on 2026-10-07 that this partial excerpt is used here under fair use. Added 2026-10-07. | The standard example of a flattened, watermarked PDF. The goal is high-quality ingest of documents like it. |
| `Fake_Math_Doc_watermarked.pdf` | `6cb672ca9667f0849368fdc14aaf540b31d266c20383760d74974ff3c610b430` | Four letter-size pages built with PyMuPDF. Each page is one page image rasterised at 110 DPI with no text layer, under a translucent diagonal watermark drawn as vector outlines at 30% opacity. Page 1 is tilted one degree and carries vertical margin text; page 4 is scaled to 80%. The pages are dense with inline and displayed mathematics: nested subscripts and superscripts, accents, integrals, sums and multi-line displays. | Pages 1, 3, 7 and 8 of the 11-page arXiv:2610.08383v1, "Random walk in a null recurrent birth-and-death dynamical environment" by Luiz Renato Fontes and Pablo A. Gomes (6 October 2026), https://arxiv.org/abs/2610.08383v1, licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: excerpted, rasterised, re-laid out and watermarked. Retrieved and built 2026-10-07. | A math-dense flattened, watermarked PDF published after the training cutoff of the models tried on it, so a model cannot be reciting it. The authors' TeX source on arXiv is the reference for scoring formulas. |

Verify with `shasum -a 256 tests/fixtures/*.pdf` from `project/`.

## Measured baseline

As of 2026-10-07, Vellric 0.1.0 with `convert --ocr auto` (PyMuPDF 1.28.2, Tesseract 5.5.2, OCRmyPDF 17.7.0).

On `Fake_Doc_watermarked.pdf`:

- Recovers 95.8% of the original paper's words on these four pages (2702 of 2821), measured against the native text of the arXiv original. The same page images without the watermark score 96.5%, so the watermark costs under one point.
- Emits no watermark text, and reports all four pages as recognized.
- Most remaining differences are mathematical symbols, superscript affiliation marks and bullets, which Tesseract's English model does not read.
- Reports pages 1 and 4 as rotated 90 degrees although every page is upright: the four-rotation scores for 0 and 90 degrees differ by under 1.5%. The recovered text is unaffected.
- Output is unstructured recognized lines: no headings, joined paragraphs, links or emphasis, and the page numbers are dropped.

On `Fake_Math_Doc_watermarked.pdf`, measured against the authors' TeX source:

- Recovers 98.6% of the words outside mathematics (982 of 996).
- Recovers none of the 250 Greek letters and operator symbols, and no formula: displayed formulas come out as scrambled fragments of look-alike characters.
- Emits no watermark text, and reports all four pages as recognized.

## Vision-model trial

As of 2026-10-07, a vision language model (Claude Opus 5.5) was given only cropped page renders of each fixture, about 1560 pixels on the long side, and asked for verbatim Markdown with LaTeX mathematics. It had no access to the originals. A second run was also given Tesseract's text as a draft.

- `Fake_Doc_watermarked.pdf`: 99.2% of the original's words and all 48 mathematical symbols, against Tesseract's 96.4% and 12 under the same scorer. Every remaining difference was a defect in the reference text, not a misreading.
- `Fake_Math_Doc_watermarked.pdf`: every word outside mathematics, all 250 Greek letters and operator symbols, and all 20 displayed formulas token-for-token after macro expansion and removal of spacing and sizing commands (2682 mathematical tokens). It kept the authors' own slips verbatim.
- The Tesseract draft changed nothing: the two runs differed only in spacing and delimiter sizing.
- Run through the shipped pipeline (`convert --vision-provider command` with a program that asks the same model), the second fixture converted in 48 seconds at `--jobs 4` with the same result, and Tesseract confirmed 96 to 99.6% of the model's prose words per page.
- Where Tesseract and the model agreed on a word of the first fixture, the word was right; all of Tesseract's errors lay in the roughly 3% of words where they disagreed. Agreement is therefore a usable quality signal without a reference for prose. It says nothing about mathematics, which Tesseract cannot read.

These are two documents of clean typeset English, eight pages in all. Tables, figures, handwriting and poor scans are untested.
