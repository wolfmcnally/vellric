# Composed configuration

As of 2026-10-20, local candidate 0.2.2 uses private Conric. Publication, public CI and Windows bundle qualification are held; see [installation](INSTALLATION.md). Invocations without configuration retain their defaults and provider opt-in behavior.

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

The `vellric` subtree accepts `local_only` (boolean) and `vision` (mapping or null). Vision accepts:

| Field | Type and bounds |
|---|---|
| `provider` | `anthropic`, `openai`, `bedrock`, `command` or null |
| `model`, `base_url`, `region`, `fallback_model`, `command`, `pages` | Nonempty string or null |
| `cross_check` | `on` or `off` |
| `max_side` | Integer 256..30000 |
| `max_output_tokens` | Integer 1..1000000 or null |
| `min_agreement` | Number 0..1 or null |
| `api_key` | Unresolved `!env NAME` reference or null; no plaintext keys |

Unknown fields and wrong types are refused. Provider-specific requirements, model/fallback checks and endpoint/key binding still run after composition. Model or credential settings without a provider remain usage errors. Ownership/license/fair-use declarations stay explicit CLI flags. Command paths retain their existing meaning relative to the invoking working directory.

Precedence is defaults, then composed YAML, then explicitly supplied CLI values, including values equal to defaults. `--vision-provider none` disables the lower-precedence YAML vision block; contradictory explicit flags still fail. `vision: null` clears a lower YAML block. `--config-root` requires `--config`. If CLI supplies provider, base URL or region (even when equal to YAML), a YAML credential reference is cleared; supply `--vision-api-key-env NAME` explicitly to bind a credential to the new destination. The existing standard-endpoint/default-variable rule still applies.

`--local-only` is an independent caller restriction that YAML cannot disable. A true configured `local_only` also restricts the invocation; a later YAML layer may replace an earlier YAML value, but cannot weaken `--local-only`. Local-only conversion refuses every selected vision route before credential access or worker launch, including arbitrary external commands and loopback-hosted providers. Fallback models receive the same restriction. Native extraction and local OCR remain available; this policy is not a network sandbox. Explicit `--config` selection of a provider opts in to that existing route when local-only is false; neither package silently chooses a provider.

Apply a file while explicitly disabling vision:

```sh
vellric convert input.pdf --out converted --config settings.yaml --vision-provider none --local-only --ocr never --preflight off
```

Conric preserves winning file/line/column provenance. The leaf's `vellric.configuration.vellric_schema` validates the `("vellric",)` subtree of a parent-composed Config without a second YAML loader. It validates shape and references; final invocation validation applies provider requirements and egress restrictions. Configuration errors produce `usage`/`settings` status and exit 2 with source location and stable reason, without scalar data. `Config.redacted()` hides tagged references; ordinary strings are not automatically secret. Credentials use the existing environment-variable resolution and private worker stdin transport. Configuration paths, command paths and credential variable names are excluded from output settings. Nonsecret `local_only` is recorded but does not change the rendering fingerprint.
