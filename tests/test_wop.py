import os
import unittest
import subprocess
import json

dname = os.path.dirname


def file(name):
    return os.path.join(dname(__file__), "data", name)


COMMANDS = [
    "wop push -n {}".format(file("sellar.py")),
    "wop push --old -n {}".format(file("sellar.py")),
    "wop upload -n -a 1 {}".format(file("run_parameters_init.py")),
    "wop upload -n {}".format(file("test_doe.csv")),
    "wop upload -n {}".format(file("test_doe.sqlite")),
    "wop status",
]


class TestWopCommand(unittest.TestCase):
    def _test_wop_cmd(self, cmd):
        try:
            return subprocess.check_output(cmd.split(), encoding="utf-8")
        except subprocess.CalledProcessError as err:
            self.fail(
                "Command '{}' failed.  Return code: {}".format(cmd, err.returncode)
            )

    def test_commands(self):
        for cmd in COMMANDS:
            self._test_wop_cmd(cmd)

    def test_push_depth(self):
        self.maxDiff = None
        for d in range(3):
            print(f"DEPTH={d}")
            out = self._test_wop_cmd(
                "wop push --old -d {} -n {}".format(
                    d, file("multipoint_beam/multipoint_beam_group.py")
                )
            )
            with open(file("multipoint_beam_group_d{}.json".format(d))) as f:
                expected = json.dumps(json.loads(f.read()), sort_keys=True, indent=2)
                actual = json.dumps(json.loads(out), sort_keys=True, indent=2)
                self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
