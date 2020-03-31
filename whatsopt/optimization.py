import sys
import numpy as np
from .whatsopt_client import WhatsOpt


class Optimization(object):
    def __init__(self, xlimits, cstr_specs=None):
        self._wop = WhatsOpt()

        url = self._wop.endpoint("/api/v1/optimizations")
        optim_config = {
            "kind": "SEGOMOE",
            "xlimits": xlimits,
            "cstr_specs": cstr_specs or [],
        }
        resp = self._wop.session.post(
            url, headers=self._wop.headers, json={"optimization": optim_config}
        )
        resp.raise_for_status()
        self._id = resp.json()["id"]
        self._x = np.array([])
        self._y = np.array([])
        self._x_suggested = None
        self._status = None

    def tell_doe(self, x, y):
        self._x = np.atleast_2d(x)
        self._y = np.atleast_2d(y)
        self._tell()

    def tell(self, x, y):
        # check if already told
        found = False
        for i, v in enumerate(self._x):
            if np.allclose(x, v):
                print(self._x)
                print(
                    "Value {} already told index {} with y = {}".format(
                        x, i, self._y[i]
                    )
                )
                found = True
                break
        if not found:
            self._x = np.vstack((self._x, np.atleast_2d(x)))
            self._y = np.vstack((self._y, np.atleast_2d(y)))
        self._tell()

    def ask(self):
        ret1, ret2 = self._x_suggested, self._status
        self._x_suggested, self._status = None, -1  # reset suggestion
        return ret1, ret2

    def get_result(self):
        y_opt = self._y[:, 0].min()
        x_opt = self._x[np.argmin(self._y[:, 0])]
        return x_opt, y_opt

    def _tell(self):
        url = self._wop.endpoint("/api/v1/optimizations/{}".format(self._id))
        resp = self._wop.session.put(
            url,
            headers=self._wop.headers,
            json={"optimization": {"x": self._x.tolist(), "y": self._y.tolist()}},
        )
        if resp.ok:
            res = resp.json()
            self._x_suggested = res["x_suggested"]
            self._status = res["status"]
        else:
            self._wop.err_msg(resp)
            sys.exit(-1)
