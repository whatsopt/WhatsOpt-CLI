import unittest
import os
import json

from openmdao.api import Problem, IndepVarComp, ScipyOptimizeDriver
from openmdao.test_suite.test_examples.test_betz_limit import ActuatorDisc
from whatsopt.push_command import PushCommand


def problem_init():
    prob = Problem()
    indeps = prob.model.add_subsystem("indeps", IndepVarComp(), promotes=["*"])
    indeps.add_output("a", 0.5)
    indeps.add_output("Area", 10.0, units="m**2")
    indeps.add_output("rho", 1.225, units="kg/m**3")
    indeps.add_output("Vu", 10.0, units="m/s")

    prob.model.add_subsystem("a_disk", ActuatorDisc(), promotes=["*"])

    # setup the optimization
    prob.driver = ScipyOptimizeDriver()
    prob.driver.options["optimizer"] = "SLSQP"

    prob.model.add_design_var("a", lower=0.0, upper=1.0)
    prob.model.add_design_var("Area", lower=0.0, upper=1.0)

    # negative one so we maximize the objective
    prob.model.add_objective("Cp", scaler=-1)

    prob.setup()
    prob.final_setup()
    return prob


class TestPushCommand(unittest.TestCase):

    DATA_PATH = os.path.join(os.path.dirname(__file__), "data")

    def test_get_mda_attributes(self):

        problem = problem_init()
        push_cmd = PushCommand(problem, 0, False)
        mda_attrs = push_cmd.get_mda_attributes(problem.model, push_cmd.tree)

        driver = mda_attrs["disciplines_attributes"][0]
        adisk = mda_attrs["disciplines_attributes"][1]

        self.assertEqual("Group", mda_attrs["name"])
        self.assertEqual("__DRIVER__", driver["name"])
        self.assertEqual("ADisk", adisk["name"])
        self.assertEqual(
            len(driver["variables_attributes"]), len(adisk["variables_attributes"])
        )

        for dic_driver in driver["variables_attributes"]:
            for dic_adisk in adisk["variables_attributes"]:
                if dic_driver["name"] == dic_adisk["name"]:
                    self.assertFalse(dic_driver["io_mode"] == dic_adisk["io_mode"])
                    self.assertTrue(dic_driver["type"] == dic_adisk["type"])
                    self.assertTrue(dic_driver["units"] == dic_adisk["units"])

    def test_cut_flatten(self):
        test_datafile = os.path.join(self.DATA_PATH, "test_push_cut_flatten.json")
        with open(test_datafile) as f:
            testdata = json.load(f)
            mda_attrs = testdata["input"]
            PushCommand.cut(mda_attrs, 1)
            expect = testdata["expected"]
            self.assertEqual(
                expect["disciplines_attributes"][1]["variables_attributes"],
                mda_attrs["disciplines_attributes"][1]["variables_attributes"],
            )


if __name__ == "__main__":
    unittest.main()
