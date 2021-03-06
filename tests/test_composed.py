from wex.composed import composable, ComposedCallable


@composable
def squared(x):
    return x * x


def add_1(x):
    return x + 1


def test_composable():
    func = squared | add_1
    assert func(2) == 5


def test_composable_on_rhs():
    func = int | squared
    assert func('2') == 4


def test_composing_composed():
    func = squared | squared | squared
    assert func(2) == 256


def test_repr():
    func = squared | squared
    assert repr(func).startswith('<wex.composed.ComposedCallable(')


def test_composed_callable_identity():
    # For the record and empty composed function is the identity function
    func = ComposedCallable()
    obj = object()
    assert func(obj) is obj
