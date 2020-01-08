from __future__ import print_function
from six import iteritems
from shutil import move
import os
import sys
import json
import getpass
import requests
import copy
import re
import zipfile
import tempfile
import csv
import numpy as np
from whatsopt.logging import log, info, warn, error, debug
from whatsopt.utils import (
    load_from_csv,
    is_user_file,
    find_analysis_base_files,
    extract_mda_id,
    format_shape,
    to_camelcase,
    load_from_sqlite,
    simple_value,
    extract_disc_var,
    print_cases,
)

try:
    # Python 3
    from urllib.parse import urlparse
except ImportError:
    # Python 2
    from urlparse import urlparse

try:  # openmdao < 2.9
    from openmdao.devtools.problem_viewer.problem_viewer import _get_viewer_data
except:  # openmdao >= 2.9
    from openmdao.visualization.n2_viewer.n2_viewer import _get_viewer_data

from openmdao.api import IndepVarComp, Problem, Group, CaseReader
from openmdao.core.component import Component
from tabulate import tabulate
from whatsopt import __version__

WHATSOPT_DIRNAME = os.path.join(os.path.expanduser("~"), ".whatsopt")
API_KEY_FILENAME = os.path.join(WHATSOPT_DIRNAME, "api_key")
URL_FILENAME = os.path.join(WHATSOPT_DIRNAME, "url")
NULL_DRIVER_NAME = "__DRIVER__"  # check WhatsOpt Discipline model

PROD_URL = "https://selene.onecert.fr/whatsopt"


class WhatsOptImportMdaError(Exception):
    pass


