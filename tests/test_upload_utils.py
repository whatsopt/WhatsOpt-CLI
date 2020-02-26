import os
import unittest
from openmdao.api import CaseReader
import numpy as np

from whatsopt.upload_utils import (
    load_from_csv,
    load_from_sqlite,
    format_upload_cases,
    check_count,
)


class TestUploadUtils(unittest.TestCase):

    DATA_PATH = os.path.join(os.path.dirname(__file__), "data")

    def test_load_from_csv(self):
        filepath = os.path.join(TestUploadUtils.DATA_PATH, "cases.csv")
        name, cases, statuses = load_from_csv(filepath)
        self.assertEqual("cases", name)
        self.assertEqual("x", cases[0]["varname"])
        self.assertEqual(-1, cases[0]["coord_index"])
        self.assertEqual(7.5, cases[0]["values"][4])
        self.assertEqual(1, statuses[0])

    def test_load_from_sqlite(self):
        name, cases, statuses = load_from_sqlite(
            os.path.join(TestUploadUtils.DATA_PATH, "test_doe.sqlite")
        )
        self.assertEqual("SMT_DOE_LHS", name)
        self.assertEqual(9.30287, round(cases[0]["values"][4], 5))
        self.assertEqual(1, cases[1]["coord_index"])
        self.assertEqual("z", cases[1]["varname"])
        for i in statuses:
            self.assertEqual(1, i)

    def test_check_count(self):
        dict1 = {"A": [1, 2], "B": [3, 4], "C": [5, 6]}
        dict2 = {"A": [1, 2], "B": [3, 4], "C": [5, 6, 7]}
        self.assertEqual(2, check_count(dict1))
        self.assertRaises(Exception, check_count, dict2)

    def test_format_upload_cases(self):
        data, statuses = format_upload_cases(
            CaseReader(os.path.join(TestUploadUtils.DATA_PATH, "test_doe.sqlite"))
        )
        self.assertEqual(9.30287, round(data[0]["values"][4], 5))
        self.assertEqual("z", data[1]["varname"])
        self.assertEqual(1, data[1]["coord_index"])
        for i in statuses:
            self.assertEqual(1, i)
