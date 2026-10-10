# Self-contained Vellric examples

Run these in the fresh environment from [installation](INSTALLATION.md). No sibling checkout or private input is required. Generate a small synthetic PDF using the already-installed native engine:

```bash
.venv/bin/python - <<'PYDEMO'
import pymupdf
with pymupdf.open() as document:
    page = document.new_page(width=300, height=400)
    page.insert_text((30, 60), "Exact native example.")
    document.save("example.pdf")
PYDEMO
.venv/bin/vellric inspect example.pdf --out example-inspected --status-json
.venv/bin/vellric convert example.pdf --ocr never --structure native --out example-converted --status-json
.venv/bin/vellric render example.pdf --pages 1 --dpi 150 --out example-rendered --status-json
```

Each output directory must be absent. Check example-converted/pages/000001/native.txt for the exact native text, example-converted/document.md for the reader and manifest.json for source identity and completeness. The example is executed against fresh release packages; machine evidence owns that result.

For a scan, use a local image-only PDF and the full-OCR setup:

```bash
.venv/bin/vellric convert scan.pdf --jobs 2 --diagnostics --out scan-result --status-json
```

Diagnostics contain document text. Keep them private. The optional public/synthetic review bundle demonstrates native typography, rotated scans with stale OCR, a five-band scroll and image comparisons; its original PDFs and visible-text expectations are provided with the local qualification evidence. No private corpus is used.

To read scans and mathematics with a vision-capable model, name a provider and a model; the key comes from the environment. To re-read two pages of that result later without redoing the rest, amend it into a new directory:

```bash
.venv/bin/vellric convert scan.pdf --vision-provider anthropic --vision-model MODEL --out scan-vision --status-json
```

```bash
.venv/bin/vellric convert scan.pdf --amend scan-vision --vision-provider anthropic --vision-model MODEL --vision-pages 3,7 --out scan-vision-2 --status-json
```

The same pass through Amazon Bedrock takes a Bedrock API key from `AWS_BEARER_TOKEN_BEDROCK`, a region and a model ID, and may name a second model for pages the first fails:

```bash
.venv/bin/vellric convert scan.pdf --vision-provider bedrock --vision-region us-east-2 --vision-model MODEL --vision-fallback-model OTHER --out scan-bedrock --status-json
```

Page images are sent to the provider. See the vision pass in [CLI](CLI.md) for local endpoints, an external program, the cross-check figures and limits.

For an encrypted PDF, provide a password file or stdin through the documented options, never a command-line password value. Blocked status can include partial inspection facts; no incomplete bundle is published. See [CLI](CLI.md) and [troubleshooting](TROUBLESHOOTING.md).
