import sys
import time
import numpy as np
from requests.exceptions import RequestException
from .whatsopt_client import WhatsOpt
from .logging import error


class OptimizationError(Exception):
    pass


class ValidOptimumNotFoundError(Exception):
    pass


class Optimization(object):

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

    def __init__(self, xlimits, cstr_specs=None):
        try:
            self._wop = WhatsOpt()
            self._cstr_specs = cstr_specs or []

            for cstr in self._cstr_specs:
                for k in ["type", "bound", "tol"]:
                    cstr[k] = cstr.get(k, self.DEFAULT_CSTR[k])

            self._xlimits = np.array(xlimits)
            optim_config = {
                "kind": "SEGOMOE",
                "xlimits": self._xlimits.tolist(),
                "cstr_specs": self._cstr_specs,
            }

            url = self._wop.endpoint("/api/v1/optimizations")
            resp = self._wop.session.post(
                url, headers=self._wop.headers, json={"optimization": optim_config}
            )
            if not resp.ok:
                raise OptimizationError("{}: {}", resp.status_code, resp.reason)

            self._id = resp.json()["id"]
            self._x = np.array([])
            self._y = np.array([])
            self._x_suggested = None
            self._status = self.PENDING
        except RequestException as e:
            raise OptimizationError(
                "Connection failed during initialization: {}".format(e)
            )

    def tell_doe(self, x, y):
        self._status = self.PENDING
        self._x = np.atleast_2d(x)
        self._y = np.atleast_2d(y)

    def run(self, f_grouped, n_iter=1):
        for i in range(n_iter):
            x_suggested, status = self.ask()
            print(
                "{} x suggested = {} with status: {}".format(
                    i, x_suggested, Optimization.STATUSES[status]
                )
            )

            # compute objective function at the suggested point
            new_y = f_grouped(np.atleast_2d(x_suggested))
            print("new y = {}".format(new_y))

            self.tell(x_suggested, new_y)
            if self.is_solution_reached():
                print("Solution is reached")
                break

            try:
                _, y = self.get_result()
                print("y_opt_tmp = {}".format(y))
                print()
            except ValidOptimumNotFoundError:  # in case no point in doe respect constraints yet
                pass

        x_opt, y_opt = self.get_result()
        print("Found minimum y_opt = {} at x_opt = {}".format(y_opt, x_opt))
        return x_opt, y_opt

    def tell(self, x, y):
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

    def ask(self):
        if not self.is_solution_reached():
            self._status = self.RUNNING
            self._optimizer_iteration()
            retry = self.TIMEOUT
            url = self._wop.endpoint("/api/v1/optimizations/{}".format(self._id))
            resp = None
            while retry > 0 and self.is_running():
                resp = self._wop.session.get(url, headers=self._wop.headers)
                if resp.ok:
                    result = resp.json()["outputs"]
                    self._x_suggested = result["x_suggested"]
                    self._status = result["status"]
                if self.is_running():
                    if retry + 1 % 10 == 0:
                        print("Waiting for result...")
                    time.sleep(1)
                retry = retry - 1

            if retry <= 0:
                self._x_suggested = self.PENDING
                self._status = self.RUNTIME_ERROR
                raise OptimizationError(
                    "Time out: please check status and history and may be ask again."
                )

            self.status = self.PENDING

        return self._x_suggested, self._status

    def get_result(self, valid_constraints=True):
        y_opt = self._y[:, 0].min()
        x_opt = self._x[np.argmin(self._y[:, 0])]

        if valid_constraints and self._cstr_specs:
            y = np.copy(self._y)
            x = np.copy(self._x)
            valid = False

            while y.shape[0] > 0 and not valid:
                index = np.argmin(y[:, 0])
                valid = True
                cstrs = y[index, 1:]
                for i, c in enumerate(cstrs):
                    typ = self._cstr_specs[i]["type"]
                    bound = self._cstr_specs[i]["bound"]
                    tol = self._cstr_specs[i]["tol"]
                    if typ == "<":
                        valid = valid and ((c - bound) < tol)
                    elif typ == "=":
                        valid = valid and (abs(bound - c) < tol)
                    else:
                        valid = valid and ((bound - c) < tol)
                if valid:
                    y_opt = y[index]
                    x_opt = x[index]
                else:
                    y = np.delete(y, (index), axis=0)
                    x = np.delete(x, (index), axis=0)

            if not valid:
                raise ValidOptimumNotFoundError(
                    "No valid point found in optimization history."
                )

        return x_opt, y_opt

    def get_history(self):
        return self._x, self._y

    def is_solution_reached(self):
        return self._status == self.SOLUTION_REACHED

    def is_running(self):
        return self._status == self.RUNNING

    def _optimizer_iteration(self):
        try:
            url = self._wop.endpoint("/api/v1/optimizations/{}".format(self._id))
            resp = self._wop.session.put(
                url,
                headers=self._wop.headers,
                json={"optimization": {"x": self._x.tolist(), "y": self._y.tolist()}},
            )
            if not resp.ok:
                self._wop.err_msg(resp)
                self._status = self.RUNTIME_ERROR
                error("Optimizer runtime error")
                sys.exit(-1)
        except RequestException as e:
            raise OptimizationError("Connection failed during tell: {}".format(e))
