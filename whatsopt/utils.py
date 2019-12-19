import os, re, csv

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
