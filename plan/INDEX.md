# Plan discovery

State lives in `phases/` and `events/`; `./bin/multioperator render --root .` produces disposable local views. Entries written before the 2026-11-20 migration name phases by their old numbers; `collaboration/manifest.json` maps each to its permanent id.

# Vellric implementation checklist

Release and consumer qualification use exact candidate gates and independent source review. Extraction/conversion work uses the compact acceptance checklist. [`pdf-conversion-checklist`](phases/pdf-conversion-checklist.md) retains the standalone implementation checklist. [`offline-brokered-vision`](phases/offline-brokered-vision.md) records the separately authorized Linux arm64 configuration and brokered vision work.

## Dependencies

`offline-brokered-vision` starts from the existing standalone implementation. See [the seed brief](../briefs/BRIEF.md#empirical-basis-and-acceptance-strategy) for the extraction and conversion evidence.
