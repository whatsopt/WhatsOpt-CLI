# -*- coding: utf-8 -*-
"""
  mda_init.py
"""


def initialize(mda):
    mda["x"] = 2
    mda["z"] = [5, 2]


if __name__ == "__main__":
    from tabulate import tabulate

    mda = {}
    initialize(mda)
    headers = ["parameter", "value"]
    data = [[k, mda[k]] for k in mda]
    print(tabulate(data, headers))
