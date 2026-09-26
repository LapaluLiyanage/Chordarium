"""Align chord boundaries to beats and clean up tiny / duplicate segments."""
import numpy as np


def merge_identical(segments: list[dict]) -> list[dict]:
    out: list[dict] = []
    for s in segments:
        if out and out[-1]["label"] == s["label"]:
            prev = out[-1]
            d1, d2 = prev["end"] - prev["start"], s["end"] - s["start"]
            if d1 + d2 > 0:
                prev["confidence"] = round((prev["confidence"] * d1 + s["confidence"] * d2) / (d1 + d2), 6)
            prev["end"] = s["end"]
        else:
            out.append(dict(s))
    return out


def _merge_short(segments: list[dict], min_len: float) -> list[dict]:
    segs = [dict(s) for s in segments]
    while len(segs) > 1:
        lengths = [s["end"] - s["start"] for s in segs]
        i = int(np.argmin(lengths))
        if lengths[i] >= min_len - 1e-6:
            break
        if i == 0:
            j = 1
        elif i == len(segs) - 1:
            j = i - 1
        else:
            j = i - 1 if segs[i - 1]["confidence"] >= segs[i + 1]["confidence"] else i + 1
        if j < i:
            segs[j]["end"] = segs[i]["end"]
        else:
            segs[j]["start"] = segs[i]["start"]
        del segs[i]
    return segs


def snap_segments(segments: list[dict], beats: list[float]) -> list[dict]:
    if not segments:
        return []
    if len(beats) < 2:
        return merge_identical([dict(s) for s in segments])
    b = np.asarray(beats, dtype=float)
    bounds = [segments[0]["start"]]
    for s in segments[1:]:
        bounds.append(float(b[np.abs(b - s["start"]).argmin()]))
    bounds.append(segments[-1]["end"])
    for i in range(1, len(bounds)):
        bounds[i] = max(bounds[i], bounds[i - 1])
    snapped = []
    for i, s in enumerate(segments):
        if bounds[i + 1] - bounds[i] > 1e-6:
            snapped.append({**s, "start": bounds[i], "end": bounds[i + 1]})
    min_len = float(np.median(np.diff(b)))
    return merge_identical(_merge_short(snapped, min_len))
