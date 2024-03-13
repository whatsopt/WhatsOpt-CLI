import os
import unittest
from openmdao.api import CaseReader

from whatsopt.upload_utils import (
    load_from_csv,
    load_from_sqlite,
    load_from_hdf5,
    _format_upload_cases,
    _check_count,
)

GEMSEO_INSTALLED = True
try:
    import gemseo  # noqa: F401
except ImportError:
    GEMSEO_INSTALLED = False


class TestUploadUtils(unittest.TestCase):
    DATA_PATH = os.path.join(os.path.dirname(__file__), "data")

    def test_load_from_csv(self):
        filepath = os.path.join(TestUploadUtils.DATA_PATH, "test_doe.csv")
        name, cases, statuses = load_from_csv(filepath)
        self.assertEqual("test_doe", name)
        self.assertEqual("x", cases[0]["varname"])
        self.assertEqual(-1, cases[0]["coord_index"])
        self.assertEqual(7.5, cases[0]["values"][4])
        self.assertEqual(1, statuses[0])

    def test_load_from_sqlite(self):
        filepath = os.path.join(TestUploadUtils.DATA_PATH, "test_doe.sqlite")
        name, cases, statuses = load_from_sqlite(filepath)
        self.assertEqual("SMT_DOE_LHS", name)
        self.assertEqual(6.87783, round(cases[0]["values"][2], 5))
        self.assertEqual("z", cases[1]["varname"])
        self.assertEqual(1, cases[2]["coord_index"])
        for i in statuses:
            self.assertEqual(1, i)

    @unittest.skipUnless(GEMSEO_INSTALLED, "GEMSEO not installed")
    def test_load_from_hdf5(self):
        filepath = os.path.join(TestUploadUtils.DATA_PATH, "test_doe.hdf5")
        name, cases, statuses = load_from_hdf5(filepath)
        self.assertEqual("GEMSEO_DOE_ALGO", name)
        self.assertEqual(9.94343, round(cases[0]["values"][2], 5))
        self.assertEqual("z", cases[2]["varname"])
        self.assertEqual(1, cases[2]["coord_index"])
        for i in statuses:
            self.assertEqual(1, i)

    @unittest.skip(
        "Test data obsolete! Has to be regenerated running run_doe --parallel with openmdao MPI"
    )
    def test_load_from_parallel_sqlite(self):
        filepath = os.path.join(TestUploadUtils.DATA_PATH, "test_parallel_doe.sqlite_0")
        name, cases, statuses = load_from_sqlite(filepath)
        self.assertEqual("SMT_DOE_LHS", name)
        n = len(cases[0]["values"])
        self.assertEqual(
            50, n
        )  # supposedly run with 150 cases on 3 processors, hence 50
        self.assertEqual(n, len(statuses))

        _, cases2, statuses2 = load_from_sqlite(filepath, parallel=True)
        self.assertEqual(3 * n, len(cases2[0]["values"]))
        self.assertEqual(3 * n, len(statuses2))

        filepath1 = os.path.join(
            TestUploadUtils.DATA_PATH, "test_parallel_doe.sqlite_1"
        )
        _, cases2, statuses2 = load_from_sqlite(filepath1, parallel=True)
        self.assertEqual(2 * n, len(cases2[0]["values"]))
        self.assertEqual(2 * n, len(statuses2))

    def test_check_count(self):
        dict1 = {"A": [1, 2], "B": [3, 4], "C": [5, 6]}
        dict2 = {"A": [1, 2], "B": [3, 4], "C": [5, 6, 7]}
        self.assertEqual(2, _check_count(dict1))
        self.assertRaises(Exception, _check_count, dict2)

    def test_format_upload_cases(self):
        data, statuses = _format_upload_cases(
            CaseReader(os.path.join(TestUploadUtils.DATA_PATH, "test_doe.sqlite"))
        )
        print(data)
        self.assertEqual(6.87783, round(data[0]["values"][2], 5))
        self.assertEqual("z", data[1]["varname"])
        self.assertEqual(1, data[2]["coord_index"])
        for i in statuses:
            self.assertEqual(1, i)
