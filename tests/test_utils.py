import os
import unittest

from whatsopt.utils import load_from_csv, is_user_file, find_analysis_base_files


class TestUtils(unittest.TestCase):
    def test_load_from_csv(self):
        filepath = os.path.join(os.path.dirname(__file__), "cases.csv")
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

if __name__ == "__main__":
    unittest.main()
