import os, re, csv
from six import iteritems
from openmdao.api import CaseReader
from tabulate import tabulate
from whatsopt.logging import log

# wop upload
def load_from_csv(filename):
    name = os.path.splitext(os.path.basename(filename))[0]
    m = re.match(r"\w+__(\w+)", name)
    if m:
        name = m.group(1)

    with open(filename) as csvfile:
        reader = csv.reader(csvfile, delimiter=";")
        cases = []
        statuses = []
        success_idx = -1
        for line, row in enumerate(reader):
            if line == 0:
                for col, elt in enumerate(row):
                    if elt == "success":
                        success_idx = col
                    else:
                        varname = elt
                        idx = -1
                        m = re.match(r"(\w+)\[(\d+)\]", elt)
                        if m:
                            varname = m.group(1)
                            idx = int(m.group(2))
                        cases.append(
                            {"varname": varname, "coord_index": idx, "values": []}
                        )
            else:
                for col, elt in enumerate(row):
                    if col == success_idx:
                        statuses.append(int(elt))
                    elif success_idx > -1:
                        if col < success_idx:
                            cases[col]["values"].append(float(elt))
                        elif col == success_idx:
                            statuses.append(int(elt))
                        else:  # col > success_idx
                            cases[col - 1]["values"].append(float(elt))
                    else:  # no success column
                        cases[col]["values"].append(float(elt))

        if len(cases) > 0 and success_idx == -1:
            statuses = len(cases[0]["values"]) * [1]
    return name, cases, statuses


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


# push_command collect_var_infos
def format_shape(scalar_format, shape):
    shape = shape.replace("L", "")  # with py27 we can get (1L,)
    if scalar_format and shape == "(1,)":
        shape = "1"
    return shape


# push_command _get_sub_analysis_attributes & wop _get_discipline_attributes
def to_camelcase(name):
    return re.sub(r"(?:^|_)(\w)", lambda x: x.group(1).upper(), name)


# utils format_upload_cases
def check_count(ios):
    count = None
    refname = None
    for name in ios:
        if count and count != len(ios[name]):
            raise Exception(
                "Bad value count between (%s, %d) and (%s, %d)"
                % (refname, count, name, len(ios[name]))
            )
        else:
            refname, count = name, len(ios[name])
    return count


# utils format_upload_cases
def insert_data(data_io, result):
    done = {}
    for n in data_io._values.dtype.names:
        values = data_io._values[n]
        name = n.split(".")[-1]
        if name in done:
            continue
        values = values.reshape(-1)
        for i in range(values.size):
            if (name, i, values.size) in result:
                result[(name, i, values.size)].append(float(values[i]))
            else:
                result[(name, i, values.size)] = [float(values[i])]
        done[name] = True


# wop upload
def load_from_sqlite(filename):
    reader = CaseReader(filename)
    cases = reader.list_cases("driver")
    if len(cases) == 0:
        raise Exception("No case found in {}".format(filename))

    # find driver name
    driver_first_coord = cases[0]
    m = re.match(r"\w+:(\w+)|.*", driver_first_coord)
    name = os.path.splitext(os.path.basename(filename))[0]
    if m:
        name = m.group(1)

    # format cases and statuses
    cases, statuses = format_upload_cases(reader)
    return name, cases, statuses


# utils load_from_sqlited
def format_upload_cases(reader):
    cases = reader.list_cases("root", recurse=False)
    inputs = {}
    outputs = {}
    for case_id in cases:
        if "compute_totals_approx" not in case_id:
            case = reader.get_case(case_id)
            if case.inputs is not None:
                insert_data(case.inputs, inputs)
            if case.outputs is not None:
                insert_data(case.outputs, outputs)
    cases = inputs.copy()
    cases.update(outputs)
    inputs_count = check_count(inputs)
    outputs_count = check_count(outputs)
    assert inputs_count == outputs_count
    data = []
    for key, values in iteritems(cases):
        idx = key[1]
        if key[2] == 1:
            idx = -1  # consider it is a scalar not an array of 1 elt
        data.append({"varname": key[0], "coord_index": idx, "values": values})

    statuses = []
    cases = reader.list_cases("driver", recurse=False)
    for case_id in cases:
        # if driver_regexp.match(case_id):
        case = reader.get_case(case_id)
        statuses.append(case.success)
    assert inputs_count == len(statuses)

    return data, statuses


# push_command get_mda_attributes
def simple_value(var):
    typ = var["type"]
    if var["shape"] == "1" or var["shape"] == "(1,)":
        ret = float(var["value"])
        if typ == "Integer":
            ret = int(ret)
    else:
        if typ == "Integer":
            var["value"] = var["value"].astype(int)
        else:
            var["value"] = var["value"].astype(float)
        ret = var["value"].tolist()
    return str(ret)


# push_command _get_varattr_from_connection
def extract_disc_var(fullname):
    name_elts = fullname.split(".")
    if len(name_elts) > 1:
        mda, disc, var = (
            ".".join(name_elts[:-2]),
            ".".join(name_elts[:-1]),
            name_elts[-1],
        )
    else:
        raise Exception(
            "Connection qualified name should contain"
            + " at least one dot, but got %s" % fullname
        )
    return mda, disc, var


# wop upload
def print_cases(cases, statuses):
    headers = ["success"]
    n = len(cases[0]["values"]) if cases else 0
    for case in cases:
        h = case["varname"]
        if case["coord_index"] > -1:
            h += "[{}]".format(case["coord_index"])
        headers.append(h)
    data = []
    for i in range(n):
        data.append([statuses[i]] + [case["values"][i] for case in cases])
    log(tabulate(data, headers))
