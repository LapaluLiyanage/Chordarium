"""The TypeScript port (client/src/theory/chord.ts) runs these same cases."""
import json
from pathlib import Path

import pytest

from server.theory import chord as ch

CASES = json.loads((Path(__file__).resolve().parents[2] / "shared" / "chord_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["render"], ids=lambda c: c["label"])
def test_render(case):
    assert ch.render(case["label"], transpose_by=case.get("transpose", 0), capo=case.get("capo", 0),
                     simplify_chord=case.get("simplify", False), prefer_flats=case.get("prefer_flats", False),
                     tonic=case.get("tonic")) == case["expected"]


@pytest.mark.parametrize("case", CASES["notes"], ids=lambda c: c["label"])
def test_notes(case):
    assert ch.note_names(ch.parse(case["label"]), tonic=case.get("tonic")) == case["expected"]


@pytest.mark.parametrize("case", CASES["key_spelling"], ids=lambda c: c["key"])
def test_key_spelling(case):
    assert ch.key_spelling(case["key"], case["transpose"]) == case["expected"]


@pytest.mark.parametrize("case", CASES["format_key"], ids=lambda c: c["key"])
def test_format_key(case):
    assert ch.format_key(case["key"], case["transpose"]) == case["expected"]
