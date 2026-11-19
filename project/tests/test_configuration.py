"""Synthetic leaf composition, policy, artifact and installed-wheel contracts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest
from conric import ConfigError, SecretRef, load

from vellric import cli, vision
from vellric.configuration import vellric_schema
from vellric.runtime import JobError


def config(tmp_path, name, body):
    file = tmp_path / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(body, encoding="utf-8")
    return file


def arguments(tmp_path, *extra):
    return ["convert", str(tmp_path / "input.pdf"), "--out", str(tmp_path / "out"), *extra]


def test_composed_leaf_precedence_provenance_and_rejections(tmp_path):
    config(
        tmp_path,
        "base.yaml",
        "other: {count: 12}\nvellric:\n  vision:\n    provider: openai\n"
        "    model: base\n    max_side: 4096\n    api_key: !env SYNTHETIC_KEY\n",
    )
    chosen = config(
        tmp_path, "chosen.yaml", "include: [base.yaml]\nvellric:\n  vision:\n    model: chosen\n"
    )
    document = load([chosen])
    assert document.validate(vellric_schema, path=("vellric",))["vision"]["model"] == "chosen"
    assert document.data["other"] == {"count": 12}
    assert isinstance(document.data["vellric"]["vision"]["api_key"], SecretRef)
    assert document.redacted()["vellric"]["vision"]["api_key"] == "<redacted>"
    source = document.source(("vellric", "vision", "model"))
    assert (source.file, source.line, source.column) == (chosen, 4, 12)
    options = vars(
        cli.parser().parse_args(
            arguments(tmp_path, "--config", str(chosen), "--vision-max-side", "2576")
        )
    )
    assert (options["vision_model"], options["vision_max_side"], options["vision_api_key_env"]) == (
        "chosen",
        2576,
        "SYNTHETIC_KEY",
    )
    override = config(tmp_path, "nested/override.yaml", "vellric: {vision: {model: last}}\n")
    with pytest.raises(ConfigError, match="include_escape"):
        load([override, chosen])
    assert (
        load([chosen, override], root=tmp_path).validate(vellric_schema, path=("vellric",))[
            "vision"
        ]["model"]
        == "last"
    )
    with pytest.raises(JobError, match="include_escape"):
        cli.parser().parse_args(
            arguments(tmp_path, "--config", str(override), "--config", str(chosen))
        )
    common = cli.parser().parse_args(
        arguments(
            tmp_path,
            "--config",
            str(override),
            "--config",
            str(chosen),
            "--config-root",
            str(tmp_path),
        )
    )
    assert common.vision_model == "chosen"
    numeric = config(tmp_path, "numeric.yaml", "vellric: {vision: {min_agreement: 1}}\n")
    normalized = load([numeric]).validate(vellric_schema, path=("vellric",))["vision"][
        "min_agreement"
    ]
    assert type(normalized) is float and normalized == 1.0
    disabled = cli.parser().parse_args(
        arguments(tmp_path, "--config", str(chosen), "--vision-provider", "none")
    )
    assert (disabled.vision_provider, disabled.vision_model, disabled.vision_api_key_env) == (
        None,
        None,
        None,
    )
    invalid = [
        ("other: {}\n", "missing_path"),
        ("vellric: {local_only: yes}\n", "expected_boolean"),
        ("vellric: {vision: {max_side: false}}\n", "invalid_type"),
        ("vellric: {vision: {max_side: 2}}\n", "out_of_range"),
        ("vellric: {vision: {provider: unknown}}\n", "unknown_provider"),
        ("vellric: {vision: {api_key: SYNTHETIC_PLAINTEXT_SECRET}}\n", "expected_secret_reference"),
        ("vellric: {vision: {model: !env SYNTHETIC_PLAINTEXT_SECRET}}\n", "invalid_type"),
        ("vellric: {unknown: SYNTHETIC_PLAINTEXT_SECRET}\n", "unknown_field"),
        *[
            (f"vellric: {{{key}: true}}\n", "unknown_field")
            for key in ("own_work", "under_license", "fair_use")
        ],
        ("vellric: [SYNTHETIC_PLAINTEXT_SECRET\n", "yaml"),
    ]
    for index, (body, reason) in enumerate(invalid):
        bad = config(tmp_path, f"bad-{index}.yaml", body)
        with pytest.raises(JobError) as caught:
            cli.parser().parse_args(arguments(tmp_path, "--config", str(bad)))
        error = caught.value
        assert error.exit_code == 2 and error.stage == "settings"
        line = 2 if reason == "yaml" else 1  # An unterminated sequence is diagnosed at EOF.
        assert reason in str(error) and f"{bad}:{line}:" in str(error)
        assert "SYNTHETIC_PLAINTEXT_SECRET" not in str(error.status())


def test_conversion_config_values_and_explicit_cli_precedence(tmp_path):
    chosen = config(
        tmp_path,
        "convert.yaml",
        """vellric:
  local_only: true
  ocr:
    mode: auto
    pages: 2-3
    language: deu
    dpi: 180
    jobs: 3
    page_timeout_seconds: 45
    preflight: off
    rotate_threshold: 1.5
    preflight_timeout_seconds: 90
    raster_threshold: 0.2
  limits:
    memory_mib: 512
    raster_mib: 12
    max_input_bytes: 123456
    max_output_bytes: 654321
    max_pages: 8
    timeout_seconds: 120
  diagnostics: true
  progress: none
