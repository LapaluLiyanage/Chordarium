from server.engine.snap import merge_identical, snap_segments


def seg(start, end, label, conf=0.8):
    return {"start": start, "end": end, "label": label, "alt": None, "confidence": conf}


BEATS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]


def test_boundaries_move_to_nearest_beat():
    out = snap_segments([seg(0.0, 1.12, "C:maj"), seg(1.12, 2.93, "G:maj"), seg(2.93, 4.0, "A:min")], BEATS)
    assert [(s["start"], s["end"]) for s in out] == [(0.0, 1.0), (1.0, 3.0), (3.0, 4.0)]


def test_short_segment_merges_into_more_confident_neighbour():
    out = snap_segments([seg(0.0, 1.0, "C:maj", 0.9), seg(1.0, 1.2, "E:min", 0.3),
                         seg(1.2, 2.0, "G:maj", 0.5)], BEATS)
    assert [s["label"] for s in out] == ["C:maj", "G:maj"]
    assert out[0]["end"] == out[1]["start"]


def test_two_boundaries_snap_to_same_beat():
    out = snap_segments([seg(0.0, 0.95, "C:maj"), seg(0.95, 1.05, "D:min"),
                         seg(1.05, 2.0, "G:maj")], BEATS)
    for a, b in zip(out, out[1:]):
        assert a["end"] == b["start"]
    assert all(s["end"] > s["start"] for s in out)
    assert out[0]["start"] == 0.0 and out[-1]["end"] == 2.0


def test_merge_identical_weights_confidence_by_duration():
    out = merge_identical([seg(0, 1, "C:maj", 1.0), seg(1, 4, "C:maj", 0.6), seg(4, 5, "G:maj")])
    assert len(out) == 2
    assert out[0]["end"] == 4
    assert abs(out[0]["confidence"] - 0.7) < 1e-6


def test_no_beats_only_merges_and_does_not_mutate():
    segs = [seg(0, 1, "C:maj"), seg(1, 2, "C:maj")]
    out = snap_segments(segs, [])
    assert len(out) == 1 and segs[0]["end"] == 1
