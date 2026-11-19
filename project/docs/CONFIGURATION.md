# Composed configuration

As of 2026-10-21, version 0.2.3 uses public MIT-licensed Conric 0.1.0. The source integration is public; tagged release artifacts require exact-commit public CI, Windows qualification and all other release checks; see [installation](INSTALLATION.md). Invocations without configuration retain their defaults and provider opt-in behavior.

`convert --config FILE` loads explicit UTF-8 YAML through Conric. Repeat the flag for later overrides. `include: [base.yaml]` loads relative bases before the including file. Mappings merge recursively; lists and null replace. Files are confined to the first explicit file's parent; `--config-root DIRECTORY` allows files in sibling directories under a common root. There is no ambient discovery, dotenv loading or environment interpolation. Conric owns include/parser safety and resource limits. A missing `vellric` subtree is a usage error. Other top-level subtrees belong to other leaves and are ignored.

```yaml
include: [base.yaml]
vellric:
  local_only: false
  vision:
    provider: openai
    model: chosen-model
    base_url: https://example.invalid/v1
    api_key: !env EXAMPLE_VISION_KEY
    max_side: 2576
    cross_check: on
```

The `vellric` subtree accepts these conversion options. Values omitted from YAML keep their CLI defaults.

| Mapping | Fields |
|---|---|
| `ocr` | `mode`, `pages`, `language`, `dpi`, `jobs`, `page_timeout_seconds`, `tessdata_dir`, `preflight`, `rotate_threshold`, `preflight_timeout_seconds`, `raster_threshold` |
| `limits` | `memory_mib`, `raster_mib`, `max_input_bytes`, `max_output_bytes`, `max_pages`, `timeout_seconds` |
| `vellric` | `temp_dir`, `path`, `diagnostics`, `structure`, `searchable_pdf`, `layout`, `title`, `progress`, `status_json`, `local_only`, `allow_brokered`, `vision` |

Booleans are written as `true` or `false`. OCR mode is `auto`, `never` or `always`. Preflight is `on` or `off`. OCR pages use the CLI's range syntax, such as `"2-5"`. `raster_mib` is an integer in MiB. `path` is a platform-separated list of absolute directories and replaces the child search path. Use `temp_dir` for a private job workspace base. Input, output and the PDF password source are per-job CLI arguments.

Vision accepts a mapping or null.

| Field | Type and bounds |
|---|---|
| `provider` | `anthropic`, `openai`, `bedrock`, `command` or null |
| `model`, `base_url`, `region`, `fallback_model`, `pages` | Nonempty string or null |
| `command` | Absolute program path for the Markdown command provider, or an `argv` mapping for Bedrock command transport |
| `command_env` | Names of caller environment variables permitted in command children, empty by default |
| `transport`, `probe`, `limits` | Bedrock transport controls described below |
| `cross_check` | `on` or `off` |
| `max_side` | Integer 256..30000 |
| `max_output_tokens` | Integer 1..1000000 or null |
| `min_agreement` | Number 0..1 or null |
| `api_key` | Unresolved `!env NAME` reference or null; no plaintext keys |

Unknown fields and wrong types are refused. Provider-specific requirements, model/fallback checks and endpoint/key binding still run after composition. Model or credential settings without a provider remain usage errors. Standalone CLI commands accept a path relative to the invoking directory. Choose an absolute executable in configuration. The ownership, license and fair-use declarations are CLI-only.

Precedence is defaults, then composed YAML, then explicitly supplied CLI values, including values equal to defaults. `--vision-provider none` disables the lower-precedence YAML vision block; contradictory explicit flags still fail. `vision: null` clears a lower YAML block. `--config-root` requires `--config`. If CLI supplies provider, base URL, region or transport (even when equal to YAML), a YAML credential reference is cleared; supply `--vision-api-key-env NAME` explicitly to bind a credential to the new destination. The existing standard-endpoint/default-variable rule still applies.

