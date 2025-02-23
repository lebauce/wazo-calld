#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup
from setuptools import find_packages


setup(
    name='wazo-calld',
    version='2.0',
    description='Wazo CTI Server Daemon',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    url='http://wazo.community',
    packages=find_packages(),
    package_data={
        'wazo_calld.plugins': ['*/api.yml'],
    },
    entry_points={
        'console_scripts': [
            'wazo-calld=wazo_calld.main:main',
        ],
        'wazo_calld.plugins': [
            'api = wazo_calld.plugins.api.plugin:Plugin',
            'applications = wazo_calld.plugins.applications.plugin:Plugin',
            'calls = wazo_calld.plugins.calls.plugin:Plugin',
            'conferences = wazo_calld.plugins.conferences.plugin:Plugin',
            'dial_mobile = wazo_calld.plugins.dial_mobile.plugin:Plugin',
            'faxes = wazo_calld.plugins.faxes.plugin:Plugin',
            'relocates = wazo_calld.plugins.relocates.plugin:Plugin',
            'status = wazo_calld.plugins.status.plugin:Plugin',
            'switchboards = wazo_calld.plugins.switchboards.plugin:Plugin',
            'transfers = wazo_calld.plugins.transfers.plugin:Plugin',
            'voicemails = wazo_calld.plugins.voicemails.plugin:Plugin',
            'mobile = wazo_calld.plugins.mobile.plugin:Plugin',
        ]
    }
)
