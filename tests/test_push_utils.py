import os
import unittest
import numpy as np

from whatsopt.push_utils import (
    build_variable_name,
    simple_value,
    format_shape,
    to_camelcase,
    extract_mda_var,
    problem_pyfile,
)


class TestPushUtils(unittest.TestCase):
    DATA_PATH = os.path.join(os.path.dirname(__file__), "data")

    def test_format_shape(self):
        self.assertEqual("_file", format_shape(False, "L_file"))
        self.assertEqual("1", format_shape(True, "(1,)"))

    def test_to_camelcase(self):
        self.assertEqual("ToCamelCase", to_camelcase("to_camel_case"))
        self.assertEqual("Camel", to_camelcase("camel"))

    def test_simple_value(self):
        dict1 = {"type": "Integer", "shape": "1", "value": 1}
        dict2 = {"type": "Float", "shape": "(1,)", "value": 1.2}
        dict3 = {"type": "Float", "shape": None, "value": np.array(["1.2", "2.3"])}
        self.assertEqual("1", simple_value(dict1))
        self.assertEqual("1.2", simple_value(dict2))
        self.assertEqual("[1.2, 2.3]", simple_value(dict3))

    def test_extract_mda_var(self):
        val1, val2 = extract_mda_var("a.b.c.d")
        self.assertEqual(["a", "b", "c"], val1)
        self.assertEqual("d", val2)
        # raise Exception
        self.assertRaises(Exception, extract_mda_var, "a")

    def test_generate_problem_pyfile(self):
        with problem_pyfile(
            os.path.join(self.DATA_PATH, "disc1.py"), "Disc1"
        ) as pbfile:
            self.assertTrue(os.path.exists(pbfile))
            self.assertTrue(os.system("python {}".format(pbfile)) == 0)
        self.assertFalse(os.path.exists(pbfile))

    def test_build_varname(self):
        name = build_variable_name("12", "ab", 7)
        self.assertEqual("12==ab", name)
        name = build_variable_name("123456789", "abcdefghi", 11)
        self.assertEqual("...bcdefghi", name)
        name = build_variable_name("123456789", "abcdefghi", 12)
        self.assertEqual("1...9==a...i", name)
        name = build_variable_name("123456789", "abcdefghi", 13)
        self.assertEqual("1...9==a...i", name)
        name = build_variable_name("123456789", "abcdefghi", 14)
        self.assertEqual("1...9==a...i", name)
        name = build_variable_name("123456789", "abcdefghi", 15)
        self.assertEqual("1...9==a...i", name)
        name = build_variable_name("123456789", "abcdefghi", 16)
        self.assertEqual("12...89==ab...hi", name)
        name = build_variable_name("123456789", "abcdefghi", 17)
        self.assertEqual("12...89==ab...hi", name)
        name = build_variable_name("123456789", "abcdefghi", 18)
        self.assertEqual("12...89==ab...hi", name)
        name = build_variable_name("123456789", "abcdefghi", 19)
        self.assertEqual("12...89==ab...hi", name)
        name = build_variable_name("123456789", "abcdefghi", 20)
        self.assertEqual("123456789==abcdefghi", name)