`--local-only` is an independent caller restriction that YAML cannot disable. A true configured `local_only` also restricts the invocation; a later YAML layer may replace an earlier YAML value, but cannot weaken `--local-only`. Local-only conversion refuses every selected vision route before credential access or worker launch, including arbitrary external commands and loopback-hosted providers. Fallback models receive the same restriction. Native extraction and local OCR remain available; this policy is not a network sandbox. Explicit `--config` selection of a provider opts in to that existing route when local-only is false; neither package silently chooses a provider.

Apply a file while explicitly disabling vision:

```sh
vellric convert input.pdf --out converted --config settings.yaml --vision-provider none --local-only --ocr never --preflight off
```

Conric preserves winning file/line/column provenance. The leaf's `vellric.configuration.vellric_schema` validates the `("vellric",)` subtree of a parent-composed Config without a second YAML loader. It validates shape and references; final invocation validation applies provider requirements and egress restrictions. Configuration errors produce `usage`/`settings` status and exit 2 with source location and stable reason, without scalar data. `Config.redacted()` hides tagged references; ordinary strings are not automatically secret. Credentials use the existing environment-variable resolution and private worker stdin transport. Configuration paths, command paths and credential variable names are excluded from output settings. Nonsecret `local_only` is recorded but does not change the rendering fingerprint.

## Bedrock transports

Bedrock endpoint settings supplied by YAML use an exact AWS region, and model IDs supplied by YAML must name foundation models. Selecting a transport in YAML or using SigV4 or a brokered command also requires an exact region and foundation-model IDs, including when the model flags came from the CLI. YAML page selection leaves CLI bearer endpoint, model and key behavior intact. Supply a single `transport` for both the primary and fallback model. `bearer` is the default. In YAML it uses an `api_key: !env NAME` reference. The standalone bearer route can still use its usual environment variable or an explicitly keyed custom endpoint. `sigv4` uses the optional `vellric[bedrock]` extra and the regional HTTPS endpoint. Selecting SigV4 on the CLI uses the standard AWS credential chain. Selecting it in YAML uses the AWS environment credential provider, which skips ambient credential files.

```yaml
vellric:
  allow_brokered: true
  vision:
    provider: bedrock
    region: us-west-2
    model: amazon.nova-lite-v1:0
    transport: command
    probe: false
    command:
      argv: [/opt/vision/bin/converse]
      pass_fds: [3]
    command_env: [BROKER_LABEL]
    limits:
      timeout_seconds: 45
      max_concurrency: 2
      max_output_tokens: 4096
      max_image_bytes: 3932160
      max_image_side_px: 8000
```

The command transport is brokered and requires `allow_brokered: true`. It is available on POSIX. The named descriptors must already be open in the Vellric process. The list accepts up to four integers in 3–255. Vellric forwards only those descriptors, at the same numbers. The child receives only the named environment entries that are present. The ordinary Markdown command also uses a replacement environment and still receives Vellric's generated page and model variables.

The broker reads one UTF-8 JSON document from stdin and returns one UTF-8 JSON document on stdout. The request has `schema: bedrock-converse-request/1`, `region`, `model`, and the Converse `body`. Images use PNG or JPEG with base64 bytes. The response has `schema: bedrock-converse-response/1` and either `status: ok` with a Converse `body` or `status: error` with a `category` of `throttled`, `refused`, `unavailable`, `invalid`, or `limit`. The response cap is 16 MiB. Requests time out and the subprocess group is terminated.

The startup probe defaults to on. It uses the same transport as page requests and has its own fixed 64-token cap. Set `probe: false` or use `--no-vision-probe` to skip it. Request timeout and concurrency limits can lower the page timeout and job concurrency. Command and SigV4 default to 4096 output tokens. Bearer uses the model's default unless a limit is provided. Image limits are ceilings. Vellric checks the encoded bytes and resizes or re-encodes as needed. A transport failure stays on that transport, including during a model fallback.
