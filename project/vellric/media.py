"""Canonical native fingerprints in a supervised, complete artifact job."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from . import __version__, pdf_tools
from .errors import ConverterUnavailable
from .runtime import BEHAVIOR, SCHEMA, JobError, digest, validate_bundle, write_json


def pixel_fingerprint(pixels) -> dict:
    mu = pdf_tools._pymupdf()
    shape = f"{pixels.width}:{pixels.height}:{pixels.n}:".encode()
    gray = mu.Pixmap(mu.csGRAY, pixels)
    small = mu.Pixmap(gray, 9, 8)
    value = 0
    samples = small.samples
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (samples[y * 9 + x] > samples[y * 9 + x + 1])
    hashed = hashlib.sha256(shape)
    hashed.update(pixels.samples_mv)
    return {
        "pixel_sha256": hashed.hexdigest(),
        "difference_hash": value,
        "width": pixels.width,
        "height": pixels.height,
        "channels": pixels.n,
        "algorithm": "mupdf-rgb-dhash-9x8/v1",
    }


def image_job(config: dict) -> dict:
    source = Path(config["source"])
    root = Path(config["staging"])
    options = config["options"]
    pdf_tools.MAX_RASTER_BYTES = options["max_raster_bytes"]
    try:
        # Header admission precedes native pixel allocation. The RSS watchdog also bounds decoding.
        with Image.open(source) as image:
            width, height = image.size
        pdf_tools.admit_raster(width, height, 1, 7)
        if max(width, height) > 30000:
            raise JobError("resource-limit", "Image side exceeds 30000 pixels", stage="image")
        mu = pdf_tools._pymupdf()
        pixels = mu.Pixmap(str(source))
        if (pixels.width, pixels.height) != (width, height):
            raise JobError("image-invalid", "Decoded image dimensions differ from admission")
        if pixels.alpha:
            pixels = mu.Pixmap(pixels, 0)
        if pixels.colorspace.n != 3:
            pixels = mu.Pixmap(mu.csRGB, pixels)
        target_width, target_height = options.get("width"), options.get("height")
        if target_width is not None:
            if target_width > width or target_height > height:
                raise JobError("usage", "Canonical image comparison never upsamples")
            pixels = mu.Pixmap(pixels, target_width, target_height)
        fingerprint = pixel_fingerprint(pixels)
        folder = root / "pages/000001"
        folder.mkdir(parents=True)
        (folder / "native.txt").write_bytes(b"")
        (folder / "text.txt").write_bytes(b"")
        pixels.save(folder / "image.png")
        (root / "document.txt").write_bytes(b"")
        (root / "document.md").write_bytes(b"")
        files = [
            {
                "path": p.relative_to(root).as_posix(),
                "size": p.stat().st_size,
                "sha256": digest(p),
                "media_type": "image/png" if p.suffix == ".png" else "text/plain",
            }
            for p in sorted(root.rglob("*"))
            if p.is_file()
        ]
        manifest = {
            "schema": SCHEMA,
            "status": "complete",
            "job": "image",
            "behavior": BEHAVIOR,
            "source": {"sha256": config["sha256"], "size": config["size"]},
            "tool": {"name": "vellric", "version": __version__},
            "engines": {"pymupdf": mu.VersionBind},
            "settings": {
                key: value
                for key, value in options.items()
                if key
                not in {
                    "input",
                    "out",
                    "password_file",
                    "password_stdin",
                    "temp_dir",
                    "tessdata_dir",
                }
            },
            "page_count": 1,
            "inspection": {
                "openable": True,
                "is_encrypted": False,
                "needs_password": False,
                "page_count": 1,
                "has_text_layer": False,
            },
            "pages": [
                {
                    "number": 1,
                    "method": "native-image",
                    "ocr_candidate": False,
                    "raster_coverage": 1.0,
                    "geometry": {
                        "displayed_rect": [0, 0, pixels.width, pixels.height],
                        "units": "px",
                    },
                    "files": {
                        "native": "pages/000001/native.txt",
                        "text": "pages/000001/text.txt",
                        "image": "pages/000001/image.png",
                    },
                    "fingerprint": fingerprint,
                }
            ],
            "outstanding_candidates": [],
            "recognition_completeness": "not-requested",
            "provenance": {
                "processing_fingerprint": hashlib.sha256(
                    json.dumps(
                        {
                            "behavior": BEHAVIOR,
                            "engine": mu.VersionBind,
                            "algorithm": fingerprint["algorithm"],
                            "width": target_width,
                            "height": target_height,
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
            },
            "files": files,
        }
        validate_bundle(root, manifest)
        write_json(root / "manifest.json", manifest)
        return manifest
    except JobError:
        raise
    except ConverterUnavailable as exc:
        raise JobError("dependency-unavailable", str(exc), stage="image") from exc
    except (MemoryError, Image.DecompressionBombError) as exc:
        raise JobError(
            "resource-limit", "Image decode exceeds memory limits", stage="image"
        ) from exc
    except Exception as exc:
        raise JobError(
            "image-operational", "Image decoding/fingerprinting failed", stage="image"
        ) from exc
