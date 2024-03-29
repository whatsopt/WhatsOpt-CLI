# -*- coding: utf-8 -*-
"""
  disc1.py generated by WhatsOpt 1.5.1
"""
# import numpy as np
from disc1_base import Disc1Base


class Disc1(Disc1Base):
    """An OpenMDAO component to encapsulate Disc1 discipline"""

    def compute(self, inputs, outputs):
        """Disc1 computation"""
        if self._impl:
            self._impl.compute(inputs, outputs)
        else:
            outputs["y1"] = 1.0


# Reminder: inputs of compute()
#
#       inputs['x'] -> shape: 1, type: Float
#       inputs['y2'] -> shape: 1, type: Float
#       inputs['z'] -> shape: (2,), type: Float

# To declare partial derivatives computation ...
#
#    def setup(self):
#        super(Disc1, self).setup()
#        self.declare_partials('*', '*')
#
#    def compute_partials(self, inputs, partials):
#        """ Jacobian for Disc1 """
#
#       	partials['y1', 'x'] = np.zeros((1, 1))
#       	partials['y1', 'y2'] = np.zeros((1, 1))
#       	partials['y1', 'z'] = np.zeros((1, 2))
