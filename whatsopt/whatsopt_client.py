from http import HTTPStatus
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
from datetime import datetime
import tomli
import tomli_w
from tabulate import tabulate
from urllib.parse import urlparse
from packaging.version import Version

# push
import openmdao.utils.hooks as hooks
from openmdao.utils.file_utils import _load_and_exec

from openmdao.utils.webview import webview
from openmdao.api import IndepVarComp
from whatsopt.convert_utils import convert_sqlite_to_csv

from whatsopt.logging import log, info, warn, error, debug
from whatsopt.publish_utils import build_package, get_pkg_metadata
from whatsopt.utils import (
    FRAMEWORK_GEMSEO,
    FRAMEWORK_OPENMDAO,
    MODE_PACKAGE,
    MODE_PLAIN,
    extract_remote_name,
    is_analysis_user_file,
    is_based_on,
    is_framework_switch,
    is_package_mode,
    is_run_script_file,
    is_test_file,
    is_user_file,
    get_analysis_id,
    get_whatsopt_url,
    move_files,
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
from whatsopt.push_command import PushCommand
from whatsopt.show_utils import generate_xdsm_html

from whatsopt import __version__

WHATSOPT_DIRNAME = os.path.join(os.path.expanduser("~"), ".whatsopt")
API_KEY_FILENAME = os.path.join(WHATSOPT_DIRNAME, "api_key")
URL_FILENAME = os.path.join(WHATSOPT_DIRNAME, "url")
REMOTES_FILENAME = os.path.join(WHATSOPT_DIRNAME, "remotes")

EXTRANET_SERVER_URL = "https://ether.onera.fr/whatsopt"


class WhatsOptImportMdaError(Exception):
    pass


class AnalysisPushedException(Exception):
    def __init__(self, xdsm):
        self.xdsm = xdsm


class WhatsOpt:
    def __init__(self, url=None, api_key=None, login=None):
        self._remotes = self._read_remotes()

        remote = self._remotes.get(url)
        debug(f"remote={remote}")
        if remote:
            self._url = remote["url"]
            self._api_key = api_key if api_key else remote["api_key"]
        else:
            debug(f"url={url} logged?={self.is_logged()}")
            if url:
                self._url = url.strip("/")
                current_url = self._read_url()
                if current_url and self._url != current_url:
                    self.logout(echo=False)
            elif self.is_logged():
                self._url = self._read_url()
            else:
                self._url = EXTRANET_SERVER_URL

            if api_key:
                self._api_key = api_key
            else:
                self._api_key = self._read_api_key()

        # config session object
        self.session = requests.Session()
        urlinfos = urlparse(self._url)
        self.session.trust_env = re.match(r"\w+.onera\.fr", urlinfos.netloc)
        self.headers = {}

    @property
    def url(self):
        return self._url

    @property
    def api_key(self):
        return self._api_key

    def endpoint(self, path):
        return self._url + path

    @staticmethod
    def _read_remotes():
        remotes = {}
        if os.path.exists(REMOTES_FILENAME):
            with open(REMOTES_FILENAME, "rb") as f:
                remotes = tomli.load(f)
        return remotes

    @staticmethod
    def _write_remotes(remotes):
        with open(REMOTES_FILENAME, "wb") as f:
            tomli_w.dump(remotes, f)

    def _ask_api_key(self):
        log("You have to set your API key.")
        log("You can get it in your profile page on WhatsOpt (%s)." % self.url)
        info(
            "Please, copy/paste your API key below then hit return (characters are hidden)."
        )
        api_key = getpass.getpass(prompt="Your API key: ")
        return api_key

    @staticmethod
    def is_logged():
        # Defensive programming: test on api_key should be enough but...
        return os.path.exists(URL_FILENAME) and os.path.exists(API_KEY_FILENAME)

    @staticmethod
    def _read_url():
        if os.path.exists(URL_FILENAME):
            with open(URL_FILENAME, "r") as f:
                return f.read()
        else:
            return None

    @staticmethod
    def _read_api_key():
        if os.path.exists(API_KEY_FILENAME):
            with open(API_KEY_FILENAME, "r") as f:
                return f.read()
        else:
            return None

    def _write_login_infos(self):
        if not os.path.exists(WHATSOPT_DIRNAME):
            os.makedirs(WHATSOPT_DIRNAME)
        with open(API_KEY_FILENAME, "w") as f:
            f.write(self.api_key)
        with open(URL_FILENAME, "w") as f:
            f.write(self.url)

    def login(self, echo=False, retry=True):
        debug(f"login(api_key={self.api_key}, echo={echo})")

        # Check login with remote name
        if not (
            self.url.startswith("http://") or self.url.startswith("https://")
        ) and not self._remotes.get(self.url):
            error(f"Unknown remote server '{self.url}'")
            WhatsOpt.list_remotes()
            sys.exit(-1)

        if self._api_key:
            # api key is provided
            pass
        elif self.is_logged():
            # check if logged in
            self._api_key = self._read_api_key()
        else:
            # check if known remote
            for _, v in self._remotes.items():
                if self.url == v["url"]:
                    self._api_key = v["api_key"]
                    break
            # ask for API key otherwise
            debug("Ask for API key")
            self._api_key = self._ask_api_key() if not self._api_key else self._api_key

        debug(f"url={self.url}, api_key={self.api_key}")
        ok = self._test_connection()
        debug(f"ok={ok}")
        if not ok and retry:
            # try to log again
            # log out silently as one may be logged on another server
            self.logout(echo=False)
            self._remotes = {
                k: v for k, v in self._remotes.items() if v["url"] != self.url
            }
            # save url again as is has been wipe out by logout
            with open(URL_FILENAME, "w") as f:
                f.write(self._url)
            return self.login(retry=False)

        # make remote info
        if ok:
            self._write_login_infos()
            remote_name = extract_remote_name(self.url)
            if remote_name:
                self._remotes[remote_name] = {"url": self.url, "api_key": self.api_key}

        debug(self._remotes)
        self._write_remotes(self._remotes)

        if not ok:
            error("Login to WhatsOpt ({}) failed.".format(self.url))
            log("")
            warn("You are not connected.")
            info("  use `wop login <url>` to connect to a remote WhatsOpt server")
            info(
                "  use `wop login <name>` to connect to a known remote WhatsOpt server"
            )
            self.list_remotes()

            sys.exit(-1)

        if echo:
            info(f"Successfully logged in to remote WhatsOpt {self.url}")
            log("")
        return self

    @staticmethod
    def logout(list=None, all=None, remote=None, echo=True):
        if list:
            WhatsOpt.list_remotes()
        elif all:
            WhatsOpt._write_remotes({})
            if echo:
                info("Sucessfully logged out from all WhatsOpt remotes")
        elif remote:
            remotes = WhatsOpt._read_remotes()
            if remotes.get(remote):
                del remotes[remote]
                WhatsOpt._write_remotes(remotes)
                if echo:
                    info(f"Sucessfully logged out from remote WhatsOpt {remote}")
        else:
            if os.path.exists(API_KEY_FILENAME):
                os.remove(API_KEY_FILENAME)
            url = WhatsOpt._read_url()
            if url:
                os.remove(URL_FILENAME)
            if echo:
                if url:
                    info(f"Sucessfully logged out from remote WhatsOpt {url}")
                else:
                    info("Not connected. You may want to connect to:")
                    WhatsOpt.list_remotes()

        if echo:
            log("")

    @staticmethod
    def list_remotes():
        remotes = WhatsOpt._read_remotes()
        headers = ["name", "url"]
        data = []
        for name, rem in remotes.items():
            data.append([name, rem["url"]])
        info("Known remote servers")
        log(tabulate(data, headers))

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
            log(tabulate(data, headers))
            log("")
        else:
            WhatsOpt.check_http_error(resp)

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
                    "Found local analysis code (id=#{}) " "pulled from {}".format(
                        mda_id, whatsopt_url
                    )
                )
                if connected:
                    # connected to another server with a pulled analysis
                    warn("You are connected to a different server")
                    log(
                        "  (use 'wop push <analysis.py>' to push from the local "
                        f"analysis code to the server {self.url})"
                    )
                    log(
                        f"  (use 'wop logout' and 'wop login {whatsopt_url}' "
                        "to log in to the original server)"
                    )
                else:
                    log(f"  (use 'wop login {whatsopt_url}' command to log in)")
        else:
            info("No local analysis found")
            if connected:
                log(
                    "  (use 'wop list' and 'wop pull <id>' to retrieve an existing analysis)\n"
                    "  (use 'wop push <analysis.py>' to push from the local OpenMDAO code to the server)"
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
        push_cmd = PushCommand(problem, depth, scalar)

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
            WhatsOpt.check_http_error(resp)
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
        WhatsOpt.check_http_error(resp)
        log("{} {} pushed".format(key, attrs["name"]))

    def pull_mda(self, mda_id, options={}, msg=None, info_keep_run_ops=True):
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

        format_query = framework
        if options.get("--package"):
            format_query += "_pkg"

        url = self.endpoint(
            ("/api/v1/analyses/{}/exports/new.{}{}".format(mda_id, format_query, param))
        )
        resp = self.session.get(url, headers=self.headers, stream=True)
        WhatsOpt.check_http_error(resp)
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
            # cmd = "Pull"
            # if options.get("--update"):
            #     cmd = "Update"
            info(
                "***************************************************\n"
                "* DRY RUN mode (actions are listed but not done) *\n"
                "***************************************************"
            )

        # Special case: When framework switch we have to update
        # user analysis main file which name depends on package name
        framework_switch = is_framework_switch(framework)
        if framework_switch:
            url = self.endpoint(f"/api/v1/analyses/{mda_id}/openmdao_impl")
            resp = self.session.get(url, headers=self.headers, stream=True)
            WhatsOpt.check_http_error(resp)
            mda_name = resp.json()["packaging"]["package_name"]
        else:
            mda_name = ""

        for f in filenames:
            file_to = f
            file_to_move[file_to] = True
            if os.path.exists(file_to):
                if options.get("--force"):
                    log(f"Update {file_to}")
                    if options.get("--dry-run"):
                        file_to_move[file_to] = False
                    else:
                        os.remove(file_to)
                elif options.get("--update"):
                    if is_run_script_file(f) and not options.get("--run-ops"):
                        if info_keep_run_ops:
                            info(f"Keep existing {file_to} (use -r to override)")
                        file_to_move[file_to] = False
                        continue
                    if is_test_file(f) and not options.get("--test-units"):
                        file_to_move[file_to] = False
                        continue
                    if is_user_file(f):
                        file_to_move[file_to] = False
                        # Have to update user analysis main file when switching frameworks
                        if is_framework_switch and is_analysis_user_file(mda_name, f):
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
                if options.get("--force"):
                    log(f"Pull {file_to}")
                    if options.get("--dry-run"):
                        file_to_move[file_to] = False
                elif options.get("--update") and (
                    (is_run_script_file(f) and not options.get("--run-ops"))
                    or (is_test_file(f) and not options.get("--test-units"))
                    or is_user_file(f)
                ):
                    file_to_move[file_to] = False
                else:
                    log(f"Pull {file_to}")

        if not options.get("--dry-run"):
            move_files(file_to_move, tempdir)
            state = {
                "whatsopt_url": self._url,
                "analysis_id": mda_id,
                "framework": framework,
                "pull_mode": MODE_PACKAGE if options.get("--package") else MODE_PLAIN,
            }
            save_state(state)
            info(msg)

    def pull_mda_json(self, mda_id):
        url = self.endpoint(f"/api/v1/analyses/{mda_id}.wopjson")
        resp = self.session.get(url, headers=self.headers, stream=True)
        WhatsOpt.check_http_error(resp)
        print(json.dumps(resp.json()))

    def pull_project_json(self, project_id):
        url = self.endpoint(f"/api/v1/design_projects/{project_id}.wopjson")
        resp = self.session.get(url, headers=self.headers, stream=True)
        WhatsOpt.check_http_error(resp)
        print(json.dumps(resp.json()))

    def update_mda(self, analysis_id=None, options={}, info_keep_run_ops=True):
        mda_id = analysis_id or get_analysis_id()
        if mda_id and not analysis_id:
            url = get_whatsopt_url()
            if url != self.url:
                warn(
                    f"You want to update code pulled from {url} while you are logged in {self.url}."
                )
                info(
                    f"  use 'wop login {url}' and retry to update using the original remote."
                )
                info(
                    f"  use 'wop update -a <id>' to update using analysis #<id> from {self.url}."
                )
                sys.exit(-1)
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
                or (not opts["--openmdao"] and is_based_on(FRAMEWORK_GEMSEO)),
                "--openmdao": opts["--openmdao"]
                or (not opts["--gemseo"] and is_based_on(FRAMEWORK_OPENMDAO)),
                "--package": is_package_mode(),
            }
        )
        self.pull_mda(
            mda_id, opts, "Analysis #{} updated".format(mda_id), info_keep_run_ops
        )

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
            WhatsOpt.check_http_error(resp)
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
        # Test sqlite files generated with MPI
        _, extension = os.path.splitext(filename)
        parallel_sqlite = re.match(r"\.sqlite_\d+$", extension)

        name = cases = statuses = None
        if not os.path.exists(filename):
            error(f"File not found ({filename})")
            sys.exit(-1)
        if os.path.basename(filename) == "mda_init.py":
            self.upload_vars_init_cmd(
                filename, {"--dry-run": dry_run, "--analysis-id": mda_id}
            )
        elif filename.endswith(".csv"):
            name, cases, statuses = load_from_csv(filename)
        elif filename.endswith(".sqlite") or (parallel_sqlite and parallel):
            name, cases, statuses = load_from_sqlite(filename, parallel)
        elif filename.endswith(".hdf5"):
            name, cases, statuses = load_from_hdf5(filename)
        else:
            error(
                f"Can not upload file {filename}: extension not recognized"
                " (should be either .csv, .sqlite or .hdf5)"
            )
            sys.exit(-1)

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
        WhatsOpt.check_http_error(resp)
        log("Results data from {} uploaded with driver {}".format(filename, driver))
        if mda_id:
            log(f"attached to analysis #{mda_id}")

    def upload_vars_init_cmd(self, py_filename, options):
        def upload_vars_init(prob):
            self.upload_vars_init(prob, options)
            sys.exit()

        d = os.path.dirname(py_filename)
        run_mda_filename = os.path.join(d, "run_mda.py")
        if not os.path.exists(run_mda_filename):
            error(f"Can not get analysis init: script {run_mda_filename} not found.")
        hooks.use_hooks = True
        hooks._register_hook("final_setup", "Problem", post=upload_vars_init)
        _load_and_exec(run_mda_filename, [])

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
            WhatsOpt.check_http_error(resp)
            log("Variables init values uploaded")

    def check_versions(self):
        url = self.endpoint("/api/v1/versioning")
        resp = self.session.get(url, headers=self.headers)
        WhatsOpt.check_http_error(resp)
        version = resp.json()
        log("WhatsOpt {} requires wop {}".format(version["whatsopt"], version["wop"]))
        log(f"You are using wop {__version__}")

    @staticmethod
    def serve(port):
        try:
            import thrift  # noqa: F401
        except ImportError:
            error(
                "Apache Thrift is not installed. You can install it with : 'pip install thrift'"
            )
            exit(-1)
        try:
            import os
            import sys

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
        if not (extension == ".sqlite" or re.match(r"\.sqlite_\d+$", extension)):
            warn(
                f"File {filename} should have '.sqlite[_n]' extension, got '{extension}'"
            )
        basename = os.path.basename(pathname)
        convert_sqlite_to_csv(filename, basename)

    def publish(self, force=False, analysis_id=None):
        mda_id = analysis_id if analysis_id else get_analysis_id()
        url = self.endpoint(f"/api/v1/analyses/{mda_id}/package")
        if not force:
            resp = self.session.get(url, headers=self.headers)
            if resp.ok:
                existing_meta = resp.json()
            elif resp.status_code == HTTPStatus.NOT_FOUND:
                existing_meta = None
            else:
                WhatsOpt.check_http_error(resp)

            if existing_meta:
                warn(
                    f"Existing package {existing_meta['name']} {existing_meta['version']} will be lost."
                )
                answer = input("Do you want to continue? (yes/no): ")
                if answer.lower() == "yes":
                    pass
                else:
                    info("Publishing aborted")
                    exit(-1)

        info("Package building...")
        filename = self.build()
        if not os.path.exists(filename):
            error(f"File {filename} not found")
            exit(-1)
        meta = get_pkg_metadata(filename)
        if (
            not force
            and existing_meta
            and existing_meta["name"] == meta.name
            and Version(existing_meta["version"]) >= Version(meta.version)
        ):
            error(f"You have to bump the version (> {existing_meta['version']})")
            error("Publishing aborted")
            exit(-1)

        files = {
            "package[description]": (None, meta.summary, "application/json"),
            "package[archive]": (filename, open(filename, "rb"), "application/gzip"),
        }
        info("Package publishing...")
        resp = self.session.post(url, headers=self.headers, files=files)
        if resp.ok:
            info(
                f"Package {meta.name} v{meta.version} is published on WopStore({self.endpoint('/packages')})"
            )
        elif resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            error(resp.json()["message"])
            error("Duplicate detected! The package already exists on WopStore!")
            exit(-1)
        else:
            WhatsOpt.check_http_error(resp)

    def build(self):
        if not is_package_mode():
            error("Package mode is required!")
            exit(-1)
        self._update_mda_base()
        filename = build_package()
        return filename

    def fetch(self, source_id=None, options={}):
        if not is_package_mode():
            error("Package mode is required!")
            exit(-1)
        mda_id = get_analysis_id()
        param = f"?src_id={source_id}"
        format_query = "mda_pkg_content"
        url = self.endpoint(
            f"/api/v1/analyses/{mda_id}/exports/new.{format_query}{param}"
        )
        resp = self.session.get(url, headers=self.headers, stream=True)
        if resp.ok:
            name = None
            with tempfile.NamedTemporaryFile(
                suffix=".zip", mode="wb", delete=False
            ) as fd:
                for chunk in resp.iter_content(chunk_size=128):
                    fd.write(chunk)
                name = fd.name
            zipf = zipfile.ZipFile(name, "r")
            tempdir = tempfile.mkdtemp(suffix="wop", dir=tempfile.tempdir)
            zipf.extractall(tempdir)
            filenames = zipf.namelist()
            if not filenames:
                warn(
                    f"Fetching but no package found for analysis #{source_id}, nothing to do"
                )
                return
            zipf.close()

            file_to_move = {}
            for f in filenames:
                file_to = f
                file_to_move[file_to] = True
                if os.path.exists(file_to):
                    if options.get("--force"):
                        log(f"Fetch {file_to}")
                        if options.get("--dry-run"):
                            file_to_move[file_to] = False
                        else:
                            os.remove(file_to)
                    else:
                        warn(
                            f"File {file_to} in the way: remove it or use --force to override"
                        )
                        file_to_move[file_to] = False
                else:
                    log(f"Fetch {file_to}")
            if not options.get("--dry-run"):
                move_files(file_to_move, tempdir)
                info(f"Analysis #{source_id} disciplines fetched")
        else:
            error(f"Error while fetching disciplines of analysis #{source_id}")
            error(resp.json().get("message"))

    def merge(self, source_id, options={}):
        if not is_package_mode():
            error("Package mode is required!")
            exit(-1)
        current_id = get_analysis_id()
        if int(source_id) == current_id:
            warn(f"Merging analysis #{current_id} in itself, nothing to do")
            return
        url = self.endpoint(f"/api/v1/analyses/{current_id}")
        params = {
            "analysis": {
                "import": {"analysis": source_id},
            },
            "requested_at": str(datetime.now()),
        }
        if options.get("--dry-run"):
            self.get_status()
            url = self.endpoint("/api/v1/analyses/{}".format(source_id))
            resp = self.session.get(url, headers=self.headers)
            log(f"Analysis #{source_id} #{resp.json()} is selected to be merged")
        else:
            resp = self.session.put(url, headers=self.headers, json=params)
        if resp.ok:
            if not options.get("--dry-run"):
                info(f"Analysis #{source_id} merged")
        elif resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            error(f"Error while merging analysis #{source_id}.")
            error(
                "    Check analyses, maybe they are not compatible (same variable produced by different disciplines)"
            )
        elif resp.status_code == HTTPStatus.FORBIDDEN:
            error(f"Error while merging analysis #{source_id}.")
            error(
                "    You are not authorized to update the current analysis: either you do not own it or"
                " current analysis is already packaged or operated"
            )
        else:
            error(f"Error while merging analysis #{source_id}")
            WhatsOpt.check_http_error(resp)

    def pull_source_mda(self, source_id, options={}):
        self.merge(source_id, options)
        self.fetch(source_id, options)
        self._update_mda_base(options.get("--dry-run"))

    def _update_mda_base(self, dry_run=False, force=False):
        update_options = {
            "--dry-run": dry_run,
            "--force": force,
            "--server": False,
            "--egmdo": False,
            "--run-ops": False,
            "--test-units": False,
            "--gemseo": is_based_on(FRAMEWORK_GEMSEO),
            "--openmdao": is_based_on(FRAMEWORK_OPENMDAO),
        }
        mda_id = get_analysis_id()
        self.update_mda(mda_id, update_options, info_keep_run_ops=False)

    def _test_connection(self):
        if self.api_key:
            self.headers = {
                "Authorization": "Token token=" + self.api_key,
                "User-Agent": "wop/{}".format(__version__),
            }
            url = self.endpoint("/api/v1/versioning")
            debug(f"Test connect: {url}, {self.api_key}")
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

    @staticmethod
    def check_http_error(resp):
        msg = resp.json().get("message")
        if msg:
            warn(msg)
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            error(f"HTTP Error : {http_err}")
            exit(-1)
