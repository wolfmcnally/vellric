---
slug: wooden-koel
title: Prove every install command a bundle has ever documented, not only the current one
status: codified
scope: local
proposed_surface: test
filed: 2026-11-04
closed: 2026-11-04
graduated_to: policies/releases.md
source: user
occurrences:
  - date: 2026-11-04
    ref: "0.2.4 Windows bundle failed offline with the earlier --find-links install command"
---

A user inside an enclave with no GitHub access upgraded from the 0.2.0 bundle to 0.2.4 by changing only the version in the command the 0.2.0 instructions gave, `pip install --no-index --find-links wheels "vellric[ocr]==X"`. From 0.2.2 the bundle's Vellric wheel named Conric by its Git source, so that resolving command made pip clone Conric from GitHub and fail. The bundle's own `INSTALL.txt` had moved to a hash-checked `--no-deps` command that still worked, and the Windows workflow proved only that new command, on a runner with network access where a Git clone would have succeeded anyway. Nothing exercised the command users already had, and nothing ran the proof without network access, so the regression shipped in three releases and the release notes never said the command had changed.

The containment was the reply naming the current command. The 0.2.5 correction makes the bundle's Vellric wheel name Conric by version, adds a Windows workflow install with the old resolving command while Git may use no transport, and documents upgrades in `INSTALL.txt` and the installation guide. The candidate prevention is broader: when an artifact promises to install with no network, prove it with the network-dependent transports actually blocked, and keep proving each install command a released artifact has documented until the owner retires it in the release notes. A passing install on a connected runner is not evidence for an offline promise. The owner graduated this lesson on 2026-11-04 as rule 2 of the standard release contents in the release policy.
