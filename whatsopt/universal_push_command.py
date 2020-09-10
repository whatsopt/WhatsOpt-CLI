import re
from whatsopt.push_utils import (
    cut,
    simple_value,
    extract_disc_var,
    extract_mda_var,
    format_shape,
)
from whatsopt.logging import debug
from openmdao.api import IndepVarComp

try:  # openmdao < 2.9
    from openmdao.devtools.problem_viewer.problem_viewer import _get_viewer_data
except ImportError:  # openmdao >= 2.9
    from openmdao.visualization.n2_viewer.n2_viewer import _get_viewer_data

# Special name for internal WhatsOpt discipline. cf. WhatsOpt Discipline model
DRIVER_NAME = "__DRIVER__"
# OpenMDAO 3.2+ component name (handles indep vars automatically)
AUTO_IVC = "_auto_ivc"


class UniversalPushCommand(object):
    """
    This push command allows to push any OpenMDAO problem
    (as opposed to regular push command which works with "all vars promoted/no connect" assumption)
    """

    def __init__(self, problem, depth, scalar_format):
        data = _get_viewer_data(problem)
        self.problem = problem
        self.depth = depth
        self.scalar_format = scalar_format
        self.tree = data["tree"]
        self.connections = data["connections_list"]
        self.vars = {"in": {}, "out": {}}
        self.vardescs = {}
        self.discmap = {}
        self.mdas = {}

    def get_mda_attributes(self, group, tree, use_depth=False):
        self._collect_disc_infos(self.problem.model, self.tree)
        self._collect_var_infos(self.problem.model)

        mda_attrs = self._get_mda_hierarchy(group, tree)

        mda_attrs["name"] = ""  # root -> ""
        self._populate_varattrs_from_connections(mda_attrs)
        self._populate_varattrs_from_outputs(mda_attrs)
        self._populate_initial_values(mda_attrs)
        for _, mda in self.mdas.items():
            self._populate_initial_values(mda)

        mda_attrs["name"] = group.__class__.__name__

        if use_depth:
            cut(mda_attrs, self.depth)

        return mda_attrs

    def _get_mda_hierarchy(self, group, tree, group_prefix=""):
        name = tree["name"]

        mda_attrs = {
            "name": name,
            "disciplines_attributes": [
                {"name": DRIVER_NAME, "variables_attributes": []}
            ],
        }
        self.mdas[group_prefix] = mda_attrs
        for child in tree["children"]:
            for s in group._subsystems_myproc:
                if s.name == child["name"]:
                    if (
                        child["type"] == "subsystem"
                        and child["subsystem_type"] == "group"
                    ):
                        prefix = child["name"]
                        if group_prefix:
                            prefix = group_prefix + "." + child["name"]
                        sub_analysis_attrs = self._get_sub_analysis_attributes(
                            s, child, prefix
                        )
                        mda_attrs["disciplines_attributes"].append(sub_analysis_attrs)
                    else:
                        if not isinstance(s, IndepVarComp):
                            discattrs = {
                                "name": child["name"],
                                "variables_attributes": [],
                            }
                            mda_attrs["disciplines_attributes"].append(discattrs)
        return mda_attrs

    def _populate_varattrs_from_connections(self, mda_attrs):
        for conn in self.connections:
            mda_src, varname_src = extract_mda_var(conn["src"])
            mda_tgt, varname_tgt = extract_mda_var(conn["tgt"])
            hat = []
            while mda_src and mda_tgt and mda_src[0] == mda_tgt[0]:
                hat.append(mda_src[0])
                mda_src = mda_src[1:]
                mda_tgt = mda_tgt[1:]
            conn_name = self._get_conn_name(conn)
            for discattrs in self.mdas[".".join(hat)]["disciplines_attributes"]:

                # mda hat: src
                if (
                    mda_src[0] != AUTO_IVC
                    and self.discmap[mda_src[0]] == discattrs["name"]
                ):
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
                    if mda_src[0] == AUTO_IVC:
                        driver_attrs = mda_attrs["disciplines_attributes"][0]
                        self._set_varattr(
                            driver_attrs, conn["src"], varname_tgt, conn_name, "out"
                        )

                    # hat -> tgt
                    self._set_varattr_in_depth(
                        discattrs.get("sub_analysis_attributes"),
                        mda_tgt[1:],
                        conn["tgt"],
                        conn_name,
                        upward=False,
                    )

    def _populate_varattrs_from_outputs(self, mda_attrs, group_prefix=""):
        mda_prefix = group_prefix
        if mda_prefix:
            mda_prefix += "."
        if mda_attrs["name"]:
            mda_prefix += mda_attrs["name"] + "."
        for discattrs in mda_attrs["disciplines_attributes"]:
            sub_mda_attrs = discattrs.get("sub_analysis_attributes")
            if sub_mda_attrs is None:
                for absname, varattrs in self.vars["out"].items():
                    mda, _ = extract_mda_var(absname)
                    scope = discattrs["name"]
                    if mda_prefix:
                        scope = mda_prefix + scope
                    if ".".join(mda) == scope:
                        vattr = {
                            "name": varattrs["name"],
                            "desc": self.vardescs.get(absname, ""),
                            "type": varattrs["type"],
                            "shape": varattrs["shape"],
                            "units": varattrs["units"],
                        }
                        self._set_varattrs_from_outputs(
                            vattr, "out", discattrs["variables_attributes"]
                        )
                        dvattr = vattr.copy()
                        dvattr["io_mode"] = "in"
                        driver_attrs = mda_attrs["disciplines_attributes"][0]
                        self._set_varattrs_from_outputs(
                            dvattr, "in", driver_attrs["variables_attributes"]
                        )
            else:
                self._populate_varattrs_from_outputs(sub_mda_attrs, mda_prefix[:-1])

    def _populate_initial_values(self, mda_attrs):
        driver_attrs = mda_attrs["disciplines_attributes"][0]
        for vattr in driver_attrs["variables_attributes"]:
            if vattr["io_mode"] == "out":
                # set init value for design variables and parameters (outputs of driver)
                conn_name = vattr["name"].split("==")[0]
                if self.vars["out"].get(conn_name):
                    v = self.vars["out"][conn_name]
                    vattr["parameter_attributes"] = {"init": simple_value(v)}
                else:  # indep comp promoted
                    for _, v in self.vars["out"].items():
                        if conn_name == v["name"]:
                            vattr["parameter_attributes"] = {"init": simple_value(v)}
                            break

    def _set_varattr_in_depth(
        self, mda_attrs, mda_endpoint, endpoint, conn_name, upward
    ):
        if mda_attrs:
            io_mode = "out" if upward else "in"
            var = self.vars[io_mode][endpoint]
            varattrs = {
                "name": conn_name,
                "io_mode": io_mode,
                "desc": self.vardescs.get(endpoint, ""),
                "type": var["type"],
                "shape": var["shape"],
                "units": var["units"],
            }
            disc_endpoint = mda_endpoint[0]
            for discattrs in mda_attrs["disciplines_attributes"]:
                if self.discmap[disc_endpoint] == discattrs["name"]:
                    if discattrs.get("variables_attributes") is not None:
                        already_present = [
                            varattr["name"]
                            for varattr in discattrs["variables_attributes"]
                        ]
                        if conn_name not in already_present:
                            discattrs["variables_attributes"].append(varattrs)
                    submda_attrs = discattrs.get("sub_analysis_attributes")
                    break
            driver_varattrs = mda_attrs["disciplines_attributes"][0][
                "variables_attributes"
            ]
            already_present = [varattr["name"] for varattr in driver_varattrs]
            if conn_name not in already_present:
                varattr_driver = varattrs.copy()
                varattr_driver["io_mode"] = "in" if upward else "out"
                driver_varattrs.append(varattr_driver)
            self._set_varattr_in_depth(
                submda_attrs, mda_endpoint[1:], endpoint, conn_name, upward
            )

    def _set_varattr(self, discattrs, endpoint, varname, conn_name, io_mode):
        if discattrs.get("variables_attributes") is None:
            return
        already_present = [
            varattr["name"] for varattr in discattrs["variables_attributes"]
        ]
        if conn_name not in already_present:
            var = self.vars[io_mode][endpoint]
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

    def _set_varattrs_from_outputs(self, varattr, io_mode, varattrs):
        already_present = [varattr["name"] for varattr in varattrs]
        if varattr["name"] not in already_present:
            vattr = varattr.copy()
            vattr["io_mode"] = io_mode
            varattrs.append(vattr)

    def _get_conn_name(self, conn):
        if (
            self.vars["out"][conn["src"]]["name"]
            == self.vars["in"][conn["tgt"]]["name"]
        ):
            return self.vars["out"][conn["src"]]["name"]
        elif conn["src"].startswith(
            AUTO_IVC
        ):  # special case take varname of target when auto_ivc
            _, varname = extract_mda_var(conn["tgt"])
            return varname
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

        for child in tree["children"]:
            for s in system._subsystems_myproc:
                if s.name == child["name"]:
                    if (
                        child["type"] == "subsystem"
                        and child["subsystem_type"] == "group"
                    ):
                        self.discmap[child["name"]] = child["name"]
                        self._collect_disc_infos(s, child)
                    else:
                        # do not represent IndepVarComp
                        if isinstance(s, IndepVarComp):
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
                self.vars[io_mode][abs_name] = {
                    "name": name,
                    "type": vtype,
                    "shape": shape,
                    "units": meta["units"],
                    "value": meta["value"],
                }

                # retrieve initial conditions
                var = self.vars[io_mode][abs_name]
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
