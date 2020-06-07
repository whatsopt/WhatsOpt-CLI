# -*- coding: utf-8 -*-
"""
  volume_comp.py generated by WhatsOpt 1.8.2
"""
import numpy as np
from volume_comp_base import VolumeCompBase

class VolumeComp(VolumeCompBase):
    """ An OpenMDAO component to encapsulate VolumeComp discipline """
		
    def compute(self, inputs, outputs):
        """ VolumeComp computation """
        if self._impl:
            # Docking mechanism: use implementation if referenced in .whatsopt_dock.yml file
            self._impl.compute(inputs, outputs)
        else:
                    
            outputs['volume'] = np.ones((1,))   

# Reminder: inputs of compute()
#   
#       inputs['h'] -> shape: (50,), type: Float      
	
# To declare partial derivatives computation ...
# 
#    def setup(self):
#        super(VolumeComp, self).setup()
#        self.declare_partials('*', '*')  
#			
#    def compute_partials(self, inputs, partials):
#        """ Jacobian for VolumeComp """
#   
#       	partials['volume', 'h'] = np.zeros((1, 50))        
