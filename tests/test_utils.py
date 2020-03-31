import os
import unittest

from whatsopt.utils import is_user_file, find_analysis_base_files, extract_mda_id


class TestUtils(unittest.TestCase):

    DATA_PATH = os.path.join(os.path.dirname(__file__), "data")

    def test_is_user_file(self):
        self.assertEqual(True, is_user_file("test.py"))
        self.assertEqual(False, is_user_file("test_base.py"))
        self.assertEqual(False, is_user_file("run_test.py"))

    def test_extract_mda_id(self):
        files = find_analysis_base_files(TestUtils.DATA_PATH)
        num = 0
        for f in files:
            num = extract_mda_id(os.path.join(TestUtils.DATA_PATH, f))
        self.assertEqual("213", num)


if __name__ == "__main__":
    unittest.main()
