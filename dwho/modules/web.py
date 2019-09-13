# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.modules.web"""

import logging

from dwho.classes.modules import DWhoModuleWebBase, MODULES

LOG = logging.getLogger('dwho.modules.web')


class DWhoModuleWeb(DWhoModuleWebBase):
    MODULE_NAME = 'web'

    def index(self, request): # pylint: disable=unused-argument
        return self.render('index.html',
                           CONFIG = self.config)


if __name__ != "__main__":
    def _start():
        MODULES.register(DWhoModuleWeb())
    _start()
