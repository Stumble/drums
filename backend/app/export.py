"""Engrave MusicXML to SVG/PDF, fully headless (no MuseScore install).

verovio renders MusicXML -> SVG pages; cairosvg + pypdf stitch those into a PDF.
All three are pip-installable and run server-side without a GUI.
"""

from __future__ import annotations

import io
from typing import List

# A4 in verovio's 1/10-mm units.
_PAGE_W = 2100
_PAGE_H = 2970


def musicxml_to_svgs(musicxml: str, scale: int = 40) -> List[str]:
    import verovio

    tk = verovio.toolkit()
    tk.setOptions({
        "scale": scale,
        "pageWidth": _PAGE_W,
        "pageHeight": _PAGE_H,
        "adjustPageHeight": False,
        "header": "none",
        "footer": "none",
        "breaks": "auto",
    })
    if not tk.loadData(musicxml):
        raise RuntimeError("verovio could not parse the MusicXML")
    return [tk.renderToSVG(p) for p in range(1, tk.getPageCount() + 1)]


def musicxml_to_pdf(musicxml: str) -> bytes:
    import cairosvg
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for svg in musicxml_to_svgs(musicxml):
        page_pdf = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))
        for page in PdfReader(io.BytesIO(page_pdf)).pages:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