""",
    )
    parsed = cli.parser().parse_args(
        arguments(tmp_path, "--config", str(chosen), "--dpi", "300", "--no-diagnostics")
    )
    options = vars(parsed)
    cli.validate_options(options)
    assert {
        key: options[key]
        for key in (
            "ocr",
            "ocr_pages",
            "language",
            "dpi",
            "jobs",
            "page_timeout_seconds",
            "preflight",
            "rotate_threshold",
            "preflight_timeout_seconds",
            "raster_threshold",
            "memory_mib",
            "max_raster_bytes",
            "max_input_bytes",
            "max_output_bytes",
            "max_pages",
            "timeout_seconds",
            "diagnostics",
            "progress",
            "local_only",
        )
    } == {
        "ocr": "auto",
        "ocr_pages": "2-3",
        "language": "deu",
        "dpi": 300,
        "jobs": 3,
        "page_timeout_seconds": 45,
        "preflight": "off",
        "rotate_threshold": 1.5,
        "preflight_timeout_seconds": 90,
        "raster_threshold": 0.2,
        "memory_mib": 512,
        "max_raster_bytes": 12 * 1024 * 1024,
        "max_input_bytes": 123456,
        "max_output_bytes": 654321,
        "max_pages": 8,
        "timeout_seconds": 120,
        "diagnostics": False,
        "progress": "none",
        "local_only": True,
    }


def test_yaml_limits_and_child_path_refuse_before_input(tmp_path, monkeypatch, capsys):
    def unexpected(*args):
        pytest.fail("input was accessed before rejecting configuration")

    monkeypatch.setattr(cli, "snapshot", unexpected)
    for index, (settings, expected) in enumerate(
        [
            ("ocr: {jobs: true}", "invalid_type"),
            ("limits: {raster_mib: 0}", "max-raster-bytes"),
            ("limits: {imaginary_limit: 3}", "unknown_field"),
            ("path: relative", "absolute directories"),
        ]
    ):
        file = config(tmp_path, f"invalid-{index}.yaml", f"vellric:\n  {settings}\n")
        raw = arguments(tmp_path, "--config", str(file), "--status-json")
        assert cli.main(raw) == 2
        assert expected in json.loads(capsys.readouterr().out)["message"]


def test_local_only_and_credential_destination_binding(tmp_path, monkeypatch):
    chosen = config(
        tmp_path,
        "chosen.yaml",
        "vellric:\n  local_only: false\n  vision:\n"
        "    provider: openai\n    model: chosen\n    fallback_model: fallback\n"
        "    api_key: !env SYNTHETIC_KEY\n",
    )
    for field, value in (
        ("--vision-provider", "openai"),
        ("--vision-base-url", "https://example.invalid/v1"),
        ("--vision-region", "us-west-2"),
    ):
        parsed = cli.parser().parse_args(arguments(tmp_path, "--config", str(chosen), field, value))
        assert parsed.vision_api_key_env is None
        explicit = cli.parser().parse_args(
            arguments(
                tmp_path,
                "--config",
                str(chosen),
                field,
                value,
                "--vision-api-key-env",
                "EXPLICIT_SYNTHETIC_KEY",
            )
        )
        assert explicit.vision_api_key_env == "EXPLICIT_SYNTHETIC_KEY"
    restricted = config(tmp_path, "restricted.yaml", "vellric: {local_only: true}\n")
    settings = []
    for provider in ("anthropic", "openai", "bedrock", "command"):
        for extra in (["--local-only"], ["--config", str(restricted)]):
            settings.append(
                vars(
                    cli.parser().parse_args(
                        arguments(
                            tmp_path, "--config", str(chosen), *extra, "--vision-provider", provider
                        )
                    )
                )
            )

    class NoCredentials(dict):
        def get(self, *args):
            raise AssertionError("credential lookup before local-only refusal")

        def __getitem__(self, key):
            raise AssertionError("credential read before local-only refusal")

        def __iter__(self):
            raise AssertionError("credential iteration")

        def keys(self):
            raise AssertionError("credential keys")

        def items(self):
            raise AssertionError("credential items")

        def values(self):
            raise AssertionError("credential values")

        def copy(self):
            raise AssertionError("credential copy")

    with monkeypatch.context() as patch:
        patch.setattr(os, "environ", NoCredentials({"SYNTHETIC_KEY": "SYNTHETIC_VALUE"}))
        # Isolate the leaf guarantee from argparse's legitimate locale/environment handling.
        loaded = load([chosen])
        assert loaded.validate(vellric_schema, path=("vellric",))["vision"]["model"] == "chosen"
        for options in settings:
            with pytest.raises(JobError, match="Local-only conversion forbids") as caught:
                cli.validate_options(options)
            assert caught.value.exit_code == 2


def test_configured_native_bundle_excludes_paths_and_references(tmp_path):
    chosen = config(
        tmp_path,
        "private-settings.yaml",
        f"""vellric:
  local_only: true
  ocr: {{mode: never, preflight: off, tessdata_dir: {json.dumps(str(tmp_path))}}}
  path: {json.dumps(str(tmp_path))}
  temp_dir: {json.dumps(str(tmp_path))}
  status_json: true
  progress: none
