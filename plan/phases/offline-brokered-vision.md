---
id: offline-brokered-vision
title: Offline Linux arm64 configuration and brokered vision
depends_on: []
informs: []
order: '2'
parent: null
---

# Offline Linux arm64 configuration and brokered vision

## Goal

Run the existing conversion workflow with explicit configuration in a networkless, hardware-isolated Linux arm64 environment. The owner authorized the necessary changes to the document conversion stack and owned dependencies on 2026-11-19. This phase covers Vellric source and local qualification. The authorization excludes real model and provider calls during verification, credentials, tags and releases.

## Deliverables

- Configure conversion OCR, resource limits, diagnostics and child paths through Conric, preserving explicit CLI precedence and local-only admission.
- Keep PDF passwords in the supervisor-to-worker pipe. Use a private workspace and allowlist command environments.
- Add selectable Bedrock bearer, SigV4 and broker transports. Cover limits, optional startup probes, exact inherited descriptors and failure without transport fallback.
- Document and qualify an installed wheel and pinned native toolchain on Linux arm64 with networking disabled.

## Acceptance

- The exact source candidate passes independent plan review and code critique. Focused tests exercise configuration, password custody, limits, malformed broker responses, subprocess timeout, descriptor forwarding, missing descriptor refusal and transport isolation using fakes.
- A fresh Linux arm64 glibc install from staged, hash-verified wheels and binaries runs doctor, preserves source hashes and publishes the expected vision-off native and OCR fixture results. Retain the exact component versions and image identity.
- Run the candidate and handoff gates. Record observed reviews, checks and qualification before closure.

## Brief refs

- [Seed brief](../../briefs/BRIEF.md)
