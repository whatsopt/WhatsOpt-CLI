# -*- coding: utf-8 -*-
"""
  fonctions_base.py generated by WhatsOpt 1.4.0
"""
# DO NOT EDIT unless you know what you are doing
# whatsopt_url: https://selene.onecert.fr/whatsopt
# analysis_id: 213

from openmdao.api import ExplicitComponent


class FonctionsBase(ExplicitComponent):
    """An OpenMDAO base component to encapsulate Fonctions discipline"""

    def setup(self):
        self.add_input("x", val=2, desc="")
        self.add_input("y1", val=1.0, desc="")
        self.add_input("y2", val=1.0, desc="")
        self.add_input("z", val=[5, 2], desc="")

        self.add_output("f", val=1.0, desc="")

        self.add_output("g1", val=1.0, desc="")

        self.add_output("g2", val=1.0, desc="")
