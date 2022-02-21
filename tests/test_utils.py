import os
import unittest
import tempfile

from whatsopt.utils import (
    ANALYSIS_ID_KEY,
    FRAMEWORK_KEY,
    PULL_MODE_KEY,
    WHATSOPT_URL_KEY,
    WOP_CONF_FILENAME,
    is_analysis_user_file,
    is_based_on,
    is_user_file,
    find_analysis_base_files,
    get_analysis_id,
    get_whatsopt_url,
    load_state,
    save_state,
    snakize,
)


class TestUtils(unittest.TestCase):

    DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "multipoint_beam")

    def setupt(self):
        if os.path.exists(WOP_CONF_FILENAME):
            os.remove(WOP_CONF_FILENAME)

    def tearDown(self):
        if os.path.exists(WOP_CONF_FILENAME):
            os.remove(WOP_CONF_FILENAME)

    def test_save_load_state(self):
        state = {
            "whatsopt_url": "http://exemple.com",
            "analysis_id": "666",
            "framework": "OpenMDAO",
            "pull_mode": "plain",
        }
        save_state(*(state.values()))
        retrieved = load_state()
        for k in [WHATSOPT_URL_KEY, ANALYSIS_ID_KEY, FRAMEWORK_KEY, PULL_MODE_KEY]:
            self.assertEqual(state[k], str(retrieved[k]), f"Diff on state key {k}")

    def test_snakize(self):
        self.assertEqual(
            "hyp_air_liner_1_1_v1_genetic", snakize("HypAir_Liner 1.1__v1-genetic")
        )

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

    def test_based_on_openmdao(self):
        self.assertEqual(False, is_based_on("gemseo", TestUtils.DATA_PATH))
        self.assertEqual(True, is_based_on("openmdao", TestUtils.DATA_PATH))

    def test_based_on_framework_on_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(False, is_based_on("openmdao", tmpdir))
            self.assertEqual(False, is_based_on("gemseo", tmpdir))

    def test_is_analysis_user_file(self):
        self.assertEqual(True, is_analysis_user_file("sellar", "sellar.py"))
        self.assertEqual(False, is_analysis_user_file("sellar", "sellar_base.py"))


if __name__ == "__main__":
    unittest.main()
