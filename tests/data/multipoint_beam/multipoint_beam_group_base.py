# -*- coding: utf-8 -*-
"""
  multipoint_beam_group_base.py generated by WhatsOpt 1.8.2
"""
# DO NOT EDIT unless you know what you are doing
# whatsopt_url: https://ether.onera.fr/whatsopt
# analysis_id: 4


import numpy as np
from numpy import nan
from packaging import version

from openmdao.api import Problem, Group, ParallelGroup, IndepVarComp
from openmdao.api import NonlinearBlockGS
from openmdao.api import ScipyKrylov
from openmdao import __version__ as OPENMDAO_VERSION

from parallel.parallel import Parallel
from interp import Interp
from i_comp import IComp
from local_stiffness_matrix_comp import LocalStiffnessMatrixComp
from volume_comp import VolumeComp
from obj_sum import ObjSum
from parallel.sub0.states_comp import StatesComp
from parallel.sub0.displacements_comp import DisplacementsComp
from parallel.sub0.compliance_comp import ComplianceComp







class MultipointBeamGroupBase(Group):
    """ An OpenMDAO base component to encapsulate MultipointBeamGroup MDA """
    def __init__(self, thrift_client=None, **kwargs):
        super(MultipointBeamGroupBase, self). __init__(**kwargs)

        self.nonlinear_solver = NonlinearBlockGS()       
        self.nonlinear_solver.options['atol'] = 1.0e-10
        self.nonlinear_solver.options['rtol'] = 1.0e-10
        if version.parse(OPENMDAO_VERSION) > version.parse("2.8.0"):
            self.nonlinear_solver.options['err_on_non_converge'] = True
            if version.parse(OPENMDAO_VERSION) > version.parse("2.9.1"):
                self.nonlinear_solver.options['reraise_child_analysiserror'] = False 
        else:
            self.nonlinear_solver.options['err_on_maxiter'] = True
        self.nonlinear_solver.options['iprint'] = 1

        self.linear_solver = ScipyKrylov()       
        self.linear_solver.options['atol'] = 1.0e-10
        self.linear_solver.options['rtol'] = 1.0e-10
        if version.parse(OPENMDAO_VERSION) > version.parse("2.8.0"):
            self.linear_solver.options['err_on_non_converge'] = True
        else:
            self.linear_solver.options['err_on_maxiter'] = True        
        self.linear_solver.options['iprint'] = 1

    def setup(self): 
        indeps = self.add_subsystem('indeps', IndepVarComp(), promotes=['*'])

        indeps.add_output('h_cp', [1.0, 1.0, 1.0, 1.0, 1.0])
        self.add_subsystem('Interp', self.create_interp(), promotes=['h', 'h_cp'])
        self.add_subsystem('IComp', self.create_i_comp(), promotes=['h', 'I'])
        self.add_subsystem('LocalStiffnessMatrixComp', self.create_local_stiffness_matrix_comp(), promotes=['I', 'K_local'])
        self.add_subsystem('Parallel', self.create_parallel(), promotes=['compliance_0', 'compliance_1', 'displacements_0', 'displacements_1', 'd_0', 'd_1', 'K_local'])
        self.add_subsystem('VolumeComp', self.create_volume_comp(), promotes=['h', 'volume'])
        self.add_subsystem('ObjSum', self.create_obj_sum(), promotes=['compliance_0', 'compliance_1', 'obj'])

    def create_parallel(self):
    	return Parallel()


    def create_interp(self):
    	return Interp()
    def create_i_comp(self):
    	return IComp()
    def create_local_stiffness_matrix_comp(self):
    	return LocalStiffnessMatrixComp()
    def create_volume_comp(self):
    	return VolumeComp()
    def create_obj_sum(self):
    	return ObjSum()


# Used by Thrift server to serve disciplines
class MultipointBeamGroupFactoryBase(object):
    @staticmethod
    def create_interp():
    	return Interp()
    @staticmethod
    def create_i_comp():
    	return IComp()
    @staticmethod
    def create_local_stiffness_matrix_comp():
    	return LocalStiffnessMatrixComp()
    @staticmethod
    def create_volume_comp():
    	return VolumeComp()
    @staticmethod
    def create_obj_sum():
    	return ObjSum()
    @staticmethod
    def create_parallel_sub0_states_comp():
    	return StatesComp()
    @staticmethod
    def create_parallel_sub0_displacements_comp():
    	return DisplacementsComp()
    @staticmethod
    def create_parallel_sub0_compliance_comp():
    	return ComplianceComp()
