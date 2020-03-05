# -*- coding: utf-8 -*-
from openmdao.test_suite.components.sellar import SellarProblem

problem = SellarProblem()

problem.setup()
problem.final_setup()
