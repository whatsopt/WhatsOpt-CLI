import os
import re
import sys
import tomli_w
from whatsopt.logging import error
from shutil import move


WOP_CONF_FILENAME = ".wop"

WOP_FORMAT_VERSION_KEY = "wop_format_version"
WHATSOPT_URL_KEY = "whatsopt_url"
ANALYSIS_ID_KEY = "analysis_id"
FRAMEWORK_KEY = "framework"
PULL_MODE_KEY = "pull_mode"

FRAMEWORK_OPENMDAO = "openmdao"
FRAMEWORK_GEMSEO = "gemseo"

MODE_PLAIN = "plain"
MODE_PACKAGE = "package"


def save_state(
    state,
    filename=WOP_CONF_FILENAME,
):
    comment = """# This file contains recorded state from wop pull/update commands
# DO NOT EDIT unless you know what you are doing
# Version history:
# * version 2: use toml format, add wop_format_version
# * version 1: initial format "key: val"
# * version 0: no wop file
#
"""
    _state = {}
    _state[WOP_FORMAT_VERSION_KEY] = 2
    _state[WHATSOPT_URL_KEY] = state[WHATSOPT_URL_KEY]
    _state[ANALYSIS_ID_KEY] = int(state[ANALYSIS_ID_KEY])
    _state[FRAMEWORK_KEY] = state[FRAMEWORK_KEY]
    _state[PULL_MODE_KEY] = state[PULL_MODE_KEY]
    content = tomli_w.dumps(_state)

    with open(filename, "w") as f:
        f.write(comment)
        f.write(content)


def load_state(filename=WOP_CONF_FILENAME):
    # Should be able to load version 0, version 1 and version 2 format
    state = {"wop_format_version": 0}
    if not os.path.exists(filename):
        return state
    with open(filename, "r") as f:
        for line in f.readlines():
            line = line.strip()
            if line == "" or line.startswith("#"):
                continue
            m = re.search(r"(\S+)\s*[:=]\s*(\S+)", line)
            if m:
                val = m.group(2)
                if val.startswith('"') or val.startswith("'"):
                    val = val[1:-1]
                if re.match(r"\d+", val):
                    val = int(val)

                state[m.group(1)] = val
            else:
                error(f"Syntax error in {filename} file: line '{line}' invalid")
                sys.exit(-1)
    if not state.get("wop_format_version"):
        state["wop_format_version"] = 1

    return state


def is_user_file(f):
    return (
        not re.match(r".*_base\.py$", f)
        and not is_run_script_file(f)
        and not is_test_file(f)
        and not re.match(r"^.*server/", f)
        and not re.match(r"^.*egmdo/", f)
    )


def is_run_script_file(f):
    return f == "mda_init.py" or re.match(r"^run_.*\.py$", f)


def is_test_file(f):
    return re.match(r"^.*tests/test_.*\.py$", f)


def is_analysis_user_file(name, f):
    return bool(re.match(rf"^{name}\.py$", f))


def find_analysis_base_files(directory="."):
    files = []
    for f in os.listdir(directory):
        if f.endswith("_base.py"):
            files.append(f)
    return files


def _extract_key(file, key):
    ident = None
    with open(file, "r") as f:
        pattern = re.compile(rf"^# {key}: (.*)")
        for line in f:
            match = pattern.match(line)
            if match:
                ident = match.group(1)
                break
    return ident


def extract_remote_name(url_or_name):
    m = re.match(r"https?:\/\/(\w+)", url_or_name)
    if m:  # url
        return m.group(1)
    elif re.match(r"^\w+$", url_or_name):  # name
        return url_or_name
    else:
        print(f"Warning: Can not find remote name out of {url_or_name}")
        return None


def _get_key(key, directory="."):
    files = find_analysis_base_files(directory)
    val = None
    for f in files:
        newval = _extract_key(os.path.join(directory, f), key)
        if val and val != newval:
            raise ValueError(
                "Several {} key detected. "
                "Find #{} then #{}.\n"
                "Check header comments in {} files.".format(
                    key, val, newval, str(files)
                )
            )
        val = newval
    return val


def get_analysis_id(directory="."):
    state = load_state()
    if state["wop_format_version"] > 0:
        return state[ANALYSIS_ID_KEY]
    else:
        return _get_key(ANALYSIS_ID_KEY, directory)


def get_whatsopt_url(directory="."):
    state = load_state()
    if state["wop_format_version"] > 0:
        return state[WHATSOPT_URL_KEY]
    else:
        try:
            return _get_key(WHATSOPT_URL_KEY, directory)
        except ValueError:
            return False


def is_based_on(module, directory="."):
    state = load_state()
    if state["wop_format_version"] > 0:
        return state[FRAMEWORK_KEY] == module
    else:
        files = find_analysis_base_files(directory)
        return len(files) > 0 and all(
            _detect_from_import(os.path.join(directory, f), module) for f in files
        )


def is_framework_switch(framework, directory="."):
    return (
        framework == FRAMEWORK_GEMSEO and is_based_on(FRAMEWORK_OPENMDAO, directory)
    ) or (framework == FRAMEWORK_OPENMDAO and is_based_on(FRAMEWORK_GEMSEO, directory))


def _detect_from_import(file, module):
    detected = False
    with open(file, "r") as f:
        for line in f:
            # TODO: Maybe would need more robust detection... We'll see!
            # first from/import detected gives the framework.
            match = re.match(rf"^(from|import) {module}\..*", line)
            if match:
                detected = True
                break
    return detected


def is_package_mode():
    state = load_state()
    return state and state[PULL_MODE_KEY] == MODE_PACKAGE


def move_files(file_to_move, tempdir):
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
