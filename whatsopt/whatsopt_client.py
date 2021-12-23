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
import numpy as np
import time
from tabulate import tabulate
from urllib.parse import urlparse

# push
import openmdao.utils.hooks as hooks
from openmdao.utils.file_utils import _load_and_exec

from openmdao.utils.webview import webview
from openmdao.api import IndepVarComp
from whatsopt.convert_utils import convert_sqlite_to_csv

from whatsopt.logging import log, info, warn, error, debug
from whatsopt.utils import (
    FRAMEWORK_GEMSEO,
    FRAMEWORK_OPENMDAO,
    MODE_PACKAGE,
    MODE_PLAIN,
    is_analysis_user_file,
    is_based_on,
    is_framework_switch,
    is_package_mode,
    is_run_script_file,
    is_test_file,
    is_user_file,
    get_analysis_id,
    get_whatsopt_url,
    snakize,
    save_state,
)
from whatsopt.upload_utils import (
    load_from_csv,
    load_from_sqlite,
    load_from_hdf5,
    print_cases,
)
from whatsopt.push_utils import (
    find_indep_var_name,
    problem_pyfile,
    to_camelcase,
)
from whatsopt.universal_push_command import UniversalPushCommand
from whatsopt.show_utils import generate_xdsm_html

from whatsopt import __version__

WHATSOPT_DIRNAME = os.path.join(os.path.expanduser("~"), ".whatsopt")
API_KEY_FILENAME = os.path.join(WHATSOPT_DIRNAME, "api_key")
URL_FILENAME = os.path.join(WHATSOPT_DIRNAME, "url")

PROD_URL = "https://selene.onecert.fr/whatsopt"
INTRANET_SERVER_URL = PROD_URL
EXTRANET_SERVER_URL = "https://ether.onera.fr/whatsopt"


class WhatsOptImportMdaError(Exception):
    pass


class AnalysisPushedException(Exception):
    def __init__(self, xdsm):
        self.xdsm = xdsm


