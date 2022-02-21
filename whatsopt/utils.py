import os, re
from whatsopt.logging import error

WOP_CONF_FILENAME = ".wop"

WHATSOPT_URL_KEY = "whatsopt_url"
ANALYSIS_ID_KEY = "analysis_id"
FRAMEWORK_KEY = "framework"
PULL_MODE_KEY = "pull_mode"

FRAMEWORK_OPENMDAO = "openmdao"
FRAMEWORK_GEMSEO = "gemseo"

MODE_PLAIN = "plain"
MODE_PACKAGE = "package"


def save_state(url, mda_id, framework, pull_mode):
    with open(WOP_CONF_FILENAME, "w") as f:
        state = {}
        state[WHATSOPT_URL_KEY] = url
        state[ANALYSIS_ID_KEY] = mda_id
        state[FRAMEWORK_KEY] = framework
        state[PULL_MODE_KEY] = pull_mode
        content = f"""
# This file contains recorded state from wop pull/update commands
# DO NOT EDIT unless you know what you are doing
{WHATSOPT_URL_KEY}: {state[WHATSOPT_URL_KEY]}
{ANALYSIS_ID_KEY}: {state[ANALYSIS_ID_KEY]}
{FRAMEWORK_KEY}: {state[FRAMEWORK_KEY]}
{PULL_MODE_KEY}: {state[PULL_MODE_KEY]}
"""
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
                exit(-1)
    if not state.get("wop_format_version"):
        state["wop_format_version"] = 1
    return state


def snakize(name):
    snaked = re.sub(
        r"(^|([a-z])\W?)([A-Z])",
        lambda m: m.group(2) + "_" + m.group(3).lower()
        if m.group(1)
        else m.group(3).lower(),
        name,
    )
    snaked = re.sub("[-\.\s]", "_", snaked)
    snaked = re.sub("__+", "_", snaked).lower()
    return snaked


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
        for line in f:
            match = re.match(rf"^# {key}: (.*)", line)
            if match:
                ident = match.group(1)
                break
    return ident


def extract_mda_id(file):
    return _extract_key(file, ANALYSIS_ID_KEY)


def extract_origin_url(file):
    return _extract_key(file, WHATSOPT_URL_KEY)


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
    if state.get(ANALYSIS_ID_KEY):
        return state[ANALYSIS_ID_KEY]
    else:
        return _get_key(ANALYSIS_ID_KEY, directory)


def get_whatsopt_url(directory="."):
    state = load_state()
    if state.get(WHATSOPT_URL_KEY):
        return state[WHATSOPT_URL_KEY]
    else:
        try:
            return _get_key(WHATSOPT_URL_KEY, directory)
        except ValueError:
            return False


def is_based_on(module, directory="."):
    state = load_state()
    if state.get(FRAMEWORK_KEY):
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
    return state.get(PULL_MODE_KEY) and state[PULL_MODE_KEY] == MODE_PACKAGE
