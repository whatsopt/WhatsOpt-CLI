import os
import unittest
import subprocess
import json

dname = os.path.dirname


def file(name):
    return os.path.join(dname(__file__), "data", name)


COMMANDS = [
    "wop push -n {}".format(file("sellar.py")),
    "wop upload -n -a 1 {}".format(file("mda_init.py")),
    "wop upload -n {}".format(file("test_doe.csv")),
    "wop upload -n {}".format(file("test_doe.sqlite")),
    # skip as test data is obsolete
    # "wop upload -p -n {}".format(file("test_parallel_doe.sqlite_0")),
    "wop show -b -f {}".format(file("multipoint_beam/multipoint_beam_group.py")),
    "wop show -b --depth 3 -f {}".format(
        file("multipoint_beam/multipoint_beam_group.py")
    ),
    "wop status",
    "wop convert {}".format(file("test_doe.sqlite")),
]


def ordered(obj):
    if isinstance(obj, dict):
        return sorted((k, ordered(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(ordered(x) for x in obj)
    else:
        return obj


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
        if os.path.exists("test_doe.csv"):
            os.remove("test_doe.csv")

    def test_push_depth(self):
        self.maxDiff = None
        for d in range(3):
            print(f"DEPTH={d}")
            out = self._test_wop_cmd(
                "wop push -d {} -n {}".format(
                    d, file("multipoint_beam/multipoint_beam_group.py")
                )
            )
            with open(file("multipoint_beam_group_d{}.json".format(d))) as f:
                expected = ordered(json.loads(f.read()))
                actual = ordered(json.loads(out))
                self.assertTrue(expected, actual)


if __name__ == "__main__":
    unittest.main()
