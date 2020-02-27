import re
from six import iteritems
from whatsopt.push_utils import (
    simple_value,
    to_camelcase,
    extract_disc_var,
    format_shape,
)
from .logging import debug, log
from openmdao.api import IndepVarComp

try:  # openmdao < 2.9
    from openmdao.devtools.problem_viewer.problem_viewer import _get_viewer_data
except ImportError:  # openmdao >= 2.9
    from openmdao.visualization.n2_viewer.n2_viewer import _get_viewer_data

NULL_DRIVER_NAME = "__DRIVER__"  # check WhatsOpt Discipline model


class PushCommand(object):
    def __init__(self, problem, scalar_format):
        data = _get_viewer_data(problem)
        self.problem = problem
        self.scalar_format = scalar_format
        self.tree = data["tree"]
        self.connections = data["connections_list"]
        self.vars = {}
        self.vardescs = {}
        self.discmap = {}

    def get_mda_attributes(self, group, tree, group_prefix=""):
        self._collect_disc_infos()
        self._collect_var_infos()
        driver_attrs = {"name": NULL_DRIVER_NAME, "variables_attributes": []}
        mda_attrs = {
            "name": group.__class__.__name__,
            "disciplines_attributes": [driver_attrs],
        }
        if "children" not in tree:
            return

        for i, child in enumerate(tree["children"]):
            if child["type"] == "subsystem" and child["subsystem_type"] == "group":
                prefix = group_prefix + child["name"] + "."
                sub_analysis_attrs = self._get_sub_analysis_attributes(
                    group._subsystems_myproc[i], child, prefix
                )
                mda_attrs["disciplines_attributes"].append(sub_analysis_attrs)
            else:
                if not isinstance(group._subsystems_myproc[i], IndepVarComp):
                    mda = group_prefix[:-1]
                    discname = group_prefix + child["name"]
                    discattrs = self._get_discipline_attributes(
                        driver_attrs, mda, discname
                    )

                    self._set_varattrs_from_outputs(
                        group._subsystems_myproc[i]._var_abs2prom["output"],
                        "out",
                        discattrs["variables_attributes"],
                    )

                    mda_attrs["disciplines_attributes"].append(discattrs)
                else:
                    self._set_varattrs_from_outputs(
                        group._subsystems_myproc[i]._var_abs2prom["output"],
                        "out",
                        driver_attrs["variables_attributes"],
                    )

        self._set_varattrs_from_outputs(
            group._var_abs2prom["output"], "in", driver_attrs["variables_attributes"]
        )

        # remove fullname in driver varattrs
        for vattr in driver_attrs["variables_attributes"]:
            vattr["desc"] = self.vardescs[vattr["name"]]
            if (
                vattr["io_mode"] == "out"
            ):  # set init value for design variables and parameters (outputs of driver)
                v = self.vars[vattr["fullname"]]
                vattr["parameter_attributes"] = {"init": simple_value(v)}
            if "fullname" in vattr:
                del vattr["fullname"]  # indeed for WhatsOpt var name is a primary key

        for discattr in mda_attrs["disciplines_attributes"]:
            if "variables_attributes" in discattr:
                for vattr in discattr["variables_attributes"]:
                    if "fullname" in vattr:
                        del vattr[
                            "fullname"
                        ]  # indeed for WhatsOpt var name is a primary key

        return mda_attrs

    def _get_sub_analysis_attributes(self, group, child, prefix):
        submda_attrs = self.get_mda_attributes(group, child, prefix)
        submda_attrs["name"] = to_camelcase(child["name"])
        superdisc_attrs = {
            "name": child["name"],
            "sub_analysis_attributes": submda_attrs,
        }
        return superdisc_attrs

    def _get_discipline_attributes(self, driver_attrs, mda, dname):
        varattrs = self._get_variables_attrs(
            driver_attrs["variables_attributes"], mda, dname
        )
        discattrs = {
            "name": to_camelcase(self.discmap[dname]),
            "variables_attributes": varattrs,
        }
        return discattrs

    def _set_varattrs_from_outputs(self, outputs, io_mode, varattrs):
        for absname, varname in iteritems(outputs):
            if varname not in [varattr["name"] for varattr in varattrs]:
                var = self.vars[absname]
                vattr = {
                    "name": varname,
                    "fullname": absname,
                    "io_mode": io_mode,
                    "desc": self.vardescs[varname],
                    "type": var["type"],
                    "shape": var["shape"],
                    "units": var["units"],
                }
                varattrs.append(vattr)

    def _get_varattr_from_connection(
        self, varattrs, driver_varattrs, mda, dname, connection
    ):
        fnamesrc = connection["src"]
        mdasrc, discsrc, varsrc = extract_disc_var(fnamesrc)
        fnametgt = connection["tgt"]
        mdatgt, disctgt, vartgt = extract_disc_var(fnametgt)
        debug("++++ MDA=%s DISC=%s" % (mda, dname))
        debug(
            "######### SRC=%s DISCSRC=%s TGT=%s DISCTGT=%s"
            % (mdasrc, discsrc, mdatgt, disctgt)
        )

        varstoadd = []
        if mda == mdasrc and discsrc == dname:
            varattrsrc = {
                "name": varsrc,
                "fullname": fnamesrc,
                "io_mode": "out",
                "type": self.vars[fnamesrc]["type"],
                "shape": self.vars[fnamesrc]["shape"],
                "units": self.vars[fnamesrc]["units"],
            }
            varstoadd.append((discsrc, varattrsrc, "source"))
            if mda != "" and mda not in mdatgt:
                discsrc = NULL_DRIVER_NAME
                varattrsrc = {
                    "name": varsrc,
                    "fullname": fnamesrc,
                    "io_mode": "in",
                    "type": self.vars[fnametgt]["type"],
                    "shape": self.vars[fnametgt]["shape"],
                    "units": self.vars[fnametgt]["units"],
                }
                varstoadd.append((discsrc, varattrsrc, "source"))

        if mda == mdatgt and disctgt == dname:
            varattrtgt = {
                "name": vartgt,
                "fullname": fnametgt,
                "io_mode": "in",
                "type": self.vars[fnametgt]["type"],
                "shape": self.vars[fnametgt]["shape"],
                "units": self.vars[fnametgt]["units"],
            }
            varstoadd.append((disctgt, varattrtgt, "target"))
            if mda != "" and mda not in mdasrc:
                disctgt = NULL_DRIVER_NAME
                varattrtgt = {
                    "name": vartgt,
                    "fullname": fnametgt,
                    "io_mode": "out",
                    "type": self.vars[fnamesrc]["type"],
                    "shape": self.vars[fnamesrc]["shape"],
                    "units": self.vars[fnamesrc]["units"],
                }
                varstoadd.append((disctgt, varattrtgt, "target"))

        for disc, varattr, orig in varstoadd:
            debug("**************%s" % connection)
            if disc == dname:
                if varattr not in varattrs:
                    debug(">>>>>>>>>>>>> from {}".format(orig))
                    debug(" ADD to {}".format(mda))
                    debug(
                        "__DRIVER__ : {} {}".format(varattr["name"], varattr["io_mode"])
                    )
                    varattrs.append(varattr)
            else:
                if varattr["name"] not in [vattr["name"] for vattr in driver_varattrs]:
                    debug(">>>>>>>>>>>>> from {}".format(orig))
                    debug(" ADD to {}".format(mda))
                    debug(
                        "__DRIVER__ : {} {}".format(varattr["name"], varattr["io_mode"])
                    )
                    driver_varattrs.append(varattr)

    def _get_variables_attrs(self, driver_varattrs, mda, dname):
        varattrs = []
        for conn in self.connections:
            self._get_varattr_from_connection(
                varattrs, driver_varattrs, mda, dname, conn
            )
        for vattr in varattrs:
            vattr["desc"] = self.vardescs[vattr["name"]]
            if "fullname" in vattr:
                del vattr["fullname"]  # indeed for WhatsOpt var name is a primary key
        return varattrs

    # # see _get_tree_dict at
    # # https://github.com/OpenMDAO/OpenMDAO/blob/master/openmdao/devtools/problem_viewer/problem_viewer.py
    def _collect_disc_infos(self, group_prefix=""):
        if "children" not in self.tree:
            return

        for i, child in enumerate(self.tree["children"]):
            # retain only components, not intermediates (subsystem or group)
            if child["type"] == "subsystem" and child["subsystem_type"] == "group":
                self.discmap[group_prefix + child["name"]] = child["name"]
                prefix = group_prefix + child["name"] + "."
                self._collect_disc_infos(prefix)
            else:
                # do not represent IndepVarComp
                if not isinstance(
                    self.problem.model._subsystems_myproc[i], IndepVarComp
                ):
                    self.discmap[group_prefix + child["name"]] = child["name"]
                else:
                    self.discmap[group_prefix + child["name"]] = "__DRIVER__"

    # see _get_tree_dict at
    # https://github.com/OpenMDAO/OpenMDAO/blob/master/openmdao/devtools/problem_viewer/problem_viewer.py
    def _collect_var_infos(self):
        for typ in ["input", "output"]:
            for abs_name in self.problem.model._var_abs_names[typ]:
                if typ == "input":
                    io_mode = "in"
                elif typ == "output":
                    io_mode = "out"
                else:
                    raise Exception("Unhandled variable type " + typ)
                meta = self.problem.model._var_abs2meta[abs_name]

                vtype = "Float"
                if re.match("int", type(meta["value"]).__name__):
                    vtype = "Integer"
                shape = str(meta["shape"])
                shape = format_shape(self.scalar_format, shape)
                name = self.problem.model._var_abs2prom[typ][abs_name]
                self.vars[abs_name] = {
                    "fullname": abs_name,
                    "name": name,
                    "io_mode": io_mode,
                    "type": vtype,
                    "shape": shape,
                    "units": meta["units"],
                    #'desc': meta['desc'],
                    "value": meta["value"],
                }

                # retrieve initial conditions
                var = self.vars[abs_name]
                if abs_name in self.problem.model._outputs._views:
                    var["value"] = self.problem.model._outputs[abs_name]
                elif abs_name in self.problem.model._inputs._views:
                    var["value"] = self.problem.model._inputs[abs_name]
                elif abs_name in self.problem.model._discrete_outputs:
                    var["value"] = self.problem.model._discrete_outputs[abs_name]
                elif abs_name in self.problem.model._discrete_inputs:
                    var["value"] = self.problem.model._discrete_inputs[abs_name]

                desc = self.vardescs.setdefault(name, "")
                if desc == "":
                    self.vardescs[name] = meta["desc"]
                elif desc != meta["desc"] and meta["desc"] != "":
                    log(
                        'Find another description for {}: "{}", keep "{}"'.format(
                            name, meta["desc"], self.vardescs[name]
                        )
                    )
