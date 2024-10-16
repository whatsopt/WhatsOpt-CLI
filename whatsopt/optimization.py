import time
import numpy as np
from requests.exceptions import RequestException
from .whatsopt_client import WhatsOpt


SEGOMOE = "SEGOMOE"


class OptimizationError(Exception):
    pass


class Optimization:
    VALID_POINT = 0
    INVALID_POINT = 1
    RUNTIME_ERROR = 2
    SOLUTION_REACHED = 3
    RUNNING = 4
    PENDING = -1

    STATUSES = [
        "valid point",
        "invalid point",
        "runtime error",
        "solution reached",
        "running",
        "pending",
    ]

    DEFAULT_CSTR = {"type": "<", "bound": 0.0, "tol": 1e-4}
    TIMEOUT = 60

    def __init__(self, xlimits, cstr_specs=None, options=None):
        """Creation of a continuous mono objective optimization context

        Parameters
        ----------
        xlimits: list of float limits for x inputs eg [[lower bound, upper bound], ...]
        cstrs_specs: list of inequality constraints specifications (optional)
            A constraint specification is a dictionary of two items {type: ..., bound: ..., tol: ...}
            where type is either '<' or '>', bound is a float value specifying a limit and tol the
            acceptable tolerance before violation (ex if we want cstr_value < bound, we accept cstr_value < bound + tol).
        options: dictionary containing options to be passed to the remote optimizer

        Returns
        -------
        Optimizer handle allowing to trigger remote optimization operations

        """
        self._kind = SEGOMOE  # at the moment only one kind of Optimizer
        self._xlimits = xlimits or []
        self._cstr_specs = cstr_specs or []
        self._options = options
        self._init_optimization()

    def _init_optimization(self):
        try:
            for cstr in self._cstr_specs:
                for k in ["type", "bound", "tol"]:
                    cstr[k] = cstr.get(k, self.DEFAULT_CSTR[k])

            optim_config = self._init_config()

            self._wop = WhatsOpt().login()
            url = self._wop.endpoint("/api/v1/optimizations")
            resp = self._wop.session.post(
                url, headers=self._wop.headers, json={"optimization": optim_config}
            )
            if not resp.ok:
                message = "Unexpected error"
                if resp.json() and resp.json().get("message"):
                    message = resp.json()["message"]
                raise OptimizationError(
                    f"Error {resp.reason} ({resp.status_code}): {message}"
                )

            self._id = resp.json()["id"]
            self._x = np.array([])
            self._y = np.array([])
            self._x_suggested = None
            self._status = self.PENDING
            self._x_best = None
            self._y_best = None
        except RequestException:
            raise OptimizationError("Connection failed during initialization")

    def _init_config(self):
        return {
            "kind": self._kind,
            "n_obj": 1,
            "xlimits": self._xlimits,
            "cstr_specs": self._cstr_specs,
            "options": self._options,
        }

    def tell_doe(self, x, y):
        """Send the initial DOE to the remote optimizer

        This operation should be executed initially to set the initial data used
        to model objectives and constraints.

        Parameters
        ----------
        x : 2d array-like of inputs  [[x1, x2, ...], ...]
        y : 2d array-like of outputs [[obj1, obj2, ..., objn, cstr1, cstr2, ... cstrn], ...]
        """
        self._x_best = None
        self._status = self.PENDING
        self._x = np.atleast_2d(x)
        self._y = np.atleast_2d(y)
        if self._x.shape[0] != self._y.shape[0]:
            raise OptimizationError(
                f"Bad DOE error: DOE x and y should of the same size, got x size = {self._x.shape[0]} and  x size = {self._y.shape[0]}"
            )

    def run(self, f_grouped, n_iter=1, with_best=False):
        """Ask and tell the optimizer to get the optimum in n_iter iteration

        Parameters
        ----------
        f_grouped : function under optimization y = f(x)
            where y is of the form [obj1, obj2, ..., objn, cstr1, cstr2, ... cstrn]

        n_iter : int, iteration budget

        with_best : when set it compute the best point found at each iteration.

        Returns
        -------
        x_opt, y_opt: 2d array, 2d array
            an optimum in case of mono-objective or a list of optima in case
            of multi-objective optimization (Pareto front).
        """
        self._x_best = None
        for i in range(n_iter):
            with_best = with_best or (i == n_iter - 1)
            x_suggested, status, self._x_best, self._y_best = self.ask(with_best)
            print(
                f"{i} x suggested = {x_suggested} with status: {Optimization.STATUSES[status]}"
            )

            if with_best:
                print(f"x_best={self._x_best}")
                print(f"y_best={self._y_best}")

            # compute objective function at the suggested point
            new_y = f_grouped(x_suggested)
            print("new y = {}".format(new_y))

            self.tell(x_suggested, new_y)
            if self.is_solution_reached():
                print("Solution is reached")
                x_suggested, status, self._x_best, self._y_best = self.ask(
                    with_best=True
                )
                self._status = self.SOLUTION_REACHED
                break

        x_opt, y_opt = self.get_result()
        print(f"Found optimum y_opt = {y_opt} at x_opt = {x_opt}")
        return x_opt, y_opt

    def tell(self, x, y):
        """Gives (x, y) values such that y = f(x).

        Parameters
        ----------
        x : 2d array-like of inputs  [x1, x2, ...]
        y : 2d array-like of outputs [obj1, obj2, ..., objn, cstr1, cstr2, ... cstrn]
        """
        self._x = np.vstack((self._x, np.atleast_2d(x)))
        self._y = np.vstack((self._y, np.atleast_2d(y)))

    def ask(self, with_best=False):
        """Trigger optimizer iteration to get next promising location of the optimum

        Parameters
        ----------
        with_best: if set compute also the best (x_best, y_best) point so far among
        points already computed.
        In case of multi-objective the Pareto front is computed.

        Returns
        -------
        status, x_suggested, x_best, y_best
            where status is an status code (int) retuned by the optimizer
                  x_suggested the next promising optimum location
                  x_best, y_best the optima so far
        """
        self._status = self.RUNNING
        self._optimizer_iteration(with_best)
        retry = self.TIMEOUT
        url = self._wop.endpoint("/api/v1/optimizations/{}".format(self._id))
        resp = None
        while retry > 0 and self.is_running():
            resp = self._wop.session.get(url, headers=self._wop.headers)
            if resp.ok:
                result = resp.json()["outputs"]
                self._x_suggested = result["x_suggested"]
                self._status = result["status"]
                if with_best:
                    self._x_best = result["x_best"]
                    self._y_best = result["y_best"]
                else:
                    self._x_best = None
                    self._y_best = None
            elif resp.status_code == 400:
                message = "Unexpected error"
                if resp.json() and resp.json().get("message"):
                    message = resp.json()["message"]
                raise OptimizationError(
                    f"Error {resp.reason} ({resp.status_code}): {message}"
                )

            if self.is_running():
                if retry + 1 % 10 == 0:
                    print("Waiting for result...")
                time.sleep(1)
            retry = retry - 1

        if retry <= 0:
            self._x_suggested = None
            self._status = self.RUNTIME_ERROR
            self._x_best = None
            self._y_best = None
            raise OptimizationError(
                "Time out: please check status and history and may be ask again."
            )

        self._status = self.PENDING

        return self._x_suggested, self._status, self._x_best, self._y_best

    def get_result(self):
        """Retrieve optimum (or optima in case of moo) among the DOE with valid constraints

        Returns
        -------
            x, y where x and y are 2d ndarrays
        """
        if not self._x_best:
            _, _, self._x_best, self._y_best = self.ask(with_best=True)
        x_opt = np.array(self._x_best)
        y_opt = np.array(self._y_best)

        return x_opt, y_opt

    def get_history(self):
        """Retrieve optimization history (initial doe + (x suggestions, y))

        Returns
        -------
            x, y where x and y are 2d ndarrays
        """
        return self._x, self._y

    def get_status(self):
        """Retrieve status string"""
        return self.STATUSES[self._status]

    def is_solution_reached(self):
        return self._status == self.SOLUTION_REACHED

    def is_running(self):
        return self._status == self.RUNNING

    def _get_best_y(self, x):
        y = None
        x = np.array(x)
        for i in range(self._x.shape[0]):
            if np.equal(x, self._x[i]).all():
                y = self._y[i].tolist()
                break
        return y

    def _optimizer_iteration(self, with_best):
        """Run optimizer iteration"""
        if self._x.size == 0 or self._y.size == 0:
            raise OptimizationError(
                f"Empty DOE error: DOE should not be empty, got DOE x={self._x} and DOE y={self._y}"
            )
        if self._x.shape[0] != self._y.shape[0]:
            raise OptimizationError(
                f"Bad DOE error: DOE x and y should of the same size, got x size = {self._x.shape[0]} and  x size = {self._y.shape[0]}"
            )
        try:
            url = self._wop.endpoint("/api/v1/optimizations/{}".format(self._id))
            resp = self._wop.session.put(
                url,
                headers=self._wop.headers,
                json={
                    "optimization": {
                        "x": self._x.tolist(),
                        "y": self._y.tolist(),
                        "with_best": with_best,
                    }
                },
            )
            if not resp.ok:
                self._status = self.RUNTIME_ERROR
                raise OptimizationError(
                    f"Error {resp.reason} ({resp.status_code}): {resp.json().get('message', 'Unexpected Error')}"
                )
        except RequestException as e:
            raise OptimizationError(f"Connection failed: {e}")
