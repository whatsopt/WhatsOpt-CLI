import sys
import time
import numpy as np
from requests.exceptions import RequestException
from .whatsopt_client import WhatsOpt
from .logging import error
from .optimization import Optimization

# from smt.applications.mixed_integer import FLOAT, INT, ORD, ENUM
# To avoid smt dependency replicate SMT mixed integer types 
FLOAT = "float_type"
INT = "int_type"
ORD = "ord_type"
ENUM = "enum_type"

SEGMOOMOE = "SEGMOOMOE"


class OptimizationError(Exception):
    pass

class MOOptimization(Optimization):
    def __init__(self, xtypes=None, n_obj=2, cstr_specs=None, options=None, xlimits=None):
        self._kind = SEGMOOMOE  # at the moment only one kind of MOO optimizer
        self._n_obj = n_obj
        self._cstr_specs = cstr_specs or []
        self._options = options

        if xtypes is None and xlimits is None:
            raise OptimizationError("Configuration Error: you should specify either xtypes or xlimits")

        if not (xtypes is None or xlimits is None):
            raise OptimizationError("Configuration Error: you should specify either xtypes or xlimits exclusively, not both")

        if xtypes is None and xlimits is not None:
            self._xtypes = []
            for xlim in xlimits:
                xlim = np.asarray(xlim).tolist()
                self._xtypes.append({"type": FLOAT, "limits": xlim})
            print(f"Convert {xlimits} to {self._xtypes}")
        else:
            self._xtypes = xtypes

        self._init_optimization()

    def _init_config(self):
        return {
            "kind": self._kind,
            "n_obj": self._n_obj,
            "xlimits": [],  # not used
            "xtypes": self._xtypes,
            "cstr_specs": self._cstr_specs,
            "options": self._options,
        }

