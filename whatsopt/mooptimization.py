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
    def __init__(self, xtypes, n_obj=2, cstr_specs=None, options=None):
        try:
            self._kind = SEGMOOMOE  # at the moment only one kind of MOO optimizer
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

    def run(self, f_grouped, n_iter=1):
        optima = None
        for i in range(n_iter):
            with_best = (i == n_iter-1) 
            x_suggested, status, optima = self.ask(with_best)
            print(
                "{} x suggested = {} with status: {}".format(
                    i, x_suggested, Optimization.STATUSES[status]
                )
            )

            # compute objective function at the suggested point
            new_y = f_grouped(np.atleast_2d(x_suggested))
            print("new y = {}".format(new_y))

            self.tell(x_suggested, new_y)

        print(f"Pareto front {optima}")
        return optima

    def get_pareto(self):
        pass
