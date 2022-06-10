import numpy as np
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
    def __init__(
        self, xtypes=None, n_obj=2, cstr_specs=None, options=None, xlimits=None
    ):
        """Creation of a mixed-integer multi-objectives optimization context

        Parameters
        ----------
        xtypes: list of x inputs type specification (maybe optional if xlimits is specified, see below).
            A type specification consists in a dictionary of two items {type: ... , limits: ...} where type is either
            FLOAT, INT, ORD or ENUM and limits the corresponding bounds: for instance [-1.5, 3.0] for a FLOAT
            [1, 3] for an INT [1, 5, 7, 12] for an ORD and ["red", "green", "blue"] for an ENUM.
        n_obj: number of objectives (default=2)
        cstrs_specs: list of inequality constraints specifications (optional)
            A constraint specification is a dictionary of two items {type: ..., bound: ..., tol: ...}
            where type is either '<' or '>', bound is a float value specifying a limit and tol the
            acceptable tolerance before violation (ex if we want cstr_value < bound, we accept cstr_value < bound + tol)
        options: dictionary containing options to be passed to the mixed-integer multi-objectives optimizer
        xlimits: list of float limits in case we are dealing with float inputs
            Convenient way when x inputs are floats to specify only [[lower bound, upper bound], ...].

        Returns
        -------
        Optimizer handle allowing to trigger remote optimization operations

        """
        self._kind = SEGMOOMOE  # at the moment only one kind of MOO optimizer
        self._n_obj = n_obj
        self._cstr_specs = cstr_specs or []
        self._options = options

        if xtypes is None and xlimits is None:
            raise OptimizationError(
                "Configuration Error: you should specify either xtypes or xlimits"
            )

        if not (xtypes is None or xlimits is None):
            raise OptimizationError(
                "Configuration Error: you should specify either xtypes or xlimits exclusively, not both"
            )

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
