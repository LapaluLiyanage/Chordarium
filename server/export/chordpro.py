"""ChordPro (.cho) export using a bar grid section."""
from server.export.grid import ExportOptions, build_bars, grid_lines, header


def to_chordpro(timeline: dict, opts: ExportOptions) -> str:
    h = header(timeline, opts)
    lines = [f"{{title: {h['title']}}}", f"{{key: {h['key_symbol']}}}", f"{{tempo: {h['tempo']}}}"]
    if h["capo"]:
        lines.append(f"{{capo: {h['capo']}}}")
    lines += ["", "{start_of_grid}", *grid_lines(build_bars(timeline, opts), opts.bars_per_row), "{end_of_grid}"]
    return "\n".join(lines) + "\n"
