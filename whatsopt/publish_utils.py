from pkginfo import SDist
from build import ProjectBuilder
import os


def get_pkg_metadata(filename):
    meta_pkg = SDist(filename)
    return meta_pkg


def build_package():
    # FIXME: Disable annoying warning
    # BetaConfiguration: Support for `[tool.setuptools]` in `pyproject.toml` is still *beta*.
    os.environ["PYTHONWARNINGS"] = "ignore"
    return ProjectBuilder(".").build("sdist", "dist")
