from __future__ import annotations

import copy
import json
from pathlib import Path

import bleach
import jsonschema
import pymupdf
import pytest
from markdown_it import MarkdownIt
from PIL import Image

from vellric import cli, runtime
from vellric.citations import CONTRACT, anchor_markup, page_anchor
from vellric.worker import load_prior, reader


def convert(source, out, command="inspect", *options):
    assert cli.main([command, str(source), "--out", str(out), "--status-json", *options]) == 0
    return json.loads((out / "manifest.json").read_text())


@pytest.fixture
def pdf(tmp_path):
    source = tmp_path / "pages.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((40, 40), "Repeated text")
        document.new_page()
        document.new_page().insert_text((40, 40), "Repeated text")
        document[2].set_rotation(90)
        document.set_page_labels([{"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1}])
        document.save(source)
    return source


def test_original_physical_mapping_and_independent_consumer(pdf, tmp_path):
    out = tmp_path / "bundle"
    manifest = convert(pdf, out)
    digest = runtime.digest(pdf)
    assert manifest["schema"] == "vellric.document/1.1"
    assert manifest["page_citations"] == {"schema": CONTRACT}
    markdown = (out / "document.md").read_text()
    with pymupdf.open(pdf) as document:
        for number, page in enumerate(manifest["pages"], 1):
            # Independent consumer algorithm: no Vellric helper or Markdown parsing.
            expected = f"vellric-pdf-{digest}-page-{number:06d}"
            assert page["anchor"] == expected
            markup = f'<a id="{expected}"></a>'
            assert markdown.count(markup) == 1
            assert f"{markup}\n\n## Page {number}\n" in markdown
            assert (out / page["files"]["native"]).read_text() == document[number - 1].get_text()
    assert (out / manifest["pages"][1]["files"]["text"]).read_bytes() == b""
    assert "## Page 2\n\n[No text recovered" in markdown
    schema = json.loads((Path(__file__).parents[1] / "docs/document.schema.json").read_text())
    jsonschema.validate(manifest, schema)
    runtime.validate_bundle(out, manifest)
    again = convert(pdf, tmp_path / "again", "convert", "--ocr", "never", "--preflight", "off")
    assert [p["anchor"] for p in again["pages"]] == [p["anchor"] for p in manifest["pages"]]
    # A legal trailing PDF comment changes exact bytes without changing its pages.
    different = tmp_path / "different.pdf"
    different.write_bytes(pdf.read_bytes() + b"\n% revised snapshot\n")
    revised = convert(different, tmp_path / "revised")
    assert all(a["anchor"] != b["anchor"] for a, b in zip(manifest["pages"], revised["pages"]))


@pytest.mark.parametrize(
    "damage", ["missing", "contract", "anchor", "digest", "ordinal", "float", "non-object", "old"]
)
def test_mapping_tamper_refuses(pdf, tmp_path, damage):
    # The public bundle boundary includes typed page order as well as citation metadata.
    out = tmp_path / "bundle"
    manifest = convert(pdf, out)
    bad = copy.deepcopy(manifest)
    if damage == "missing":
        del bad["page_citations"]
    elif damage == "contract":
        bad["page_citations"]["schema"] += "unknown"
    elif damage == "anchor":
        bad["pages"][0]["anchor"] = bad["pages"][1]["anchor"]
    elif damage == "digest":
        bad["source"]["sha256"] = "f" * 64
    elif damage == "ordinal":
        bad["pages"][0]["number"] = True
    elif damage == "float":
        bad["pages"][0]["number"] = 1.0
    elif damage == "non-object":
        bad["pages"] = [1]
    else:
        bad["schema"] = "vellric.document/1.0"
    with pytest.raises(runtime.JobError) as error:
        runtime.validate_bundle(out, bad)
    assert error.value.code == "artifact-invalid"


def test_images_do_not_claim_pdf_pages(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (30, 40), "white").save(source)
    out = tmp_path / "image"
    manifest = convert(source, out, "image")
    assert "page_citations" not in manifest and "anchor" not in manifest["pages"][0]
    schema = json.loads((Path(__file__).parents[1] / "docs/document.schema.json").read_text())
    jsonschema.validate(manifest, schema)
    for ordinal in (True, 1.0):
        malformed = copy.deepcopy(manifest)
        malformed["pages"][0]["number"] = ordinal
        with pytest.raises(runtime.JobError, match="page count/order"):
            runtime.validate_bundle(out, malformed)
    manifest["page_citations"] = {"schema": CONTRACT}
    with pytest.raises(runtime.JobError, match="citation"):
        runtime.validate_bundle(out, manifest)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, schema)


def test_old_amend_base_refuses_at_amend_boundary(pdf, tmp_path):
    out = tmp_path / "base"
    manifest = convert(pdf, out, "convert", "--ocr", "never", "--preflight", "off")
    manifest["schema"] = "vellric.document/1.0"
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(runtime.JobError) as error:
        load_prior(out, {"sha256": runtime.digest(pdf), "size": pdf.stat().st_size}, 3)
    assert error.value.code == "artifact-invalid" and error.value.stage == "amend"
    assert "not a valid complete bundle" in str(error.value)


def test_raw_markdown_and_actual_renderer_sanitizer_limits():
    digest = "a" * 64
    anchor = page_anchor(digest, 1)
    markdown = reader("Title", ["Text", ""], digest)
    html = MarkdownIt("commonmark", {"html": True}).render(markdown)
    assert f'<p><a id="{anchor}"></a></p>' in html
    escaped = MarkdownIt("commonmark", {"html": False}).render(markdown)
    assert f'<a id="{anchor}">' not in escaped
    assert f"&lt;a id=&quot;{anchor}&quot;&gt;&lt;/a&gt;" in escaped
    assert f'id="{anchor}"' not in bleach.clean(html)
    retained = bleach.clean(html, tags={"a", "p", "h1", "h2"}, attributes={"a": ["id"]})
    assert f'id="{anchor}"' in retained
    # These are explicit presentation limitations, not a claimed sanitizer boundary.
    second = page_anchor(digest, 2)
    hostile = reader("Title", [anchor_markup(second) + "\n\n```\nunclosed", "Next"], digest)
    rendered = MarkdownIt("commonmark", {"html": True}).render(hostile)
    assert rendered.count(f'<a id="{second}">') == 1  # source preempts generated anchor
    assert f"&lt;a id=&quot;{second}&quot;&gt;" in rendered  # generated one is inside the fence
    assert hostile.count(anchor_markup(second)) == 2
    assert "```\nunclosed" in hostile


@pytest.mark.parametrize(
    "digest,number", [("A" * 64, 1), ('a" onclick="x', 1), ("a" * 64, True), ("a" * 64, 0)]
)
def test_only_exact_generated_identity_enters_markup(digest, number):
    with pytest.raises(ValueError):
        page_anchor(digest, number)


def test_large_ordinal_never_truncates():
    assert page_anchor("a" * 64, 1000000).endswith("-page-1000000")


@pytest.mark.parametrize(
    "anchor",
    [
        'x" onclick="y',
        "vellric-pdf-" + "A" * 64 + "-page-000001",
        "vellric-pdf-" + "a" * 64 + "-page-00001",
    ],
)
def test_markup_rejects_non_generated_attribute_values(anchor):
    with pytest.raises(ValueError):
        anchor_markup(anchor)


def test_selected_render_keeps_original_physical_mapping(pdf, tmp_path):
    manifest = convert(pdf, tmp_path / "rendered", "render", "--pages", "2", "--dpi", "72")
    assert manifest["page_citations"] == {"schema": CONTRACT}
    assert [p["anchor"] for p in manifest["pages"]] == [
        f"vellric-pdf-{runtime.digest(pdf)}-page-{n:06d}" for n in (1, 2, 3)
    ]
    assert manifest["pages"][1]["renders"]
    assert "renders" not in manifest["pages"][0]
