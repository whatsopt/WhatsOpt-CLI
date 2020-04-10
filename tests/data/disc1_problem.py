from openmdao.api import Problem
from disc1 import Disc1

pb = Problem(Disc1())
pb.setup()
pb.final_setup()
