# -*- coding: utf-8 -*-
"""
  interp.py generated by WhatsOpt 1.8.2
"""
import numpy as np
from interp_base import InterpBase


class Interp(InterpBase):
    """An OpenMDAO component to encapsulate Interp discipline"""

    def compute(self, inputs, outputs):
        """Interp computation"""
        if self._impl:
            # Docking mechanism: use implementation if referenced in .whatsopt_dock.yml file
            self._impl.compute(inputs, outputs)
        else:
            outputs["h"] = np.ones((1, 50))


# Reminder: inputs of compute()
#
#       inputs['h_cp'] -> shape: (1, 5), type: Float

# To declare partial derivatives computation ...
#
#    def setup(self):
#        super(Interp, self).setup()
#        self.declare_partials('*', '*')
#
#    def compute_partials(self, inputs, partials):
#        """ Jacobian for Interp """
#
#       	partials['h', 'h_cp'] = np.zeros((50, 5))
