from xbar5090 import safety


def test_check_xbar_freq_bounds():
    safety.check_xbar_freq(0)
    safety.check_xbar_freq(205_000)
    try:
        safety.check_xbar_freq(2_000_000)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_check_msvdd_bounds():
    safety.check_msvdd(10_000)
    try:
        safety.check_msvdd(200_000)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_validated_ranges():
    assert safety.is_validated_xbar(205_000)
    assert safety.is_validated_xbar(235_000)
    assert not safety.is_validated_xbar(240_000)
    assert safety.is_validated_ratio(1.2)
    assert not safety.is_validated_ratio(1.3)
