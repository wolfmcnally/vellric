# License and source provenance

Vellric's owner-selected project grant is AGPL-3.0-only. The full GNU AGPL version 3 text is in `LICENSE`; package metadata and `doctor` agree. Original MIT material and dependency grants remain operative.

The scaffold preserves universal methodology, skills, agent mirrors, policies, scripts, libraries, tests and offline renderer assets from Starter from a source snapshot whose exact origin remains privately retained. Its original copyright/MIT grant remains in `LICENSES/starter-MIT.txt`; adaptations do not erase that grant. Vendored renderer assets retain their own adjacent license. The project command shell and identity/manifest files were specialized for this seed. The imported Drawbridge processing source is recorded below.

PyMuPDF 1.28.2 is declared and locked; it has its own AGPL/commercial and bundled-native notices. OCRmyPDF 17.7.0 is an optional extra whose dependency closure is locked. Dependencies are not vendored by this scaffold. The seed brief describes additional engine/source obligations; a release must generate a verified full component/source/NOTICE inventory rather than treating this file as complete certification.

## Drawbridge MIT source

PDF processing, orientation recovery, native formatting, typed exceptions and the strict native word gate are adapted from Drawbridge MIT source snapshot, files `src/drawbridge/{pdf_tools,orientation,native,errors,structure,ocr,mirror}.py`. Original copyright and MIT grant remain under `LICENSES/drawbridge-MIT.txt`. No provider stages or unrelated adapters are imported. Synthetic typography fixture/golden comes from `tests/test_native.py` from that source snapshot.

## Qualified dependency terms

The Linux arm64 full-OCR installation inventory and exact bundled license evidence are summarized in [qualification evidence](project/docs/QUALIFICATION.md). The closure is not wholly permissive: OCRmyPDF/pikepdf are MPL-2.0; fpdf2 and img2pdf are LGPLv3; pi-heif has BSD source but LGPLv3 binary wheels (libheif/libde265). PDFium wheels, fonts, codecs and runtime libraries carry component-specific notices. These terms do not establish a need for a stronger project grant than AGPL-3.0-only, but a root label is not a completed redistribution/source/NOTICE audit. No commercial Artifex grant is claimed.

The prepared standalone source/wheel route includes project NOTICE, the exact runtime lock and pinned build material. The release-preparation companion retains all 34 qualified runtime source releases, six build source releases and actual dependency notices; the project artifacts do not bundle dependency binaries. See [the release route](project/docs/RELEASE-PREPARATION.md).
