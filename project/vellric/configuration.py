"""Vellric-owned configuration schema; Conric owns YAML composition and sources."""

from __future__ import annotations

from conric import ConfigError, SchemaError, SecretRef, Value, load

from . import vision
from .runtime import JobError

VISION_DEFAULTS = {
    "provider": None,
    "model": None,
    "base_url": None,
    "region": None,
    "fallback_model": None,
    "min_agreement": None,
    "api_key_env": None,
    "command": None,
    "pages": None,
    "cross_check": "on",
    "max_side": vision.DEFAULT_MAX_SIDE,
    "max_output_tokens": None,
}


def vision_schema(value: Value) -> dict:
    """Validate leaf shape without resolving credentials or invoking a provider."""
    if not isinstance(value, dict):
        raise SchemaError("expected_mapping")
    allowed = set(VISION_DEFAULTS) - {"api_key_env"} | {"api_key"}
    if value.keys() - allowed:
        raise SchemaError("unknown_field")
    result = {}
    for key, item in value.items():
        if key == "api_key":
            if item is not None and not isinstance(item, SecretRef):
                raise SchemaError("expected_secret_reference", path=(key,))
            result["api_key_env"] = item.name if item is not None else None
            continue
        if item is not None:
            valid = (
                type(item) is int
                if key in {"max_side", "max_output_tokens"}
                else type(item) in {int, float}
                if key == "min_agreement"
                else isinstance(item, str) and bool(item)
            )
            if not valid:
                raise SchemaError("invalid_type", path=(key,))
        if key == "provider" and item is not None and item not in vision.PROVIDERS:
            raise SchemaError("unknown_provider", path=(key,))
        if key == "cross_check" and item not in {"on", "off"}:
            raise SchemaError("invalid_cross_check", path=(key,))
        if key == "max_side" and item is None:
            raise SchemaError("expected_integer", path=(key,))
        if item is not None and (
            (key == "max_side" and not 256 <= item <= 30000)
            or (key == "max_output_tokens" and not 1 <= item <= 1_000_000)
            or (key == "min_agreement" and not 0 <= item <= 1)
        ):
            raise SchemaError("out_of_range", path=(key,))
        result[key] = float(item) if key == "min_agreement" and item is not None else item
    return result


def vellric_schema(value: Value) -> dict:
    """Reusable subtree validator for CLI and composed parent configurations."""
    if not isinstance(value, dict):
        raise SchemaError("expected_mapping")
    if value.keys() - {"vision", "local_only"}:
        raise SchemaError("unknown_field")
    local_only = value.get("local_only", False)
    if type(local_only) is not bool:
        raise SchemaError("expected_boolean", path=("local_only",))
    selected = value.get("vision")
    try:
        settings = vision_schema(selected) if selected is not None else {}
    except SchemaError as exc:
        raise SchemaError(exc.reason, path=("vision",) + exc.path) from None
    return {"local_only": local_only, "vision": settings}


def resolve_options(explicit: dict) -> dict:
    """Defaults < explicit YAML layers < explicit CLI; policy restrictions accumulate."""
    configured = {"local_only": False, "vision": {}}
    paths = explicit.get("config")
    if explicit.get("config_root") and not paths:
        raise JobError("usage", "--config-root requires --config", stage="settings")
    if paths:
        try:
            config = load(paths, root=explicit.get("config_root"))
            configured = config.validate(vellric_schema, path=("vellric",))
        except ConfigError as exc:
            source = exc.source
            location = f" at {source.file}:{source.line}:{source.column}" if source else ""
            reason = f" ({exc.reason})" if exc.reason else ""
            raise JobError(
                "usage", f"Configuration {exc.code}{reason}{location}", stage="settings"
            ) from None
    settings = {f"vision_{key}": item for key, item in configured["vision"].items()}
    if any(key in explicit for key in ("vision_provider", "vision_base_url", "vision_region")):
        # A reference explicitly bound to a YAML destination does not follow a CLI reroute.
        settings.pop("vision_api_key_env", None)
    if explicit.get("vision_provider") == "none":
        settings = {}
        explicit = explicit | {"vision_provider": None}
    return (
        {f"vision_{key}": item for key, item in VISION_DEFAULTS.items()}
        | settings
        | explicit
        | {"local_only": configured["local_only"] or explicit.get("local_only", False)}
    )
