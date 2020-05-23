import re
import os
import tempfile
from contextlib import contextmanager

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
def extract_disc_var2(fullname):
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
