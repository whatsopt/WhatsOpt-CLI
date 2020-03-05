import os
import unittest
import subprocess

dname = os.path.dirname


def file(name):
    return os.path.join(dname(__file__), "data", name)


COMMANDS = [
    "wop push -n {}".format(file("sellar.py")),
    "wop upload -n -a 1 {}".format(file("run_parameters_init.py")),
    "wop upload -n {}".format(file("test_doe.csv")),
    "wop upload -n {}".format(file("test_doe.sqlite")),
]


class TestWopCommand(unittest.TestCase):
    def _test_wop_cmd(self, cmd):
        try:
            subprocess.check_output(cmd.split())
        except subprocess.CalledProcessError as err:
            self.fail(
                "Command '{}' failed.  Return code: {}".format(cmd, err.returncode)
            )

    def test_commands(self):
        for cmd in COMMANDS:
            self._test_wop_cmd(cmd)


if __name__ == "__main__":
    unittest.main()
