import sys
import time
import numpy as np
from requests.exceptions import RequestException
from .whatsopt_client import WhatsOpt
from .logging import error
from .optimization import Optimization

SEGMOOMOE = "SEGMOOMOE"


class OptimizationError(Exception):
    pass


class ValidOptimumNotFoundError(Exception):
    pass


class MOOptimization(Optimization):
    def __init__(self, xtypes, kind=SEGMOOMOE, n_obj=2, cstr_specs=None, options=None):
        try:
            self._kind = kind
            self._n_obj = n_obj
            self._xtypes = xtypes
            self._cstr_specs = cstr_specs or []
            self._options = options
            self._init_optimization()
        except RequestException as e:
            raise OptimizationError(f"Connection failed during initialization")

    def _init_config(self):
        return {
            "kind": self._kind,
            "n_obj": self._n_obj,
            "xlimits": [],  # not used
            "xtypes": self._xtypes,
            "cstr_specs": self._cstr_specs,
            "options": self._options,
        }
