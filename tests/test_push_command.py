import unittest
import json

import openmdao.api as om
from openmdao.test_suite.test_examples.test_betz_limit import ActuatorDisc
from openmdao.test_suite.test_examples.beam_optimization.multipoint_beam_stress import (
    MultipointBeamGroup,
)
from whatsopt.push_command import PushCommand


def problem_init():
    prob = om.Problem()
    indeps = prob.model.add_subsystem("indeps", om.IndepVarComp(), promotes=["*"])
    indeps.add_output("a", 0.5)
    indeps.add_output("Area", 10.0, units="m**2")
    indeps.add_output("rho", 1.225, units="kg/m**3")
    indeps.add_output("Vu", 10.0, units="m/s")

    prob.model.add_subsystem("a_disk", ActuatorDisc(), promotes=["*"])

    # setup the optimization
    prob.driver = om.ScipyOptimizeDriver()
    prob.driver.options["optimizer"] = "SLSQP"

    prob.model.add_design_var("a", lower=0.0, upper=1.0)
    prob.model.add_design_var("Area", lower=0.0, upper=1.0)

    # negative one so we maximize the objective
    prob.model.add_objective("Cp", scaler=-1)

    prob.setup()
    prob.final_setup()
    return prob


def problem_init2():
    E = 1.0
    L = 1.0
    b = 0.1
    volume = 0.01
    max_bending = 100.0

    num_cp = 5
    num_elements = 25
    num_load_cases = 2

    model = MultipointBeamGroup(
        E=E,
        L=L,
        b=b,
        volume=volume,
        max_bending=max_bending,
        num_elements=num_elements,
        num_cp=num_cp,
        num_load_cases=num_load_cases,
    )

    prob = om.Problem(model=model)

    prob.driver = om.ScipyOptimizeDriver()
    prob.driver.options["optimizer"] = "SLSQP"
    prob.driver.options["tol"] = 1e-9
    prob.driver.options["disp"] = True

    prob.setup(mode="rev")
    prob.setup()
    prob.final_setup()
    return prob


class TestPushCommand2(unittest.TestCase):
    def test_get_mda_attributes(self):
        problem = problem_init2()
        push_cmd = PushCommand(problem, 0, False)
        mda_attrs = push_cmd.get_mda_attributes(problem.model, push_cmd.tree)
        print(json.dumps(mda_attrs, indent=2))


if __name__ == "__main__":
    unittest.main()
