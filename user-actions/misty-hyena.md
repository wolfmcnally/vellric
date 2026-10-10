---
slug: misty-hyena
title: Settle the Windows version on the target machine and decide how its bundle may be shared
status: pending
category: release
urgency: medium
blocks:
  - Calling the Windows support of 0.2.0 accepted
  - Giving the Windows bundle to anyone outside the owner's own machines
filed: 2026-10-10
needed_at: before the Windows bundle is shared or 0.2.0 is released
source: primary
refs:
  - project/docs/INSTALLATION.md
  - project/docs/LICENSING.md
  - project/packaging/windows_bundle.py
  - .github/workflows/windows.yml
---

Version 0.2.0 runs natively on Windows and has been proved on a GitHub-hosted Windows Server 2025 machine under an administrator account. Three things need the owner.

First, try it on the target machine, which no agent session can reach: a Windows 11 desktop edition, an account without administrator rights and Python 3.13. Install the bundle as its `INSTALL.txt` says, run `vellric doctor`, and convert a document with the Bedrock vision provider. Report anything that fails; a fix is a patch release.

Second, ask the machine's administrators to install Tesseract 5.5.3 (`tesseract-ocr-w64-setup-5.5.3.20260724.exe`) and Ghostscript 10.07.1 (`gs10071w64.exe`) to their default folders. Until they do, scanned pages read by a vision model have no independent check.

Third, decide how the Windows bundle may be shared. It holds unmodified third-party binary wheels, including PyMuPDF under AGPL and libraries under LGPL and MPL, with only the license files each wheel carries. The licensing guide says such an artifact needs its source and notice closure assembled before it is given to anyone else. Installing it on the owner's own machines is the use it was built for. Three bundles built by the first workflow runs were public workflow artifacts for about two hours until they were deleted on 2026-10-10; the workflow no longer publishes the bundle.