class WhatsOpt:
    def __init__(self, url=None, api_key=None, login=True):
        if url:
            self._url = url.strip("/")
        elif os.path.exists(URL_FILENAME):
            with open(URL_FILENAME, "r") as f:
                self._url = f.read()
        else:
            self._url = self.default_url

        # config session object
        self.session = requests.Session()
        urlinfos = urlparse(self._url)
        self.session.trust_env = re.match(r"\w+.onera\.fr", urlinfos.netloc)
        self.headers = {}

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

    def endpoint(self, path):
        return self._url + path

    @staticmethod
    def err_msg(resp):
        error(
            "{} ({}) : {}".format(
                resp.status_code,
                requests.status_codes._codes[resp.status_code][0],
                resp.json()["message"],
            )
        )

    @property
    def default_url(self):
        self._default_url = INTRANET_SERVER_URL
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

    @staticmethod
    def _read_api_key():
        with open(API_KEY_FILENAME, "r") as f:
            api_key = f.read()
            return api_key

    def login(self, api_key=None, echo=None):
        debug("login()")
        already_logged = False
        if api_key:
            self.api_key = api_key
        elif os.path.exists(API_KEY_FILENAME):
            already_logged = True
            self.api_key = self._read_api_key()
        else:
            debug("Ask for API key")
            self.api_key = self._ask_and_write_api_key()
        ok = self._test_connection(api_key)

        if not api_key and already_logged and not ok:
            # try to propose re-login
            self.logout(
                echo=False
            )  # log out silently, one may be logged on another server
            # save url again
            with open(URL_FILENAME, "w") as f:
                f.write(self._url)
            ok = self.login(api_key, echo=False)

        if not ok and echo:
            error("Login to WhatsOpt ({}) failed.".format(self.url))
            log("")
            sys.exit(-1)

        if echo:
            log("Successfully logged into WhatsOpt (%s)" % self.url)
            log("")
        return ok

    @staticmethod
    def logout(echo=True):
        if os.path.exists(API_KEY_FILENAME):
            os.remove(API_KEY_FILENAME)
        if os.path.exists(URL_FILENAME):
            os.remove(URL_FILENAME)
        if echo:
            log("Sucessfully logged out from WhatsOpt")
            log("")

    def list_analyses(self, all=False, project_query=None):
        param = ""
        if all:
            param = "?all=true"
        elif project_query:
            param = "?design_project_query={}".format(project_query)
        url = self.endpoint("/api/v1/analyses" + param)
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
            log("")
        else:
            resp.raise_for_status()

    def is_connected(self):
        return self._test_connection()

    def get_status(self):
        connected = self.is_connected()
        whatsopt_url = get_whatsopt_url() or self.url
        if connected:
            info("You are logged in {}".format(self.url))
        else:
            info("You are not connected.")
        mda_id = None
        try:
            mda_id = get_analysis_id()
        except ValueError as err:
            warn(str(err))
        if mda_id:
            if connected and whatsopt_url == self.url:
                info("Found local analysis code (id=#{})".format(mda_id))
                # connected to the right server from which the analysis was pulled
                url = self.endpoint("/api/v1/analyses/{}".format(mda_id))
                resp = self.session.get(url, headers=self.headers)

                if resp.ok:
                    mda = resp.json()
                    if is_based_on(FRAMEWORK_GEMSEO):
                        mda["framework"] = "GEMSEO"
                    elif is_based_on(FRAMEWORK_OPENMDAO):
                        mda["framework"] = "OpenMDAO"
                    else:  # should not happen
                        raise ValueError(
                            "No framework detected. Check your *_base.py files."
                        )
                    headers = ["id", "name", "created_at", "owner_email", "framework"]
                    data = [[mda[k] for k in headers]]
                    log(tabulate(data, headers))
                else:
                    error("Analysis not found on the server anymore (probably deleted)")
                    log(
                        "  (use 'wop push <analysis.py>' to push from an OpenMDAO code to the server)"
                    )
            else:
                info(
                    "Found local analysis code (id=#{}) "
                    "pulled from {}".format(mda_id, whatsopt_url)
                )
                if connected:
                    # connected to another server with a pulled analysis
                    warn("You are connected to a different server")
                    log(
                        "  (use 'wop push <analysis.py>' to push the local "
                        "analysis in the current server {})".format(self.url)
                    )
                    log(
                        "  (use 'wop logout' and 'wop login {}' "
                        "to log in to the right server)".format(whatsopt_url)
                    )
                else:
                    log("  (use 'wop login {}' command to log in)".format(whatsopt_url))
        else:
            info("No local analysis found")
            if connected:
                log(
                    "  (use 'wop list' and 'wop pull <id>' to retrieve an existing analysis)\n"
                    "  (use 'wop push <analysis.py>' to push from an OpenMDAO code to the server)"
                )
        log("")

    def push_component_cmd(self, py_filename, component, options):
        with problem_pyfile(py_filename, component) as pyf:
            if options["--dry-run"]:
                with open(pyf, "r") as pbf:
                    print(pbf.read())
                    sys.exit()
            self.push_mda_cmd(pyf, options)

    def push_mda_cmd(self, py_filename, options):
        def push_mda(prob):
            name = options["--name"]
            pbname = prob.model.__class__.__name__
            if name and pbname != name:
                info("Analysis %s skipped" % pbname)
                # do not exit seeking for another problem (ie analysis)
            else:
                options["--pyfilename"] = py_filename
                xdsm = self.push_mda(prob, options)
                if options.get("--xdsm"):  # show command
                    # required to interrupt pb execution
                    raise AnalysisPushedException(xdsm=xdsm)
                else:
                    sys.exit()

        hooks.use_hooks = True
        hooks._register_hook("final_setup", "Problem", post=push_mda)
        _load_and_exec(py_filename, [])
        return push_mda

    def push_mda(self, problem, options):
        scalar = options.get("--scalar")
        depth = options.get("--depth")
        push_cmd = UniversalPushCommand(problem, depth, scalar)

        mda_attrs = push_cmd.get_mda_attributes(
            problem.model, push_cmd.tree, use_depth=True
        )

        if mda_attrs["name"] == "Group" and options.get("--pyfilename"):
            mda_attrs["name"] = os.path.splitext(
                to_camelcase(os.path.basename(options.get("--pyfilename")))
            )[0]

        if options["--dry-run"]:
            log(json.dumps(mda_attrs, indent=2))
        else:
            suffix = ""
            if options.get("--xdsm"):
                suffix = ".xdsm"
            url = self.endpoint("/api/v1/analyses{}".format(suffix))
            resp = self.session.post(
                url, headers=self.headers, json={"analysis": mda_attrs}
            )
            resp.raise_for_status()
            log("Analysis %s pushed" % mda_attrs["name"])
            return resp.json()

    def push_json(self, filename):
        with open(filename, "rb") as f:
            attrs = json.load(f)
        if "analyses_attributes" in attrs:  # project detection
            url = self.endpoint("/api/v1/design_projects")
            key = "Project"
        else:
            url = self.endpoint("/api/v1/analyses")
            key = "Analysis"
        params = {}
        params[key.lower()] = attrs
        resp = self.session.post(url, headers=self.headers, json=params)
        resp.raise_for_status()
        log("{} {} pushed".format(key, attrs["name"]))

    def pull_mda(self, mda_id, options={}, msg=None):
        if not msg:
            msg = "Analysis %s pulled" % mda_id

        framework = FRAMEWORK_OPENMDAO
        if options.get("--gemseo"):
            framework = FRAMEWORK_GEMSEO

        param = ""
        if options.get("--run-ops"):
            param += "&with_runops=true"
        if options.get("--server"):
            if framework == FRAMEWORK_OPENMDAO:
                param += "&with_server=true"
            else:
                warn(
                    "Can not generate server with GEMSEO framework. --server is ignored"
                )
        if options.get("--egmdo"):
            if framework == FRAMEWORK_OPENMDAO:
                param += "&with_egmdo=true"
            else:
                warn("Can not generate EGMDO with GEMSEO framework. --egmdo is ignored")
        if options.get("--test-units"):
            if framework == FRAMEWORK_OPENMDAO:
                param += "&with_unittests=true"
            else:
                warn(
                    "Can not generate tests with GEMSEO framework. --test-units is ignored"
                )
        if param:
            param = "?" + param[1:]

        format = framework
        if options.get("--package"):
            format += "_pkg"

        url = self.endpoint(
            ("/api/v1/analyses/{}/exports/new.{}{}".format(mda_id, format, param))
        )
        resp = self.session.get(url, headers=self.headers, stream=True)
        resp.raise_for_status()
        name = None
        with tempfile.NamedTemporaryFile(suffix=".zip", mode="wb", delete=False) as fd:
            for chunk in resp.iter_content(chunk_size=128):
                fd.write(chunk)
            name = fd.name
        zipf = zipfile.ZipFile(name, "r")
        tempdir = tempfile.mkdtemp(suffix="wop", dir=tempfile.tempdir)
        zipf.extractall(tempdir)
        filenames = zipf.namelist()
        zipf.close()
        file_to_move = {}
        if options.get("--dry-run"):
            cmd = "Pull"
            if options.get("--update"):
                cmd = "Update"
            info(
                "*******************************************************************\n"
                f"* {cmd} is run in DRY RUN mode (actions are listed but not done) *\n"
                "*******************************************************************"
            )
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
                    if is_run_script_file(f) and not options.get("--run-ops"):
                        info(
                            f"Keep existing {file_to} (remove it or use -r to override)"
                        )
                        file_to_move[file_to] = False
                        continue
                    if is_test_file(f) and not options.get("--test-units"):
                        file_to_move[file_to] = False
                        continue
                    if is_user_file(f):
                        file_to_move[file_to] = False

                        # Have to update user analysis main file when switching frameworks
                        url = self.endpoint(f"/api/v1/analyses/{mda_id}")
                        resp = self.session.get(url, headers=self.headers, stream=True)
                        resp.raise_for_status()
                        mda_name = snakize(resp.json()["name"])
                        if is_analysis_user_file(mda_name, f) and is_framework_switch(
                            framework
                        ):
                            file_to_move[file_to] = True
                        else:
                            continue
                    log(f"Update {file_to}")
                    if not options.get("--dry-run"):
                        os.remove(file_to)
                else:
                    warn(
                        f"File {file_to} in the way: remove it or use --force to override"
                    )
                    file_to_move[file_to] = False
            else:
                log(f"Pull {file_to}")
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
            save_state(
                self._url,
                mda_id,
                framework,
                MODE_PACKAGE if options.get("--package") else MODE_PLAIN,
            )
            log(msg)

    def pull_mda_json(self, mda_id):
        url = self.endpoint(f"/api/v1/analyses/{mda_id}.wopjson")
        resp = self.session.get(url, headers=self.headers, stream=True)
        resp.raise_for_status()
        print(json.dumps(resp.json()))

    def pull_project_json(self, project_id):
        url = self.endpoint(f"/api/v1/design_projects/{project_id}.wopjson")
        resp = self.session.get(url, headers=self.headers, stream=True)
        resp.raise_for_status()
        print(json.dumps(resp.json()))

    def update_mda(self, analysis_id=None, options={}):
        mda_id = analysis_id or get_analysis_id()
        if mda_id is None:
            error(
                f"Unknown analysis with id=#{mda_id} (maybe use wop pull <analysis-id>)"
            )
            sys.exit(-1)
        # keep options unchanged, work on a copy
        opts = copy.deepcopy(options)
        # sanity checks
        if not (is_based_on(FRAMEWORK_OPENMDAO) or is_based_on(FRAMEWORK_GEMSEO)):
            error("No framework detected. Check your *_base.py files.")
            sys.exit(-1)
        if opts["--openmdao"] and opts["--gemseo"]:
            error("Please choose either --openmdao or --gemseo.")
            sys.exit(-1)
        opts.update(
            {
                "--base": True,
                "--update": True,
                "--gemseo": opts["--gemseo"]
                or (not opts["--openmdao"] and is_based_on("gemseo")),
                "--openmdao": opts["--openmdao"]
                or (not opts["--gemseo"] and is_based_on("openmdao")),
                "--package": is_package_mode(),
            }
        )
        self.pull_mda(mda_id, opts, "Analysis #{} updated".format(mda_id))

    def show_mda(self, analysis_id, pbfile, name, outfile, batch, depth):
        options = {
            "--xdsm": True,
            "--name": name,
            "--dry-run": False,
            "--depth": depth,
        }
        xdsm = None
        if pbfile:
            start = time.time()
            try:
                info("XDSM info retrieval...")
                self.push_mda_cmd(pbfile, options)
            except AnalysisPushedException as pushed:
                xdsm = pushed.xdsm
            end = time.time()
            log("Retrieved in {:.2f}s".format(end - start))
            source = os.path.basename(pbfile)
        else:
            mda_id = analysis_id or get_analysis_id()
            if mda_id is None:
                error(
                    "Unknown analysis with id={} (maybe use wop pull <analysis-id>)".format(
                        mda_id
                    )
                )
                sys.exit(-1)
            url = self.endpoint("/api/v1/analyses/{}.xdsm".format(mda_id))
            resp = self.session.get(url, headers=self.headers)
            resp.raise_for_status()
            xdsm = resp.json()
            source = f"{mda_id}@{self._url}"

        info("XDSM building...")
        generate_xdsm_html(source, xdsm, outfile)
        if pbfile:
            log("XDSM of analysis from {} generated in {}".format(pbfile, outfile))
        else:
            log("XDSM of analysis {} generated in {}".format(mda_id, outfile))
        if not batch:
            webview(outfile)

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
        if (
            os.path.basename(filename) == "run_parameters_init.py"
            or os.path.basename(filename) == "mda_init.py"
        ):
            self.upload_vars_init_cmd(
                filename, {"--dry-run": dry_run, "--analysis-id": mda_id}
            )
        elif filename.endswith(".csv"):
            name, cases, statuses = load_from_csv(filename)
        elif filename.endswith(".sqlite"):
            name, cases, statuses = load_from_sqlite(filename, parallel)
        elif filename.endswith(".hdf5"):
            name, cases, statuses = load_from_hdf5(filename)
        else:
            error(
                f"Can not upload file {filename}: extension not recognized"
                " (should be either .csv, .sqlite or .hdf5)"
            )
            exit(-1)

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
            sys.exit()

        resp = None
        if operation_id:
            url = self.endpoint(("/api/v1/operations/%s") % operation_id)
            operation_params = {"cases": cases}
            resp = self.session.patch(
                url, headers=self.headers, json={"operation": operation_params}
            )
        else:
            if mda_id:
                url = self.endpoint(("/api/v1/analyses/%s/operations") % mda_id)
            else:
                url = self.endpoint("/api/v1/operations")
            if driver_kind:
                driver = "user_{}_algo".format(driver_kind)
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

    def upload_vars_init_cmd(self, py_filename, options):
        def upload_vars_init(prob):
            self.upload_vars_init(prob, options)
            sys.exit()

        d = os.path.dirname(py_filename)
        run_analysis_filename = os.path.join(d, "run_analysis.py")
        if not os.path.exists(run_analysis_filename):
            error(
                f"Can not get analysis init: script {run_analysis_filename} not found."
            )
        hooks.use_hooks = True
        hooks._register_hook("final_setup", "Problem", post=upload_vars_init)
        _load_and_exec(run_analysis_filename, [])

    def upload_vars_init(self, problem, options):
        mda_id = get_analysis_id() if get_analysis_id() else options["--analysis-id"]
        if mda_id is None:
            error("Unknown analysis with id={}".format(mda_id))
            sys.exit(-1)
        parameters = []
        headers = ["variable", "init value"]
        data = []
        for s in problem.model._subsystems_myproc:
            if isinstance(s, IndepVarComp):
                for absname in s._var_abs2meta["output"]:
                    name = find_indep_var_name(problem, absname)
                    value = s._outputs._views[absname][:]
                    if isinstance(value, np.ndarray):
                        value = str(value.tolist())
                    parameters.append({"varname": name, "value": value})
        data = [[p["varname"], p["value"]] for p in parameters]
        params = {"parameterization": {"parameters": parameters}}
        log(tabulate(data, headers))
        if not options["--dry-run"]:
            url = self.endpoint(f"/api/v1/analyses/{mda_id}/parameterization")
            resp = self.session.put(url, headers=self.headers, json=params)
            resp.raise_for_status()
            log("Variables init values uploaded")

    def check_versions(self):
        url = self.endpoint("/api/v1/versioning")
        resp = self.session.get(url, headers=self.headers)
        resp.raise_for_status()
        version = resp.json()
        log("WhatsOpt {} requires wop {}".format(version["whatsopt"], version["wop"]))
        log(f"You are using wop {__version__}")

    @staticmethod
    def serve(port):
        try:
            import thrift
        except ImportError:
            error(
                "Apache Thrift is not installed. You can install it with : 'pip install thrift'"
            )
            sys.exit(-1)
        try:
            import os, sys

            # insert current dir first as another run_server exists under whatsopt/services
            sys.path.insert(0, os.getcwd())
            from run_server import run_server
        except ImportError as err:
            print(str(err))
            error("Server not found!")
            try:
                mda_id = get_analysis_id()
                if mda_id:
                    log(
                        f"  (use 'wop update -s' to generate server for current analysis #{mda_id})"
                    )
                else:
                    warn("No local analysis found")
                    log(
                        "  (use 'wop pull -s <id>' to generate server for the analysis #id)"
                    )
            except ValueError as err:
                warn(str(err))
            sys.exit(-1)
        run_server(port)

    @staticmethod
    def convert(filename):
        if not os.path.exists(filename):
            error(f"File {filename} not found.")
        pathname, extension = os.path.splitext(filename)
        if not extension == ".sqlite":
            error(f"File {filename} should have '.sqlite' extension, got '{extension}'")
        basename = os.path.basename(pathname)
        convert_sqlite_to_csv(filename, basename)

    def _test_connection(self, api_key=None):
        test_api_key = api_key
        if test_api_key is None and os.path.exists(API_KEY_FILENAME):
            test_api_key = self._read_api_key()

        if test_api_key:
            self.headers = {
                "Authorization": "Token token=" + test_api_key,
                "User-Agent": "wop/{}".format(__version__),
            }
            url = self.endpoint("/api/v1/versioning")
            try:
                resp = self.session.get(url, headers=self.headers)
                # special case: bad wop version < minimal required version
                if resp.status_code == requests.codes.forbidden:
                    error(resp.json()["message"])
                    sys.exit(-1)
                return resp.ok
            except requests.exceptions.ConnectionError:
                return False
        else:
            return False
