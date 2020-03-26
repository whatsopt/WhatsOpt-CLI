import numpy as np
from .whatsopt_client import WhatsOpt


class Optimization(object):
    def __init__(self, xlimits):
        self._wop = WhatsOpt()

        url = self._wop.endpoint("/api/v1/optimizations")
        optim_config = {"kind": "SEGOMOE", "xlimits": xlimits}
        resp = self._wop.session.post(
            url, headers=self._wop.headers, json={"optimization": optim_config}
        )
        resp.raise_for_status()
        self._id = resp.json()["id"]
        self._x = np.array([])
        self._y = np.array([])
        self._x_suggested = None

    def tell_doe(self, x, y):
        self._x = np.atleast_2d(x)
        self._y = np.atleast_2d(y)
        self._tell()

    def tell(self, x, y):
        if x in self._x:
            print(
                "Value {} already told with y = {}",
                self._x,
                self._y[np.argmax(self._x)],
            )
        else:
            self._x = np.vstack((self._x, np.atleast_2d(x)))
            self._y = np.vstack((self._y, np.atleast_2d(y)))
            self._tell()

    def ask(self):
        ret = self._x_suggested
        self._x_suggested = None  # reset suggestion
        return ret

    def get_result(self):
        y_opt = self._y.min()
        x_opt = self._x[np.argmin(self._y)]
        return x_opt, y_opt

    def _tell(self):
        url = self._wop.endpoint("/api/v1/optimizations/{}".format(self._id))
        resp = self._wop.session.put(
            url,
            headers=self._wop.headers,
            json={"optimization": {"x": self._x.tolist(), "y": self._y.tolist()}},
        )
        resp.raise_for_status()  # raise when not ok
        res = resp.json()
        self._x_suggested = res["x_suggested"]
