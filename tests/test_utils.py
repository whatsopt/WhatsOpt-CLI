import os
import unittest
import tempfile

from whatsopt.utils import (
    WOP_CONF_FILENAME,
    is_analysis_user_file,
    is_based_on,
    is_user_file,
    find_analysis_base_files,
    get_analysis_id,
    get_whatsopt_url,
    load_state,
    save_state,
)


class TestUtils(unittest.TestCase):
    DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
    MBEAM_PATH = os.path.join(DATA_PATH, "multipoint_beam")

    def setup(self):
        if os.path.exists(WOP_CONF_FILENAME):
            os.remove(WOP_CONF_FILENAME)

    def tearDown(self):
        if os.path.exists(WOP_CONF_FILENAME):
            os.remove(WOP_CONF_FILENAME)

    def test_save_load_state(self):
        state = {
            "wop_format_version": 2,
            "whatsopt_url": "https://example.com",
            "analysis_id": 666,
            "framework": "openmdao",
            "pull_mode": "package",
        }
        save_state(state)
        with open(WOP_CONF_FILENAME, "r") as file:
            data = file.read()
            with open(os.path.join(TestUtils.DATA_PATH, "wop_ref"), "r") as file:
                ref = file.read()
                self.assertEqual(ref, data)
        retrieved = load_state()
        self.assertEqual(state, retrieved)

    def test_load_state_old_format(self):
        state = {
            "wop_format_version": 1,
            "whatsopt_url": "https://erebe.onecert.fr/whatsopt",
            "analysis_id": 67,
            "framework": "gemseo",
            "pull_mode": "plain",
        }
        retrieved = load_state(
            filename=os.path.join(TestUtils.DATA_PATH, "wop_format_v1")
        )
        self.assertEqual(state, retrieved)

    def test_load_state_toml(self):
        state = {
            "wop_format_version": 2,
            "whatsopt_url": "https://erebe.onecert.fr/whatsopt",
            "analysis_id": 67,
            "framework": "gemseo",
            "pull_mode": "plain",
        }
        retrieved = load_state(
            filename=os.path.join(TestUtils.DATA_PATH, "wop_format_v2")
        )
        self.assertEqual(state, retrieved)

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
            set(find_analysis_base_files(TestUtils.MBEAM_PATH)),
        )

    def test_get_analysis_id(self):
        self.assertEqual("4", get_analysis_id(TestUtils.MBEAM_PATH))

    def test_get_whatsopt_url(self):
        self.assertEqual(
            "https://ether.onera.fr/whatsopt", get_whatsopt_url(TestUtils.MBEAM_PATH)
        )

    def test_based_on_openmdao(self):
        self.assertEqual(False, is_based_on("gemseo", TestUtils.MBEAM_PATH))
        self.assertEqual(True, is_based_on("openmdao", TestUtils.MBEAM_PATH))

    def test_based_on_framework_on_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(False, is_based_on("openmdao", tmpdir))
            self.assertEqual(False, is_based_on("gemseo", tmpdir))

    def test_is_analysis_user_file(self):
        self.assertEqual(True, is_analysis_user_file("sellar", "sellar.py"))
        self.assertEqual(False, is_analysis_user_file("sellar", "sellar_base.py"))


if __name__ == "__main__":
    unittest.main()
