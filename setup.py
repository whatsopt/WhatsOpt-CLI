"""
Author: Remi Lafage <remi.lafage@onera.fr>

This package is distributed under Apache 2 license.
"""

from setuptools import setup
from whatsopt import __version__

CLASSIFIERS = """
Development Status :: 5 - Production/Stable
Intended Audience :: Science/Research
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Programming Language :: Python :: 3
Topic :: Software Development
Topic :: Scientific/Engineering
Operating System :: Microsoft :: Windows
Operating System :: Unix
Operating System :: MacOS
"""

metadata = dict(
    name="wop",
    version=__version__,
    description="WhatsOpt web application command line client",
    author="Rémi Lafage",
    author_email="remi.lafage@onera.fr",
    license="Apache License, Version 2.0",
    classifiers=[_f for _f in CLASSIFIERS.split("\n") if _f],
    packages=["whatsopt"],
    install_requires=[
        "openmdao>=3.0.0",
        "openmdao_extensions>=1.0.0",
        "xdsmjs",
        "Click>=6.7",
        "tabulate>=0.8.2",
        "requests",
        "pyyaml",
    ],
    python_requires=">=3.6",
    entry_points="""
        [console_scripts]
        wop=whatsopt.wop:cli
    """,
    zip_safe=True,
    url="https://github.com/OneraHub/WhatsOpt-CLI",
    download_url="https://github.com/OneraHub/WhatsOpt-CLI/releases",
)

setup(**metadata)
