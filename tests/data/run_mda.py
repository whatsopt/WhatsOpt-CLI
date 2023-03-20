from openmdao.api import Problem
from mda_init import initialize
from openmdao.test_suite.components.sellar import SellarNoDerivatives as Sellar

pb = Problem(Sellar())
pb.setup()

initialize(pb)

pb.run_model()
