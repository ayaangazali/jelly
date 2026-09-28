from calc.mod_02 import is_even


def test_is_even():
    assert is_even(4)
    assert not is_even(7)
