# Troubleshooting

Start with `vellric doctor --json`, then preserve the terminal `--status-json` result for the failed job. Require both exit zero and terminal complete status; missing status or output is failure. Do not infer completion from a directory name.

| Symptom | Action |
| --- | --- |
| Output destination already exists | Choose a new absent directory; Vellric never overwrites a completed result. |
| Missing or wrong OCR engine | Install the pinned Python extra and qualified Tesseract/system tools; compare doctor versions. Native-only `--ocr never` remains available. |
| Missing traineddata | Point `--tessdata-dir` at actual requested language packs; include osd when preflight rotates. |
| Password-protected / zero pages | These are typed blocked inputs. Supply a valid password through file/stdin if appropriate; blind retry does not fix an empty PDF. |
| Deadline / memory / raster budget | Inspect the typed code/stage, adjust explicit limits only for a measured workload, or use bounded strips. Do not treat a resource refusal as bad OCR text. |
| Source hash mismatch | Reacquire the intended immutable input and expected hash; never accept a later source for an earlier mirror. |
| Native bundle has outstanding candidates | Install OCR and convert, or keep the truthful native-only result. A caller requiring recognition must refuse it. |
| Unsupported publication platform | Use a qualified macOS/Linux environment; atomic publication is required. |
| `vision-operational` or `vision-refused` | Read the status `details` (HTTP status, stop reason, page). Check the key variable, model name and endpoint; lower `--vision-max-side` for an oversize image; raise `--vision-max-output-tokens` for a truncated reply; raise `--memory-mib` for a heavy `--vision-command` program. "Model ... is not available to this key" comes from the Bedrock check made before any page is read: correct the model or inference-profile ID, the region or the key's permissions, or retry if the status is 503. Nothing is published, so rerun, or amend an earlier result. |
| A manifest warning that no model transcription was accepted | The named pages show the independent reading, not a model's. Read each page record's `vision.attempts`: `low-agreement` usually means the model declined or summarised, so add `--own-work`, `--under-license` or `--fair-use` if one is true, name a `--vision-fallback-model`, or lower `--vision-min-agreement` if the transcription was in fact right; then amend those pages. |
| Forced kill left private directories | Treat them as incomplete and remove after confirming no live job owns them. The watchdog is not a hostile-document sandbox. |

Exit/status classifications, configured defaults, publication and cancellation limits are detailed in [CLI](CLI.md). For Drawbridge failures, consult that package's troubleshooting guide; typed document failures are mapped across the standalone CLI boundary.
