---
title: Vellric security review
date: 2026-10-14
status: draft
scope: Whole-project security review of Vellric at a named revision — attack surface, sinks examined, findings, hardening follow-ups and coverage limits.
---

# Vellric security review

This brief records a security review of the whole Vellric repository, so that later work can see what was examined, what was concluded and what was left open. It is a snapshot: line references are to the reviewed revision and will drift.

## 1. Revision, scope and method

- **Revision:** `6aef264a57789dbcd61b182e1fc413e194783f7d` on `master`, clean tree, reviewed 2026-10-14.
- **Scope:** every product module under `project/vellric/`, `project/packaging/windows_bundle.py`, both workflows under `.github/workflows/`, both hooks under `.githooks/`, and the subprocess, deserialization and network-facing parts of `bin/` and `lib/agentic_starter/`. Test-only files and Markdown documentation were out of scope.
- **Method:** a read-only discovery pass traced attacker-controlled input to every sensitive sink: subprocess calls, filesystem paths, deserialization, XML parsing, network requests and emitted text formats. A finding had to show a concrete exploit path with at least 80% confidence at HIGH or MEDIUM severity. Each candidate would then have gone to an independent false-positive check; none reached the bar, so that stage had nothing to filter. The key claims below were spot-checked against the source afterwards.
- **Exclusions applied:** denial of service and resource exhaustion; memory-safety bugs in native dependencies (MuPDF, Ghostscript, Tesseract); outdated third-party versions; lack of hardening without a concrete exploit. Command-line flags and environment variables are treated as trusted, as they are set by whoever runs the tool.

## 2. Threat model as built

Vellric is a command-line tool with no daemon, RPC server, job file or network listener ([seed brief](BRIEF.md)). A pipeline integrates it by running the trusted `vellric` command once per job. Every path, executable name and URL therefore arrives as a command-line flag. The only attacker-controlled input is the content of the PDF or image being processed, plus the contents of an earlier result folder named by `--amend`.

The input is opened with `O_NOFOLLOW` and checked as a regular file (lstat plus a same-file check on Windows), then copied once into a private 0700 workspace as `source.pdf` (`project/vellric/cli.py`, around lines 501–567).

## 3. Findings

**No confirmed or suspected vulnerabilities met the reporting bar (HIGH or MEDIUM severity at 80% or higher confidence).**

## 4. Sinks examined and why each held

1. **OCRmyPDF call** (`worker.py` ~201–226): fixed argument list, no shell. Input and output are fixed workspace names, so they cannot be read as options. The OCR language is restricted to `[A-Za-z0-9_+.-]+` (`cli.py` ~300); the other values are numbers or page lists.
2. **Ghostscript:** Vellric never calls it directly; OCRmyPDF 17.7.0 does, and passes `-dSAFER` on both of its Ghostscript paths. Ghostscript 10.x also enables SAFER by default.
3. **Tesseract call** (`orientation.py` ~136–149): only the program, a fixed `band-N-rotation-A.pnm` image name that Vellric rendered itself, `stdout`, the validated language and constants. No text from the PDF reaches the arguments.
4. **Operator-supplied vision program** (`vision.py` ~393–422): run as `[executable, fixed vision-NNNNNN.png]` with no shell, and a constant prompt on stdin.
5. **Child environment and program lookup** (`runtime.py` ~80–152): child processes get a private environment with no inherited credentials or Python or loader variables, and programs are looked up only on absolute search paths. On Windows the current folder is skipped and `NoDefaultCurrentDirectoryInExePath=1` is set.
6. **Worker start-up** (`cli.py` ~656–670): `sys.executable -I -c <constant>`, given the package root and a config path the parent wrote. No `eval` or `exec` of input-controlled text.
7. **Output paths:** every artifact name is a constant or a number (`pages/NNNNNN/…`, `tables/NNNN.csv`, `render-NNNN.ext`, `diagnostics/page-…tsv`). No embedded-file, attachment, font, metadata or link name from the PDF becomes a path. Results are staged in a 0700 temporary folder and published by an atomic rename that refuses to replace anything (`RENAME_EXCL` on macOS, `RENAME_NOREPLACE` on Linux, non-replacing `os.rename` on Windows), after the destination is checked for existence or a link (`cli.py` ~594–598, `runtime.py` ~311–359).
8. **`--amend` folder** (`worker.py` ~234–257 and ~458–463, `runtime.py` ~362–408): the bundle check refuses absolute paths, `..`, non-portable forms, duplicates and any link or junction in any path part, and verifies each file's size, SHA-256 and the full file list. Carried-over files are read only if the verified manifest declares them.
9. **Deserialization:** product code uses only `json.loads`, on files the worker or parent wrote; the worker's result file is size-capped and strictly shape-checked (`cli.py` ~742–799). No pickle, unsafe YAML, `eval` or `marshal`. Developer tooling uses `yaml.safe_load` only.
10. **XML:** the product parses no XML; XMP and other metadata are not parsed, so XXE does not arise.
11. **Image input** (`media.py` ~45–62): Pillow reads only the header for dimensions and `.load()` is never called, so Pillow's EPS reader never starts Ghostscript. Pixels are decoded by MuPDF.
12. **Vision API key:** delivered to the worker over a pipe and never written to the manifest. HTTP redirects are refused (a no-redirect handler for urllib, `follow_redirects=False` for the Anthropic client), so the key cannot be sent to a host the operator did not name. The base URL must be http(s) with a host and no embedded credentials (`cli.py` ~404–431, `vision.py` ~108–137).
13. **Emitted text:** Markdown, plain text, JSON (via `json.dumps`) and CSV; never HTML. The document title is derived from the input filename reduced to `[a-z0-9 ]`.
14. **Windows bundle builder:** creates a zip from files on disk and never extracts one, so zip-slip does not arise. Wheels are downloaded with `--require-hashes`.
15. **GitHub workflows:** triggered only by `push`, `pull_request` and `workflow_dispatch`, never `pull_request_target`; `contents: read`; no `github.event.*` value interpolated into a script; actions pinned to commit SHAs; downloaded installers and tarballs checked against SHA-256 values.
16. **Hooks and `bin/`:** no `shell=True` or `os.system`. Scripts operate on the repository's own files. The execution dashboard server binds `127.0.0.1:18080` and serves only the committed `reports/execution` folder.

