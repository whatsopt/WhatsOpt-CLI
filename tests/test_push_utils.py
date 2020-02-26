import os
import unittest
import numpy as np

from whatsopt.push_utils import (
    simple_value,
    extract_disc_var,
    format_shape,
    to_camelcase,
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

    def test_extract_disc_var(self):
        val1, val2, val3 = extract_disc_var("a.b.c.d")
        self.assertEqual("a.b", val1)
        self.assertEqual("a.b.c", val2)
        self.assertEqual("d", val3)
        # raise Exception
        self.assertRaises(Exception, extract_disc_var, "a")