class WhatsOpt(object):
    def __init__(self, url=None, api_key=None, login=True):
        if url:
            self._url = url
        elif os.path.exists(URL_FILENAME):
            with open(URL_FILENAME, "r") as f:
                self._url = f.read()
        else:
            self._url = self.default_url

        # config session object
        self.session = requests.Session()
        self.set_trust_env()

        # login by default
        if login:
            self.login(api_key)

        # save url
        if not os.path.exists(WHATSOPT_DIRNAME):
            os.makedirs(WHATSOPT_DIRNAME)
        with open(URL_FILENAME, "w") as f:
            f.write(self._url)

    @property
    def url(self):
        return self._url

    def _endpoint(self, path):
        return self._url + path

    def set_trust_env(self):
        urlinfos = urlparse(self._url)
        self.session.trust_env = re.match(r"\w+.onera\.fr", urlinfos.netloc)

    @property
    def default_url(self):
        self._default_url = PROD_URL
        return self._default_url

    def _ask_and_write_api_key(self):
        log("You have to set your API key.")
        log("You can get it in your profile page on WhatsOpt (%s)." % self.url)
        info(
            "Please, copy/paste your API key below then hit return (characters are hidden)."
        )
        api_key = getpass.getpass(prompt="Your API key: ")
        if not os.path.exists(WHATSOPT_DIRNAME):
            os.makedirs(WHATSOPT_DIRNAME)
        with open(API_KEY_FILENAME, "w") as f:
            f.write(api_key)
        return api_key

    def _read_api_key(self):
        with open(API_KEY_FILENAME, "r") as f:
            api_key = f.read()
            return api_key

    def login(self, api_key=None, echo=None):
        already_logged = False
        if api_key:
            self.api_key = api_key
        elif os.path.exists(API_KEY_FILENAME):
            already_logged = True
            self.api_key = self._read_api_key()
        else:
            self.api_key = self._ask_and_write_api_key()
        self.headers = {
            "Authorization": "Token token=" + self.api_key,
            "User-Agent": "wop/{}".format(__version__),
        }

        url = self._endpoint("/api/v1/analyses")
        resp = self.session.get(url, headers=self.headers)
        if not api_key and already_logged and not resp.ok:
            self.logout(
                echo=False
            )  # log out silently, suppose one was logged on another server
            resp = self.login(api_key, echo)
        resp.raise_for_status()
        if echo:
            log("Successfully logged into WhatsOpt (%s)" % self.url)
        return resp

    def logout(self, echo=True):
        if os.path.exists(API_KEY_FILENAME):
            os.remove(API_KEY_FILENAME)
        if os.path.exists(URL_FILENAME):
            os.remove(URL_FILENAME)
        if echo:
            log("Sucessfully logged out from WhatsOpt (%s)" % self.url)

    def list_analyses(self):
        url = self._endpoint("/api/v1/analyses")
        resp = self.session.get(url, headers=self.headers)
        if resp.ok:
            mdas = resp.json()
            headers = ["id", "name", "created at"]
            data = []
            for mda in mdas:
                date = mda.get("created_at", None)
                data.append([mda["id"], mda["name"], date])
            info("Server: {}".format(self._url))
            log(tabulate(data, headers))
        else:
            resp.raise_for_status()

    def execute(self, progname, func, options={}):
        dir = os.path.dirname(progname)
        sys.path.insert(0, dir)
        with open(progname, "rb") as fp:
            code = compile(fp.read(), progname, "exec")
        globals_dict = {
            "__file__": progname,
            "__name__": "__main__",
            "__package__": None,
            "__cached__": None,
        }
        Problem._post_setup_func = func(options)
        sys.argv = [progname]  # suppose progname do not need options
        exec(code, globals_dict)

    def push_mda_cmd(self, options):
        def push_mda(prob):
            name = options["--name"]
            pbname = prob.model.__class__.__name__
            if name and pbname != name:
                info("Analysis %s skipped" % pbname)
                pass  # do not exit
            else:
                self.push_mda(prob, options)
                exit()

        return push_mda

    def push_mda(self, problem, options):
        name = problem.model.__class__.__name__
        data = _get_viewer_data(problem)
        scalar_format = options["--scalar-format"]
        self.tree = data["tree"]
        self.connections = data["connections_list"]

        # MDA informations
        # push_cmd = PushCommand()
        # mda_attrs = push_cmd.get_mda_attributes()

        self.vars = {}
        self.vardescs = {}
        self.discmap = {}
        self._collect_disc_infos(problem.model, self.tree)
        self._collect_var_infos(problem.model, scalar_format)
        mda_attrs = self._get_mda_attributes(problem.model, self.tree)

        if options["--dry-run"]:
            log(json.dumps(mda_attrs, indent=2))
        else:
            url = self._endpoint("/api/v1/analyses")
            resp = self.session.post(
                url, headers=self.headers, json={"analysis": mda_attrs}
            )
            resp.raise_for_status()
            log("Analysis %s pushed" % name)

    def pull_mda(self, mda_id, options={}, msg=None):
        if not msg:
            msg = "Analysis %s pulled" % mda_id
        base = ""
        param = ""
        if options.get("--server"):
            param += "&with_server=true"
        if options.get("--run-ops"):
            param += "&with_runops=true"
        if options.get("--test-units"):
            param += "&with_unittests=true"
        if param is not "":
            param = "?" + param[1:]
        url = self._endpoint(
            ("/api/v1/analyses/%s/exports/new.openmdao" + base + param) % mda_id
        )
        resp = self.session.get(url, headers=self.headers, stream=True)
        resp.raise_for_status()
        name = None
        with tempfile.NamedTemporaryFile(suffix=".zip", mode="wb", delete=False) as fd:
            for chunk in resp.iter_content(chunk_size=128):
                fd.write(chunk)
            name = fd.name
        zip = zipfile.ZipFile(name, "r")
        tempdir = tempfile.mkdtemp(suffix="wop", dir=tempfile.tempdir)
        zip.extractall(tempdir)
        filenames = zip.namelist()
        zip.close()
        file_to_move = {}
        for f in filenames:
            file_to = f
            file_to_move[file_to] = True
            if os.path.exists(file_to):
                if options.get("--force"):
                    log("Update %s" % file_to)
                    if options.get("--dry-run"):
                        file_to_move[file_to] = False
                    else:
                        os.remove(file_to)
                elif options.get("--update"):
                    if re.match(r"^run_.*\.py$", f) and not options.get("--run-ops"):
                        # keep current run scripts if any
                        info(
                            "Keep existing %s (remove it or use --run-ops to override)"
                            % file_to
                        )
                        file_to_move[file_to] = False
                        continue
                    if is_user_file(f):
                        file_to_move[file_to] = False
                        continue
                    log("Update %s" % file_to)
                    if not options.get("--dry-run"):
                        os.remove(file_to)
                else:
                    warn(
                        "File %s in the way: remove it or use --force to override"
                        % file_to
                    )
                    file_to_move[file_to] = False
            else:
                log("Pull %s" % file_to)
        if not options.get("--dry-run"):
            for f in file_to_move.keys():
                file_from = os.path.join(tempdir, f)
                file_to = f
                dir_to = os.path.dirname(f)
                if dir_to == "":
                    dir_to = "."
                elif not os.path.exists(dir_to):
                    os.makedirs(dir_to)
                if file_to_move[file_to]:
                    move(file_from, dir_to)
            log(msg)

    def update_mda(self, analysis_id=None, options={}):
        mda_id = analysis_id or self.get_analysis_id()
        if mda_id is None:
            error(
                "Unknown analysis with id={} (maybe use wop pull <analysis-id>)".format(
                    mda_id
                )
            )
            exit(-1)
        opts = copy.deepcopy(options)
        opts.update({"--base": True, "--update": True})
        self.pull_mda(mda_id, opts, "Analysis %s updated" % mda_id)

    def upload(
        self,
        filename,
        driver_kind=None,
        analysis_id=None,
        operation_id=None,
        dry_run=False,
        outvar_count=1,
        only_success=False,
    ):
        from socket import gethostname

        mda_id = self.get_analysis_id() if not analysis_id else analysis_id

        name = cases = statuses = None
        if filename == "run_parameters_init.py":
            if mda_id is None:
                error("Unknown analysis with id={}".format(mda_id))
                exit(-1)
            self.execute(
                "run_analysis.py", self.upload_parameters_cmd, {"--dry-run": dry_run}
            )
            exit()
        elif filename.endswith(".csv"):
            name, cases, statuses = load_from_csv(filename)
        else:
            name, cases, statuses = load_from_sqlite(filename)

        if only_success:
            for c in cases:
                c["values"] = [
                    val for i, val in enumerate(c["values"]) if statuses[i] > 0
                ]
            statuses = [1 for s in statuses if s > 0]

        for c in cases:
            c["values"] = np.nan_to_num(np.array(c["values"])).tolist()

        if dry_run:
            print_cases(cases, statuses)
            exit()

        resp = None
        if operation_id:
            url = self._endpoint(("/api/v1/operations/%s") % operation_id)
            operation_params = {"cases": cases}
            resp = self.session.patch(
                url, headers=self.headers, json={"operation": operation_params}
            )
        else:
            if mda_id:
                url = self._endpoint(("/api/v1/analyses/%s/operations") % mda_id)
            else:
                url = self._endpoint("/api/v1/operations")
            if driver_kind:
                driver = "user_{}_algo".format(driver_kind)
            else:
                if name == "LHS":
                    driver = "smt_doe_lhs"
                elif name == "Morris":
                    driver = "salib_doe_morris"
                elif name == "SLSQP":
                    driver = "scipy_optimizer_slsqp"
                else:
                    # suppose name well-formed <lib>-<doe|optimizer|screening>-<algoname>
                    # otherwise it will default to doe
                    m = re.match(r"(\w+)_(doe|optimizer|screening)_(\w+)", name.lower())
                    if m:
                        driver = name.lower()
                    else:
                        driver = "user_defined_algo"
            operation_params = {
                "name": name,
                "driver": driver,
                "host": gethostname(),
                "cases": cases,
                "success": statuses,
            }
            params = {"operation": operation_params}
            if outvar_count > 0 and outvar_count < len(cases):
                params["outvar_count_hint"] = outvar_count
            resp = self.session.post(url, headers=self.headers, json=params)
        resp.raise_for_status()
        log("Results data from {} uploaded with driver {}".format(filename, driver))

    def upload_parameters_cmd(self, options):
        def upload_parameters(prob):
            self.upload_parameters(prob, options)
            exit()

        return upload_parameters

    def upload_parameters(self, problem, options):
        mda_id = self.get_analysis_id()
        if mda_id is None:
            error("Unknown analysis with id={}".format(mda_id))
            exit(-1)
        parameters = []
        headers = ["parameter", "value"]
        data = []
        for s in problem.model._subsystems_myproc:
            if isinstance(s, IndepVarComp):
                for absname in s._var_allprocs_abs_names["output"]:
                    name = s._var_allprocs_abs2prom["output"][absname]
                    value = s._outputs._views[absname][:]
                    if isinstance(value, np.ndarray):
                        value = str(value.tolist())
                    parameters.append({"varname": name, "value": value})
        data = [[p["varname"], p["value"]] for p in parameters]
        params = {"parameterization": {"parameters": parameters}}
        log(tabulate(data, headers))
        if not options["--dry-run"]:
            url = self._endpoint(("/api/v1/analyses/%s/parameterization") % mda_id)
            resp = self.session.put(url, headers=self.headers, json=params)
            resp.raise_for_status()
            log("Parameters uploaded")

    def check_versions(self):
        url = self._endpoint("/api/v1/versioning")
        resp = self.session.get(url, headers=self.headers)
        resp.raise_for_status()
        version = resp.json()
        log(
            "WhatsOpt:{} recommended wop:{}".format(version["whatsopt"], version["wop"])
        )
        log("current wop:{}".format(__version__))

    def serve(self):
        from subprocess import call

        try:
            import thrift
        except ImportError:
            log(
                "Apache Thrift is not installed. You can install it with : 'pip install thrift'"
            )
            exit(-1)
        call(["python", "run_server.py"])

    def get_analysis_id(self):
        files = find_analysis_base_files()
        id = None
        for f in files:
            ident = extract_mda_id(f)
            if id and id != ident:
                raise Exception(
                    "Warning: several analysis identifier detected. \n"
                    "Find %s got %s. Check header comments in %s files ."
                    % (id, ident, str(files))
                )
            id = ident
        return id

    # # see _get_tree_dict at
    # # https://github.com/OpenMDAO/OpenMDAO/blob/master/openmdao/devtools/problem_viewer/problem_viewer.py
    def _collect_disc_infos(self, system, tree, group_prefix=""):
        if "children" not in tree:
            return

        for i, child in enumerate(tree["children"]):
            # retain only components, not intermediates (subsystem or group)
            if child["type"] == "subsystem" and child["subsystem_type"] == "group":
                self.discmap[group_prefix + child["name"]] = child["name"]
                prefix = group_prefix + child["name"] + "."
                self._collect_disc_infos(system._subsystems_myproc[i], child, prefix)
            else:
                # do not represent IndepVarComp
                if not isinstance(system._subsystems_myproc[i], IndepVarComp):
                    self.discmap[group_prefix + child["name"]] = child["name"]
                else:
                    self.discmap[group_prefix + child["name"]] = "__DRIVER__"

    # see _get_tree_dict at
    # https://github.com/OpenMDAO/OpenMDAO/blob/master/openmdao/devtools/problem_viewer/problem_viewer.py
    def _collect_var_infos(self, system, scalar_format):
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
                shape = format_shape(scalar_format, shape)
                name = system._var_abs2prom[typ][abs_name]
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
                    log(
                        'Find another description for {}: "{}", keep "{}"'.format(
                            name, meta["desc"], self.vardescs[name]
                        )
                    )

    def _get_mda_attributes(self, group, tree, group_prefix=""):
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
        submda_attrs = self._get_mda_attributes(group, child, prefix)
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
            debug("**************", connection)
            if disc == dname:
                if varattr not in varattrs:
                    debug(
                        ">>>>>>>>>>>>> from",
                        orig,
                        " ADD to ",
                        mda,
                        dname,
                        ": ",
                        varattr["name"],
                        varattr["io_mode"],
                    )
                    varattrs.append(varattr)
            else:
                if varattr["name"] not in [vattr["name"] for vattr in driver_varattrs]:
                    debug(
                        ">>>>>>>>>>>>> from",
                        orig,
                        " ADD to ",
                        mda,
                        "__DRIVER__ :",
                        varattr["name"],
                        varattr["io_mode"],
                    )
                    driver_varattrs.append(varattr)

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
