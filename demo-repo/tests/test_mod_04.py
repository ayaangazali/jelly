from calc.mod_04 import to_fahrenheit


def test_to_fahrenheit():
    assert to_fahrenheit(100) == 212
    assert to_fahrenheit(0) == 32
