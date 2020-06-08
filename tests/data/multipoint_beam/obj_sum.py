# -*- coding: utf-8 -*-
"""
  obj_sum.py generated by WhatsOpt 1.8.2
"""
import numpy as np
from obj_sum_base import ObjSumBase

class ObjSum(ObjSumBase):
    """ An OpenMDAO component to encapsulate ObjSum discipline """
		
    def compute(self, inputs, outputs):
        """ ObjSum computation """
        if self._impl:
            # Docking mechanism: use implementation if referenced in .whatsopt_dock.yml file
            self._impl.compute(inputs, outputs)
        else:
                    
            outputs['obj'] = np.ones((1,))   

# Reminder: inputs of compute()
#   
#       inputs['compliance_0'] -> shape: (1,), type: Float    
#       inputs['compliance_1'] -> shape: (1,), type: Float      
	
# To declare partial derivatives computation ...
# 
#    def setup(self):
#        super(ObjSum, self).setup()
#        self.declare_partials('*', '*')  
#			
#    def compute_partials(self, inputs, partials):
#        """ Jacobian for ObjSum """
#   
#       	partials['obj', 'compliance_0'] = np.zeros((1, 1))
#       	partials['obj', 'compliance_1'] = np.zeros((1, 1))        