## 5. Hardening follow-ups (below the reporting bar)

These are not vulnerabilities in Vellric itself. Each depends on a downstream consumer or an attacker who already has local write access. They are cheap to address and are recorded here so the decision is visible.

1. **CSV formula injection.** Table cells from the PDF are written verbatim to `pages/NNNNNN/tables/NNNN.csv` (`worker.py` ~728–729). A hostile cell beginning `=`, `+`, `-` or `@` could become a live formula if someone opens the file in a spreadsheet and accepts its warnings. Mitigation: prefix such cells (and cells starting with tab or carriage return) with a single quote, or document that the CSV is data, not a spreadsheet. This trades exact cell fidelity for safety, so it is a product decision.
2. **Markdown link schemes.** In the structured Markdown view, link targets from the PDF are only percent-encoded for spaces and parentheses (`native.py` ~65–66), so a `javascript:` or `data:` target survives. This matters only if a consumer renders the Markdown to HTML without sanitizing it. Mitigation: emit only `http`, `https` and `mailto` targets as links and render others as plain text, or document that consumers must sanitize.
3. **Windows working folder for OCR children.** Tesseract and OCRmyPDF inherit the caller's working folder on Windows when the default environment is used (`runtime.py` ~258). DLL planting there needs an attacker who can already write into that folder, which is outside the hostile-document model. Mitigation: run them in the private workspace folder, as the custom-environment path already does.

## 6. Coverage limits and residual risk

- **Native parsers are the real attack surface and were not reviewed.** A memory-safety bug in MuPDF, Ghostscript or Tesseract triggered by a crafted document would run inside the caller's account. The seed brief already says genuinely untrusted inputs need an operating-system sandbox, and `vellric doctor` reports `hard_sandbox: false`. Running hostile documents in a container or VM remains the mitigation.
- **Static review only.** No fuzzing, dynamic testing or proof-of-concept documents were run.
- **Dependency claims were checked once.** The `-dSAFER` behaviour was confirmed in the locally cached OCRmyPDF 17.7.0 source; a version change needs re-checking.
- **Out of scope:** test-only files, Markdown documentation and third-party dependency versions.

## 7. Follow-up

- Decide on the three hardening items in section 5.
- Re-run this review after any change that adds a new input channel (a job file, daemon or network listener), adds XML or metadata parsing, or lets document-derived text reach a filesystem path or subprocess argument.
