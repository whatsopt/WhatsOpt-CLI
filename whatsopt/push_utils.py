import re
import os
import tempfile
from contextlib import contextmanager


def cut(mda_attrs, depth):
    if depth <= 0:
        return mda_attrs
    elif depth == 1:
        flatten(mda_attrs)
    else:
        for disc in mda_attrs["disciplines_attributes"]:
            sub_mdattrs = disc.get("sub_analysis_attributes")
            if sub_mdattrs:
                cut(sub_mdattrs, depth - 1)


def flatten(mda_attrs):
    # print("-------- flatten ", mda_attrs["name"])
    for disc in mda_attrs["disciplines_attributes"]:
        # print("************** ", disc["name"])
        sub_mdattrs = disc.get("sub_analysis_attributes")
        if sub_mdattrs:
            varattrs = disc.get("variables_attributes", [])
            subdriver = sub_mdattrs["disciplines_attributes"][0]
            # print("<<<< DRIVER ", subdriver["variables_attributes"])
            for vattr in subdriver["variables_attributes"]:
                v = vattr.copy()
                v["io_mode"] = "out" if vattr["io_mode"] == "in" else "in"
                varattrs.append(v)
            del disc["sub_analysis_attributes"]
            disc["variables_attributes"] = varattrs
            # print(">>>>", disc["name"])
            # print(disc["variables_attributes"])

            driver = mda_attrs["disciplines_attributes"][0]
            for vattr in subdriver["variables_attributes"]:
                already_present = [v["name"] for v in driver["variables_attributes"]]
                if vattr["name"] not in already_present:
                    v = vattr.copy()
                    # print("ADD DRIVER of ", mda_attrs["name"], v)
                    driver["variables_attributes"].append(v)


# push_command collect_var_infos
def format_shape(scalar_format, shape):
    shape = shape.replace("L", "")  # with py27 we can get (1L,)
    if scalar_format and shape == "(1,)":
        shape = "1"
    return shape


# push_command _get_sub_analysis_attributes & wop _get_discipline_attributes
def to_camelcase(name):
    return re.sub(r"(?:^|_)(\w)", lambda x: x.group(1).upper(), name)


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


# push_command _get_varattr_from_connection
def extract_mda_var(fullname):
    name_elts = fullname.split(".")
    if len(name_elts) > 1:
        mda, var = name_elts[:-1], name_elts[-1]
    else:
        raise Exception(
            "Connection qualified name should contain"
            + " at least one dot, but got %s" % fullname
        )
    return mda, var


@contextmanager
def problem_pyfile(py_filename, component):
    dirname = os.path.dirname(py_filename)
    filename = os.path.basename(py_filename)
    module = os.path.splitext(filename)[0]
    content = """from openmdao.api import Problem, Group, IndepVarComp
from {} import {}

comp = {}()
comp_name = "{}"


class {}ComponentDiscovery(Group):
    pass


class {}Component(Group):
    pass


model_discovery = {}ComponentDiscovery()
model_discovery.add_subsystem(comp_name, comp, promotes=["*"])
pb_discovery = Problem(model_discovery)
pb_discovery.setup()


inputs = comp.list_inputs(out_stream=None)
indeps = IndepVarComp()
for name, meta in inputs:
    args = {{
        "val": meta.get("value"),
        "shape": meta.get("shape"),
        "desc": meta.get("desc", ""),
        "units": meta.get("units", None)
    }}
    indeps.add_output(name, **args)

model = {}Component()
model.add_subsystem("indeps", indeps, promotes=["*"])
model.add_subsystem(comp_name, comp, promotes=["*"])
pb = Problem(model)
pb.setup()
pb.final_setup()
""".format(
        module,
        component,
        component,
        component,
        component,
        component,
        component,
        component,
    )
    handle, pbfile = tempfile.mkstemp(suffix=".py", dir=dirname)
    os.close(handle)
    with open(pbfile, "w") as pbf:
        pbf.write(content)

    try:
        yield pbfile
    finally:
        os.unlink(pbfile)
