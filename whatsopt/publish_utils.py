from pkginfo import SDist
from build import ProjectBuilder


def get_pkg_metadata(filename):
    meta_pkg = SDist(filename)
    return meta_pkg


def build_package():
    return ProjectBuilder(".").build("sdist", "dist")
