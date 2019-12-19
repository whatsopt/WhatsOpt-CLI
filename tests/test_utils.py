import os
import unittest

from whatsopt.utils import load_from_csv


class TestUtils(unittest.TestCase):
    def test_load_from_csv(self):
        filepath = os.path.join(os.path.dirname(__file__), "cases.csv")
        name, cases, statuses = load_from_csv(filepath)
        self.assertEqual("cases", name)
        self.assertEqual("x", cases[0]["varname"])
        self.assertEqual(-1, cases[0]["coord_index"])
        self.assertEqual(7.5, cases[0]["values"][4])
        self.assertEqual(1, statuses[0])


if __name__ == "__main__":
    unittest.main()
