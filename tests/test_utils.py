import os
import unittest
from openmdao.api import CaseReader
import numpy as np

from whatsopt.utils import (
    load_from_csv,
    is_user_file,
    format_shape,
    to_camelcase,
    find_analysis_base_files,
    extract_mda_id,
    check_count,
    load_from_sqlite,
    format_upload_cases,
    simple_value,
    extract_disc_var,
)


class TestUtils(unittest.TestCase):

    DATA_PATH = os.path.join(os.path.dirname(__file__), "data")

    def test_load_from_csv(self):
        filepath = os.path.join(TestUtils.DATA_PATH, "cases.csv")
        name, cases, statuses = load_from_csv(filepath)
        self.assertEqual("cases", name)
        self.assertEqual("x", cases[0]["varname"])
        self.assertEqual(-1, cases[0]["coord_index"])
        self.assertEqual(7.5, cases[0]["values"][4])
        self.assertEqual(1, statuses[0])

    def test_is_user_file(self):
        self.assertEqual(True, is_user_file("test.py"))
        self.assertEqual(False, is_user_file("test_base.py"))
        self.assertEqual(False, is_user_file("run_test.py"))

    def test_format_shape(self):
        self.assertEqual("_file", format_shape(False, "L_file"))
        self.assertEqual("1", format_shape(True, "(1,)"))

    def test_to_camelcase(self):
        self.assertEqual("ToCamelCase", to_camelcase("to_camel_case"))
        self.assertEqual("Camel", to_camelcase("camel"))

    def test_extract_mda_id(self):
        files = find_analysis_base_files(TestUtils.DATA_PATH)
        num = 0
        for f in files:
            num = extract_mda_id(os.path.join(TestUtils.DATA_PATH, f))
        self.assertEqual("213", num)

    def test_check_count(self):
        dict1 = {"A": [1, 2], "B": [3, 4], "C": [5, 6]}
        dict2 = {"A": [1, 2], "B": [3, 4], "C": [5, 6, 7]}
        self.assertEqual(2, check_count(dict1))
        self.assertRaises(Exception, check_count, dict2)

    def test_load_from_sqlite(self):
        name, cases, statuses = load_from_sqlite(
            os.path.join(TestUtils.DATA_PATH, "test_doe.sqlite")
        )
        self.assertEqual("SMT_DOE_LHS", name)
        self.assertEqual(19.52945, round(cases[0]["values"][4], 5))
        self.assertEqual(1, cases[2]["coord_index"])
        self.assertEqual("g2", cases[5]["varname"])
        for i in statuses:
            self.assertEqual(1, i)

    def test_format_upload_cases(self):
        data, statuses = format_upload_cases(
            CaseReader(os.path.join(TestUtils.DATA_PATH, "test_doe.sqlite"))
        )
        self.assertEqual(19.52945, round(data[0]["values"][4], 5))
        self.assertEqual("z", data[1]["varname"])
        self.assertEqual(1, data[2]["coord_index"])
        for i in statuses:
            self.assertEqual(1, i)

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


if __name__ == "__main__":
    unittest.main()
