"""The release boundary must refuse unjoined bytes and incomplete source materials."""

import hashlib
import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader("windows_release", str(ROOT / "bin/windows-release"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
RELEASE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(RELEASE)


def wheel(name, version, native=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        prefix = f"{name}-{version}.dist-info/"
        archive.writestr(prefix + "METADATA", f"Name: {name}\nVersion: {version}\n")
        archive.writestr(prefix + "WHEEL", "Tag: cp313-cp313-win_amd64\n")
        archive.writestr(
            prefix + "licenses/LICENSE", "Synthetic test license, not third-party material"
        )
        if native:
            archive.writestr("synthetic.pyd", b"synthetic native payload; never executed")
    return stream.getvalue()


def fixture(tmp_path):
    root = tmp_path / "source"
    project = root / "project"
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text('[project]\nname="vellric"\nversion="0.2.4"\n')
    data = {
        "vellric": wheel("vellric", "0.2.4"),
        "conric": wheel("conric", "0.1.0"),
        "demo": wheel("demo", "1.0", True),
    }
    source_bytes = b"synthetic source and build instructions"
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    digest = hashlib.sha256(data["demo"]).hexdigest()
    revision = "1" * 40
    (project / "uv.lock").write_text(f"""[[package]]
name="vellric"
version="0.2.4"
source={{editable="."}}
[[package]]
name="conric"
version="0.1.0"
source={{git="https://example.invalid/conric.git?rev={revision}#{revision}"}}
[[package]]
name="demo"
version="1.0"
source={{registry="https://pypi.org/simple"}}
sdist={{url="https://files.pythonhosted.org/demo.tar.gz",hash="sha256:{source_sha}"}}
wheels=[{{hash="sha256:{digest}"}}]
""")
    for args in [
        ["init", "-b", "master", "-q"],
        ["config", "user.name", "Synthetic"],
        ["config", "user.email", "synthetic@example.invalid"],
        ["add", "project"],
        ["commit", "-qm", "Synthetic fixture"],
        ["tag", "v0.2.4"],
    ]:
        subprocess.run(["git", "-C", str(root), *args], check=True)
    bundle = root / "input.zip"
    requirements = []
    with zipfile.ZipFile(bundle, "w") as archive:
        for name, content in data.items():
            version = {"vellric": "0.2.4", "conric": "0.1.0", "demo": "1.0"}[name]
            path = f"wheels/{name}-{version}-cp313-cp313-win_amd64.whl"
            archive.writestr(path, content)
            requirements.append(f"./{path} --hash=sha256:{hashlib.sha256(content).hexdigest()}")
        archive.writestr("requirements-wheels.txt", "\n".join(requirements) + "\n")
        archive.writestr(
            "SOURCE.txt", f"conric @ git+https://example.invalid/conric.git@{revision}\n"
        )
    report = RELEASE.inventory(bundle, root)
    report["native_probe"] = {"demo": "1.0"}
    proof = root / "provenance.json"
    proof.write_text(json.dumps(report))
    sources = root / "materials"
    sources.mkdir()
    (sources / "demo.tar.gz").write_bytes(source_bytes)
    declaration = {
        "status": "qualified",
        "notice": "Synthetic notice; no third-party or license authority claimed",
        "uv_lock_sha256": report["uv_lock_sha256"],
        "native_versions": {"demo": "1.0"},
        "native_wheels": {
            "demo": {
                "sha256": digest,
                "materials": ["demo.tar.gz"],
                "basis": "Synthetic test only; not a license authorization",
            }
        },
        "materials": [
            {
                "file": "demo.tar.gz",
                "sha256": source_sha,
                "upstream": "https://files.pythonhosted.org/demo.tar.gz",
                "purpose": "synthetic corresponding material",
            }
        ],
    }
    closure = root / "closure.json"
    closure.write_text(json.dumps(declaration))
    return root, bundle, closure, sources, proof, declaration


def test_release_zip_preserves_wheels_and_binds_sources_reproducibly(tmp_path):
    root, bundle, closure, sources, proof, _ = fixture(tmp_path)
    first = root / "first.zip"
    second = root / "second.zip"
    RELEASE.assemble(bundle, root, closure, sources, first, proof, "v0.2.4")
    RELEASE.assemble(bundle, root, closure, sources, second, proof, "v0.2.4")
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(bundle) as original, zipfile.ZipFile(first) as delivered:
        for name in original.namelist():
            assert delivered.read(name) == original.read(name)
        assert delivered.read("sources/demo.tar.gz") == (sources / "demo.tar.gz").read_bytes()
        assert json.loads(delivered.read("WINDOWS-RELEASE.json"))["native_probe"] == {"demo": "1.0"}
        assert (
            delivered.read("WINDOWS-NATIVE-NOTICES.txt")
            == b"Synthetic notice; no third-party or license authority claimed"
        )
        assert any(name.startswith("third-party-notices/") for name in delivered.namelist())
    with pytest.raises(ValueError, match="replacement"):
        RELEASE.assemble(bundle, root, closure, sources, first, proof, "v0.2.4")

    # The immutable builder's text writer uses native CRLF on Windows; keep
    # identity exact while accepting that transport newline, without stripping.
    with zipfile.ZipFile(bundle) as original:
        payload = {name: original.read(name) for name in original.namelist()}
    payload["SOURCE.txt"] = payload["SOURCE.txt"].replace(b"\n", b"\r\n")
    payload["requirements-wheels.txt"] = payload["requirements-wheels.txt"].replace(b"\n", b"\r\n")
    with zipfile.ZipFile(bundle, "w") as changed:
        for name, data in payload.items():
            changed.writestr(name, data)
    assert RELEASE.inventory(bundle, root)["release_source"] == RELEASE.git(
        root, "rev-parse", "HEAD"
    )
    payload["SOURCE.txt"] += b"\r\n"
    with zipfile.ZipFile(bundle, "w") as changed:
        for name, data in payload.items():
            changed.writestr(name, data)
    with pytest.raises(ValueError, match="Conric source declaration"):
        RELEASE.inventory(bundle, root)


def test_release_refuses_unqualified_or_unjoined_material_without_output(tmp_path):
    root, bundle, closure, sources, proof, original = fixture(tmp_path)
    output = root / "refused.zip"

    def refuse(message, tag="v0.2.4"):
        with pytest.raises(ValueError, match=message):
            RELEASE.assemble(bundle, root, closure, sources, output, proof, tag)
        assert not output.exists()

    for change, message in [
        ({"status": "pending"}, "basis remains unqualified"),
        ({"notice": ""}, "Closure notice companion is empty"),
        ({"uv_lock_sha256": "0" * 64}, "different dependency lock"),
        ({"native_versions": {"demo": "2.0"}}, "Native runtime versions differ"),
        ({"native_wheels": {}}, "cover every native distribution"),
        ({"materials": []}, "No corresponding source material"),
    ]:
        closure.write_text(json.dumps(original | change))
        refuse(message)
    closure.write_text(json.dumps(original))
    refuse("Requested release tag differs", tag="v0.2.5")
    original_proof = json.loads(proof.read_text())
    for key in ("raw_bundle_sha256", "release_source", "uv_lock_sha256"):
        proof.write_text(json.dumps(original_proof | {key: "0" * 64}))
        refuse("observation belongs to another artifact/source")
    proof.write_text(json.dumps(original_proof))
    for key, value, message in [
        ("sha256", "0" * 64, "Native wheel differs"),
        ("materials", ["absent.tar.gz"], "lacks material/basis"),
        ("basis", "", "lacks material/basis"),
        ("basis", "UNQUALIFIED: pending", "lacks material/basis"),
    ]:
        changed = json.loads(json.dumps(original))
        changed["native_wheels"]["demo"][key] = value
        closure.write_text(json.dumps(changed))
        refuse(message)
    for unsafe in ("../escape", "..\\escape", "C:escape"):
        changed = json.loads(json.dumps(original))
        changed["materials"][0]["file"] = unsafe
        closure.write_text(json.dumps(changed))
        refuse("Invalid closure material identity")
        with pytest.raises(ValueError, match="Invalid pinned primary-source material"):
            RELEASE.fetch(closure, root / "fetch")
    changed = json.loads(json.dumps(original))
    changed["materials"][0]["purpose"] = ""
    closure.write_text(json.dumps(changed))
    refuse("Missing or mismatched corresponding material")
    for url in ("http://files.pythonhosted.org/demo", "https://example.invalid/demo"):
        changed = json.loads(json.dumps(original))
        changed["materials"][0]["upstream"] = url
        closure.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match="Invalid pinned primary-source material"):
            RELEASE.fetch(closure, root / "fetch")
    changed = json.loads(json.dumps(original))
    changed["materials"][0]["file"] = "different.tar.gz"
    (sources / "different.tar.gz").write_bytes((sources / "demo.tar.gz").read_bytes())
    closure.write_text(json.dumps(changed))
    refuse("Locked source archive absent")
    closure.write_text(json.dumps(original))
    source_bytes = (sources / "demo.tar.gz").read_bytes()
    (sources / "demo.tar.gz").write_bytes(b"wrong bytes")
    refuse("mismatched")
    (sources / "demo.tar.gz").write_bytes(source_bytes)


def test_inventory_refuses_unlocked_or_unreleased_artifacts(tmp_path):
    root, bundle, closure, sources, proof, _ = fixture(tmp_path)
    original_bundle = bundle.read_bytes()
    with zipfile.ZipFile(io.BytesIO(original_bundle)) as z:
        payload = {n: z.read(n) for n in z.namelist()}

    def write_payload(changed):
        with zipfile.ZipFile(bundle, "w") as z:
            for name, data in changed.items():
                z.writestr(name, data)

    demo_name = next(n for n in payload if "/demo-" in n)
    for changed, message in [
        (payload | {demo_name: wheel("demo", "1.0", False)}, "Wheel hash is not in the exact lock"),
        (payload | {"SOURCE.txt": b"different source"}, "Conric source declaration"),
        (payload | {"requirements-wheels.txt": b""}, "Offline requirements"),
        (payload | {"../outside": b"hostile"}, "Unsafe or duplicate"),
    ]:
        write_payload(changed)
        with pytest.raises(ValueError, match=message):
            RELEASE.inventory(bundle, root)
    vellric_name = next(n for n in payload if "/vellric-" in n)
    with zipfile.ZipFile(io.BytesIO(payload[vellric_name])) as z:
        files = {n: z.read(n) for n in z.namelist()}
    for field, replacement, message in [
        ("licenses/LICENSE", None, "No retained license/notice material"),
        ("WHEEL", b"Tag: cp313-cp313-linux_x86_64\n", "not Windows x64 or portable"),
    ]:
        changed = dict(files)
        name = next(n for n in changed if n.endswith(field))
        if replacement is None:
            del changed[name]
        else:
            changed[name] = replacement
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            for name, data in changed.items():
                z.writestr(name, data)
        write_payload(payload | {vellric_name: stream.getvalue()})
        with pytest.raises(ValueError, match=message):
            RELEASE.inventory(bundle, root)
    bundle.write_bytes(original_bundle)
    project = root / "project/pyproject.toml"
    clean = project.read_bytes()
    project.write_bytes(clean + b"\n")
    with pytest.raises(ValueError, match="uncommitted changes"):
        RELEASE.inventory(bundle, root)
    project.write_bytes(clean)
    # Only a disposable synthetic repository is changed; real release refs remain untouched.
    subprocess.run(["git", "-C", str(root), "update-ref", "-d", "refs/tags/v0.2.4"], check=True)
    assert RELEASE.inventory(bundle, root)["release_source"] is None
    with pytest.raises(ValueError, match="requires an existing immutable source tag"):
        RELEASE.assemble(bundle, root, closure, sources, root / "refused.zip", proof, "v0.2.4")
    if sys.platform != "win32":
        with pytest.raises(ValueError, match="actual Windows installed-wheel environment"):
            RELEASE.probe_native()
