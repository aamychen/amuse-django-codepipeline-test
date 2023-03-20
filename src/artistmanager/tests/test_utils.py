from django.test import TestCase
from artistmanager.utils import (
    is_splitable,
    remove_non_digits,
    parse_input_string_to_digits,
)


class TestUtils(TestCase):
    def test_is_splitable(self):
        case1 = "123"
        case2 = "1,2,5"
        case3 = "1;2;"
        status, separator = is_splitable(case1)
        self.assertFalse(status)
        status, separator = is_splitable(case2)
        self.assertTrue(status)
        self.assertEqual(separator, ',')
        status, separator = is_splitable(case3)
        self.assertTrue(status)
        self.assertEqual(separator, ';')

    def test_remove_no_digits(self):
        test_list = ['1', '2', 'a', 'b']
        cleared = remove_non_digits(test_list)
        self.assertTrue('a' not in cleared)
        self.assertTrue('b' not in cleared)
        self.assertEqual(len(cleared), 2)

    def test_parse_input_strings_to_digits(self):
        case1 = "1, 3, 5"
        case2 = "1;3;5"
        case3 = "xyz"
        case1_list = parse_input_string_to_digits(case1)
        case2_list = parse_input_string_to_digits(case2)
        case3_list = parse_input_string_to_digits(case3)
        self.assertEqual(len(case1_list), 3)
        self.assertEqual(len(case2_list), 3)
        self.assertEqual(case3_list, [])
