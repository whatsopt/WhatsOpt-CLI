import sys
import time
import numpy as np
from requests.exceptions import RequestException
from .whatsopt_client import WhatsOpt


SEGOMOE = "SEGOMOE"


class OptimizationError(Exception):
    pass


class ValidOptimumNotFoundError(Exception):
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
        try:
            self._kind = SEGOMOE  # at the moment only one kind of Optimizer
            self._xlimits = xlimits or []
            self._cstr_specs = cstr_specs or []
            self._options = options
            self._init_optimization()
        except RequestException as e:
            raise OptimizationError(f"Connection failed during initialization")

    def _init_optimization(self):
        try:
            for cstr in self._cstr_specs:
                for k in ["type", "bound", "tol"]:
                    cstr[k] = cstr.get(k, self.DEFAULT_CSTR[k])

            optim_config = self._init_config()

            self._wop = WhatsOpt(url="http://localhost:3000").login()
            url = self._wop.endpoint("/api/v1/optimizations")
            resp = self._wop.session.post(
                url, headers=self._wop.headers, json={"optimization": optim_config}
            )
            if not resp.ok:
                raise OptimizationError(
                    f"Error {resp.reason} ({resp.status_code}): {resp.json()['message']}"
                )

            self._id = resp.json()["id"]
            self._x = np.array([])
            self._y = np.array([])
            self._x_suggested = None
            self._status = self.PENDING
            self._x_best = None
        except RequestException as e:
            raise OptimizationError(f"Connection failed during initialization")

    def _init_config(self):
        return {
            "kind": self._kind,
            "n_obj": 1,
            "xlimits": self._xlimits,
            "cstr_specs": self._cstr_specs,
            "options": self._options,
        }

    def tell_doe(self, x, y):
        self._x_best = None
        self._status = self.PENDING
        self._x = np.atleast_2d(x)
        self._y = np.atleast_2d(y)

    def run(self, f_grouped, n_iter=1, with_best=False):
        """ Ask and tell the optimizer to get the optimum in n_iter iteration.
        When with_best is set optimum is computed at each iteration by the algorithm
        """
        self._x_best = None
        for i in range(n_iter):
            with_best = with_best or (i == n_iter-1)
            x_suggested, status, self._x_best = self.ask(with_best)
            print(f"{i} x suggested = {x_suggested} with status: {Optimization.STATUSES[status]}")

            if with_best:
                y_best = self._get_y(self._x_best)
                print(f"y_best={y_best} at x_best={self._x_best}")

            # compute objective function at the suggested point
            new_y = f_grouped(np.atleast_2d(x_suggested))
            print("new y = {}".format(new_y))

            self.tell(x_suggested, new_y)
            if self.is_solution_reached():
                print("Solution is reached")
                x_suggested, status, self._x_best = self.ask(with_best=True)
                break

        x_opt, y_opt = self.get_result()
        print(f"Found minimum y_opt = {y_opt} at x_opt = {x_opt}")
        return x_opt, y_opt

    def tell(self, x, y):
        """ Gives (x, y) values such that y = f(x) """
        # check if already told
        found = False
        for i, v in enumerate(self._x):
            if np.allclose(x, v):
                print(
                    "Value {} already told index {} with y = {}".format(
                        x, i, self._y[i]
                    )
                )
                found = True
                break
        if found:
            self._status = self.SOLUTION_REACHED
        else:
            self._x = np.vstack((self._x, np.atleast_2d(x)))
            self._y = np.vstack((self._y, np.atleast_2d(y)))

    def ask(self, with_best=False):
        """ Trigger optimizer iteration to get next location of the optimum """
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
                else:
                    self._x_best = None
            elif resp.status_code == 400:
                raise OptimizationError(
                    f"Error {resp.reason} ({resp.status_code}): {resp.json()['message']}"
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
            raise OptimizationError(
                "Time out: please check status and history and may be ask again."
            )

        self.status = self.PENDING

        return self._x_suggested, self._status, self._x_best

    def get_result(self, valid_constraints=True):
        """ Retrieve best point among the doe with valid constraints """
        if not self._x_best:
            _, _, self._xbest = self.ask(with_best=True)
        x_opt = np.array(self._x_best)
        y_opt = self._get_y(x_opt)

        return x_opt, y_opt

    def get_history(self):
        return self._x, self._y

    def is_solution_reached(self):
        return self._status == self.SOLUTION_REACHED

    def is_running(self):
        return self._status == self.RUNNING

    def _get_y(self, x):
        idx = np.argmin(np.apply_along_axis(lambda x: np.sum(np.abs(x)), 1, self._x - self._x_best))
        return np.atleast_2d(self._y[idx])

    def _optimizer_iteration(self, with_best):
        """ Run optimizer iteration """
        try:
            url = self._wop.endpoint("/api/v1/optimizations/{}".format(self._id))
            resp = self._wop.session.put(
                url,
                headers=self._wop.headers,
                json={"optimization": {"x": self._x.tolist(), "y": self._y.tolist(), "with_best": with_best}},
            )
            if not resp.ok:
                self._wop.err_msg(resp)
                self._status = self.RUNTIME_ERROR
                raise OptimizationError(
                    f"Error {resp.reason} ({resp.status_code}): {resp.json()['message']}"
                )
        except RequestException as e:
            raise OptimizationError(f"Connection failed: {e}")
