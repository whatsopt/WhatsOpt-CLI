import os
import unittest

from whatsopt.convert_utils import (
    convert_sqlite_to_csv,
)


class TestUploadUtils(unittest.TestCase):
    DATA_PATH = os.path.join(os.path.dirname(__file__), "data")

    def test_convert_sqlite_to_csv(self):
        filepath = os.path.join(TestUploadUtils.DATA_PATH, "test_doe.sqlite")
        convert_sqlite_to_csv(filepath, "test_doe")
        self.assertTrue(os.path.exists("test_doe.csv"))
        os.remove("test_doe.csv")
