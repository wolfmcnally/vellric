"""Vellric-owned configuration schema; Conric owns YAML composition and sources."""

from __future__ import annotations

import re

from conric import ConfigError, SchemaError, SecretRef, Value, load

from . import vision
from .runtime import JobError

OCR_FIELDS = {
    "mode": ("ocr", str),
    "pages": ("ocr_pages", str),
    "language": ("language", str),
    "dpi": ("dpi", float),
    "jobs": ("jobs", int),
    "page_timeout_seconds": ("page_timeout_seconds", float),
    "tessdata_dir": ("tessdata_dir", str),
    "preflight": ("preflight", str),
    "rotate_threshold": ("rotate_threshold", float),
    "preflight_timeout_seconds": ("preflight_timeout_seconds", float),
    "raster_threshold": ("raster_threshold", float),
}
LIMIT_FIELDS = {
    "memory_mib": ("memory_mib", int),
    "raster_mib": ("max_raster_bytes", int),
    "max_input_bytes": ("max_input_bytes", int),
    "max_output_bytes": ("max_output_bytes", int),
    "max_pages": ("max_pages", int),
    "timeout_seconds": ("timeout_seconds", float),
}
CONVERT_FIELDS = {
    "temp_dir": str,
    "path": str,
    "diagnostics": bool,
    "structure": str,
    "searchable_pdf": bool,
    "layout": bool,
    "title": str,
    "progress": str,
    "status_json": bool,
}
CONVERT_OPTIONS = {
    dest for dest, _ in (*OCR_FIELDS.values(), *LIMIT_FIELDS.values())
} | CONVERT_FIELDS.keys()
VISION_LIMIT_FIELDS = {
    "timeout_seconds": ("timeout_seconds", float),
    "max_concurrency": ("max_concurrency", int),
    "max_output_tokens": ("max_output_tokens", int),
    "max_image_bytes": ("max_image_bytes", int),
    "max_image_side_px": ("max_image_side_px", int),
}

VISION_DEFAULTS = {
    "provider": None,
    "model": None,
    "base_url": None,
    "region": None,
    "fallback_model": None,
    "min_agreement": None,
    "api_key_env": None,
    "command": None,
    "command_env": (),
    "transport": None,
    "probe": True,
    "limits": {},
    "pages": None,
    "cross_check": "on",
    "max_side": vision.DEFAULT_MAX_SIDE,
    "max_output_tokens": None,
}


def typed_value(value: Value, kind: type, path: tuple) -> Value:
    if kind is float and type(value) in (int, float):
        return value
    if type(value) is not kind or (kind is str and (not value or "\x00" in value)):
        raise SchemaError("invalid_type", path=path)
    return value


def fields(value: Value, spec: dict, path: tuple) -> dict:
    if not isinstance(value, dict):
        raise SchemaError("expected_mapping", path=path)
    if value.keys() - spec.keys():
        raise SchemaError("unknown_field", path=path)
    return {
        spec[key][0]: typed_value(item, spec[key][1], (*path, key)) for key, item in value.items()
    }


def command_schema(value: dict) -> dict:
    if value.keys() - {"argv", "pass_fds"}:
        raise SchemaError("unknown_field", path=("command",))
    argv, fds = value.get("argv"), value.get("pass_fds", [])
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(arg, str) or "\x00" in arg for arg in argv)
    ):
        raise SchemaError("invalid_argv", path=("command", "argv"))
    if (
        not isinstance(fds, list)
        or len(fds) > 4
        or any(type(fd) is not int or not 3 <= fd <= 255 for fd in fds)
    ):
        raise SchemaError("invalid_pass_fds", path=("command", "pass_fds"))
    return {"argv": argv, "pass_fds": fds}


def vision_schema(value: Value) -> dict:
    """Validate leaf shape without resolving credentials or invoking a provider."""
    if not isinstance(value, dict):
        raise SchemaError("expected_mapping")
    allowed = set(VISION_DEFAULTS) - {"api_key_env"} | {"api_key"}
    if value.keys() - allowed:
        raise SchemaError("unknown_field")
    result = {}
    for key, item in value.items():
        if key == "limits":
            result[key] = fields(item, VISION_LIMIT_FIELDS, (key,))
            continue
        if key == "command" and isinstance(item, dict):
            result[key] = command_schema(item)
            continue
        if key == "command_env":
            if not isinstance(item, list) or any(
                not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
                for name in item
            ):
                raise SchemaError("invalid_environment_names", path=(key,))
            result[key] = item
            continue
        if key == "probe":
            result[key] = typed_value(item, bool, (key,))
            continue
        if key == "transport" and item not in ("bearer", "sigv4", "command"):
            raise SchemaError("unknown_transport", path=(key,))
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
    if value.keys() - (
        CONVERT_FIELDS.keys() | {"vision", "local_only", "allow_brokered", "ocr", "limits"}
    ):
        raise SchemaError("unknown_field")
    local_only = value.get("local_only", False)
    if type(local_only) is not bool:
        raise SchemaError("expected_boolean", path=("local_only",))
    allow_brokered = typed_value(value.get("allow_brokered", False), bool, ("allow_brokered",))
    selected = value.get("vision")
    try:
        settings = vision_schema(selected) if selected is not None else {}
    except SchemaError as exc:
        raise SchemaError(exc.reason, path=("vision",) + exc.path) from None
    ocr = fields(value.get("ocr", {}), OCR_FIELDS, ("ocr",))
    limits = fields(value.get("limits", {}), LIMIT_FIELDS, ("limits",))
    if "max_raster_bytes" in limits:
        limits["max_raster_bytes"] *= 1024 * 1024
    general = {
        key: typed_value(value[key], kind, (key,))
        for key, kind in CONVERT_FIELDS.items()
        if key in value
    }
    return {
        "local_only": local_only,
        "vision": settings,
        "allow_brokered": allow_brokered,
        "conversion": ocr | limits | general,
    }


def resolve_options(explicit: dict, defaults: dict) -> dict:
    """Defaults < explicit YAML layers < explicit CLI; policy restrictions accumulate."""
    configured = {"local_only": False, "vision": {}, "conversion": {}, "allow_brokered": False}
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
    if any(
        key in explicit
        for key in ("vision_provider", "vision_base_url", "vision_region", "vision_transport")
    ):
        # A reference explicitly bound to a YAML destination does not follow a CLI reroute.
        settings.pop("vision_api_key_env", None)
    if explicit.get("vision_provider") == "none":
        settings = {}
        explicit = explicit | {"vision_provider": None}
    if "vision_max_output_tokens" in explicit and "vision_limits" in settings:
        settings["vision_limits"]["max_output_tokens"] = explicit["vision_max_output_tokens"]
    return (
        defaults
        | configured["conversion"]
        | {f"vision_{key}": item for key, item in VISION_DEFAULTS.items()}
        | settings
        | explicit
        | {
            "local_only": configured["local_only"] or explicit.get("local_only", False),
            "allow_brokered": configured["allow_brokered"] or explicit.get("allow_brokered", False),
            "vision_yaml_fields": frozenset(settings.keys() - explicit.keys()),
        }
    )
