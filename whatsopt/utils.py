import os, re

ANALYSIS_ID_KEY = "analysis_id"
WHATSOPT_URL_KEY = "whatsopt_url"


def is_user_file(f):
    return (
        not re.match(r".*_base\.py$", f)
        and not re.match(r"^run_.*\.py$", f)
        and not re.match(r"^server/", f)
    )


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
            raise Exception(
                "Several {} key detected. "
                "Find {} then {}.\n"
                "Check header comments in {} files.".format(
                    key, val, newval, str(files)
                )
            )
        val = newval
    return val


def get_analysis_id(directory="."):
    return _get_key(ANALYSIS_ID_KEY, directory)


def get_whatsopt_url(directory="."):
    return _get_key(WHATSOPT_URL_KEY, directory)
