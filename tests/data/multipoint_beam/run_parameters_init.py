# -*- coding: utf-8 -*-
"""
  mda_init.py
"""
import numpy as np
from numpy import nan


def initialize(mda):
    mda["h_cp"] = [1.0, 1.0, 1.0, 1.0, 1.0]


if __name__ == "__main__":
    from tabulate import tabulate

    mda = {}
    initialize(mda)
    headers = ["parameter", "value"]
    data = [[k, mda[k]] for k in mda]
    print(tabulate(data, headers))
