from amuse.db.helpers import dict_to_choices


def test_dict_to_choices():
    input = {'foo': 1, 'bar': 2, 'baz': 3}
    expected = [('foo', 1), ('bar', 2), ('baz', 3)]
    assert dict_to_choices(input) == expected
