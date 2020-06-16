import os
import unittest

from whatsopt.utils import (
    is_user_file,
    find_analysis_base_files,
    get_analysis_id,
    get_whatsopt_url,
)


class TestUtils(unittest.TestCase):

    DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "multipoint_beam")

    def test_is_user_file(self):
        self.assertEqual(True, is_user_file("test.py"))
        self.assertEqual(False, is_user_file("test_base.py"))
        self.assertEqual(False, is_user_file("run_test.py"))

    def test_find_analysis_base_files(self):
        self.assertEqual(
            set(
                [
                    "i_comp_base.py",
                    "interp_base.py",
                    "multipoint_beam_group_base.py",
                    "volume_comp_base.py",
                    "obj_sum_base.py",
                    "local_stiffness_matrix_comp_base.py",
                ]
            ),
            set(find_analysis_base_files(TestUtils.DATA_PATH)),
        )

    def test_get_analysis_id(self):
        self.assertEqual("4", get_analysis_id(TestUtils.DATA_PATH))

    def test_get_whatsopt_url(self):
        self.assertEqual(
            "https://ether.onera.fr/whatsopt", get_whatsopt_url(TestUtils.DATA_PATH)
        )


if __name__ == "__main__":
    unittest.main()