""",
    )
    source, out = tmp_path / "input.pdf", tmp_path / "out"
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Configuration preserves native text.")
        document.save(source)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vellric",
            *arguments(
                tmp_path,
                "--config",
                str(chosen),
                "--config-root",
                str(tmp_path),
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["settings"]["local_only"] is True
    assert not {"config", "config_root", "vision_api_key_env"} & manifest["settings"].keys()
    assert (out / "pages/000001/text.txt").read_text() == "Configuration preserves native text.\n"
    assert str(chosen).encode() not in b"".join(
        p.read_bytes() for p in out.rglob("*") if p.is_file()
    )


def test_installed_wheel_composes_outside_checkout(tmp_path):
    """Install a real wheel and locked dependencies from the exact public Git source."""
    project = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    assert uv is not None

    def run(*argv):
        result = subprocess.run(argv, cwd=tmp_path, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, (
            "Installed-wheel proof requires the locked public runtime/build sources.\n"
            + result.stdout
            + result.stderr
        )
        return result.stdout

    wheelhouse = tmp_path / "wheels"
    run(
        uv,
        "build",
        "--python",
        sys._base_executable,
        "--wheel",
        str(project),
        "--out-dir",
        str(wheelhouse),
    )
    (wheel,) = wheelhouse.glob("*.whl")
    constraints = tmp_path / "locked.txt"
    run(
        uv,
        "export",
        "--python",
        sys._base_executable,
        "--project",
        str(project),
        "--locked",
        "--no-dev",
        "--no-emit-project",
        "--no-hashes",
        "--output-file",
        str(constraints),
    )
    environment = tmp_path / "installed"
    run(uv, "venv", "--python", sys._base_executable, str(environment))
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run(
        uv,
        "pip",
        "install",
        "--python",
        str(python),
        "--constraints",
        str(constraints),
        str(wheel),
    )
    chosen = config(
        tmp_path, "chosen.yaml", "vellric: {vision: {provider: openai, model: installed}}\n"
    )
    script = tmp_path / "caller.py"
    script.write_text(
        "import json, sys\nfrom pathlib import Path\nfrom importlib.metadata import requires\n"
        "import vellric, conric\nfrom conric import load\n"
        "from vellric.configuration import vellric_schema\n"
        "from vellric.cli import parser, validate_options\nfrom vellric.runtime import JobError\n"
        "settings = load([sys.argv[1]]).validate(vellric_schema, path=('vellric',))\n"
        "p = parser().parse_args(['convert','missing.pdf','--out','out','--config',sys.argv[1],"
        "'--local-only'])\n"
        "try:\n    validate_options(vars(p))\nexcept JobError as e:\n    refusal = e.exit_code\n"
        "else:\n    refusal = 0\n"
        "print(json.dumps({'model': settings['vision']['model'], 'refusal': refusal,"
        "'vellric': vellric.__file__, 'conric': conric.__file__, "
        "'requirements': requires('vellric')}))\n",
        encoding="utf-8",
    )
    observed = json.loads(run(str(python), "-I", str(script), str(chosen)))
    assert (observed["model"], observed["refusal"]) == ("installed", 2)
    assert not Path(observed["vellric"]).is_relative_to(project)
    assert not Path(observed["conric"]).is_relative_to(project.parent.parent / "conric")
    assert any(
        "conric@git+https://github.com/wolfmcnally/conric.git@"
        "ed9286297e92b8c049f70eb15a3b5556ed107ff0" == "".join(item.split())
        for item in observed["requirements"]
    )


@pytest.mark.parametrize("section", ['vision: {pages: "1-2"}'])
def test_yaml_does_not_change_cli_vision_admission(tmp_path, monkeypatch, section):
    chosen = config(tmp_path, "config.yaml", f"vellric: {{{section}}}\n")
    monkeypatch.setenv("VISION_TEST_KEY", "synthetic")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "synthetic")
    common = arguments(tmp_path, "--config", str(chosen))
    for location in (
        ["--vision-base-url", "http://example.invalid"],
        ["--vision-region", "eusc-de-east-1"],
    ):
        options = vars(
            cli.parser().parse_args(
                [
                    *common,
                    "--vision-provider",
                    "bedrock",
                    "--vision-model",
                    "global.example.profile",
                    "--vision-api-key-env",
                    "VISION_TEST_KEY",
                    *location,
                ]
            )
        )
        cli.validate_options(options)
        assert options["vision_region"] == (
            "eusc-de-east-1" if location[0] == "--vision-region" else None
        )
    default_key = vars(
        cli.parser().parse_args(
            [
                *common,
                "--vision-provider",
                "bedrock",
                "--vision-model",
                "global.example.profile",
                "--vision-region",
                "us-west-2",
            ]
        )
    )
    cli.validate_options(default_key)
    assert default_key["vision_api_key_env"] == "AWS_BEARER_TOKEN_BEDROCK"
    monkeypatch.chdir(tmp_path)
    relative = vars(
        cli.parser().parse_args(
            [
                *common,
                "--vision-provider",
                "command",
                "--vision-command",
                Path(sys.executable).name,
            ]
        )
    )
    executable = tmp_path / Path(sys.executable).name
    executable.write_bytes(b"synthetic")
    executable.chmod(0o755)
    cli.validate_options(relative)
    assert relative["vision_command"] == str(executable)


def test_cli_sigv4_uses_default_chain_with_ocr_yaml(tmp_path, monkeypatch):
    chosen = config(tmp_path, "config.yaml", "vellric: {ocr: {mode: never}}\n")
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda name: object())
    seen = []

    def signing_credentials(*, explicit_config):
        seen.append(explicit_config)
        return ("synthetic-access", "synthetic-secret", None)

    monkeypatch.setattr(vision, "signing_credentials", signing_credentials)
    options = vars(
        cli.parser().parse_args(
            arguments(
                tmp_path,
                "--config",
                str(chosen),
                "--vision-provider",
                "bedrock",
                "--vision-model",
                "amazon.nova-lite-v1:0",
                "--vision-region",
                "us-west-2",
                "--vision-transport",
                "sigv4",
            )
        )
    )
    cli.validate_options(options)
    assert cli.vision_settings(options, tmp_path)["transport"] == "sigv4"
    assert seen == [False]
