"""Plain-text chord sheet export."""
from server.export.grid import ExportOptions, build_bars, chord_legend, grid_lines, header


def to_txt(timeline: dict, opts: ExportOptions) -> str:
    h = header(timeline, opts)
    meta = f"Key: {h['key_text']} | Tempo: {h['tempo']} BPM"
    if h["capo"]:
        meta += f" | Capo: {h['capo']}"
    lines = [h["title"], "=" * len(h["title"]), meta, ""]
    lines += grid_lines(build_bars(timeline, opts), opts.bars_per_row)
    lines += ["", "Chords: " + ", ".join(symbol for symbol, _ in chord_legend(timeline, opts))]
    return "\n".join(lines) + "\n"
