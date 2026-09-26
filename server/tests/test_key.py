from server.engine.key import estimate_key
from server.tests.synth import SR, progression


def test_c_major_cadence():
    y = progression([([0, 4, 7], 1.5, 0), ([5, 9, 0], 1.5, 5), ([7, 11, 2], 1.5, 7), ([0, 4, 7], 1.5, 0)])
    assert estimate_key(y, SR) == "C:maj"


def test_a_minor_cadence():
    y = progression([([9, 0, 4], 1.5, 9), ([2, 5, 9], 1.5, 2), ([4, 8, 11], 1.5, 4), ([9, 0, 4], 1.5, 9)])
    assert estimate_key(y, SR) == "A:min"
