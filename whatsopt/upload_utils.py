import os
import re
import csv
import sys
from openmdao.api import CaseReader
from tabulate import tabulate
from whatsopt.logging import log, error


def load_from_csv(filename):
    name = os.path.splitext(os.path.basename(filename))[0]
    m = re.match(r"\w+__(\w+)", name)
    if m:
        name = m.group(1)

    with open(filename) as csvfile:
        reader = csv.reader(csvfile, delimiter=";")
        cases = []  # [{"varname": varname, "coord_index": idx, "values": []}]
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


def load_from_sqlite(filename, parallel=False):
    if parallel:
        m = re.match(r"(.*_)(\d+)$", filename)
        if m:
            file_prefix = m.group(1)
            file_count = int(m.group(2)) + 1
            name, cases, statuses = load_sqlite_file(filename)
            next_filename = file_prefix + str(file_count)
            while os.path.exists(next_filename):
                _, tmp_cases, tmp_statuses = load_sqlite_file(next_filename)
                for i, tmp_case in enumerate(tmp_cases):
                    cases[i]["values"].extend(tmp_case["values"])
                statuses.extend(tmp_statuses)
                file_count = file_count + 1
                next_filename = file_prefix + str(file_count)
            return name, cases, statuses
        else:
            error(
                "In parallel mode (-p option), "
                "filename should end with '_<number>', got {}".format(filename)
            )
            sys.exit(-1)
    else:
        return load_sqlite_file(filename)


def load_from_hdf5(filename):
    try:
        from gemseo.algos.opt_problem import OptimizationProblem
    except ImportError:
        error("GEMSEO module not found: cannot upload hdf5")
        sys.exit(-1)

    opt_pb = OptimizationProblem.import_hdf(filename)
    ds = opt_pb.export_to_dataset("OptimizationProblem")

    name = os.path.splitext(os.path.basename(filename))[0]
    driver_kind = "DOE"
    m = re.match(r"\w+_(doe|optim)", name)
    if m and m.group(1) == "optim":
        driver_kind = "optimizer"

    name = f"GEMSEO_{driver_kind}_ALGO"
    cases = []
    statuses = []

    for varname, data in ds.get_all_data(by_group=False, as_dict=True).items():
        for j in range(data.shape[1]):
            coord_index = -1
            if data.shape[1] > 1:
                coord_index = j
            values = data[:, j].tolist()
            cases.append(
                {"varname": varname, "coord_index": coord_index, "values": values}
            )

    statuses = len(cases[0]["values"]) * [1]
    return name, cases, statuses


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


def load_sqlite_file(filename):
    log("Load {}...".format(filename))
    reader = CaseReader(filename)
    cases = reader.list_cases("driver", out_stream=None)
    if len(cases) == 0:
        error("No case found in {}".format(filename))
        sys.exit(-1)

    # find driver name
    driver_first_coord = cases[0]
    m = re.match(r"\w+:(\w+)|.*", driver_first_coord)
    name = os.path.splitext(os.path.basename(filename))[0]
    if m:
        name = m.group(1)

    # format cases and statuses
    # cases : [{"varname": varname, "coord_index": idx, "values": [...]}*]
    cases, statuses = _format_upload_cases(reader)
    return name, cases, statuses


def _format_upload_cases(reader):
    cases = reader.list_cases("driver", out_stream=None, recurse=False)
    inputs = {}
    outputs = {}
    statuses = []
    for case_id in cases:
        case = reader.get_case(case_id)
        if not case.get_design_vars():
            error("No design variable found in recorded cases")
            sys.exit(-1)
        _insert_data(case.get_design_vars(), inputs)
        if not case.outputs:
            error("No output found in recorded cases")
            sys.exit(-1)
        _insert_data(case.outputs, outputs)
        statuses.append(case.success)

    cases = inputs.copy()
    cases.update(outputs)
    inputs_count = _check_count(inputs)
    outputs_count = _check_count(outputs)
    if (inputs_count != outputs_count) or (inputs_count != len(statuses)):
        raise Exception(
            "Bad counts: inputs({})!=outputs({}) or inputs({})!=statuses({})".format(
                inputs_count, outputs_count, inputs_count, len(statuses)
            )
        )

    data = []
    for key, values in cases.items():
        idx = key[1]
        if key[2] == 1:
            idx = -1  # consider it is a scalar not an array of 1 elt
        data.append({"varname": key[0], "coord_index": idx, "values": values})

    return data, statuses


def _insert_data(data_io, result):
    done = {}
    for name in data_io:
        values = data_io[name]
        if name in done:
            continue
        values = values.reshape(-1)
        for i in range(values.size):
            if (name, i, values.size) in result:
                result[(name, i, values.size)].append(float(values[i]))
            else:
                result[(name, i, values.size)] = [float(values[i])]
        done[name] = True


def _check_count(ios):
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
