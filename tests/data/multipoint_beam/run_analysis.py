# -*- coding: utf-8 -*-
"""
  run_analysis.py generated by WhatsOpt 1.8.2
"""
# DO NOT EDIT unless you know what you are doing
# analysis_id: 4

from openmdao.api import Problem
from mda_init import initialize
from multipoint_beam_group import MultipointBeamGroup

pb = Problem(MultipointBeamGroup())
pb.setup()

initialize(pb)

pb.run_model()
pb.model.list_inputs(print_arrays=False)
pb.model.list_outputs(print_arrays=False)
