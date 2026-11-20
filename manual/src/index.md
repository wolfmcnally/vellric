# Vellric

You have PDFs and you need their text: exactly as the document carries it where the PDF has a text layer, and recovered by OCR where a page is only a scan. Ordinary extractors quietly normalize whitespace, drop pages they cannot read, or leave you guessing which pages were scanned images. Cloud services want the document sent away. When the text feeds search, citation or review, you need to know what was read, how, and what is still missing.

Vellric reads a PDF on your own machine and publishes one complete, inspectable result. Each run owns a single document job. It keeps every page's native text byte for byte, recognizes scanned pages with Tesseract at four rotations, and records which method produced each page and which pages still need recognition. The result appears atomically in a new directory with a manifest that names every artifact by size and SHA-256, or it does not appear at all.

Start with [Get Started](getting_started.md) to install Vellric and convert a first document. [Command Line](command_line.md) summarizes the commands, the result layout and the exit codes.

```admonish note title="Status"
This manual describes Vellric 0.2.6. PDF inspection, conversion, rendering and English OCR are qualified on macOS and Linux arm64 fixtures. The optional vision pass, which sends page images to a model you choose, is off by default; its human acceptance remains open and unqualified. The repository's `project/docs/` directory holds the complete reference for each topic summarized here.
```

Vellric is developed with the [Agentic Coding Starter](https://github.com/wolfmcnally/agentic-coding-starter) methodology: written briefs, binding policies, a phased plan, independent review and executable checks. That methodology is documented in its own manual; this one is about Vellric.
