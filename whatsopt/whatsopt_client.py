from __future__ import print_function
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
from whatsopt.logging import log, info, warn, error
from whatsopt.utils import is_user_file, get_analysis_id
from whatsopt.upload_utils import (
    load_from_csv,
    load_from_sqlite,
    print_cases,
)
from whatsopt.push_command import PushCommand

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

from openmdao.api import IndepVarComp, Problem
from tabulate import tabulate
from whatsopt import __version__

WHATSOPT_DIRNAME = os.path.join(os.path.expanduser("~"), ".whatsopt")
API_KEY_FILENAME = os.path.join(WHATSOPT_DIRNAME, "api_key")
URL_FILENAME = os.path.join(WHATSOPT_DIRNAME, "url")

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

        # bad wop version
        if resp.status_code == requests.codes.forbidden:
            error(resp.json()["message"])
            exit(-1)

        if not api_key and already_logged and not resp.ok:
            # try to propose re-login
            self.logout(
                echo=False
            )  # log out silently, suppose one was logged on another server
            resp = self.login(api_key, echo)

        if not resp.ok and echo:
            error("Login to WhatsOpt (%s) failed." % self.url)
            exit(-1)

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
        scalar_format = options["--scalar-format"]
        push_cmd = PushCommand(problem, scalar_format)
        mda_attrs = push_cmd.get_mda_attributes(problem.model, push_cmd.tree)

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
        mda_id = analysis_id or get_analysis_id()
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
        parallel=False,
    ):
        from socket import gethostname

        mda_id = get_analysis_id() if not analysis_id else analysis_id

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
            name, cases, statuses = load_from_sqlite(filename, parallel)

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
                        driver = "user_data_uploading"
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
        mda_id = get_analysis_id()
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
            error(
                "Apache Thrift is not installed. You can install it with : 'pip install thrift'"
            )
            exit(-1)
        call(["python", "run_server.py"])

