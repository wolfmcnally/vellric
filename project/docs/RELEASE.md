# Local release preparation

Vellric 0.1.0 and Drawbridge 0.1.0 are prepared as local standalone release candidates. Vellric is AGPL-3.0-only; Drawbridge remains MIT. Publish the fresh audited history and corresponding tested artifacts in coordinated order. Live consumer changes remain separate.

The concrete source/NOTICE/dependency inventory, locked build/install commands, output/privacy audit and publication/consumer sequence are in [RELEASE-PREPARATION.md](RELEASE-PREPARATION.md). Package source includes the dependency lock and exact build constraints. Project wheels contain their own source and notices; dependencies/engines install independently. Local companion evidence retains upstream source archives and actual qualified dependency notices/hashes. A future bundled binary/container offering would require its own matching source/build/NOTICE closure; no such artifact is proposed here.

Unchanged native/OCR output is established by the preserved 27-page public parity, synthetic expected text and word goldens. The two image samples retain exact text; their confidence and one corrected rotation metadata value are documented. There is no new qualified text difference requiring owner readability judgment and no blanket perceptual-approval hold. Optional visual review remains available.

The original implementation review, local integration review/dispositions and earlier Linux qualification remain separate historical evidence in [QUALIFICATION.md](QUALIFICATION.md) and [INTEGRATION-QUALIFICATION.md](INTEGRATION-QUALIFICATION.md). Final package/install audit receipts and full-gate receipts own release-preparation results. This preparation adds build/version/notice/docs material without changing extraction algorithms or weakening existing tests.
