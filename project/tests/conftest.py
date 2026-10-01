# Copyright (c) 2026 Wolf McNally; adapted from Drawbridge MIT fixtures.
from pathlib import Path

import pymupdf
import pytest

EXPECTED = """### Annual Report

#### Findings

The committee met on nine occasions during the year and heard from forty witnesses, whose evidence is set out below in full.

It found the **central claim** to be *unsupported* by `run_check()`.

- first exhibit
- second exhibit

See the [archive](https://example.org/archive) for more.

| Year | Hearings | Witnesses |
| --- | --- | --- |
| 2019 | 4 | 17 |
| 2020 | 5 | 23 |

Jane Example
Clerk of the Committee
12 Long Example Street North"""  # noqa: E501 — exact inherited golden


def _styled(page, origin, pieces, size=11):
    x, y = origin
    for text, font in pieces:
        page.insert_text((x, y), text, fontname=font, fontsize=size)
        x += pymupdf.get_text_length(text, fontname=font, fontsize=size)


def _rich_page(page) -> None:
    page.insert_text((72, 80), "Annual Report", fontname="hebo", fontsize=20)
    page.insert_text((72, 110), "Findings", fontname="helv", fontsize=15)
    y = 140
    for line in [
        "The committee met on nine occasions during the year and",
        "heard from forty witnesses, whose evidence is set out",
        "below in full.",
    ]:
        page.insert_text((72, y), line, fontname="helv", fontsize=11)
        y += 14
    y += 10
    _styled(
        page,
        (72, y),
        [
            ("It found the ", "helv"),
            ("central claim", "hebo"),
            (" to be ", "helv"),
            ("unsupported", "heit"),
            (" by ", "helv"),
            ("run_check()", "cour"),
            (".", "helv"),
        ],
    )
    y += 24
    for item in ["• first exhibit", "• second exhibit"]:
        page.insert_text((72, y), item, fontname="helv", fontsize=11)
        y += 14
    y += 10
    page.insert_text((72, y), "See the archive for more.", fontname="helv", fontsize=11)
    lead = pymupdf.get_text_length("See the ", fontname="helv", fontsize=11)
    word = pymupdf.get_text_length("archive", fontname="helv", fontsize=11)
    page.insert_link(
        {
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(72 + lead, y - 10, 72 + lead + word, y + 3),
            "uri": "https://example.org/archive",
        }
    )
    y += 30
    rows = [["Year", "Hearings", "Witnesses"], ["2019", "4", "17"], ["2020", "5", "23"]]
    shape = page.new_shape()
    for r in range(len(rows) + 1):
        shape.draw_line((72, y + r * 20), (372, y + r * 20))
    for c in range(4):
        shape.draw_line((72 + c * 100, y), (72 + c * 100, y + len(rows) * 20))
    shape.finish(color=(0, 0, 0))
    shape.commit()
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            page.insert_text((78 + c * 100, y + r * 20 + 14), cell, fontname="helv", fontsize=11)
    y += 90
    for line in ["Jane Example", "Clerk of the Committee", "12 Long Example Street North"]:
        page.insert_text((72, y), line, fontname="helv", fontsize=11)
        y += 14


@pytest.fixture
def rich_pdf(tmp_path: Path) -> Path:
    target = tmp_path / "report.pdf"
    with pymupdf.open() as document:
        _rich_page(document.new_page())
        document.new_page().insert_text(
            (72, 80), "A plain second page.", fontname="helv", fontsize=11
        )
        document.save(target)
    return target
