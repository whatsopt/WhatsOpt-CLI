import os, re


# wop pull_mda
def is_user_file(f):
    return (
        not re.match(r".*_base\.py$", f)
        and not re.match(r"^run_.*\.py$", f)
        and not re.match(r"^server/", f)
    )


# wop get_analysis_id
def find_analysis_base_files(directory="."):
    files = []
    for f in os.listdir(directory):
        if f.endswith("_base.py"):
            files.append(f)
    return files


# wop get_analysis_id
def extract_mda_id(file):
    ident = None
    with open(file, "r") as f:
        for line in f:
            match = re.match(r"^# analysis_id: (\d+)", line)
            if match:
                ident = match.group(1)
                break
    return ident


def get_analysis_id():
    files = find_analysis_base_files()
    aid = None
    for f in files:
        ident = extract_mda_id(f)
        if aid and aid != ident:
            raise Exception(
                "Warning: several analysis identifier detected. \n"
                "Find %s got %s. Check header comments in %s files ."
                % (aid, ident, str(files))
            )
        aid = ident
    return aid
