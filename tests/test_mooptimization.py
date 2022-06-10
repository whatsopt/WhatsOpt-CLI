import unittest
from whatsopt.mooptimization import MOOptimization, FLOAT, INT


class TestMOOptimization(unittest.TestCase):
    def test_constructor(self):
        xtypes = [
            {"type": FLOAT, "limits": [0.0, 1.0]},
            {"type": INT, "limits": [0, 3]},
            {"type": INT, "limits": [0, 3]},
        ]

        optim = MOOptimization(xtypes, n_obj=3)
