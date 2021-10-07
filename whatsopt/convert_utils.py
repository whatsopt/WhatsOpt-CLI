import csv
import openmdao.api as om
from whatsopt.logging import log

from whatsopt.upload_utils import load_sqlite_file


def convert_sqlite_to_csv(sqlite_filename, basename):
    cr = om.CaseReader(sqlite_filename)
    driver_cases = cr.list_cases("driver", out_stream=None)
    design_vars = sorted(cr.get_case(driver_cases[0]).get_design_vars())
    driver_name, cases, statuses = load_sqlite_file(sqlite_filename)
    all_vars = [v["varname"] for v in cases]
    out_vars = sorted(list(set(all_vars) - set(design_vars)))

    fieldnames = []
    values = {}
    nb_cases = len(statuses)
    for name in design_vars + out_vars:
        for case in cases:
            if name == case["varname"]:
                if case["coord_index"] == -1:
                    fieldnames.append(name)
                    values[name] = case["values"]
                else:
                    name_i = f"{name}[{case['coord_index']}]"
                    fieldnames.append(name_i)
                    values[name_i] = case["values"]

    outfile = f"{basename}.csv"
    with open(outfile, "w") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\n")
        writer.writerow(["success"] + fieldnames)

        for i in range(nb_cases):
            data = [statuses[i]]
            for var in fieldnames:
                data.append(values[var][i])
            writer.writerow(data)
    log(f"Convert {nb_cases} cases ({driver_name}) to {outfile}")
