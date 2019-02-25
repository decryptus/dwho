#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
from setuptools import find_packages, setup

requirements = [line.strip() for line in open('requirements.txt', 'r').readlines()]
version      = '0.2.91'

if os.path.isfile('VERSION'):
    version = open('VERSION', 'r').readline().strip() or version

setup(
    name                = 'dwho',
    version             = version,
    description         = 'dwho',
    author              = 'Adrien Delle Cave',
    author_email        = 'pypi@doowan.net',
    license             = 'License GPL-2',
    packages		= find_packages(),
    install_requires    = requirements,
    url                 = 'https://github.com/decryptus/dwho',
    python_requires     = '<3',
)
