from xbar5090 import prop_rels


def test_ratio_roundtrip():
    assert prop_rels.ratio_raw_to_float(prop_rels.DEFAULT_RATIO_RAW) == 0.89990234375
    assert prop_rels.ratio_float_to_raw(1.2) == int(round(1.2 * 65536))


def test_default_ratio_maps_to_hardware_default():
    assert prop_rels.ratio_float_to_raw(0.9) == prop_rels.DEFAULT_RATIO_RAW


def test_ratio_out_of_range():
    try:
        prop_rels.ratio_float_to_raw(3.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
