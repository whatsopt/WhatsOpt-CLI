import re

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
