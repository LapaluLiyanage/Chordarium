"""PDF chord sheet: header, bar grid, chord legend."""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from server.export.grid import HOLD, ExportOptions, build_bars, chord_legend, header

MARGIN = 18 * mm
ROW_H = 12 * mm


def to_pdf(timeline: dict, opts: ExportOptions) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    h = header(timeline, opts)
    c.setTitle(h["title"])

    y = height - MARGIN
    c.setFont("Helvetica-Bold", 20)
    c.drawString(MARGIN, y, h["title"])
    y -= 9 * mm
    meta = f"Key: {h['key_text']}   {h['tempo']} BPM"
    if h["capo"]:
        meta += f"   Capo {h['capo']}"
    c.setFont("Helvetica", 11)
    c.drawString(MARGIN, y, meta)
    y -= 12 * mm

    bars = build_bars(timeline, opts)
    col_w = (width - 2 * MARGIN) / opts.bars_per_row
    for i in range(0, len(bars), opts.bars_per_row):
        if y < MARGIN + ROW_H:
            c.showPage()
            y = height - MARGIN
        row = bars[i:i + opts.bars_per_row]
        for k, bar in enumerate(row):
            x = MARGIN + k * col_w
            c.line(x, y - ROW_H + 4 * mm, x, y + 3 * mm)
            slot_w = (col_w - 4) / len(bar)
            for s, slot in enumerate(bar):
                c.setFont("Helvetica" if slot == HOLD else "Helvetica-Bold", 12)
                c.drawString(x + 3 + s * slot_w, y - 3 * mm, slot)
        end_x = MARGIN + len(row) * col_w
        c.line(end_x, y - ROW_H + 4 * mm, end_x, y + 3 * mm)
        y -= ROW_H

    legend = chord_legend(timeline, opts)
    if legend:
        if y < MARGIN + 20 * mm:
            c.showPage()
            y = height - MARGIN
        y -= 4 * mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(MARGIN, y, "Chords")
        y -= 6 * mm
        c.setFont("Helvetica", 10)
        for symbol, notes in legend:
            if y < MARGIN:
                c.showPage()
                y = height - MARGIN
                c.setFont("Helvetica", 10)
            c.drawString(MARGIN, y, f"{symbol}:  {' '.join(notes)}")
            y -= 5 * mm

    c.save()
    return buf.getvalue()
