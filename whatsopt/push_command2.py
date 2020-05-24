import re
from six import iteritems
from whatsopt.push_utils import (
    simple_value,
    to_camelcase,
    extract_disc_var,
    extract_disc_var2,
    format_shape,
)
from .logging import debug, log
from openmdao.api import IndepVarComp

try:  # openmdao < 2.9
    from openmdao.devtools.problem_viewer.problem_viewer import _get_viewer_data
except ImportError:  # openmdao >= 2.9
    from openmdao.visualization.n2_viewer.n2_viewer import _get_viewer_data

DRIVER_NAME = "__DRIVER__"  # check WhatsOpt Discipline model


class PushCommand2(object):
    def __init__(self, problem, scalar_format):
        data = _get_viewer_data(problem)
        self.problem = problem
        self.scalar_format = scalar_format
        self.tree = data["tree"]
        self.connections = data["connections_list"]
        self.vars = {}
        self.vardescs = {}
        self.discmap = {}
        self.mdas = {}

    def get_mda_attributes(self, group, tree, group_prefix=""):
        self._collect_disc_infos(self.problem.model, self.tree)
        self._collect_var_infos(self.problem.model)

        mda_attrs = self._get_mda_hierarchy(group, tree, group_prefix="")
        self._populate_varattrs(mda_attrs)

        return mda_attrs

    def _get_mda_hierarchy(self, group, tree, group_prefix=""):
        name = tree["name"]

        mda_attrs = {
            "name": group.__class__.__name__ if name is "root" else name,
            "disciplines_attributes": [
                {"name": DRIVER_NAME, "variables_attributes": []}
            ],
        }
        self.mdas[group_prefix] = mda_attrs
        for i, child in enumerate(tree["children"]):
            if child["type"] == "subsystem" and child["subsystem_type"] == "group":
                prefix = child["name"]
                if group_prefix:
                    prefix = group_prefix + "." + child["name"]
                sub_analysis_attrs = self._get_sub_analysis_attributes(
                    group._subsystems_myproc[i], child, prefix
                )
                mda_attrs["disciplines_attributes"].append(sub_analysis_attrs)
            else:
                if not isinstance(group._subsystems_myproc[i], IndepVarComp):
                    discattrs = {"name": child["name"], "variables_attributes": []}
                    mda_attrs["disciplines_attributes"].append(discattrs)
        return mda_attrs

    def _populate_varattrs(self, mda_attrs):
        for conn in self.connections:
            mda_src, varname_src = extract_disc_var2(conn["src"])
            mda_tgt, varname_tgt = extract_disc_var2(conn["tgt"])
            hat = []
            while mda_src and mda_tgt and mda_src[0] == mda_tgt[0]:
                hat.append(mda_src[0])
                mda_src = mda_src[1:]
                mda_tgt = mda_tgt[1:]
            conn_name = self._get_conn_name(conn)
            for discattrs in self.mdas[".".join(hat)]["disciplines_attributes"]:
                # mda hat: src
                if self.discmap[mda_src[0]] == discattrs["name"]:
                    self._set_varattr(
                        discattrs, conn["src"], varname_src, conn_name, "out"
                    )
                    # src -> hat
                    self._set_varattr_in_depth(
                        discattrs.get("sub_analysis_attributes"),
                        mda_src[1:],
                        conn["src"],
                        conn_name,
                        upward=True,
                    )

                # mda hat: tgt
                if self.discmap[mda_tgt[0]] == discattrs["name"]:
                    self._set_varattr(
                        discattrs, conn["tgt"], varname_tgt, conn_name, "in"
                    )
                    # hat -> tgt
                    self._set_varattr_in_depth(
                        discattrs.get("sub_analysis_attributes"),
                        mda_tgt[1:],
                        conn["tgt"],
                        conn_name,
                        upward=False,
                    )

    def _set_varattr_in_depth(
        self, mda_attrs, mda_endpoint, endpoint, conn_name, upward
    ):
        if mda_attrs:
            var = self.vars[endpoint]
            varattrs = {
                "name": conn_name,
                "io_mode": "out" if upward else "in",
                "desc": self.vardescs.get(endpoint, ""),
                "type": var["type"],
                "shape": var["shape"],
                "units": var["units"],
            }
            disc_endpoint = mda_endpoint[0]
            for discattrs in mda_attrs["disciplines_attributes"]:
                if self.discmap[disc_endpoint] == discattrs["name"]:
                    if discattrs.get("variables_attributes") is not None:
                        discattrs["variables_attributes"].append(varattrs)
                    submda_attrs = discattrs.get("sub_analysis_attributes")
                    break
            varattr_driver = varattrs.copy()
            varattr_driver["io_mode"] = "in" if upward else "out"
            mda_attrs["disciplines_attributes"][0]["variables_attributes"].append(
                varattr_driver
            )
            self._set_varattr_in_depth(
                submda_attrs, mda_endpoint[1:], endpoint, conn_name, upward
            )

    def _set_varattr(self, discattrs, endpoint, varname, conn_name, io_mode):
        if discattrs.get("variables_attributes") is None:
            return
        found = False
        for vattr in discattrs["variables_attributes"]:
            found = vattr["name"] == varname
            if found:
                break
        if not found:
            var = self.vars[endpoint]
            discattrs["variables_attributes"].append(
                {
                    "name": conn_name,
                    "io_mode": io_mode,
                    "desc": self.vardescs.get(endpoint, ""),
                    "type": var["type"],
                    "shape": var["shape"],
                    "units": var["units"],
                }
            )

    def _get_reduced(self, conn):
        src = conn["src"].split(".")
        tgt = conn["tgt"].split(".")
        while src[0] == tgt[0]:
            src = src[1:]
            tgt = tgt[1:]
        return src, tgt

    def _get_conn_name(self, conn):
        if self.vars[conn["src"]]["name"] == self.vars[conn["tgt"]]["name"]:
            return self.vars[conn["src"]]["name"]
        else:
            return conn["src"] + "==" + conn["tgt"]

    def _get_sub_analysis_attributes(self, group, child, prefix):
        submda_attrs = self._get_mda_hierarchy(group, child, prefix)
        submda_attrs["name"] = child["name"]
        submda_attrs["disciplines_attributes"] = submda_attrs["disciplines_attributes"]
        self.mdas[prefix] = submda_attrs
        superdisc_attrs = {
            "name": child["name"],
            # "variables_attributes": [],
            "sub_analysis_attributes": submda_attrs,
        }
        return superdisc_attrs

    # # see _get_tree_dict at
    # # https://github.com/OpenMDAO/OpenMDAO/blob/master/openmdao/devtools/problem_viewer/problem_viewer.py
    def _collect_disc_infos(self, system, tree):
        if "children" not in tree:
            return

        for i, child in enumerate(tree["children"]):
            if child["type"] == "subsystem" and child["subsystem_type"] == "group":
                self.discmap[child["name"]] = child["name"]
                self._collect_disc_infos(system._subsystems_myproc[i], child)
            else:
                # do not represent IndepVarComp
                if isinstance(system._subsystems_myproc[i], IndepVarComp):
                    self.discmap[child["name"]] = DRIVER_NAME
                else:
                    self.discmap[child["name"]] = child["name"]

    def _collect_var_infos(self, system):
        for typ in ["input", "output"]:
            for abs_name in system._var_abs_names[typ]:
                if typ == "input":
                    io_mode = "in"
                elif typ == "output":
                    io_mode = "out"
                else:
                    raise Exception("Unhandled variable type " + typ)
                meta = system._var_abs2meta[abs_name]

                vtype = "Float"
                if re.match("int", type(meta["value"]).__name__):
                    vtype = "Integer"
                shape = str(meta["shape"])
                shape = format_shape(self.scalar_format, shape)
                name = system._var_abs2prom[typ][abs_name]
                # name = abs_name
                self.vars[abs_name] = {
                    "name": name,
                    "io_mode": io_mode,
                    "type": vtype,
                    "shape": shape,
                    "units": meta["units"],
                    "value": meta["value"],
                }

                # retrieve initial conditions
                var = self.vars[abs_name]
                if abs_name in system._outputs._views:
                    var["value"] = system._outputs[abs_name]
                elif abs_name in system._inputs._views:
                    var["value"] = system._inputs[abs_name]
                elif abs_name in system._discrete_outputs:
                    var["value"] = system._discrete_outputs[abs_name]
                elif abs_name in system._discrete_inputs:
                    var["value"] = system._discrete_inputs[abs_name]

                desc = self.vardescs.setdefault(name, "")
                if desc == "":
                    self.vardescs[name] = meta["desc"]
                elif desc != meta["desc"] and meta["desc"] != "":
                    debug(
                        'Find another description for {}: "{}", keep "{}"'.format(
                            name, meta["desc"], self.vardescs[name]
                        )
                    )
